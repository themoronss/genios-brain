# Plugin · `speed_vs_certainty`

**Class:** `tradeoff_unit.py:SpeedVersusCertaintyPlugin` (lines 111–132)
**`plugin_id`:** `speed_vs_certainty`
**Runs:** third of three, in `plugin_id` order
**Status in production:** **dark.** Neither of its two sources is declared as a dependency of
`core.tradeoff` in the shipped manifest, though both units complete in the same run. See §3.1.

---

## 1 · The claim it makes

> *Move now, or wait until we are surer?*

```python
class SpeedVersusCertaintyPlugin:
    """Move now, or wait until we are surer?

    The oldest argument in any commercial operation. Time pressure is what the temporal unit
    measured; the pull in the other direction is *doubt*, which is the complement of published
    confidence — the less well evidenced we are, the more a delay is worth. Reading confidence and
    inverting it here is the whole point of the axis: acting fast is only cheap when we are sure.

    This unit reads `confidence_bp`; it must never publish it. `core.confidence` is its sole
    authority, and a second publisher would silently re-score every decision in the system.
    """
```

This is the only axis whose two sides are not both directly measured. Side A is read straight;
side B is *derived* — by inverting a published metric. That derivation is the plugin's entire
contribution, and it is worth spelling out why it is correct rather than convenient.

No unit in the roster publishes "the value of waiting". `core.scheduling` publishes timing fit,
`core.temporal` publishes urgency; nothing publishes patience. But the case for waiting has an exact
proxy already in the system: **remaining doubt.** If the evidence is 9,000bp good, there are 1,000bp
of doubt left and very little to gain by waiting for more. If the evidence is 2,500bp good, there are
7,500bp of doubt and waiting buys a great deal. *Acting fast is only cheap when we are sure.*

Side names: **`speed`** and **`certainty`**.

---

## 2 · What exists

```python
plugin_id = "speed_vs_certainty"

def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    speed = _prior_bp(view, "speed_source", "core.temporal", "urgency_bp")
    confidence = _prior_bp(view, "certainty_source", "core.confidence", "confidence_bp")
    if speed is None or confidence is None:
        return ()
    # The case for waiting is exactly as strong as our remaining doubt.
    return _weigh(view, self.plugin_id, "speed_vs_certainty",
                  "speed", speed, "certainty", clamp_bp(10_000 - confidence))
```

### Config keys

| Key | Default | Type | Validated by | Meaning |
|---|---|---|---|---|
| `speed_source` | `"core.temporal"` | non-empty string | `_config_id` | Which unit publishes `urgency_bp` |
| `certainty_source` | `"core.confidence"` | non-empty string | `_config_id` | Which unit publishes `confidence_bp`, which is then inverted |
| `decisive_margin_bp` | `500` | int 0–10,000 | `_config_bp`, inside `_weigh` | Below this margin no side is named |

### The inversion

```python
certainty_side = clamp_bp(10_000 - confidence)
```

`confidence` is already `0..10000` — `_prior_bp` clamps it, and `ReasonerResult` validated it before
that — so `10_000 - confidence` is already in range and the `clamp_bp` never binds. It is defensive.

The mapping is exact and worth having in a table, because it is the one place in this unit where a
number changes meaning:

| `confidence_bp` published by `core.confidence` | `trailing`/`leading` value used as the certainty side | Reading |
|---|---|---|
| 10,000 | 0 | Nothing left to learn. Waiting is worthless |
| 9,000 | 1,000 | Well evidenced. Waiting buys almost nothing |
| 6,950 | 3,050 | The shipped run's confidence |
| 5,200 | 4,800 | Genuinely ambiguous |
| 2,500 | 7,500 | Thin evidence. Waiting buys a lot |
| 0 | 10,000 | We know nothing. Waiting is everything |

### 2.1 · Read it, never publish it

The docstring makes this a rule rather than an observation:

> *This unit reads `confidence_bp`; it must never publish it. `core.confidence` is its sole
> authority, and a second publisher would silently re-score every decision in the system.*

`tests/test_unit_roster.py:test_only_the_named_authority_publishes_a_shared_decision_metric` enforces
it across the roster, and this unit's own test file re-asserts it locally:

```python
def test_the_unit_never_republishes_a_reserved_shared_metric():
    published = set(TradeoffUnit().publishes)
    assert published.isdisjoint({"confidence_bp", "urgency_bp", "priority_override_bp"})
    ...
    assert set(result.metrics) <= published
```

The teeth are in `decision_maker.py:calculate_confidence`, which scans results in plan order taking
any `confidence_bp` it finds and **breaks** at `CONFIDENCE_AUTHORITY`. A second publisher scheduled
before `core.confidence` would silently become the confidence of every decision in the system.

Note what the unit publishes instead: `trailing_bp` or `leading_bp`, whichever side doubt landed on.
That number is `10,000 − confidence_bp` and it is derived from a reserved metric — but it carries a
different name and a different meaning, so it cannot be mistaken for the authority's value by any
consumer that scans metrics by name.

### 2.2 · The default `speed_source` reads an un-audited publisher

`speed_source` defaults to `core.temporal`, which is a **supplementary** reasoner, not a framework
unit. It has no `publishes` tuple, which is exactly why it is allowed to emit `urgency_bp`:

```python
# temporal.py
urgency_bp = clamp_bp(drop_bp + min(hours, 168) * 20)
```

`test_unit_roster.py` reserves `urgency_bp` for `core.priority` — and passes anyway, because it reads
`getattr(instance, "publishes", ())` and `TemporalReasoner` has no such attribute. So there are two
publishers of `urgency_bp` in the roster, and this plugin's default points at the one the roster test
does not audit.

Does it matter here? In the shipped run, no: `core.temporal` reports `urgency_bp 9,360` and
`core.priority` reports `urgency_bp 9,360`. They agree because `core.priority` does not compute
urgency at all — *"the value is not computed here from scratch: it is sourced, from a unit that
already measured the thing urgency is made of"* — and `sales.deal_cooling` names `core.temporal` as
its `source_reasoner`.

They agree **in that capability**. A capability that named a different `source_reasoner`, or that
named none and let `core.priority` fall back to *"the maximum `urgency_bp` any prior unit
reported"*, would have the two diverge — and this plugin's default would read the raw input rather
than the authority's resolved answer. A capability that wants the audited number must author
`speed_source: "core.priority"` explicitly. The default reaches past the authority to its input.

### The observation it emits

| Metric | Value |
|---|---|
| `tension_bp` | `min(speed, doubt) × (10,000 − margin) ÷ 10,000`, half-up |
| `margin_bp` | `abs(speed − doubt)` |
| `leading_bp` | `max(speed, doubt)` |
| `trailing_bp` | `min(speed, doubt)` |

| Reason code | Condition |
|---|---|
| `tradeoff.speed_vs_certainty` | always |
| `balanced.speed_vs_certainty` | `margin_bp < decisive_margin_bp` |
| `favours.speed` + `concedes.certainty` | `speed > doubt` and margin at or above the deadband |
| `favours.certainty` + `concedes.speed` | `doubt >= speed` and margin at or above the deadband |

---

## 3 · When it stays silent

```python
if speed is None or confidence is None:
    return ()
```

Same three absence paths as every other axis: source not in `view.prior`, source did not complete,
source published no metric of that name. `test_no_axis_is_reported_when_nothing_ran_before_it` covers
the empty case for all three plugins at once.

The inversion makes one silence case worth calling out specifically. **An absent confidence unit
cannot be read as "no confidence".** If `_prior_bp` returned `0` on absence instead of `None`, the
inversion would turn it into `10,000` of doubt — a maximal case for waiting, manufactured out of a
unit that never ran. The `_ABSENT = -1` sentinel is what stops that, and it is a more dangerous
failure here than on the other two axes because the inversion amplifies it: absence would become the
*strongest possible* signal rather than the weakest.

### 3.1 · Why it is dark in production

`deal_cooling_v2` declares:

```python
_spec("core.tradeoff", ("core.risk", "core.opportunity", "core.impact", "core.cost"))
```

Neither `core.temporal` nor `core.confidence` is in that tuple. Both complete successfully in the
same run — `urgency_bp 9,360` and `confidence_bp 6,950` — and `orchestrator.py` filters them out
because the spec did not name them:

```python
dependencies = {item: prior[item] for item in spec.dependencies if item in prior}
```

