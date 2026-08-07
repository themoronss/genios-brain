# 03a · Plugin `coverage_completeness`

**Class:** `genios_engine/reason/reasoners/confidence.py:188` — `CoverageCompletenessPlugin`
**`plugin_id`:** `coverage_completeness` · runs **first** (alphabetical)
**`Observation.kind`:** `confidence.coverage_completeness`
**Emits:** `completeness_bp`, `evidence_coverage_bp`, `independent_evidence_groups`,
`declared_field_count`, `present_field_count` · **Reason codes:** none · **Evidence ids:** none

---

## 1 · The claims it makes

Two, and they are about different things:

> *Of the fields this capability said it needs, this fraction actually arrived.*

> *The picture as a whole is backed by this many genuinely independent sources.*

The class docstring separates them precisely:

> *Completeness is a structural claim about the **request**: of the fields this capability declared
> it needs, what fraction is in the snapshot. It is measured even when no fact carries metadata,
> which is why it is the axis that keeps a thin snapshot from scoring as a confident one.*
>
> *Coverage is a claim about the **evidence**: how many independent source groups stand behind the
> snapshot as a whole.*

Neither needs a single byte of fact metadata. That is what makes this plugin the one that cannot be
silenced by a producer that writes bare scalars — and why it carries the 30-point weight, the second
largest in the blend.

---

## 2 · The code

```python
# confidence.py:203
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    if _bridged_confidence_bp(view) is not None:
        return ()
    declared = _declared_fields(view)
    present = _present_fields(view)
    # A capability that declared no required fields asked for nothing and got all of it.
    completeness_bp = divide_half_up(len(present) * 10_000, len(declared)) if declared \
        else 10_000
    groups = {item.independence_group or _UNATTRIBUTED_GROUP
              for item in view.request.context.evidence}
    return (Observation(
        plugin_id=self.plugin_id,
        kind="confidence.coverage_completeness",
        metrics={
            "completeness_bp": completeness_bp,
            "evidence_coverage_bp": min(10_000, len(groups) * _GROUP_COVERAGE_BP),
            "independent_evidence_groups": len(groups),
            "declared_field_count": len(declared),
            "present_field_count": len(present),
        },
    ),)
```

### Dependencies

| Symbol | Defined at | What it does |
|---|---|---|
| `_bridged_confidence_bp(view)` | `confidence.py:82` | `None` unless a `source_reasoner` is named, present in `prior`, and published `confidence_bp` |
| `_declared_fields(view)` | `confidence.py:102` | `spec.required_fields` if non-empty, else `capability.required_fields`; both pre-sorted and de-duplicated |
| `_present_fields(view)` | `confidence.py:111` | the declared fields found in `request.context.facts`, in declared order |
| `divide_half_up(n, d)` | `common.py:79` | integer division rounding half away from zero; raises if `d <= 0` |
| `_GROUP_COVERAGE_BP` | `confidence.py:67` | `2_500` |
| `_UNATTRIBUTED_GROUP` | `confidence.py:71` | `"unattributed"` |

---

## 3 · Config

**None.** This plugin reads no config key. `_GROUP_COVERAGE_BP`, the saturation ceiling and the
completeness formula are all module constants. There is no per-capability tuning of either axis —
the only per-capability lever is `required_fields`, which is a declaration of need, not a knob.

The one config key the unit reads, `source_reasoner`, reaches this plugin only as an on/off switch
through `_bridged_confidence_bp`.

---

## 4 · When it stays silent

**Exactly one condition:** `_bridged_confidence_bp(view) is not None` — the capability declared that
confidence belongs to another reasoner, so neither of this plugin's claims is wanted.

It never stays silent because it found nothing. Every degenerate input produces a number:

| Input | `completeness_bp` | `evidence_coverage_bp` | Silent? |
|---|---|---|---|
| No declared fields at all | `10,000` | per evidence | no |
| Declared fields, none present | `0` | per evidence | no |
| No evidence at all | per declaration | `0` | no |
| Neither declaration nor evidence | `10,000` | `0` | no |
| A bridge applies | — | — | **yes** |

Note the asymmetry between the two axes on empty input, and that it is deliberate. *Nothing
declared* is `10,000` — "asked for nothing, got all of it". *No evidence* is `0` — a snapshot with no
citations behind it genuinely has zero independent backing. The neutral midpoint `_NEUTRAL_BP` is
**not** used by this plugin at all, because for both of its axes zero is a real measurement rather
than an absence of one.

