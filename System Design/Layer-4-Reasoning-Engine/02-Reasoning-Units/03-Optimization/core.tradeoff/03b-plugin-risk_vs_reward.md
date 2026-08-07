# Plugin · `risk_vs_reward`

**Class:** `tradeoff_unit.py:RiskVersusRewardPlugin` (lines 135–152)
**`plugin_id`:** `risk_vs_reward`
**Runs:** second of three, in `plugin_id` order
**Status in production:** **live.** The only axis that fires in the shipped `sales.deal_cooling_full`

---

## 1 · The claim it makes

> *Chase the upside, or protect the downside?*

```python
class RiskVersusRewardPlugin:
    """Chase the upside, or protect the downside?

    Both sides already exist as audited units, and until now they were only ever summed into a
    score. Holding them apart is what lets an explanation say "the upside is worth more than the
    exposure, and here is the exposure we accepted" — which is the sentence an executive needs and
    a weighted average destroys.
    """
```

That docstring is the clearest statement in the module of why the whole unit exists. `core.risk`
publishes `risk_bp` and `core.opportunity` publishes `opportunity_bp`, and Part 3's ranking math
folds both into a single utility. The fold is correct for *choosing*; it is useless for *explaining*,
because once 8,500 of upside and 5,000 of exposure have become one number nobody can recover the
sentence "we accepted 5,000bp of exposure to chase it." This plugin recovers exactly that sentence
and nothing else.

Side names: **`reward`** and **`caution`**. As with `restraint` on the cost axis, the losing side is
named for the *posture* rather than the metric — leaning to the risk side means leaning to caution,
and `favours.risk` would read as a recommendation to be reckless.

---

## 2 · What exists

```python
plugin_id = "risk_vs_reward"

def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    reward = _prior_bp(view, "reward_source", "core.opportunity", "opportunity_bp")
    risk = _prior_bp(view, "risk_source", "core.risk", "risk_bp")
    if reward is None or risk is None:
        return ()
    return _weigh(view, self.plugin_id, "risk_vs_reward",
                  "reward", reward, "caution", risk)
```

### Config keys

| Key | Default | Type | Validated by | Meaning |
|---|---|---|---|---|
| `reward_source` | `"core.opportunity"` | non-empty string | `_config_id` | Which unit publishes `opportunity_bp` |
| `risk_source` | `"core.risk"` | non-empty string | `_config_id` | Which unit publishes `risk_bp` |
| `decisive_margin_bp` | `500` | int 0–10,000 | `_config_bp`, inside `_weigh` | Below this margin no side is named |

Both defaults resolve to real units that are declared as dependencies in the shipped manifest. That
is why this is the one axis that works out of the box.

`_config_id` rejects anything that is not a non-empty string. Verified:

```text
config {"risk_source": "  "}  → ValueError: risk_source must name a reasoning unit
config {"risk_source": 7}     → ValueError: risk_source must name a reasoning unit
```

It does **not** check that the string names a unit that exists — which is the hole
[`cost_vs_benefit`](03a-plugin-cost_vs_benefit.md) fell into. A source id pointing at nothing is
indistinguishable, at this layer, from a unit that did not complete.

### The observation it emits

| Metric | Value |
|---|---|
| `tension_bp` | `min(reward, risk) × (10,000 − margin) ÷ 10,000`, half-up |
| `margin_bp` | `abs(reward − risk)` |
| `leading_bp` | `max(reward, risk)` |
| `trailing_bp` | `min(reward, risk)` |

| Reason code | Condition |
|---|---|
| `tradeoff.risk_vs_reward` | always |
| `balanced.risk_vs_reward` | `margin_bp < decisive_margin_bp` |
| `favours.reward` + `concedes.caution` | `reward > risk` and margin at or above the deadband |
| `favours.caution` + `concedes.reward` | `risk >= reward` and margin at or above the deadband |

---

## 3 · When it stays silent

```python
if reward is None or risk is None:
    return ()
```

Three tests pin the three ways a side can be absent, and each carries the fabrication it prevents:

| Test | Input | Why silence is right |
|---|---|---|
| `test_no_axis_is_reported_when_nothing_ran_before_it` | empty `prior` | *"Scheduled first by mistake, the unit must say nothing rather than invent a dilemma."* |
| `test_one_published_side_is_a_blind_spot_not_a_landslide` | `risk_bp 8,000`, no opportunity | *"Risk without opportunity would read as 'all downside' — the exact fabrication L4 forbids."* |
| `test_a_unit_that_failed_is_treated_as_absent_not_as_zero` | `risk_bp 8,000`, `core.opportunity` `FAILED` | *"A crashed opportunity unit has no opinion; reading it as 'no upside' inverts the call."* |

