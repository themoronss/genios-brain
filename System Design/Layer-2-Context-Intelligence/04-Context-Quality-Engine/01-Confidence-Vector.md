# The Confidence Vector

*Layer 2 · [context/situations.py:100–225](../../../genios_engine/context/situations.py) · four pure functions, one dataclass, one combiner*

> **How sure are we that this situation is true — and which of the four ways it could be
> wrong is the one that is actually wrong right now?**

| | |
|---|---|
| **File** | [context/situations.py](../../../genios_engine/context/situations.py) |
| **Owns** | `evidence_score` · `freshness_score` · `consistency_score` · `identity_score` · `Confidence` · `score_situation` |
| **Purity** | All five are pure. Every input is an explicit keyword argument, including `now`. No clock, no I/O, no LLM |
| **Persisted to** | `context_situations.confidence_overall / _evidence / _freshness / _consistency / _identity` + `inputs` jsonb |
| **Migration** | [`0038_l2_situations.sql`](../../../migrations/0038_l2_situations.sql) |
| **Tests** | [tests/test_situations.py](../../../tests/test_situations.py) — 12 of its 46 tests are about this vector alone |

---

## 1 · Why a vector and not a number

A situation is assembled from evidence that arrived through four independent systems. It can
fail in four independent ways, and they are not interchangeable:

| Dimension | The failure it detects | Fix, if it is low |
|---|---|---|
| `evidence` | We are looking at one email and calling it a situation | Connect another source; wait for more traffic |
| `freshness` | Everything we know is six months old | Nothing — the world went quiet, and that is the news |
| `consistency` | The CRM says closed-won and the inbox says the customer is unhappy | Open the discrepancy queue and decide which is true |
| `identity` | There are two "Acme"s and we do not know which one this is about | Resolve the merge proposal |

Collapsing those into one percentage destroys the only actionable part. From
[api/situation_routes.py](../../../genios_engine/api/situation_routes.py):

> "82% overall, 12% identity" tells you to go resolve a duplicate. "82%" tells you nothing
> you can act on.

The module docstring states the two rules that govern everything below:

> `overall` is the minimum of those, never the average. They are failure modes, not
> features, and averaging lets one strong dimension hide a fatal one: perfect evidence
> about an entity we cannot identify is not 60% confidence, it is unusable. **You are only
> as sure as your weakest link.**

> A dimension with no basis is left out of the minimum and marked, so the score says
> "we cannot tell" rather than "it is old".

---

## 2 · `evidence_score` — corroboration beats volume

```python
# situations.py:102
def evidence_score(*, event_count: int, source_count: int) -> int:
    volume        = min(40, max(0, int(event_count))  * 8)
    corroboration = min(60, max(0, int(source_count)) * 25)
    return max(0, min(100, volume + corroboration))
```

### The arithmetic

| Term | Formula | Cap | Saturates at |
|---|---|---|---|
| `volume` | `event_count × 8` | **40** | 5 events |
| `corroboration` | `source_count × 25` | **60** | 3 sources (`3 × 25 = 75 → 60`) |
| total | `volume + corroboration` | 100 | 5 events across 3 sources |

`max(0, …)` on each input means a negative count is treated as zero, not as a subtraction —
`test_evidence_is_bounded` pins `evidence_score(event_count=-5, source_count=-2) == 0`.

### Why 60/40 and not 40/60

Twenty emails in one thread are **one person's account of events**. An email plus a CRM
record plus a calendar invite are **three systems independently agreeing**. The caps encode
that: corroboration alone can reach 60, volume alone can only reach 40, so *no amount of
single-source noise can outscore genuine cross-tool agreement*.

The docstring records that this was once backwards:

> An earlier split (60 volume / 40 sources) inverted it and made this docstring a lie;
> tests/test_situations.py now pins the ordering.

With the inverted split, a 20-email single-source thread scored `min(60, 160) + min(40, 25)`
= **85**, while three quiet sources scored `min(60, 24) + min(40, 75)` = **64**. The comment
claimed corroboration mattered and the arithmetic said the opposite. The test that now
prevents it:

```python
# tests/test_situations.py:58
def test_corroboration_across_tools_beats_volume_in_one() -> None:
    one_noisy_source   = evidence_score(event_count=20, source_count=1)
    three_quiet_sources = evidence_score(event_count=3,  source_count=3)
    assert three_quiet_sources > one_noisy_source
```

