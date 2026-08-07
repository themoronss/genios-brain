# 03a · Plugin `delay_cost`

**Class:** `genios_engine/reason/reasoners/cost_unit.py:DelayCostPlugin` (lines 137–175)
**`plugin_id`:** `delay_cost` · **`kind`:** `cost.delay` · **runs first** in `plugin_id` order
**Tests:** `test_delay_cost_says_nothing_when_nothing_dates_the_silence` ·
`test_delay_cost_ignores_an_unparseable_timestamp_rather_than_guessing` ·
`test_delay_cost_prices_whole_days_of_waiting` ·
`test_delay_cost_falls_back_to_measured_momentum_loss_when_no_timestamp_exists` ·
`test_delay_cost_takes_the_stronger_reading_instead_of_adding_them`

---

## 1 · The claim it makes

*Waiting is not free, and here is what it costs.*

This is the number that makes "expensive" a comparison rather than a verdict. From the unit
docstring:

> *"A quiet thread does not stay warm, and the headroom another unit found does not stay open. This
> is the number that makes 'expensive' a comparison rather than a verdict: an expensive play against
> a very expensive silence is cheap."*

Two independent readings of the same silence, either of which alone is enough to speak:

| Reading | Source | Prices the wait as |
|---|---|---|
| Elapsed time | `context.facts[delay_field]` against `request.evaluation_time` | duration — how long nobody has moved |
| Momentum loss | `core.temporal.drop_bp` via `prior_metric` | warmth — how much heat the thread has lost |

The stronger leads. They are never summed, *"because they measure the same decay and adding them
would double-count it."*

---

## 2 · When it stays silent

**This is the only plugin in the unit with a reachable silence, and it is the most load-bearing
behaviour in the unit.** From the plugin docstring:

> *"Silent when neither exists. An unknown cost of waiting must stay unknown — reporting it as zero
> would tell the Decision Maker that delay is free, which is the single most expensive thing this
> unit could get wrong."*

The gate is one line:

```python
if hours is None and momentum_bp <= 0:
    return ()
```

| Condition | `hours` | `momentum_bp` | Result |
|---|---|---|---|
| No fact at the delay field, no prior | `None` | `0` | **`()`** |
| Fact present but unparseable | `None` | `0` | **`()`** |
| Fact present but timezone-naive | `None` | `0` | **`()`** |
| Fact present but future-dated | `None` | `0` | **`()`** |
| Fact not a datetime or ISO string, e.g. `1234` | `None` | `0` | **`()`** |
| `delay_field` names a `neighbor_facts` key | `None` | `0` | **`()`** |
| No fact, but `core.temporal.drop_bp = 7,000` | `None` | `7,000` | observation, **no `waiting_hours`** |
| No fact, and `core.temporal.drop_bp = 0` | `None` | `0` | **`()`** — a zero drop is not a reading |
| Fact parses, any age including zero | `int ≥ 0` | anything | observation |

Note the two-part asymmetry in that table. A **parseable timestamp always speaks**, even when it
prices at zero. A **momentum reading only speaks when it is positive** — `momentum_bp <= 0` is
treated as "no reading" rather than "measured no decay". That asymmetry is where the unit's
best-known contradiction comes from. §6.1.

---

## 3 · The full arithmetic

```python
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    field = str(view.config.get("delay_field") or "deal.last_inbound")
    per_day = _config_bp(view, "delay_cost_per_day_bp", 400)
    hours: int | None = None
    if fact_value(view.request, field) is not None:
        try:
            hours = elapsed_hours(view.request, field)
        except ValueError:
            hours = None                # unparseable or future-dated: no claim, not a zero
    elapsed_cost = clamp_bp((hours // 24) * per_day) if hours is not None else 0
    momentum_bp = clamp_bp(view.prior_metric("core.temporal", "drop_bp", 0))
    if hours is None and momentum_bp <= 0:
        return ()
    metrics = {"delay_cost_bp": max(elapsed_cost, momentum_bp),
               "momentum_drop_bp": momentum_bp}
    if hours is not None:
        metrics["waiting_hours"] = hours
    return (Observation(
        plugin_id=self.plugin_id,
        kind="cost.delay",
        metrics=metrics,
        evidence_ids=evidence_ids(view.request, field),
        reason_codes=("waiting_has_a_price",),
    ),)
```

