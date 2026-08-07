# Plugin · `cost_vs_benefit`

**Class:** `tradeoff_unit.py:CostVersusBenefitPlugin` (lines 155–175)
**`plugin_id`:** `cost_vs_benefit`
**Runs:** first of three — `analyze` sorts by `plugin_id` and this sorts first alphabetically
**Status in production:** **dark.** Its default cost authority does not exist. See §3.

---

## 1 · The claim it makes

> *Is the prize worth the work?*

```python
class CostVersusBenefitPlugin:
    """Is the prize worth the work?

    Effort is the one cost that never appears on an invoice and is therefore the one most often
    ignored. A modest benefit that consumes a week of a senior person is a worse call than a
    smaller benefit that costs an hour, and a system that only ever reported benefit would keep
    recommending the first.

    Both sides come from whichever units a capability appoints; where neither has been deployed the
    plugin stays silent rather than treating unmeasured effort as free.
    """
```

The argument is about the cost nobody invoices. `core.impact` measures what a situation is worth;
nothing in the ranking math holds that against what it takes to act. This plugin does — and its
output is a *reading*, not an adjustment. It says "the benefit outweighs the effort by 4,000bp and
here is the effort we accepted"; it does not deduct anything from a candidate's utility.

Side names: **`benefit`** and **`restraint`**. The second is the interesting choice. The plugin does
not call the cost side "cost" or "effort" — a lean toward the cost side is a lean toward *not doing
the thing*, and `favours.restraint` says that where `favours.cost` would read as nonsense.

---

## 2 · What exists

```python
plugin_id = "cost_vs_benefit"

def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    benefit = _prior_bp(view, "benefit_source", "core.impact", "impact_bp")
    cost = _prior_bp(view, "cost_source", "core.effort", "effort_bp")
    if benefit is None or cost is None:
        return ()
    return _weigh(view, self.plugin_id, "cost_vs_benefit",
                  "benefit", benefit, "restraint", cost)
```

### Config keys

| Key | Default | Type | Validated by | Meaning |
|---|---|---|---|---|
| `benefit_source` | `"core.impact"` | non-empty string | `_config_id` | Which unit publishes `impact_bp` |
| `cost_source` | `"core.effort"` | non-empty string | `_config_id` | Which unit publishes `effort_bp`. **No such unit exists** |
| `decisive_margin_bp` | `500` | int 0–10,000 | `_config_bp`, inside `_weigh` | Below this margin no side is named |

The metric *names* are hard-coded. A capability can point `benefit_source` at any unit it likes, but
that unit must publish a metric called exactly `impact_bp`; likewise `effort_bp` for the cost side.
Both keys are validated only when the plugin reaches them, so a malformed `cost_source` on a
capability whose benefit side never publishes will never raise.

### The observation it emits

| Metric | Value |
|---|---|
| `tension_bp` | `min(benefit, cost) × (10,000 − margin) ÷ 10,000`, half-up |
| `margin_bp` | `abs(benefit − cost)` |
| `leading_bp` | `max(benefit, cost)` |
| `trailing_bp` | `min(benefit, cost)` |

| Reason code | Condition |
|---|---|
| `tradeoff.cost_vs_benefit` | always |
| `balanced.cost_vs_benefit` | `margin_bp < decisive_margin_bp` |
| `favours.benefit` + `concedes.restraint` | `benefit > cost` and margin at or above the deadband |
| `favours.restraint` + `concedes.benefit` | `cost >= benefit` and margin at or above the deadband |

`kind` is `"tradeoff.cost_vs_benefit"`.

---

## 3 · When it stays silent — and why it always does

```python
if benefit is None or cost is None:
    return ()
```

`_prior_bp` returns `None` in three situations, all of them meaning *that authority has no opinion*:

| Situation | `prior_metric` returns | `_prior_bp` returns |
|---|---|---|
| The source unit is not in `view.prior` — not declared as a dependency, or never scheduled | `-1` (the default) | `None` |
| The source unit is in `view.prior` but its status is not `COMPLETED` | `-1` | `None` |
| The source unit completed but published no metric of that name | `-1` | `None` |

The docstring's own framing: *"where neither has been deployed the plugin stays silent rather than
treating unmeasured effort as free."* That is the right instinct. Reading an absent effort authority
as `effort_bp: 0` would make every action look free, and a system that believes action is free
recommends action constantly.