The third is the sharpest. `UnitView.prior_metric` returns the caller's default when the dependency
did not complete, so a `FAILED` unit and an absent unit are the same thing to `_prior_bp`. Both map
to `None`, both produce silence. If the sentinel were `0` instead of `-1`, a crashed opportunity unit
would turn an 8,000bp risk into `favours.caution` at maximum margin — an inverted call presented with
full confidence.

And the counter-case, `test_a_measured_zero_still_produces_an_axis`:

```python
view = _view([_completed("core.opportunity", opportunity_bp=9_000),
              _completed("core.risk", risk_bp=0)])
observation, = RiskVersusRewardPlugin().contribute(view)
assert observation.metrics["tension_bp"] == 0        # a free move, not an agonising one
assert "favours.reward" in _codes(observation)
```

> *Zero risk is a finding; the absence of a tradeoff is itself worth reporting.*

Both sides spoke. One of them said zero. That is a measurement, and it produces a real axis with
`tension_bp: 0` — the unit's way of saying *this is a free move.*

---

## 4 · Worked examples

### 4.1 · The shipped run — a £500k deal gone quiet

`sales.deal_cooling_full` on the standard fixture. This is the only tradeoff arithmetic that runs in
production today.

```text
reward_source  core.opportunity  opportunity_bp  7,000
risk_source    core.risk         risk_bp         5,934

margin  = |7000 − 5934| = 1,066
tension = min(7000, 5934) × (10000 − 1066) ÷ 10000
        = 5934 × 8934 ÷ 10000
        = 53,014,356 ÷ 10,000
        = 5301.4356  → half-up → 5,301

margin 1,066 ≥ decisive_margin_bp 500 → a side is named
reward 7,000 > risk 5,934 → favours.reward · concedes.caution

tension 5,301 ≥ tension_threshold_bp 3,000 → contested
```

```text
result core.tradeoff  COMPLETED  matched=True
    tension_bp 5,301 · margin_bp 1,066 · axis_count 1 · contested_count 1
    reason_codes  concedes.caution · favours.reward
                  headline.concedes.caution · headline.favours.reward
                  tradeoff.risk_vs_reward · tradeoff_contested
    finding tradeoff.risk_vs_reward  matched=True
        tension_bp 5,301 · margin_bp 1,066 · leading_bp 7,000 · trailing_bp 5,934
```

In English: *there is a real argument here. The upside leads by about eleven points on a hundred, so
we lean to acting — and the 5,934bp of exposure is what we are accepting to do it.* That last clause
is the thing no other unit in the run produces.

### 4.2 · The hardest call in the system

From `test_two_strong_and_close_pressures_are_the_hardest_call` — *"8000 upside against 7900 exposure
is the situation a human is actually needed for."*

```text
opportunity_bp 8,000 · risk_bp 7,900

margin  = 100
tension = 7900 × (10000 − 100) ÷ 10000
        = 7900 × 9900 ÷ 10000
        = 78,210,000 ÷ 10,000
        = 7,821

margin 100 < 500 → balanced, no side named
tension 7,821 ≥ 3,000 → contested
```

```text
metrics       tension_bp 7,821 · margin_bp 100 · leading_bp 8,000 · trailing_bp 7,900
reason_codes  balanced.risk_vs_reward · tradeoff.risk_vs_reward
```

The highest tension in the whole test suite, and the unit names no winner. That combination —
`matched=True` on the finding, `balanced.*` on the codes — is the correct output for a genuine
dilemma, and it is the shape a renderer must be able to handle: *this is hard, and the evidence does
not settle it.*

### 4.3 · A large number that settles nothing

From `test_a_wide_gap_is_a_settled_question_however_large_the_numbers`:

```text
opportunity_bp 9,500 · risk_bp 1,000

margin  = 8,500
tension = 1000 × 1500 ÷ 10000 = 1,500,000 ÷ 10,000 = 150
```

9,500bp of opportunity — near the maximum the system can report — produces 150bp of tension, because
the weaker side sets the ceiling and the gap discounts what is left. That is the formula's central
claim working: *a four-thousand-point gap has already been settled by the evidence, whatever its
absolute level.*