### The table it produces

| events | sources | volume | corroboration | **evidence** |
|---:|---:|---:|---:|---:|
| 1 | 1 | 8 | 25 | **33** |
| 3 | 1 | 24 | 25 | **49** |
| 20 | 1 | 40 | 25 | **65** |
| 3 | 3 | 24 | 60 | **84** |
| 5 | 2 | 40 | 50 | **90** |
| 5 | 3 | 40 | 60 | **100** |
| 10 000 | 50 | 40 | 60 | **100** |

`test_a_single_email_is_weak_evidence` asserts the first row is `< 50`. It is 33.

### Where `source_count` comes from

Not from the correlation row. `refresh_situations` runs a dedicated query for **distinct
sources**, because that is the thing that makes evidence strong:

```sql
-- situations.py:303
select m.correlation_id, count(distinct se.source) as n
from context_correlation_members m
join source_events se on se.org_id = m.org_id and se.event_id = m.event_id
where m.org_id = :o group by m.correlation_id
```

A correlation the query returns nothing for gets `sources.get(correlation_id, 0)` → `0`, so
corroboration contributes nothing and evidence is capped at 40. That is the correct answer
for a group whose member events have no matching `source_events` row.

---

## 3 · `freshness_score` — and the `known` flag that makes the whole design work

```python
# situations.py:120
def freshness_score(*, last_seen_at: datetime | None, now: datetime) -> tuple[int, bool]:
    if last_seen_at is None:
        return 0, False
    age_days = (now - last_seen_at).total_seconds() / 86400.0
    if age_days <= 3:   return 100, True
    if age_days <= 7:   return  85, True
    if age_days <= 14:  return  70, True
    if age_days <= 30:  return  50, True
    if age_days <= DORMANT_AFTER_DAYS: return 30, True    # 45
    return 10, True
```

### The ladder

| Age of the newest evidence | Score | The business reading |
|---|---:|---|
| ≤ 3 days | **100** | Live. Something happened this week |
| ≤ 7 days | **85** | Current |
| ≤ 14 days | **70** | Recent, one reply cycle behind |
| ≤ 30 days | **50** | Ageing — half of what we know may have moved |
| ≤ 45 days | **30** | About to go dormant |
| > 45 days | **10** | Historical. Never 0 — the evidence still exists |
| **no date at all** | **0**, `known=False` | **Not a score. An admission** |

The 45-day step is not a free parameter. `DORMANT_AFTER_DAYS = 45` is the same constant that
drives `decide_lifecycle`, and the comment ties it to the correlation engine:

```python
# situations.py:71
DORMANT_AFTER_DAYS = 45        # matches the correlation window: past it, a new
                               # generation opens and this one has genuinely ended
```

[correlation.py:59](../../../genios_engine/context/correlation.py) declares
`CORRELATION_WINDOW_DAYS = 45`. Past that, an arriving event does not join the existing
correlation — it opens generation *n+1*. So a 46-day-old situation is not "stale", it is
**over**, and 10 is the score for something that will never gain another event.

### The two-value return is the point

`(0, False)` and `(10, True)` are both low numbers and they mean opposite things:

* `(10, True)` — *we know when this last moved, and it was a long time ago.*
* `(0, False)` — *we have no dated evidence at all. We cannot tell you anything about time.*

The caller treats them completely differently — §5. The test that pins the distinction:

```python
# tests/test_situations.py:86
def test_undated_evidence_is_unknown_not_stale() -> None:
    score, known = freshness_score(last_seen_at=None, now=NOW)
    assert known is False
    assert score == 0
```

> **Edge case — the future.** A `last_seen_at` in the future gives a negative `age_days`,
> which passes `<= 3` and scores **100**. Nothing clamps it. In practice `last_event_at`
> comes from `context_correlations`, which is fed from `source_events.occurred_at`, so a
> provider clock skewed forward makes a situation maximally fresh. Not a defect that has
> bitten, but it is unguarded.

---

## 4 · `consistency_score` and `identity_score` — the two steep ones

### Consistency: three strikes and you are at zero

```python
# situations.py:143
def consistency_score(*, open_discrepancies: int) -> int:
    return max(0, 100 - min(100, max(0, int(open_discrepancies)) * 34))
```

