# 04 · Calculator

**Stage 5 of eight.** `risk.py:RiskUnit.calculate` — **abstract in the base class, implemented here.**

---

## 1 · What it is for

Turn three observations into one number: **a floor plus the weighted blend of the two exposures.**
Five lines, pure integer arithmetic, no branches.

---

## 2 · What exists

```python
# risk.py:RiskUnit.calculate
def calculate(self, view: UnitView,
              observations: Sequence[Observation]) -> Mapping[str, int]:
    """A floor plus the weighted blend of the two exposures.

        risk_bp = clamp(base + round_half_up((drop*60 + relationship*40) / 100))

    The division happens once, over the summed numerator, rather than per term: rounding each
    contribution separately would let two 50bp halves round to 100bp of risk that neither
    signal actually reported.
    """
    drop = _observed(observations, MOMENTUM_PLUGIN, "drop_bp")
    relationship_risk = _observed(observations, RELATIONSHIP_PLUGIN, "relationship_risk_bp")
    base = basis_points(view.config.get("base_risk_bp", 1_000), "base_risk_bp")
    return {"risk_bp": clamp_bp(base + divide_half_up(
        drop * MOMENTUM_WEIGHT + relationship_risk * RELATIONSHIP_WEIGHT, WEIGHT_BASIS))}
```

| Symbol | Source | Range |
|---|---|---|
| `drop` | observation `momentum_decay`, metric `drop_bp` | 0–10,000 |
| `relationship_risk` | observation `relationship_health`, metric `relationship_risk_bp` | 0–10,000 |
| `base` | `config["base_risk_bp"]`, default `1_000` | 0–10,000, validated |
| `MOMENTUM_WEIGHT` | module constant | `60` |
| `RELATIONSHIP_WEIGHT` | module constant | `40` |
| `WEIGHT_BASIS` | module constant | `100` |

The `risk_mitigation` observation is present in `observations` and is deliberately **not read**.
Mitigation is what a play would change; `risk_bp` is what is true before anyone acts.

### 2.1 · The helpers

```python
# common.py
def clamp_bp(value: int) -> int:
    return min(10_000, max(0, int(value)))

def divide_half_up(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    if numerator >= 0:
        return (numerator + denominator // 2) // denominator
    return -((-numerator + denominator // 2) // denominator)
```

Both are integer-only. No `float`, no `round()`, no `Decimal` in the hot path — because `round()` in
Python is banker's rounding (`round(2.5) == 2`) and a float would make the decision hash
machine-dependent, which `platform/canonical.py` rejects outright at the semantic boundary anyway.

---

## 3 · Why this shape

The code's docstring and the module header argue four separate decisions. Mining them rather than
inventing a new rationale:

### 3.1 · Why the division happens once

> *The division happens once, over the summed numerator, rather than per term: rounding each
> contribution separately would let two 50bp halves round to 100bp of risk that neither signal
> actually reported.*

The pinned demonstration, `test_rounding_is_half_up_on_the_summed_numerator_not_per_term`:

```text
drop_bp = 1, relationship_risk_bp = 2

as written:   (1×60 + 2×40) / 100 = 140/100 = 1.4  → 1     → risk_bp = 1,001
per term:     round(60/100) + round(80/100) = 1 + 1 = 2     → risk_bp = 1,002
```

One basis point, on a scale of ten thousand. It matters because the difference is not noise — it is
a *systematic* upward bias. Every run would round both terms independently, and the error would
always point the same way.

### 3.2 · Why 60/40, and why it is not configurable

> *Decay leads because a deal that has stopped moving is the nearer loss; thin coverage is the
> slower one. Named rather than inlined so the weighting is reviewable, but **not** configurable —
> moving these would re-score every shipped decision.*

The distinction from `base_risk_bp` is the interesting part. The floor *is* config, because *"the
capability author sets how much of that irreducible exposure to carry"* — a per-domain judgement. The
weights are not, because they encode the engine's model of what risk *is*, and a capability that
could re-weight them would be authoring a different risk model under the same unit id and the same
version string.

**Neither number has ever been fitted to data.** The 60/40 blend and the 1,000bp floor were
inherited from the pre-framework implementation, which inherited whatever justification the system
before it had — which was also not an empirical one. This is recorded honestly in
[Category 2 §3.8](../README.md).