---

## 5 · The arithmetic — completeness

```
declared        = spec.required_fields or capability.required_fields
present         = [f for f in declared if f in context.facts]
completeness_bp = half_up(len(present) × 10,000, len(declared))    if declared
                = 10,000                                            if not declared
```

`divide_half_up` rounds half away from zero, so the value is reproducible on every machine:

```python
# common.py:79
if numerator >= 0:
    return (numerator + denominator // 2) // denominator
```

The full table for small denominators, computed from the code:

| present ⁄ declared | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|
| **0** | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **1** | 10,000 | 5,000 | 3,333 | 2,500 | 2,000 | 1,667 | 1,429 |
| **2** | — | 10,000 | 6,667 | 5,000 | 4,000 | 3,333 | 2,857 |
| **3** | — | — | 10,000 | 7,500 | 6,000 | 5,000 | 4,286 |
| **4** | — | — | — | 10,000 | 8,000 | 6,667 | 5,714 |
| **5** | — | — | — | — | 10,000 | 8,333 | 7,143 |
| **6** | — | — | — | — | — | 10,000 | 8,571 |
| **7** | — | — | — | — | — | — | 10,000 |

Note `2/3 = 6,667` rather than `6,666`: `half_up(20,000, 3) = (20,000 + 1) // 3 = 6,667`. Truncating
division would give `6,666` and every legacy decision hash would move.

**Presence, not truthiness.** `_present_fields` tests `field in facts`. A field whose value is
`None`, `0`, `""` or `{}` counts as arrived — because it did. Layer 2's job is to omit a fact it
does not have, and this unit trusts that boundary rather than second-guessing it.

## 5.1 · The arithmetic — coverage

```
groups               = { item.independence_group or "unattributed"
                         for item in context.evidence }          ← a set, over ALL evidence
evidence_coverage_bp = min(10,000, len(groups) × 2,500)
```

| Distinct groups | `evidence_coverage_bp` | Reading |
|---|---|---|
| 0 | 0 | nothing cites anything |
| 1 | 2,500 | one source told us the whole story |
| 2 | 5,000 | two |
| 3 | 7,500 | three |
| 4 | 10,000 | saturated |
| 6 | 10,000 | saturated — but `independent_evidence_groups` still reports **6** |

`test_each_independent_source_group_buys_coverage_up_to_a_ceiling` parametrises 0, 1, 3, 4 and 6 and
asserts both metrics. The uncapped count is published alongside the capped score precisely so the
saturation is visible: a snapshot with six independent groups and one with four are indistinguishable
by `evidence_coverage_bp` and distinguishable by `independent_evidence_groups`.

**`None` collapses to one group, not to none.**

```python
groups = {item.independence_group or _UNATTRIBUTED_GROUP for item in ...}
```

Twenty evidence items with no independence metadata form the single set `{"unattributed"}` →
`2,500bp`. The constant's comment states the reasoning: *"Missing independence metadata is one
unknown group, not proof that every field came from an independent source."* Pinned by
`test_evidence_without_independence_metadata_collapses_into_one_unknown_group`.

The falsy-`or` also catches the **empty string**, which `EvidenceRef` permits (`independence_group`
is typed `str | None` and is not run through `_identifier`). `""` and `None` are therefore the same
group. That is almost certainly what was intended and it is not stated anywhere in the code.

**The scan is unfiltered.** No `context_scope` filter, no field filter, no deduplication by fact.
Neighbour-scoped evidence counts. Evidence for root fields this unit never declared counts. That is
the docstring's explicit intent — *"independence is a property of where the picture came from, not
of which field is being read right now"* — and it means this unit's confidence rises when a
*different* unit's data source is added to the capability.

---

## 6 · What it ignores, and what that costs

`EvidenceRef` carries nine fields (`contracts/reasoning.py:136`). This plugin reads **one**.

| `EvidenceRef` field | Read? | Consequence of ignoring it |
|---|---|---|
| `independence_group` | **yes** | — |
| `confidence_bp` | no | Layer 2 populates it on every item via `adapters/native.py:101`. The evidence's own reliability claim plays no part in confidence. |
| `authority_rank` | no | 1–4, where 4 is a system of record. A CRM-of-record citation and a guessed one count identically toward coverage. |
| `context_scope` | no | neighbour evidence inflates the group count for a unit that reads no neighbour facts |
| `occurred_at` | no | a five-year-old citation is as good as today's — freshness is `core.context`'s axis, not this one |
| `source_ref_id`, `fact_version_id`, `field`, `value` | no | — |