In arithmetic:

```text
field         = str(config["delay_field"] or "deal.last_inbound")
per_day       = config["delay_cost_per_day_bp"]            default 400

hours         = floor( (evaluation_time − occurred_at).total_seconds() / 3600 )
                or None if absent / unparseable / naive / future-dated

elapsed_cost  = clamp_bp( floor(hours / 24) × per_day )    or 0 when hours is None
momentum_bp   = clamp_bp( core.temporal.drop_bp )          default 0

if hours is None and momentum_bp ≤ 0:  →  SILENCE

delay_cost_bp = max(elapsed_cost, momentum_bp)
```

Two floor divisions stacked. `elapsed_hours` truncates seconds to whole hours; `hours // 24`
truncates hours to whole days. A silence of 47 hours 59 minutes prices as **one** day.

### 3.1 · Why whole days

The plugin costs whole days at a fixed configured rate rather than fitting a curve, and the reason is
the same one `step_effort` gives for costing steps: a reviewer must be able to reproduce the number
by hand from the manifest and the timestamp. `10 days × 400bp = 4,000bp` is checkable; a decay
exponent is not.

The cost is a step function with a 400bp discontinuity at every midnight-offset from the inbound
timestamp. Nothing smooths it, and nothing needs to — the number is an input to a comparison against
a 2,000bp threshold, not a ranking key.

### 3.2 · The elapsed-time helper

```python
# common.py:elapsed_hours
def elapsed_hours(request: ReasoningRequest, field: str) -> int:
    occurred = parse_time(fact_value(request, field), field)
    seconds = int((request.evaluation_time - occurred).total_seconds())
    if seconds < 0:
        raise ValueError(f"{field} is in the future")
    return seconds // 3600
```

`request.evaluation_time`, never `datetime.now()`. That is what makes the number replayable: the
same request produces the same `waiting_hours` in 2026 and in 2030.

`common.py:parse_time` raises on three shapes, all of which the plugin catches and converts to
`hours = None`:

| Input | `parse_time` |
|---|---|
| `datetime` with tzinfo | accepted, converted to UTC |
| ISO-8601 string, `Z` or offset | accepted |
| ISO-8601 string with no offset | `ValueError: must be timezone-aware` |
| Any non-string, non-datetime | `ValueError: must be an ISO-8601 datetime` |
| Unparseable string | `ValueError: must be an ISO-8601 datetime` |

### 3.3 · Config keys

| Key | Default | Validated by | Notes |
|---|---|---|---|
| `delay_cost_per_day_bp` | `400` | `_config_bp` — int `0..10_000` | at the default, `delay_cost_bp` saturates at **25 days** |
| `delay_field` | `"deal.last_inbound"` | **nothing** | `str(view.config.get("delay_field") or "deal.last_inbound")`. `""`, `0`, `None` and `False` all fall back to the default; `17` becomes the literal field name `"17"` and the plugin stays silent |

`delay_field` is the only config value in the whole unit that does not pass through `_config_bp`, and
therefore the only one where a deployment fault produces silence instead of a raise. Verified:
`{"delay_field": 17}` against a snapshot carrying `deal.last_inbound` yields `()` — the cost of
waiting silently disappears, and the only symptom is a `do_nothing_cost_unknown` code that looks
exactly like a snapshot with no timestamp in it.

---

## 4 · Worked example 1 — ten days of buyer silence

`test_delay_cost_prices_whole_days_of_waiting` and the end-to-end Acme scenario.

```text
evaluation_time            2026-08-06T12:00:00Z
deal.last_inbound          2026-07-27T12:00:00Z
core.temporal              not a declared dependency → prior_metric returns 0
config                     defaults

parse_time                 → 2026-07-27T12:00:00+00:00
seconds                    = 864,000
hours                      = 864,000 // 3600            = 240
elapsed_cost               = clamp_bp( (240 // 24) × 400 )
                           = clamp_bp( 10 × 400 )       = 4,000
momentum_bp                = clamp_bp(0)                = 0

hours is not None          → no silence
delay_cost_bp              = max(4,000, 0)              = 4,000
```

