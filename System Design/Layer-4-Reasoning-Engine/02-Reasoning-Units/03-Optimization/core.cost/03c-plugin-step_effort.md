# 03c · Plugin `step_effort`

**Class:** `genios_engine/reason/reasoners/cost_unit.py:StepEffortPlugin` (lines 111–134)
**Helper:** `cost_unit.py:_step_effort` (lines 73–81)
**`plugin_id`:** `step_effort` · **`kind`:** `cost.step_effort` · **runs third**
**Tests:** `test_effort_is_the_cheapest_route_the_roster_offers` ·
`test_effort_rate_is_tunable_per_capability` ·
`test_a_non_integer_effort_rate_is_a_deployment_fault`

---

## 1 · The claim it makes

*What the declared plays actually cost to carry out — re-derived from their steps, not read off
their declaration.*

From the helper docstring:

> *"Steps are the only honest unit of work a play carries: a three-step play is three things a human
> has to do, whatever number the author typed into `effort_bp` last quarter. Costing each declared
> step at a fixed configured rate keeps this arithmetic auditable — a reviewer can count the steps in
> the manifest and reproduce the number by hand."*

`PlayDefinition` already carries an `effort_bp` field. This plugin deliberately does not use it. The
two numbers are compared later, in `_effort_adjustments`, and the disagreement between them is what
the unit reports as a `CandidateAdjustment` — *"because a play whose declared effort drifted away
from its real steps will otherwise be scored on a number nobody has checked since it was written."*

**It reports the roster's floor.** From the class docstring:

> *"Acting means running one play, and the cheapest route is the least anyone could pay, so anything
> above it is real."*

The ceiling travels alongside it *"because a roster whose cheapest and dearest routes are far apart
is a roster where the choice of play matters to cost — a fact the Decision Maker should be able to
see rather than infer."*

---

## 2 · When it stays silent

```python
plays = _plays(view)
if not plays:
    return ()                       # nothing declared to do; no effort claim to make
```

**Never, through a legally constructed manifest.** `CapabilityManifest.__post_init__` raises
`capability requires at least one play`. The guard is unreachable defensive code, exactly as in
[03b](03b-plugin-reversibility_exposure.md) §2.

`PlayDefinition.__post_init__` raises `a play requires at least one step`, so `len(play.steps) ≥ 1`
and the minimum possible `effort_bp` is one step at the configured rate — **1,200bp on defaults, not
zero**. There is no legal input that makes this plugin report free work.

---

## 3 · The full arithmetic

```python
def _step_effort(view: UnitView, play: PlayDefinition) -> int:
    return clamp_bp(_config_bp(view, "step_effort_bp", 1_200) * len(play.steps))
```

```python
def contribute(self, view: UnitView) -> tuple[Observation, ...]:
    plays = _plays(view)
    if not plays:
        return ()
    estimates = tuple(_step_effort(view, play) for play in plays)
    return (Observation(
        plugin_id=self.plugin_id,
        kind="cost.step_effort",
        metrics={"effort_bp": min(estimates),
                 "effort_ceiling_bp": max(estimates),
                 "play_count": len(plays)},
        reason_codes=("effort_estimated_from_declared_steps",),
    ),)
```

```text
per play          effort  = clamp_bp( step_effort_bp × len(play.steps) )
roster floor      effort_bp         = MIN over plays
roster ceiling    effort_ceiling_bp = MAX over plays
                  play_count        = len(plays)
```

One multiplication and two reductions. No division, no rounding, nothing that could differ between
machines. `plays` is `_plays(view)`, which is `sorted(..., key=play_id)`, but the sort is irrelevant
to `min`/`max`/`len` — it matters only in `_effort_adjustments` and `_cost_benefit_checks`, which
iterate the same helper.

The plugin emits **no** `evidence_ids`. Its entire input is the manifest, and a manifest is not
evidence in the `EvidenceRef` sense — it is the authored action space, not an observation about the
world.

### 3.1 · The clamp, and where it binds

`clamp_bp` is `min(10_000, max(0, int(value)))`. On the default rate:

```text
9 steps × 1,200 = 10,800  →  clamped to 10,000
```