So `view.prior` has four entries, neither source is among them, `_prior_bp` returns `None` twice, and
the plugin returns `()`. No error, no reason code, no telemetry.

The fix is two ids in a tuple. Verified — adding `core.temporal` and `core.confidence` to the
dependencies of the shipped spec lights the axis with `tension_bp 1,125`, and takes the result's
`axis_count` from 1 to 3 (in combination with the `cost_source` fix from
[03a](03a-plugin-cost_vs_benefit.md)).

There is a scheduling constraint behind that edit worth checking before it is made. `core.confidence`
sits in `deal_cooling_v2`'s Category 2 block and `core.tradeoff` in Category 3, and
`test_l4_end_to_end.py:147` already asserts `stage_of["core.temporal"] < stage_of["core.risk"] <
stage_of["core.tradeoff"]`, so both sources already run before the tradeoff unit does. Adding the
dependencies makes the existing order explicit rather than reordering anything.

---

## 4 · Worked examples

### 4.1 · High confidence removes the case for waiting

From `test_high_confidence_removes_the_case_for_waiting` — *"Well-evidenced and time-pressured is not
a dilemma; it is a reason to move."*

```text
core.temporal    urgency_bp     8,000
core.confidence  confidence_bp  9,000  →  doubt = 10,000 − 9,000 = 1,000

margin  = |8000 − 1000| = 7,000
tension = min(8000, 1000) × (10000 − 7000) ÷ 10000
        = 1000 × 3000 ÷ 10000
        = 3,000,000 ÷ 10,000
        = 300

margin 7,000 ≥ 500 → a side is named
speed 8,000 > certainty 1,000 → favours.speed · concedes.certainty
```

```text
metrics       tension_bp 300 · margin_bp 7,000 · leading_bp 8,000 · trailing_bp 1,000
reason_codes  concedes.certainty · favours.speed · tradeoff.speed_vs_certainty
```

300bp of tension against a 3,000bp threshold: not contested, and correctly so. Strong time pressure
with strong evidence is not a dilemma. The `concedes.certainty` code still records that we gave up
1,000bp of potential further certainty by moving — a small concession, but the sentence is available
if anyone asks.

### 4.2 · Thin evidence pulls against a deadline

From `test_thin_evidence_pulls_against_a_deadline` — *"Urgent and barely evidenced is the classic
contested call, and must read as one."*

```text
core.temporal    urgency_bp     6,000
core.confidence  confidence_bp  2,500  →  doubt = 10,000 − 2,500 = 7,500

margin  = |6000 − 7500| = 1,500
tension = min(6000, 7500) × (10000 − 1500) ÷ 10000
        = 6000 × 8500 ÷ 10000
        = 51,000,000 ÷ 10,000
        = 5,100

margin 1,500 ≥ 500 → a side is named
speed 6,000 > certainty 7,500?  no  → favours.certainty · concedes.speed
```

```text
metrics       tension_bp 5,100 · margin_bp 1,500 · leading_bp 7,500 · trailing_bp 6,000
reason_codes  concedes.speed · favours.certainty · tradeoff.speed_vs_certainty
```

5,100bp clears the threshold, so this axis is contested and its finding is `matched=True`. The lean
is toward waiting — *"the case for waiting leads by 1500"* — and what is conceded is 6,000bp of time
pressure, which is the sentence that makes the recommendation arguable rather than merely stated.

This is the only assertion in the test file where the second side wins. Everything else tests the
first side winning.

### 4.3 · A capability appointing a different speed authority

From `test_a_capability_may_appoint_different_units_for_an_axis` — *"Substituting an authority is
configuration, not a code change."*

```python
view = _view([_completed("sales.deadline", urgency_bp=7_000),
              _completed("core.confidence", confidence_bp=5_000)],
             config={"speed_source": "sales.deadline"})
observation, = SpeedVersusCertaintyPlugin().contribute(view)
assert observation.metrics["leading_bp"] == 7_000
```

```text
speed 7,000 (from sales.deadline) · doubt 10,000 − 5,000 = 5,000
margin  = 2,000
tension = 5000 × 8000 ÷ 10000 = 4,000
→ favours.speed · concedes.certainty
```

A domain pack that measures deadline pressure better than the generic temporal reasoner substitutes
itself with one config key. The metric *name* it must publish is still `urgency_bp` — that part is
hard-coded — so the substitution is "a different unit computing the same quantity", not "a different
quantity".