```text
Observation(plugin_id='delay_cost', kind='cost.delay',
            metrics={'delay_cost_bp': 4000, 'momentum_drop_bp': 0, 'waiting_hours': 240},
            evidence_ids=('ev_inbound',),
            reason_codes=('waiting_has_a_price',))
```

`4,000bp` means 0.40. Against the same run's `cost_bp` of 3,120, acting is cheaper than waiting — and
that comparison is the entire reason this plugin exists.

## 5 · Worked example 2 — the momentum fallback, and why it is dark

`test_delay_cost_falls_back_to_measured_momentum_loss_when_no_timestamp_exists`. No timestamp
anywhere in the snapshot, but `core.temporal` has already run and reported the same thread as cold:

```text
snapshot.facts             = {}
prior["core.temporal"]     = ReasonerResult(status=COMPLETED, metrics={"drop_bp": 7000})

fact_value(request, "deal.last_inbound")  → None
hours                      = None
elapsed_cost               = 0
momentum_bp                = clamp_bp(7,000)            = 7,000

hours is None BUT momentum_bp > 0        → no silence
delay_cost_bp              = max(0, 7,000)              = 7,000
"waiting_hours" NOT in metrics                          ← nothing was timed
```

```text
Observation(metrics={'delay_cost_bp': 7000, 'momentum_drop_bp': 7000},
            evidence_ids=(), reason_codes=('waiting_has_a_price',))
```

The omitted `waiting_hours` is the honest part. The plugin reports a price for the wait without
claiming to know how long the wait has been, and a consumer that needed the duration finds the key
absent rather than zero.

**And the third reading, when both exist.** `test_delay_cost_takes_the_stronger_reading_instead_of_adding_them`:

```text
deal.last_inbound          = evaluation_time − 5 days
core.temporal.drop_bp      = 6,000

elapsed_cost               = (120 // 24) × 400          = 2,000
momentum_bp                = 6,000
delay_cost_bp              = max(2,000, 6,000)          = 6,000     ← not 8,000
waiting_hours              = 120
```

Both readings survive into the metrics — `delay_cost_bp: 6,000` and `momentum_drop_bp: 6,000` — so
a reader can see that the two agreed on direction and disagreed on magnitude, and which one won.

**Why this is dark in production.** `prior_metric` returns its default when the dependency did not
run, did not complete, or was never declared:

```python
result = self.prior.get(reasoner_id)
if result is None or result.status != ResultStatus.COMPLETED:
    return default
```

The shipped `core.cost` spec in `deal_cooling_v2.py` declares `dependencies=()`, and the orchestrator
populates `prior` with **declared dependencies only** — precisely so that passing every earlier
result cannot create hidden order-dependent edges. So `prior` is `{}` on every production run,
`momentum_bp` is always `0`, and this entire branch has never executed outside the test suite. No
error, no reason code, no telemetry. Adding `"core.temporal"` to the spec's `dependencies` tuple
lights it with no code change.

---

## 6 · Edge cases and the known contradiction

### 6.1 · A measured zero is reported as unknown

The plugin fires on any parseable timestamp and prices whole days only. A message that arrived six
hours ago therefore produces a **measured** `delay_cost_bp: 0`, which the Evaluator cannot
distinguish from the plugin having been silent. Verified end to end:

```text
deal.last_inbound = evaluation_time − 6 hours

waiting_hours      = 6
elapsed_cost       = (6 // 24) × 400 = 0 × 400 = 0
delay_cost_bp      = 0
do_nothing_cost_bp = 0

result.reason_codes = ('cost_within_tolerance', 'do_nothing_cost_unknown',
                       'effort_estimated_from_declared_steps', 'roster_is_reversible',
                       'waiting_has_a_price')
```

**`waiting_has_a_price` and `do_nothing_cost_unknown` on the same result.** They contradict each
other: one says the plugin measured the silence, the other says nobody could.