### 3.3 · Why the floor exists

> *The `base_risk_bp` floor exists because a deal that looks perfect is still a deal that can be
> lost; the capability author sets how much of that irreducible exposure to carry.*

`test_a_quiet_situation_still_carries_the_authored_floor` pins all three cases in one test:

```python
assert _run(config={"base_risk_bp": 4_200}).metrics["risk_bp"] == 4_200
assert _run().metrics["risk_bp"]                                == 1_000
assert _run(config={"base_risk_bp": 0}).metrics["risk_bp"]      == 0
```

An authored `0` is a real choice, not an absent value: a capability may say the do-nothing branch
costs nothing when nothing is measurably wrong.

### 3.4 · Why it clamps rather than normalises

`base + weighted` can reach `10,000 + 10,000 = 20,000`. The unit clamps instead of rescaling,
because rescaling would make the meaning of a given `risk_bp` depend on the configured floor: 5,000bp
would mean one thing under `base_risk_bp = 0` and another under `base_risk_bp = 4,200`. Clamping
keeps `risk_bp` on one absolute scale at the cost of a ceiling effect at the top. See §5.3.

---

## 4 · Two properties of this arithmetic that are worth writing down

### 4.1 · The half-up tie-break is unreachable

`divide_half_up` exists to break ties upward, but with weights 60 and 40 the numerator
`60·drop + 40·rel` is **always a multiple of 20** — `gcd(60, 40) = 20`. So `numerator / 100` can
only ever have a fractional part in `{0.0, 0.2, 0.4, 0.6, 0.8}`. It is never exactly `0.5`, and the
tie-break branch never fires.

What `divide_half_up` *does* buy over plain floor division is the `0.6` and `0.8` cases:

| numerator | `/100` | `divide_half_up` | `//100` |
|---|---|---|---|
| 626,680 | 6,266.8 | **6,267** | 6,266 |
| 266,680 | 2,666.8 | **2,667** | 2,666 |
| 140 | 1.4 | 1 | 1 |
| 220 | 2.2 | 2 | 2 |

So the helper is doing real work — it just is not doing the specific work its name advertises. This
matters if anyone ever changes the weights: `55/45` would make the numerator a multiple of 5 and put
`.5` back in reach, at which point the tie-break stops being decorative.

### 4.2 · The negative branch is unreachable too

`divide_half_up` handles a negative numerator. It cannot receive one here: both inputs are
`_bp`-suffixed metrics validated to `0..10_000` by `contracts/reasoning.py:_bp` when the upstream
result was constructed, and both weights are positive. `clamp_bp`'s `max(0, ...)` lower bound is
likewise dead for the same reason unless `base` is `0` and the weighted term is `0`, in which case
it returns `0` without clamping anything.

---

## 5 · Worked examples

### 5.1 · The full shipped combination

`sales.deal_cooling`, a deal with engagement 0.40, one verified stakeholder out of a target of
three, and the authored floor.

```text
inputs
  drop_bp              = 10,000 − 4,000        = 6,000        (core.temporal)
  relationship_risk_bp = 10,000 − 3,333        = 6,667        (core.relationship, 1 of 3)
  base_risk_bp         = 1,000                                (config)

step 1 — weight, without dividing
  6,000 × 60                                   =   360,000
  6,667 × 40                                   = + 266,680
                                                 ---------
  numerator                                    =   626,680

step 2 — one division, half up
  (626,680 + 100 // 2) // 100
  = (626,680 + 50) // 100
  = 626,730 // 100
  = 6,267                                                     (exact value 6,266.8)

step 3 — floor and clamp
  1,000 + 6,267                                = 7,267
  clamp_bp(7,267)                              = 7,267

result
  {"risk_bp": 7267}        →  0.7267 of the scale
```

Read as a sentence: **1,000bp of irreducible exposure, 3,600bp because the conversation has cooled,
2,667bp because one person holds the account.**

### 5.2 · The two-term isolation cases

| Case | `drop_bp` | `rel_risk_bp` | numerator | weighted | `risk_bp` |
|---|---|---|---|---|---|
| `temporal_only` | 6,200 | 0 | 372,000 | 3,720 | **4,720** |
| `relationship_only` | 0 | 7,500 | 300,000 | 3,000 | **4,000** |
| `both_dependencies` | 6,200 | 7,500 | 672,000 | 6,720 | **7,720** |