The `authority_rank` omission is the one worth arguing about. The unit's stated purpose is *"a
measurement of the inputs"*, and `authority_rank` is the single most direct statement Layer 2 makes
about an input's standing. Four independent low-rank guesses saturate coverage at `10,000bp` exactly
as four systems of record do. Nothing in the code acknowledges this; it is a design gap, not a
recorded compromise.

Compare `core.context`'s `SourceCorroborationPlugin` (`context_unit.py:180`, group key at `:100`), which builds its group
key from `independence_group` *or* `source_ref_id` with namespace prefixes — a strictly richer read
of the same structure, in a unit that publishes no confidence.

---

## 7 · Worked examples

### 7.1 · `sales.deal_cooling`, three of four fields

**Setup.** The shipped spec declares four required fields (`deal_cooling.py:216`). The snapshot
carries three of them plus two evidence items from different systems.

```
declared = ("deal.status", "deal.value", "derived.engagement", "thread.last_inbound")
facts    = {"deal.status": {...}, "deal.value": {...}, "derived.engagement": 42}
evidence = (EvidenceRef("ev_crm",  field="deal.status",        independence_group="crm"),
            EvidenceRef("ev_mail", field="derived.engagement", independence_group="mailbox"))
```

```
present              = ("deal.status", "deal.value", "derived.engagement")     → 3
completeness_bp      = half_up(3 × 10,000, 4) = (30,000 + 2) // 4 = 7,500
groups               = {"crm", "mailbox"}                                      → 2
evidence_coverage_bp = min(10,000, 2 × 2,500)                                  = 5,000
```

```
Observation(plugin_id="coverage_completeness",
            kind="confidence.coverage_completeness",
            metrics={"completeness_bp": 7500,
                     "evidence_coverage_bp": 5000,
                     "independent_evidence_groups": 2,
                     "declared_field_count": 4,
                     "present_field_count": 3},
            evidence_ids=(), reason_codes=())
```

Verified end to end: the full unit on this input publishes
`{confidence_bp: 8000, source_quality_bp: 8500, completeness_bp: 7500, corroboration_bp: 9250,
evidence_coverage_bp: 5000, independent_evidence_groups: 2}`.

**Note the production caveat.** This example cannot occur in the deployed `sales.deal_cooling`,
because `orchestrator.py:178` refuses the step when a declared field is absent — see §7.5.

### 7.2 · The capability-level fallback

**Setup.** The spec declares nothing; the capability declares three fields; one arrived; no evidence.

```
spec.required_fields       = ()
capability.required_fields = ("a.one", "a.two", "a.three")
facts                      = {"a.one": 1}
evidence                   = ()
```

```
declared             = ("a.one", "a.two", "a.three")     ← the fallback engaged
present              = ("a.one",)                        → 1
completeness_bp      = half_up(10,000, 3) = (10,000 + 1) // 3 = 3,333
groups               = set()                             → 0
evidence_coverage_bp = min(10,000, 0)                    = 0
```

Full-unit result, verified: `confidence_bp = 4,000`.

```
half_up(5,000×40 + 3,333×30 + 5,000×20 + 0×10, 100)
= half_up(200,000 + 99,990 + 100,000 + 0, 100)
= half_up(399,990, 100) = (399,990 + 50) // 100 = 4,000
```

Note that `view.facts` is `{}` on this run — the base retriever selected nothing, because
`spec.required_fields` is empty. The plugin reads `view.request.context.facts` directly, which is
why the fallback works at all. See [02 · Retriever](02-Retriever.md) §3.1.

### 7.3 · Saturation, with the count preserved

**Setup.** Six declared fields, all present, each with its own independence group.

```
declared             = ("f.0" … "f.5")                       → 6
present              = all six                               → 6
completeness_bp      = half_up(60,000, 6)                    = 10,000
groups               = {"g_0" … "g_5"}                       → 6
evidence_coverage_bp = min(10,000, 6 × 2,500) = min(10,000, 15,000) = 10,000
```

Full-unit result, verified: `{confidence_bp: 7000, source_quality_bp: 5000, completeness_bp: 10000,
corroboration_bp: 5000, evidence_coverage_bp: 10000, independent_evidence_groups: 6}`.

```
half_up(5,000×40 + 10,000×30 + 5,000×20 + 10,000×10, 100)
= half_up(200,000 + 300,000 + 100,000 + 100,000, 100) = 7,000
```