**Effort saturates at 9 steps.** A 9-step play and a 20-step play are the same number. Verified:

| Steps | `step_effort_bp × n` | `effort_bp` |
|---|---|---|
| 1 | 1,200 | 1,200 |
| 3 | 3,600 | 3,600 |
| 8 | 9,600 | 9,600 |
| 9 | 10,800 | **10,000** |
| 10 | 12,000 | 10,000 |
| 20 | 24,000 | 10,000 |

That is a genuine loss of resolution at the top of the range, and it is undocumented in the module.
It matters in exactly one place: `_effort_adjustments` computes `drift = _step_effort(...) − play.effort_bp`,
and a saturated estimate makes a 9-step play and a 20-step play produce the same correction. Since
the correction is capped at `±3,000bp` anyway, both would land on `+3,000` for any declared effort
below 7,000bp — so the saturation is invisible in practice on the shipped defaults, and would stop
being invisible the moment `step_effort_bp` were lowered.

### 3.2 · What a "step" is

`PlayDefinition.steps` is `tuple[str, ...]` — free-text instructions, validated only as non-empty
strings. Nothing constrains their granularity. The shipped `sales.deal_cooling_full` plays each
carry three steps, which is why all three price identically at 3,600bp and the floor equals the
ceiling.

This is the honest weakness in the claim *"steps are the only honest unit of work a play carries"*.
An author who writes one step reading *"draft, review, get approval, and send the message"* prices at
1,200bp; an author who writes those as four steps prices at 4,800bp. The unit is measuring the
author's prose style as much as the work. The counter-argument the code implicitly makes is that this
is still better than the alternative — a hand-typed `effort_bp` measures the author's *memory* of the
work, which drifts silently, whereas step count at least drifts visibly and in the same direction as
the work.

### 3.3 · Config keys

| Key | Default | Validated | Effect |
|---|---|---|---|
| `step_effort_bp` | `1_200` | `_config_bp` — int `0..10_000`, `bool` rejected | Cost per declared step |

One key. `_config_bp` is called **once per play per call site**, so a three-play roster reads it nine
times per evaluation (`step_effort`, `_effort_adjustments`, `_cost_benefit_checks`). All nine reads
hit the same frozen `spec.config` mapping and cannot disagree.

Two other keys govern what is *done* with this plugin's arithmetic but are read in the Evaluator, not
here: `effort_mismatch_tolerance_bp` (2,500) and `max_effort_adjustment_bp` (3,000).
[05](05-Evaluator.md) §3.2.

**`play_effort_bp` is not a key of this unit.** `packs/capabilities/deal_cooling_v2.py` configures
`core.cost` with `{"play_effort_bp": {"multithread_account": 600}}` and a comment explaining that
multithreading spends relationship capital. `cost_unit.py` contains no such string. The intent was a
per-play effort override; it was never implemented, and the config travels into every shipped run
doing nothing.

---

## 4 · Worked example 1 — a roster where the choice of play matters

`test_effort_is_the_cheapest_route_the_roster_offers`. Two plays, default rate:

```text
log_note      steps = ("Log a note",)                                   1 step
full_review   steps = ("Pull the history", "Draft a brief", "Book a call")   3 steps

log_note      effort = clamp_bp(1,200 × 1) = 1,200
full_review   effort = clamp_bp(1,200 × 3) = 3,600

effort_bp         = min(1,200, 3,600) = 1,200
effort_ceiling_bp = max(1,200, 3,600) = 3,600
play_count        = 2
```

```text
Observation(plugin_id='step_effort', kind='cost.step_effort',
            metrics={'effort_bp': 1200, 'effort_ceiling_bp': 3600, 'play_count': 2},
            evidence_ids=(), reason_codes=('effort_estimated_from_declared_steps',))
```

`1,200bp` means 0.12 and `3,600bp` means 0.36 — a 3× spread. The test's docstring states the choice
directly:

> *"Averaging would price a route nobody has to take, and the max would price effort that a cheaper
> alternative makes optional."*

Averaging would give 2,400bp, which is what neither play costs. The max would give 3,600bp, which
overprices a capability that offers a one-step route. The min is the only reduction that is true of
*something the Decision Maker can actually choose to do*.