The third row is `test_the_blend_is_sixty_forty_over_the_authored_floor`, and its docstring states
the arithmetic verbatim: *"1000 + round((6200\*60 + 7500\*40)/100) = 1000 + round(6720) = 7720."*
Note that 6,720 = 3,720 + 3,000 exactly — the terms are additive here because neither rounded.

### 5.3 · The clamp

`test_risk_saturates_rather_than_overflowing_the_scale`:

```text
drop_bp = 10,000, relationship_risk_bp = 10,000, base_risk_bp = 9,000

numerator = 600,000 + 400,000 = 1,000,000
weighted  = 10,000
9,000 + 10,000 = 19,000
clamp_bp(19,000) = **10,000**
```

The clamp is reachable with the *shipped* config too, not only with an extreme floor. With zero
verified stakeholders (`relationship_risk_bp = 10,000`) and `base_risk_bp = 1,000`:

| `drop_bp` | numerator | weighted | `base + weighted` | `risk_bp` |
|---|---|---|---|---|
| 8,334 | 900,040 | 9,000 | 10,000 | 10,000 — at the ceiling, clamp does not bind |
| **8,335** | 900,100 | 9,001 | **10,001** | **10,000 — first value the clamp discards** |
| 10,000 | 1,000,000 | 10,000 | 11,000 | 10,000 |

Above `drop_bp = 8,334` the metric stops discriminating.

### 5.4 · The full reachable surface in `sales.deal_cooling`

`base_risk_bp = 1,000`, `target_relationships = 3`. `drop_bp < 5,000` cannot reach this unit — the
gating rule on `core.temporal` ends the run first — and `relationship_risk_bp` can only take four
values. So the entire live output space is this table:

| `drop_bp` ↓ / `rel_risk_bp` → | 0 (3+ verified) | 3,334 (2) | 6,667 (1) | 10,000 (none) |
|---|---|---|---|---|
| **5,000** | 4,000 | 5,334 | 6,667 | 8,000 |
| **6,000** | 4,600 | 5,934 | 7,267 | 8,600 |
| **7,000** | 5,200 | 6,534 | 7,867 | 9,200 |
| **8,000** | 5,800 | 7,134 | 8,467 | 9,800 |
| **9,000** | 6,400 | 7,734 | 9,067 | **10,000** (clamped from 10,400) |
| **10,000** | 7,000 | 8,334 | 9,667 | **10,000** (clamped from 11,000) |

`risk_bp` never falls below **4,000** in a live `deal_cooling` run, and the two bottom-right cells
are indistinguishable. A consumer treating 4,000bp as "low risk" should know that 4,000bp is this
capability's floor, not a measurement of safety.

### 5.5 · Boundary and malformed inputs

| Input | `risk_bp` | Why |
|---|---|---|
| no priors, no config | 1,000 | default floor, both terms 0 |
| no priors, `base_risk_bp: 0` | 0 | pinned; an authored zero is a real choice |
| `base_risk_bp: 4_200`, no priors | 4,200 | the floor alone |
| `drop_bp: 1`, `rel: 2`, default floor | 1,001 | `140/100 = 1.4 → 1` |
| `base_risk_bp: "4200"` | 4,200 | `integer()` parses integral strings |
| `base_risk_bp: 4200.0` | **`ValueError`** | any `float` is rejected, even an integral one |
| `base_risk_bp: True` | **`ValueError`** | `bool` rejected before the `int` check |
| `base_risk_bp: -1` or `10_001` | **`ValueError`** | range |
| `base_risk_bp` absent | 1,000 | `.get("base_risk_bp", 1_000)` |

Every `ValueError` propagates out of `evaluate`, becomes `ResultStatus.FAILED` in the orchestrator,
and — because `core.risk` is `FailurePolicy.REQUIRED` in both shipped capabilities — makes the run's
terminal outcome `DecisionOutcome.FAILED`. A malformed floor stops the capability rather than
degrading it, which is the right trade for a constant an engineer typed.

---

## Next

[05 · Evaluator](05-Evaluator.md) — what this number is allowed to mean, and why it is never a
boolean.