| open discrepancies | arithmetic | score |
|---:|---|---:|
| 0 | `100 − 0` | **100** |
| 1 | `100 − 34` | **66** |
| 2 | `100 − 68` | **32** |
| 3 | `100 − min(100, 102)` | **0** |
| 5+ | `100 − 100` | **0** |

**Why 34 and not 33?** `ceil(100 / 3) = 34`. The constant is chosen so that *three* open
conflicts reach exactly zero — not 1, and not 4. The docstring states the intent:

> One is a real dent in trust; **three make the situation something a human must look at
> before anything acts on it.**

Because `overall` is a minimum, three open discrepancies on the anchor entity pin the whole
situation to `overall = 0` regardless of how good the evidence is. That is deliberate: a
situation whose sources contradict each other three ways is not a situation, it is a
question.

`test_contradicting_sources_cost_confidence` pins `d=0 → 100`, `d=1 < 70`, `d=5 == 0`.

> **The consequence nobody has closed.** Nothing in the repository ever moves a discrepancy
> out of `status='open'` — verified by `grep -rn "update discrepancies"` returning nothing.
> So this dimension is **monotonically non-increasing** for the lifetime of an entity. See
> [03 · Conflict Detection](03-Conflict-Detection.md).

### Identity: one open duplicate costs 60 points

```python
# situations.py:153
def identity_score(*, open_merge_proposals: int) -> int:
    if open_merge_proposals <= 0:
        return 100
    return 40 if open_merge_proposals == 1 else 20
```

| open proposals | score |
|---:|---:|
| 0 | **100** |
| 1 | **40** |
| ≥ 2 | **20** |

A step function, not a ladder, because the doubt is not proportional. The docstring:

> An unresolved duplicate means the evidence may be split across two nodes, so this
> situation is probably **missing half its material** — or is about the **wrong entity
> entirely**. Neither is a small doubt, which is why one open proposal costs so much.

**Why 40 rather than 0.** A situation about a possibly-duplicated entity is still worth
looking at; you just must not act on it as if the picture were complete. 40 leaves it
visible and below every threshold that matters. 20 for two-or-more says *we have lost track
of who this is*.

The counting is **per node, either side**:

```python
# situations.py:336
for row in _bulk(conn, "select left_node_id, right_node_id from merge_proposals "
                       "where org_id = :o and status = 'open'", {"o": org_id}):
    for node in (row.left_node_id, row.right_node_id):
        proposals[node] = proposals.get(node, 0) + 1
```

Both ends of a proposal are ambiguous, so both take the hit. A node in two separate open
proposals scores 20.

This is the connection [`Rohit_Updates/Layer 2.md`](../../../Rohit_Updates/Layer%202.md) calls
deliberate:

> Every unresolved duplicate lowers the confidence of every situation about that entity —
> that connection is deliberate. **Unreviewed proposals are a measurable defect, not a quiet
> queue.**

A proposal is only ever raised when two nodes claim the same alias key, and
[identity.py:147](../../../genios_engine/context/identity.py) refuses to re-ask a settled
question:

```python
settled = conn.execute(text(
    "select 1 from merge_proposals where org_id=:o and left_node_id=:l "
    "and right_node_id=:r and status in ('merged','rejected') limit 1"), …)
if settled is not None:
    return None          # a human already ruled on this pair; do not ask again
```

So a *rejected* proposal stops costing identity confidence. Only an **unanswered** one does.

---

## 5 · `score_situation` — the combiner

```python
# situations.py:190
def score_situation(*, event_count, source_count, last_seen_at, open_discrepancies,
                    open_merge_proposals, present_fields, expected_fields, now) -> Confidence:
    evidence               = evidence_score(event_count=event_count, source_count=source_count)
    freshness, known       = freshness_score(last_seen_at=last_seen_at, now=now)
    consistency            = consistency_score(open_discrepancies=open_discrepancies)
    identity               = identity_score(open_merge_proposals=open_merge_proposals)
    coverage, missing      = coverage_score(present_fields=present_fields,
                                            expected=expected_fields)

    trust = [evidence, consistency, identity]
    if known:
        trust.append(freshness)

    return Confidence(overall=min(trust), …)
```

Three lines carry the whole design:

1. **`trust` contains three dimensions, not four.** Coverage is never in it — [02 · Coverage
   and Missing](02-Coverage-and-Missing.md).