### 4.4 · A capability demanding a wider margin

From `test_a_capability_can_demand_a_wider_margin_before_a_side_is_named` — *"A regulated capability
may want a decisive gap before claiming one objective beat another."*

```text
opportunity_bp 6,600 · risk_bp 6,000 · margin 600 · tension = 6000 × 9400 ÷ 10000 = 5,640

decisive_margin_bp 500  (default)  → 600 ≥ 500 → favours.reward · concedes.caution
decisive_margin_bp 2,000           → 600 <  2000 → balanced.risk_vs_reward
```

Same evidence, same tension, same margin. Only the tenant's tolerance for calling a winner changed —
and the numbers are identical either way, so nothing downstream that reads metrics is affected. Only
the explanation moves. That is the correct blast radius for a knob of this kind.

### 4.5 · Edge cases

| `opportunity_bp` | `risk_bp` | margin | tension | Codes | Note |
|---|---|---|---|---|---|
| absent | 8,000 | — | — | — | `()` — silent |
| 9,000 | source `FAILED` | — | — | — | `()` — failure is absence |
| 9,000 | 0 | 9,000 | **0** | `favours.reward` · `concedes.caution` | Measured zero risk. A free move, and it says so |
| 0 | 0 | 0 | 0 | `balanced.risk_vs_reward` | Both measured nothing. `tension_bp 0` is the only disambiguator |
| 6,100 | 6,000 | 100 | 5,940 | `balanced.risk_vs_reward` | *"One basis point must not decide which objective won"* |
| 6,500 | 6,000 | 500 | 5,700 | `favours.reward` · `concedes.caution` | The deadband boundary — exactly 500 names a side |
| 6,499 | 6,000 | 499 | 5,701 | `balanced.risk_vs_reward` | One point below, no winner. Note the tension is *higher* |
| 3,000 | 3,000 | 0 | 3,000 | `balanced.risk_vs_reward` | The lowest equal pair that still clears the default contested threshold |
| 10,000 | 10,000 | 0 | **10,000** | `balanced.risk_vs_reward` | Maximum tension. Both clamps in `_weigh` are exercised here and neither binds |

Rows 6 and 7 together are the deadband's honest cost: a one-basis-point change in the input flips the
explanation between "the upside wins" and "too close to call", while the tension moves by one point
in the *opposite* direction. Any deadband has a cliff somewhere. This one is placed where the
docstring argues it should be — at the width of "rounding noise" — and 500bp is an unfitted guess for
that width.

---

## 5 · Test coverage

This is the best-covered plugin in the unit. Eight of the file's twenty-four tests drive it directly.

| Test | Pins |
|---|---|
| `test_no_axis_is_reported_when_nothing_ran_before_it` | `()` on an empty `prior` |
| `test_one_published_side_is_a_blind_spot_not_a_landslide` | `()` when only risk published |
| `test_a_unit_that_failed_is_treated_as_absent_not_as_zero` | `FAILED` is absence, not zero |
| `test_a_measured_zero_still_produces_an_axis` | `tension_bp 0` and `favours.reward` on zero risk |
| `test_two_strong_and_close_pressures_are_the_hardest_call` | `tension_bp 7,821`, `margin_bp 100` |
| `test_a_wide_gap_is_a_settled_question_however_large_the_numbers` | `tension_bp 150` |
| `test_an_immaterial_lean_names_no_winner` | `balanced.*` and the absence of both `favours.` and `concedes.` |
| `test_a_capability_can_demand_a_wider_margin_before_a_side_is_named` | `decisive_margin_bp` overriding the deadband |
| `test_a_malformed_margin_setting_is_a_manifest_fault` | `ValueError` on `decisive_margin_bp: 25_000` |

Not pinned: `reward_source` / `risk_source` substitution (only `speed_source` is tested for that),
and the `favours.caution` direction — every named-lean assertion in the file happens to test the
reward side winning.

---

## Related

| Document | Covers |
|---|---|
| [03-Analyzer.md](03-Analyzer.md) | `_weigh`, `_prior_bp`, the `_ABSENT` sentinel, the deadband |
| [03a-plugin-cost_vs_benefit.md](03a-plugin-cost_vs_benefit.md) | The axis whose default source id names nothing |
| [04-Calculator.md](04-Calculator.md) | Why this axis is usually the headline, and what happens when it is not |
| [`core.opportunity`](../../02-Business-Evaluation/core.opportunity/README.md) | Where `opportunity_bp` comes from |