Perfect completeness and saturated coverage, yet only `7,000bp` — because all six facts are bare
scalars, so both fact-metadata axes report the neutral `5,000`. That is the blend working as
designed: structural perfection cannot buy confidence the facts themselves never claimed.

This is differential case `saturating_evidence_coverage` in `test_unit_confidence.py:614`, hash-pinned
against the pre-framework implementation.

### 7.4 · Unattributed evidence

```
facts    = {"f.0": 0, "f.1": 1}
evidence = (EvidenceRef("ev_0", field="f.0", value=0),      # no independence_group
            EvidenceRef("ev_1", field="f.1", value=1))
```

```
groups               = {None or "unattributed", None or "unattributed"} = {"unattributed"} → 1
evidence_coverage_bp = 1 × 2,500 = 2,500
```

Two citations, one group. `test_evidence_without_independence_metadata_collapses_into_one_unknown_group`.

**This is the production default on the native path.** `adapters/native.py:103` writes
`independence_group="unattributed"` whenever the fact record carries none, and
`reason/runner.py:106` writes `f"source:{source_group}"` where `source_group` is
`min(sr.source)` over the fact's source refs. So a fact corroborated by both `crm` and `gmail`
reports the single group `source:crm` — the alphabetical minimum, not the set. Two facts each backed
by the same two systems therefore produce **one** group and `2,500bp`, understating independence.
The `src_count` ladder in [03b](03b-plugin-fact_source_quality.md) does see both sources; this axis
does not.

### 7.5 · The boundary this axis cannot reach in production

In `sales.deal_cooling` and `sales.deal_cooling_full`, this unit's spec declares four
`required_fields` and `failure_policy=REQUIRED`. `orchestrator.py:178` calls
`guards.py:required_missing` **before** invoking the unit; any absent field produces
`INSUFFICIENT_CONTEXT` and terminates the run.

```
declared_field_count = 4          always
present_field_count  = 4          always — the run cannot proceed otherwise
completeness_bp      = 10,000     always
```

So the completeness axis contributes a constant `10,000 × 30 / 100 = 3,000bp` to every shipped
computed run, and §7.1's `7,500` is reachable only by calling `evaluate` directly, as the tests do.
The axis is live and correct; the deployment configuration has pinned it.

The other two shipped capabilities declare no `required_fields` on this spec — but both name a
`source_reasoner`, so this plugin is silent there. **Across the entire shipped surface,
`completeness_bp` is either `10,000` or absent.**

---

## 8 · Edge cases

| Input | `completeness_bp` | `evidence_coverage_bp` | Note |
|---|---|---|---|
| `declared = ()` | `10,000` | per evidence | `test_a_capability_that_declared_nothing_asked_for_nothing_and_got_all_of_it` |
| `declared` non-empty, `present = ()` | `0` | per evidence | the thin-snapshot case |
| A present field valued `None` | counts as present | — | presence is `in`, not truthiness |
| A `neighbor:`-prefixed declared field | counted in the denominator, never in the numerator | — | permanently caps completeness; nothing declares one today |
| `independence_group = ""` | — | same group as `None` | falsy, so `or` substitutes `"unattributed"` |
| Evidence for a neighbour fact | — | **counts** | no `context_scope` filter |
| Evidence for an undeclared root field | — | **counts** | no field filter |
| 40 evidence items, one group | — | `2,500` | volume is not independence |
| 4 evidence items, 4 groups | — | `10,000` | the ceiling |
| `declared` with `len` 0 and evidence present | `10,000` | per evidence | `divide_half_up` is never called, so its "denominator must be positive" guard is never reached |

The last row matters: `divide_half_up` raises `ValueError("denominator must be positive")` on a zero
denominator, and the `if declared` guard is the only thing standing between this plugin and that
exception. It is a real guard, not defensive decoration.

---

## Related

- [03 · Analyzer](03-Analyzer.md) — how this plugin composes with the other two
- [03b · `fact_source_quality`](03b-plugin-fact_source_quality.md) — the axes that need fact metadata
- [03c · `legacy_bridge`](03c-plugin-legacy_bridge.md) — the only thing that silences this plugin
- [04 · Calculator](04-Calculator.md) — where the two axes get their 30 and 10 weights
- [`core.context` · `fact_coverage`](../../01-Situation-Understanding/core.context/03b-plugin-fact_coverage.md) — the other `completeness_bp`