`evaluate_meaning` adds `do_nothing_cost_unknown` whenever `metrics["do_nothing_cost_bp"] == 0`,
keying off the **value**. The unit's own principle — a published zero is a claim, an absent metric is
an admission — argues it should key off whether the `cost.delay` observation exists at all. The fix
is one line in `evaluate_meaning`, and it is not built. Full argument at [05](05-Evaluator.md) §4.2.

The same shape appears inside the plugin's own silence gate: `momentum_bp <= 0` treats a measured
zero drop as no reading, while `hours = 0` is treated as a reading. Two zeros, two different
meanings, in one function.

### 6.2 · The day-boundary table

Real outputs at the default 400bp/day, `evaluation_time = 2026-08-06T12:00Z`:

| Age | `waiting_hours` | `hours // 24` | `delay_cost_bp` |
|---|---|---|---|
| 0 h | 0 | 0 | **0** |
| 6 h | 6 | 0 | **0** |
| 23 h 59 m | 23 | 0 | **0** |
| 24 h | 24 | 1 | 400 |
| 6 d | 144 | 6 | 2,400 |
| 10 d | 240 | 10 | 4,000 |
| 25 d | 600 | 25 | **10,000** |
| 26 d | 624 | 26 | 10,000 — clamped |
| 60 d | 1,440 | 60 | 10,000 — clamped |

**Delay cost saturates at 25 days on the default rate**, so a month of silence and a year of silence
are the same number. `waiting_hours` is *not* clamped — it keeps counting — so the fact survives
even where the score does not. That is the right split, and it is undocumented in the module.

### 6.3 · Every input shape

| `snapshot.facts["deal.last_inbound"]` | `hours` | Observation |
|---|---|---|
| `"2026-08-02T12:00:00+00:00"` | 96 | 1,600bp |
| `"2026-08-02T12:00:00Z"` | 96 | 1,600bp — `Z` is rewritten to `+00:00` |
| `{"value": "2026-08-02T12:00:00+00:00", "source": "crm"}` | 96 | 1,600bp — `fact_value` unwraps the envelope |
| `datetime(2026, 8, 2, 12, tzinfo=utc)` | 96 | 1,600bp |
| `"2026-08-02T12:00:00"` — no offset | `None` | **silent** — naive datetimes are refused |
| `"last tuesday"` | `None` | **silent** |
| `1234` | `None` | **silent** |
| `evaluation_time + 2 days` | `None` | **silent** — `elapsed_hours` raises `is in the future` |
| absent | `None` | **silent** |
| present in `neighbor_facts` only | `None` | **silent** — `fact_value` defaults to `neighbor=False` |
| `None` | `None` | **silent** — the presence test is `is not None` |

A future-dated timestamp deserves its own note. Clock skew between a CRM and the engine is ordinary,
and the plugin's response is to say nothing rather than to report a negative or a zero. *"A corrupt
fact is missing evidence, not evidence of a fresh conversation."*

### 6.4 · The citation

```python
evidence_ids=evidence_ids(view.request, field),
```

Every evidence row whose `field` equals the delay field, sorted. This is the **only** citation
anywhere in `core.cost` — the other two plugins emit `evidence_ids=()`, and the adjustments and
checks carry none. So a `core.cost` result cites evidence if and only if this plugin fired *and* the
snapshot happened to carry an `EvidenceRef` for that field.

On the shipped `sales.deal_cooling_full` run the snapshot carried the fact but no evidence row for
it, so the result cites nothing while still asserting three matched findings. [02](02-Retriever.md)
§4.1 covers what that would mean if `core.validation` could see it.

`EvidenceRef.context_scope` is ignored by `common.py:evidence_ids`, so a neighbour-scoped row on the
same field name would be cited even though `fact_value` refuses to read the neighbour fact itself.

---

## Related

| File | Covers |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | Why this plugin runs first, and how `calculate` finds its observation by `kind` |
| [04 · Calculator](04-Calculator.md) §3.3 | Where `delay_cost_bp` is corroborated by `core.opportunity`, at a different strength |
| [05 · Evaluator](05-Evaluator.md) §4.2 | `do_nothing_cost_unknown` and the contradiction in full |
| [02 · Retriever](02-Retriever.md) §3.2 | Why this plugin's citation bypasses the unit's window |
| [README](README.md) §6 | The unit's silence semantics table |
