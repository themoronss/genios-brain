# 03a · Plugin `evidence_freshness`

**Class:** `context_unit.py:EvidenceFreshnessPlugin` · **`plugin_id`:** `evidence_freshness`
**Observation kind:** `context.evidence_freshness` · **First** in execution order.

---

## 1 · The claim it makes

> *How old the newest thing we know is.*

Three integers: a linear decay score, the raw age in whole hours, and how many evidence rows carried
a usable date at all.

The plugin makes no statement about whether that age is acceptable. It reports the number and the
horizon that number was scaled against; the reading of *stale* or *current* happens one stage later
in [05 · Evaluator](05-Evaluator.md), against a separately tunable floor.

### Why the newest row rather than an average

> *"Freshness is measured from the newest dated evidence rather than an average, because staleness
> is about whether anything has happened recently: one message yesterday makes a situation current
> no matter how much of the file is a year old."*

An average punishes depth. A relationship with two hundred rows of history and one message this
morning would average to something ancient, which describes the archive rather than the situation.

### Why a straight line rather than exponential decay

> *"Decay is linear to zero across a horizon the capability owns, because 'fresh' is
> domain-specific — a week-old touch is current on an enterprise deal and ancient on a live support
> thread — and a straight line is the only decay curve a reviewer can verify by hand from the
> trace."*

That second clause is the operative one. Every number this layer produces has to be reconstructible
from an audit record with a calculator. `10_000 - age × 10_000 / horizon` is; a half-life is not.

---

## 2 · When it stays silent

```python
dated = [item for item in view.request.context.evidence
         if item.occurred_at is not None and item.occurred_at <= evaluation_time]
if not dated:
    return ()
```

**Silent when no evidence row carries an `occurred_at` at or before `evaluation_time`.** Three
distinct situations collapse into that one silence:

| Situation | Why it is silence and not a number |
|---|---|
| No evidence rows at all | Nothing to date. |
| Rows present, all with `occurred_at = None` | *"'We do not know how old this is' and 'this is stale' are different claims."* (`test_undated_evidence_produces_no_freshness_claim_rather_than_a_zero`) |
| Rows present, all dated **after** `evaluation_time` | *"Evidence dated after the evaluation instant cannot describe the situation being reasoned about; treating it as 'zero hours old' would let a clock skew read as perfect freshness."* (`test_evidence_dated_after_the_evaluation_instant_is_not_treated_as_perfectly_fresh`) |

The third is the one that earns its keep. A skewed source clock producing timestamps three hours in
the future would otherwise pin `freshness_bp` at 10,000 forever, and the failure would be invisible
because a maximum score looks exactly like a healthy one.

**What silence does not mean:** it never means `freshness_bp = 0`. Zero is reserved for *"we have a
date and it is past the horizon"*, which is a claim the plugin can support.

---

## 3 · The arithmetic, in full

```python
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    horizon = _config_count(view, "freshness_horizon_hours", 168)
    evaluation_time = view.request.evaluation_time
    dated = [item for item in view.request.context.evidence
             if item.occurred_at is not None and item.occurred_at <= evaluation_time]
    if not dated:
        return ()
    newest = max(item.occurred_at for item in dated)
    age_hours = int((evaluation_time - newest).total_seconds()) // 3600
    cited = tuple(sorted(item.evidence_id for item in dated if item.occurred_at == newest))
    return (Observation(
        plugin_id=self.plugin_id,
        kind="context.evidence_freshness",
        metrics={
            "freshness_bp": clamp_bp(
                10_000 - divide_half_up(min(age_hours, horizon) * 10_000, horizon)),
            "evidence_age_hours": age_hours,
            "dated_evidence_count": len(dated),
        },
        evidence_ids=cited[:1],
        reason_codes=("context_evidence_dated",),
    ),)
```

Stated as arithmetic:

```text
horizon      = config["freshness_horizon_hours"]            default 168 hours (7 days)
dated        = { e ∈ snapshot.evidence : e.occurred_at ≠ None
                                       ∧ e.occurred_at ≤ evaluation_time }
newest       = max{ e.occurred_at : e ∈ dated }
age_hours    = ⌊ (evaluation_time − newest) in seconds ⌋ // 3600      # whole hours, truncated
decayed      = divide_half_up( min(age_hours, horizon) × 10_000 , horizon )
freshness_bp = clamp_bp( 10_000 − decayed )

evidence_age_hours   = age_hours          # NOT capped at the horizon
dated_evidence_count = |dated|            # all scopes, all fields
```

`common.py:divide_half_up(n, d)` is `(n + d//2) // d` for non-negative `n` — half-up rounding with
no float anywhere in the path.

### 3.1 · The clamp never binds

`clamp_bp` is `min(10_000, max(0, int(value)))`. For any `horizon ≥ 1`:

```text
min(age, horizon) ≤ horizon
  ⇒ min(age,horizon) × 10_000 / horizon ≤ 10_000
  ⇒ divide_half_up(...) ≤ 10_000                 (half-up of a value ≤ 10,000 is ≤ 10,000)
  ⇒ 10_000 − decayed ∈ [0, 10_000]

and at age ≥ horizon exactly:
  divide_half_up(horizon × 10_000, horizon) = (horizon×10_000 + horizon//2) // horizon = 10_000
  ⇒ freshness_bp = 0                             exactly, never negative
```

So `clamp_bp` here is defensive rather than functional. Worth knowing before someone "simplifies"
the expression by removing the `min(age_hours, horizon)` on the grounds that the clamp will catch
it — it would, but only after the subtraction had already gone negative, which is a different code
path from the one the tests cover.

### 3.2 · Hours are truncated, not rounded

`int(delta.total_seconds()) // 3600` floors. 59 minutes is 0 hours; 167 minutes is 2 hours. Verified
at the boundary:

```text
occurred_at = evaluation_time − 59 minutes
  → evidence_age_hours = 0
  → freshness_bp       = 10_000 − divide_half_up(0, 168) = 10_000
```

The truncation is generous by up to one hour on a horizon measured in hours. On the default 168-hour
horizon that is at most 60bp of optimism; on a 4-hour support-thread horizon it would be 2,500bp,
which is the configuration where the choice would need revisiting.

### 3.3 · `evidence_age_hours` is uncapped, `freshness_bp` is not

`min(age_hours, horizon)` applies only inside the score. The raw age is published as-is. That is why
a 5,000-hour-old snapshot reports `freshness_bp: 0, evidence_age_hours: 5_000` rather than
`0, 168` — the score saturates, the fact does not, and the fact is what a human reads in the trace.

---

## 4 · Configuration

| Key | Type | Default | Validator | Failure mode |
|---|---|---|---|---|
| `freshness_horizon_hours` | positive integer | `168` (7 days) | `context_unit.py:_config_count` | `ValueError("freshness_horizon_hours must be a positive integer")` |

```python
def _config_count(view: UnitView, key: str, default: int) -> int:
    """A positive integer count or duration from capability config (not a basis-point value)."""
    value = view.config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{key} must be a positive integer")
    return value
```

**Validated eagerly.** The read is the first statement in `contribute`, before the silence check, so
a malformed horizon raises on every run — including runs with no evidence at all. Verified:

```text
config={"freshness_horizon_hours": 0}, evidence=()
  → ValueError: freshness_horizon_hours must be a positive integer
```

This is the opposite of how `evaluate_meaning`'s two floors behave, and it is the better half of
that inconsistency. See [05 · Evaluator](05-Evaluator.md) §4.

**There is no upper bound.** `_config_count` accepts any integer ≥ 1, so a capability can set a
horizon of 100,000 hours (11 years) and every situation will read as current. Nothing catches it.

---

## 5 · What it cites

```python
cited = tuple(sorted(item.evidence_id for item in dated if item.occurred_at == newest))
...
evidence_ids=cited[:1]
```

**One row, even when several share the newest instant.** The `[:1]` keeps the lexicographically
smallest `evidence_id` and discards the rest.

Verified on the README worked example: `ev_mail_status` and `ev_thread` are both dated 288 hours
ago, and the observation cites only `ev_mail_status` (`'ev_mail_status' < 'ev_thread'`).

The rationale is not stated in the module. The defensible reading is that the claim is *"the newest
thing is this old"* and one representative is enough to prove the instant; citing every co-newest
row would inflate the evidence set without adding information. But the effect is real and worth
recording: **a reader following the trace to check the freshness reading sees one of the sources
that produced it, chosen by string sort.** If two integrations both delivered at the same instant
and one of them is the suspect, the trace may point at the other.

For contrast, `core.validation:StalenessPlugin` — which measures the same underlying quantity —
cites `(freshest_id,) + stale`, that is, the freshest row *plus every row past the limit*.

---

## 6 · Worked examples

### 6.1 · One day old, default horizon

`test_freshness_follows_the_newest_evidence_not_the_oldest`. Two rows: `ev_old` on `deal.status`
dated 2,000 hours ago, `ev_new` on `thread.last_inbound` dated 24 hours ago.

```text
dated        = [ev_old, ev_new]                             both ≤ evaluation_time
newest       = evaluation_time − 24h
age_hours    = 86,400 s // 3600                             = 24
decayed      = divide_half_up(24 × 10_000, 168)
             = (240,000 + 84) // 168 = 240,084 // 168       = 1,429
freshness_bp = 10,000 − 1,429                               = 8,571

metrics      {freshness_bp: 8,571, evidence_age_hours: 24, dated_evidence_count: 2}
evidence_ids ('ev_new',)
reason_codes ('context_evidence_dated',)
```