`test_unmeasured_effort_is_never_treated_as_free` pins it with `core.impact` present and no cost
authority at all:

```python
view = _view([_completed("core.impact", impact_bp=7_000)])
assert CostVersusBenefitPlugin().contribute(view) == ()
```

### 3.1 · `core.effort` is not a unit

This is the gap that matters. Grep the roster:

```text
unit_id = "core.context"       unit_id = "core.risk"          unit_id = "core.tradeoff"
unit_id = "core.timeline"      unit_id = "core.opportunity"   unit_id = "core.resource"
unit_id = "core.dependency"    unit_id = "core.impact"        unit_id = "core.scheduling"
unit_id = CONSTRAINT_UNIT_ID   unit_id = "core.priority"      unit_id = "core.cost"
                               unit_id = "core.confidence"    unit_id = "core.policy"
unit_id = "core.alternative"   unit_id = "core.validation"    unit_id = "core.recommendation"
```

Seventeen ids. None is `core.effort`. The metric `effort_bp` is published by **`core.cost`**:

```python
# cost_unit.py:219
publishes = ("cost_bp", "effort_bp", "exposure_bp", "delay_cost_bp",
             "do_nothing_cost_bp", "cost_benefit_gap_bp")
```

So the axis is silent under default configuration in every capability that runs the unit. The
plugin's silence rule is behaving correctly — it genuinely cannot find a cost authority — but the
cause is a **name**, not a missing deployment. The authority exists and the manifest already
declares it as a dependency.

The fix is one config key, no code change:

```python
_spec("core.tradeoff",
      ("core.risk", "core.opportunity", "core.impact", "core.cost"),
      config={"cost_source": "core.cost"})
```

Verified on the shipped `sales.deal_cooling_full` fixture: adding that key alone takes `axis_count`
from 1 to 2 and adds `favours.benefit` / `concedes.restraint` to the result's reason codes.

Whether `core.cost`'s `effort_bp` is the *right* number for this axis is a separate question worth
asking before the change is made. `cost_unit.py:StepEffortPlugin` costs each play at
`clamp_bp(step_effort_bp × len(play.steps))` — `step_effort_bp` defaults to 1,200 — and then
publishes `min(estimates)` across the capability's plays: *"the roster's cheapest route as the floor
of acting"*. So `effort_bp` is the cost of the **cheapest** play on offer, not of the play that will
be selected, and a one-step play reports 1,200bp regardless of how hard that step is. Feeding a
cheapest-route floor into a unit-level axis is a shape mismatch nobody has had to confront yet,
because the axis has never fired.

---

## 4 · Worked examples

### 4.1 · Heavy effort against a modest benefit

From `test_heavy_effort_against_modest_benefit_concedes_the_benefit`.

```text
benefit_source  core.impact   impact_bp   3,000
cost_source     core.effort   effort_bp   8,000

margin  = |3000 − 8000| = 5,000
tension = min(3000, 8000) × (10000 − 5000) ÷ 10000
        = 3000 × 5000 ÷ 10000
        = 15,000,000 ÷ 10,000
        = 1,500

margin 5,000 ≥ decisive_margin_bp 500 → a side is named
benefit 3,000 > cost 8,000?  no  → the else branch
```

```text
Observation
    plugin_id     cost_vs_benefit
    kind          tradeoff.cost_vs_benefit
    metrics       tension_bp 1,500 · margin_bp 5,000 · leading_bp 8,000 · trailing_bp 3,000
    reason_codes  concedes.benefit · favours.restraint · tradeoff.cost_vs_benefit
```

Read out loud: *the work outweighs the prize by 5,000bp, and what we are giving up by not acting is
3,000bp of benefit.* At the default threshold of 3,000bp this axis is **not contested** — 1,500 is
below it — so the finding it produces will carry `matched=False`. The call was easy; the concession
is on the record anyway.

### 4.2 · The shipped situation, with the axis lit

`sales.deal_cooling_full` on the standard fixture, with `cost_source: "core.cost"` added.

```text
core.impact  impact_bp  10,000     (a £500k deal — revenue_exposure_bp is at maximum)
core.cost    effort_bp   3,600     (cheapest declared play: 3 steps × step_effort_bp 1,200)

margin  = |10000 − 3600| = 6,400
tension = 3600 × (10000 − 6400) ÷ 10000
        = 3600 × 3600 ÷ 10000
        = 12,960,000 ÷ 10,000
        = 1,296

margin 6,400 ≥ 500 → a side is named
benefit 10,000 > cost 3,600 → favours.benefit · concedes.restraint
```