2. **`freshness` is appended conditionally.** An unmeasurable dimension is *excluded*, not
   zeroed.
3. **`min(trust)`**, never `sum(trust) / len(trust)`.

### Why exclusion and not zeroing — the arithmetic

Take a solid situation with no dated evidence: 5 events across 2 sources, no conflicts, no
duplicates.

| Approach | `trust` | `overall` | What it tells a reader |
|---|---|---:|---|
| **Zeroing** (rejected) | `[90, 0, 100, 100]` | **0** | "This situation is worthless" |
| **Averaging** (rejected) | `mean([90, 0, 100, 100])` | **72.5** | "Fine" — hides that we have no idea when this happened |
| **Excluding** (built) | `[90, 100, 100]` | **90** | "Strong, and we cannot tell you how current it is" |

The zeroing version turns a *missing timestamp on a connector* into *a claim that the
business relationship is dead*. That is absence read as negative evidence — the failure this
codebase refuses in Layer 1's coverage predicates, in `node_lifecycle`, in
`domain_spec.generic_spec`, and here.

```python
# tests/test_situations.py:122
def test_an_unknown_dimension_is_excluded_not_zeroed() -> None:
    c = _score(last_seen_at=None)
    assert c.freshness == 0
    assert c.overall > 0
    assert c.inputs["freshness_known"] is False
```

And the mirror-image test, so exclusion cannot be used to hide *real* staleness:

```python
# tests/test_situations.py:131
def test_a_stale_but_known_date_does_lower_confidence() -> None:
    c = _score(last_seen_at=_ago(300))
    assert c.inputs["freshness_known"] is True
    assert c.overall == c.freshness          # 10
```

> ### ⚠️ A trap in the persisted shape
> `confidence_freshness` is stored as the raw `0`. The `known` flag lives **only** inside
> the `inputs` jsonb, as `inputs["freshness_known"]`. There is no `measured` column on
> `context_situations` — unlike `graph_health`, which has a first-class `measured` jsonb.
>
> So a caller that reads the five confidence columns and renders them as bars will paint
> **freshness at 0%** for a situation whose `overall` is 90. `_shape` in
> [api/situation_routes.py:52](../../../genios_engine/api/situation_routes.py) returns exactly
> those five numbers for the list endpoint; only the *detail* endpoint attaches `inputs`.
> **The list view cannot distinguish "stale" from "undated".** The two engines diverge here
> and `health.py` has the better shape.

### `inputs` — the score explains itself

```python
inputs={"event_count": …, "source_count": …, "freshness_known": …,
        "open_discrepancies": …, "open_merge_proposals": …,
        "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
        "domain_spec_version": spec_version(),
        "weakest": …}
```

`test_the_score_explains_itself` pins it: *"A confidence number nobody can account for is a
number nobody should act on."* Every input that produced the score is stored with the score,
so any row can be re-derived by hand.

**`domain_spec_version`** is the subtle one. `situation_type`, `coverage` and `missing` are
all derived from the domain registry and then *persisted*. A registry change silently
rewrites stored values on the next refresh. Stamping the registry's content hash makes a
re-typing attributable — [domain_spec.py:102](../../../genios_engine/context/domain_spec.py)
explains it at length, and [02 · Coverage and Missing §6](02-Coverage-and-Missing.md) covers
the mechanism.

### `weakest` — and its tie-breaking order

```python
"weakest": "freshness" if freshness_known and freshness == min(trust)
           else ("evidence" if evidence == min(trust)
                 else "consistency" if consistency == min(trust)
                 else "identity")
```

When two dimensions tie at the minimum, the reported `weakest` follows a fixed precedence:
**freshness → evidence → consistency → identity**. It is a label for a human, not an input to
anything, so the ordering only matters for readability. When `freshness_known` is `False`,
`weakest` can never be `"freshness"` — which is correct, since an unmeasured dimension is not
a weakness.

---

## 6 · Worked example — an unidentified Acme

The exact inputs of `test_overall_is_the_minimum_not_the_average`, computed by hand.

**Situation:** a company-anchored sales opportunity. 50 correlated events across 5 sources,
newest yesterday, no open discrepancies, **one open merge proposal** on the anchor node
(there are two "Acme" entities and nobody has ruled on them).