Note what the ceiling is **not** used for: nothing downstream reads `effort_ceiling_bp`. It reaches
the result only inside the `cost.step_effort` finding, and no unit and no Layer 5 module reads it.
It is a diagnostic for a human reading the record.

## 5 · Worked example 2 — a heavier capability, tuned in Layer 3

`test_effort_rate_is_tunable_per_capability`. Same code, different business:

```text
spec.config = {"step_effort_bp": 2_000}
draft_reply   steps = ("Draft", "Send")                                 2 steps

effort            = clamp_bp(2,000 × 2)   = 4,000
effort_bp         = 4,000
effort_ceiling_bp = 4,000
play_count        = 1
```

> *"A capability whose steps are heavier says so in Layer 3 config, not in this unit's code."*

The same two-step play prices at 2,400bp on defaults and 4,000bp here. Nothing about the play changed;
the capability's judgement about what a step of its work costs did.

**And the shipped roster, where floor and ceiling coincide.** `sales.deal_cooling_full`:

```text
clarify_next_step     3 steps  → 3,600
multithread_account   3 steps  → 3,600
restore_momentum      3 steps  → 3,600

effort_bp         = 3,600
effort_ceiling_bp = 3,600
play_count        = 3
```

A roster where the choice of play is irrelevant to effort. `effort_ceiling_bp == effort_bp` is the
signal that says so, and it is the reason the ceiling is published at all.

---

## 6 · Edge cases

| Input | Behaviour |
|---|---|
| One play | `effort_bp == effort_ceiling_bp`; `play_count: 1` |
| A play with one step | 1,200bp on defaults — the minimum any play can cost |
| A play with zero steps | unreachable — `PlayDefinition.__post_init__` raises `a play requires at least one step` |
| Empty roster | `()` — unreachable, `CapabilityManifest` requires at least one play |
| 9 or more steps | `10,000bp`, saturated. §3.1 |
| `step_effort_bp: 0` | every play prices at 0; `effort_bp: 0`, `effort_ceiling_bp: 0`. Legal — `_config_bp` accepts 0 — and it turns `cost_bp` into `exposure × 4,000 ÷ 10,000`. Also makes every play with a declared `effort_bp ≥ 2,500` earn a `declared_effort_overstated` adjustment |
| `step_effort_bp: 10_000` | every play saturates at 10,000bp regardless of step count; the floor/ceiling distinction disappears |
| `step_effort_bp: "cheap"` | `ValueError: step_effort_bp must be integer basis points` — `test_a_non_integer_effort_rate_is_a_deployment_fault` |
| `step_effort_bp: True` | same `ValueError` — `bool` is rejected before the `int` check |
| `step_effort_bp: -5` or `10_001` | same `ValueError` |
| `play.effort_bp` set to anything | **ignored by this plugin.** Read only in `_effort_adjustments` |
| Two plays with identical step counts | floor equals ceiling; the roster offers no cheaper route |

The `ValueError` rows deserve one more sentence. The raise propagates out of `contribute`, out of
`analyze`, out of `evaluate`, and `orchestrator.py:_evaluate` converts it to
`ResultStatus.FAILED` with `reason_codes=('reasoner_failure',)`. Because the shipped spec is
`FailurePolicy.OPTIONAL`, the run continues and produces advice without a cost ledger, recorded only
as a degradation string. Loud at the unit; quiet at the deployment.
[01](01-Input-and-Validator.md) §4.3.

---

## Related

| File | Covers |
|---|---|
| [03 · Analyzer](03-Analyzer.md) | Execution order, and why `_step_effort` runs three times per play |
| [03b · `reversibility_exposure`](03b-plugin-reversibility_exposure.md) | The mirror asymmetry — the roster's ceiling rather than its floor |
| [04 · Calculator](04-Calculator.md) §3.2 | Why the floor is blended with the ceiling of a different quantity |
| [05 · Evaluator](05-Evaluator.md) §3.2 | `_effort_adjustments` — where `_step_effort` is compared against `play.effort_bp` |
| [README](README.md) §5 | Every config key with its default |