```text
finding tradeoff.cost_vs_benefit  matched=False
    tension_bp 1,296 · margin_bp 6,400 · leading_bp 10,000 · trailing_bp 3,600
    concedes.restraint · favours.benefit · tradeoff.cost_vs_benefit
```

A settled question: a maximal-value deal against three steps of work is not a dilemma. The axis
still earns its place in the explanation — it is the sentence *"and we are spending 3,600bp of
effort to do it"*, which nothing else in the run says.

### 4.3 · A genuinely contested cost

The shape this axis exists to catch, which no shipped situation has yet produced:

```text
impact_bp 6,000 · effort_bp 5,800

margin  = 200
tension = 5800 × (10000 − 200) ÷ 10000 = 5800 × 9800 ÷ 10000 = 56,840,000 ÷ 10,000 = 5,684

margin 200 < 500 → balanced, no side named
```

```text
metrics       tension_bp 5,684 · margin_bp 200 · leading_bp 6,000 · trailing_bp 5,800
reason_codes  balanced.cost_vs_benefit · tradeoff.cost_vs_benefit
```

5,684bp clears the 3,000bp threshold comfortably, so this axis is contested and its finding is
`matched=True` — while naming no winner. *This is hard and nobody can tell you which way it goes* is
a legitimate and useful thing for a reasoning system to say.

### 4.4 · Edge cases

| `impact_bp` | `effort_bp` | margin | tension | Codes | Note |
|---|---|---|---|---|---|
| absent | 8,000 | — | — | — | `()` — silent. One side is a blind spot |
| 7,000 | absent | — | — | — | `()` — silent. The production default, because `core.effort` does not exist |
| 7,000 | source `FAILED` | — | — | — | `()` — a crashed unit has no opinion, not zero effort |
| 0 | 0 | 0 | 0 | `balanced.cost_vs_benefit` | Both measured zero. `tension_bp 0` is the only thing distinguishing this from a real tie |
| 9,000 | 200 | 8,800 | **24** | `favours.benefit` · `concedes.restraint` | Near-free action on a strong benefit. The weaker side sets the ceiling, so tension collapses to almost nothing |
| 10,000 | 10,000 | 0 | **10,000** | `balanced.cost_vs_benefit` | Maximum benefit against maximum effort. The hardest possible call, and correctly unwinnable |
| 4,000 | 4,000 | 0 | 4,000 | `balanced.cost_vs_benefit` | Exact tie. With `decisive_margin_bp: 0` this instead emits `favours.restraint` / `concedes.benefit` — see [03-Analyzer.md](03-Analyzer.md) §4 |

---

## 5 · Test coverage

| Test | Pins |
|---|---|
| `test_no_axis_is_reported_when_nothing_ran_before_it` | `()` when no prior unit ran |
| `test_unmeasured_effort_is_never_treated_as_free` | `()` when only the benefit side published |
| `test_heavy_effort_against_modest_benefit_concedes_the_benefit` | `favours.restraint` and `concedes.benefit` on 3,000 against 8,000 |
| `test_a_perfect_tie_between_axes_is_broken_by_name_not_by_order` | This plugin wins a cross-axis tie on `plugin_id` alone |
| `test_the_headline_is_the_sharpest_axis_not_the_first_plugin` | This plugin sorting first must **not** make it the headline |

Not pinned: the tension arithmetic on this axis specifically (only the codes are asserted), the
`balanced` path, and — most consequentially — the fact that `cost_source` names a non-existent unit.
A test that instantiated the whole roster and asserted every default source id resolves to a real
`unit_id` would have caught it on the day the plugin was written.

---

## Related

| Document | Covers |
|---|---|
| [03-Analyzer.md](03-Analyzer.md) | `_weigh`, `_prior_bp`, the deadband, and which axes fire in production |
| [03b-plugin-risk_vs_reward.md](03b-plugin-risk_vs_reward.md) | The only axis that fires today |
| [04-Calculator.md](04-Calculator.md) | How this axis competes with the other two for the headline |
| [Category 3 · Optimization](../README.md) | §3.4 — the same `core.effort` finding at category level, and `core.cost`'s own effort derivation |