| Step | Computation | Result |
|---|---|---:|
| `volume` | `min(40, 50 × 8) = min(40, 400)` | 40 |
| `corroboration` | `min(60, 5 × 25) = min(60, 125)` | 60 |
| **`evidence`** | `40 + 60` | **100** |
| `age_days` | 1 day | — |
| **`freshness`** | `age_days ≤ 3` | **100**, `known=True` |
| **`consistency`** | `100 − 0 × 34` | **100** |
| **`identity`** | `open_merge_proposals == 1` | **40** |
| `trust` | `[100, 100, 40]` + `[100]` (freshness known) | `[100, 100, 40, 100]` |
| **`overall`** | `min(trust)` | **40** |
| `weakest` | freshness ≠ 40 → evidence ≠ 40 → consistency ≠ 40 → | `"identity"` |

**What the API returns:**

```json
{
  "confidence": {
    "overall": 40, "evidence": 100, "freshness": 100,
    "consistency": 100, "identity": 40
  }
}
```

**What an average would have returned:** `(100 + 100 + 100 + 40) / 4 = 85`. A reader would
have seen "85% confident" on a situation that might be about the wrong company. The minimum
says 40 and names the reason, and the fix — resolve the merge proposal — is one click away
in `GET /api/org/{org}/identity/proposals`.

### The same situation, one week later, with the duplicate resolved

| Dimension | Before | After |
|---|---:|---:|
| evidence | 100 | 100 |
| freshness | 100 | 85 *(now 5 days old)* |
| consistency | 100 | 100 |
| identity | 40 | **100** |
| **overall** | **40** | **85** |
| `weakest` | identity | freshness |

One human decision moved `overall` from 40 to 85. Nothing else changed.

---

## 7 · Edge cases and invariants

| Case | Behaviour | Where |
|---|---|---|
| Correlation with `event_count = 0` | **No situation is written at all** — `if not corr.event_count: continue`. A group with no evidence describes nothing | situations.py:349; `test_a_correlation_with_no_evidence_produces_no_situation` |
| Negative counts | Clamped to 0 by `max(0, int(...))` in `evidence_score` and `consistency_score` | `test_evidence_is_bounded` |
| `event_count` huge | Capped at 40; no overflow path | `evidence_score(10_000, 50) == 100` |
| Scoring called twice with identical inputs | Byte-identical `Confidence` — `frozen=True, slots=True` dataclass, all-integer fields | `test_scoring_is_pure_and_repeatable` |
| A situation is rebuilt every drain | Everything except `situation_id`, `resolved_by='human'` and `resolved_at` is recomputed from scratch. *"A situation you cannot rebuild is a situation you cannot trust"* | `refresh_situations` docstring |
| `overall` for a brand-new correlation with 1 event, 1 source, dated today | `trust = [33, 100, 100, 100]` → **33** | — |

### The `Confidence` dataclass

```python
# situations.py:178
@dataclass(frozen=True, slots=True)
class Confidence:
    overall: int
    evidence: int
    freshness: int
    consistency: int
    identity: int
    coverage: int
    missing: tuple[str, ...] = ()
    inputs: dict = field(default_factory=dict)
```

`frozen` so a score cannot be edited after it is computed. `slots` because it is instantiated
once per correlation per drain. Every score field is `int` — there is no float anywhere in
the vector, so two workers computing the same situation produce identical rows.

---

## 8 · What this vector must never become

`test_situations_never_carry_priority_or_risk` greps the module source:

```python
for forbidden in ("def priority", "def risk_score", "def recommend", "def urgency"):
    assert forbidden not in source
```

Confidence says *how sure we are*. It never says *how much this matters*. Those are
different questions and the second one is a decision, which belongs to Layer 4. The read
endpoint carries the same discipline in its response body:

```python
# api/situation_routes.py:78
return {"situations": …, "ordering": "confidence_desc",
        "note": "ordered by confidence, not priority — ranking is a decision made downstream"}
```

Sorting by confidence is honest — a situation we are sure about is worth more thought than
one assembled from a single unverified email. Calling that ordering a *priority* would be
this layer making a decision it is not allowed to make.

---

## 9 · See also

* [02 · Coverage and Missing](02-Coverage-and-Missing.md) — the fifth number, and why it is not in `trust`
* [03 · Conflict Detection](03-Conflict-Detection.md) — where `open_discrepancies` comes from
* [04 · Graph Health Metrics](04-Graph-Health-Metrics.md) — the same minimum-not-average rule, one level up