The 2,000-hour row contributes to `dated_evidence_count` and to nothing else. That is the point: one
message yesterday makes the situation current.

### 6.2 · Past the horizon

`test_evidence_older_than_the_horizon_reads_as_zero_freshness_not_negative`. One row, 5,000 hours
old.

```text
age_hours    = 5,000
min(5,000, 168)                                              = 168
decayed      = divide_half_up(168 × 10_000, 168)             = 10,000
freshness_bp = 10,000 − 10,000                               = 0

metrics      {freshness_bp: 0, evidence_age_hours: 5,000, dated_evidence_count: 1}
```

Zero, not negative — and the uncapped `evidence_age_hours: 5_000` is what tells a reader the
difference between *"just past the week"* and *"seven months"*, both of which score 0.

### 6.3 · A capability that owns a shorter horizon

`test_the_freshness_horizon_belongs_to_the_capability`. One row 12 hours old,
`freshness_horizon_hours = 24`.

```text
decayed      = divide_half_up(12 × 10_000, 24) = (120,000 + 12) // 24 = 5,000
freshness_bp = 10,000 − 5,000                                          = 5,000
```

The same 12-hour-old row scores **9,286bp** on the default 168-hour horizon and **5,000bp** here.
*"A week-old touch is current on an enterprise deal and ancient on a live support thread."*

### 6.4 · The full default decay curve

Every value below computed from `10_000 − divide_half_up(min(h,168) × 10_000, 168)`:

| Age (hours) | `freshness_bp` | Reading at the default 3,000bp floor |
|---|---|---|
| 0 | 10,000 | current |
| 1 | 9,940 | current |
| 12 | 9,286 | current |
| 24 (1 day) | 8,571 | current |
| 48 | 7,143 | current |
| 72 (3 days) | 5,714 | current |
| 84 (3.5 days) | 5,000 | current |
| 100 | 4,048 | current |
| 117 | 3,036 | current |
| **118** | **2,976** | **stale** — the boundary |
| 120 (5 days) | 2,857 | stale |
| 168 (7 days) | 0 | stale |
| 720 (30 days) | 0 | stale |

**The default configuration calls a situation stale at 118 hours — four days and twenty-two
hours.** That is not stated anywhere in the module; it falls out of the interaction between a
168-hour horizon and a 3,000bp floor, both defaults chosen independently. A capability author
tuning one without the other will move the boundary without meaning to.

### 6.5 · An 11-year horizon

Not a test — a demonstration that nothing stops it. `freshness_horizon_hours = 100_000`, one row 720
hours (30 days) old:

```text
decayed      = divide_half_up(720 × 10_000, 100_000) = (7,200,000 + 50,000) // 100,000 = 72
freshness_bp = 10,000 − 72                                                              = 9,928
                                                                       → context_current
```

A month-old deal reads as 99% fresh. The horizon is the capability's to own, and owning it badly is
not a validation error.

---

## 7 · Cross-unit note: the same measurement, taken twice, differently

`core.validation:StalenessPlugin` measures the age of the freshest dated evidence in the same run.
Both units are declared in `sales.deal_cooling_full`. They differ in four ways:

| | `core.context:evidence_freshness` | `core.validation:staleness` |
|---|---|---|
| Config key | `freshness_horizon_hours` (default 168) | `max_evidence_age_hours` (default 168) |
| Future-dated rows | **excluded entirely** | `max(seconds, 0)` — treated as **age zero** |
| Metric | `freshness_bp` — decays from 10,000 to 0 across the horizon | `staleness_bp` — stays 0 *within* the limit, then rises past it |
| Cites | one row at the newest instant | freshest row **plus** every row past the limit |

The future-dated row is a genuine disagreement, not a stylistic difference. A clock-skewed
integration produces:

```text
core.context     → no freshness observation at all      (refuses to read a skewed clock)
core.validation  → freshest_age_hours = 0, staleness_bp = 0, reason "evidence_current"
```

One unit declines to answer; the other answers *"perfectly current"*. `core.context`'s own comment
names this exact failure — *"treating it as 'zero hours old' would let a clock skew read as perfect
freshness"* — and the other unit does precisely that, with a comment arguing it is the safer choice
because a negative age would be worse. Both comments are right about the alternative they rejected;
neither considered the third option the other took. The metric names are different, so
`core.validation`'s own divergence check will never flag it.

---

## Related

| File | Covers |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | Execution order, and why the three plugins do not interact |
| [03b · `fact_coverage`](03b-plugin-fact_coverage.md) | The second plugin |
| [03c · `source_corroboration`](03c-plugin-source_corroboration.md) | The third |
| [05 · Evaluator](05-Evaluator.md) | `freshness_floor_bp`, and the 118-hour boundary |