### 4.4 · The shipped situation, with the axis lit

`sales.deal_cooling_full` on the standard fixture, with the two dependencies added:

```text
core.temporal    urgency_bp     9,360
core.confidence  confidence_bp  6,950  →  doubt = 3,050

margin  = 6,310
tension = 3050 × 3690 ÷ 10000 = 11,254,500 ÷ 10,000 = 1125.45 → half-up → 1,125
→ favours.speed · concedes.certainty
```

`tension_bp 1,125`, below the 3,000bp threshold, so `matched=False` on the finding. The reading:
*ten days of silence on a £500k deal is urgent and we are reasonably well evidenced, so move — and
what we give up is 3,050bp of certainty we could have bought by waiting.* Not a hard call, but the
concession is stated.

### 4.5 · Edge cases

| `urgency_bp` | `confidence_bp` | doubt | margin | tension | Codes |
|---|---|---|---|---|---|
| absent | 9,000 | — | — | — | `()` — silent |
| 8,000 | absent | — | — | — | `()` — silent. **Never** read as 10,000 of doubt |
| 8,000 | source `FAILED` | — | — | — | `()` — failure is absence |
| 10,000 | 0 | 10,000 | 0 | **10,000** | `balanced.speed_vs_certainty` — maximum urgency against total ignorance. The hardest possible call, correctly unwinnable |
| 10,000 | 10,000 | 0 | 10,000 | 0 | `favours.speed` · `concedes.certainty` — maximum urgency, nothing left to learn. A free move |
| 0 | 10,000 | 0 | 0 | 0 | `balanced.speed_vs_certainty` — no time pressure and no doubt. Nothing is pulling either way, reported as "balanced" |
| 5,000 | 5,000 | 5,000 | 0 | 5,000 | `balanced.speed_vs_certainty` — an exact tie, contested at the default threshold |
| 5,000 | 9,700 | 300 | 4,700 | 159 | `favours.speed` · `concedes.certainty` |

Row 6 is the semantic oddity this axis shares with the other two: two sides that both measured zero
emit `balanced.<axis>`, whose plain reading is "evenly matched" applied to a situation where neither
pressure exists. Row 4 is the axis's extreme — total urgency against total ignorance is exactly the
case a human must be pulled into, and the unit scores it at the maximum without naming a winner.

---

## 5 · Test coverage

| Test | Pins |
|---|---|
| `test_no_axis_is_reported_when_nothing_ran_before_it` | `()` on an empty `prior` |
| `test_high_confidence_removes_the_case_for_waiting` | `trailing_bp == 1,000`, the inversion, `favours.speed`, `concedes.certainty` |
| `test_thin_evidence_pulls_against_a_deadline` | `leading_bp 7,500`, `tension_bp 5,100`, `favours.certainty` |
| `test_a_capability_may_appoint_different_units_for_an_axis` | `speed_source` substitution |
| `test_the_unit_never_republishes_a_reserved_shared_metric` | `confidence_bp` and `urgency_bp` are absent from `publishes`, and from the emitted metric set |
| `test_the_quiet_enterprise_renewal_leans_to_the_upside_and_says_what_it_gave_up` | This axis's codes survive to the result even when another axis is the headline |

Not pinned: `certainty_source` substitution, and the fact that the shipped manifest cannot reach this
plugin at all. Every test that drives it passes `core.temporal` and `core.confidence` directly into
`prior`, which the orchestrator would not do for the shipped spec.

---

## Related

| Document | Covers |
|---|---|
| [03-Analyzer.md](03-Analyzer.md) | `_weigh`, `_prior_bp`, the `_ABSENT` sentinel, which axes fire |
| [03b-plugin-risk_vs_reward.md](03b-plugin-risk_vs_reward.md) | The axis that does fire in production |
| [06-Builder-and-Metrics.md](06-Builder-and-Metrics.md) | The `publishes` guard that enforces the read-never-publish rule |
| [Part 3 · Decision Maker](../../../03-Decision-Maker/README.md) | `calculate_confidence` and why a second `confidence_bp` publisher would be catastrophic |
| [Part 2 · The Unit Framework](../../README.md) | §3.5 — the two publishers of `urgency_bp` and why the roster test misses one |
