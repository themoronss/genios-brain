# L2 · B6 — the lost axis gets a receipt · audit, cross-check, then execute

**Written for:** Rohit and Harsh (CTO). **Date:** 2026-10-01.
**Reads with:** `07-DOES-IT-ACTUALLY-WORK.md` (the measurement) and
`08-AUDIT-AND-PLAN-the-silence-receipt.md` (the previous step — **and the document this one corrects**).

---

# ⛔ PART 0 · I WAS WRONG IN `08`, AND THE CORRECTION IS THE REASON THIS IS CHEAP

`08-AUDIT-AND-PLAN` refused this fix in three places, and its **central reason was false**:

> *"An axis is lost on ~100% of runs, so the receipt would fire on ~100% and **rehash ~100% of 12,170
> traces**. The information would be gained and the replay guarantee lost."*

**That is not what happens.** Verified by reading `ReasoningStore._verify_replay_bundle`
(`reason/store.py:1639`): it hashes **the content stored inside the bundle** and compares it against
**the hash stored beside it**. `_semantic_hash(manifest)` over the stored manifest, and so on for every
row. **It never re-runs a unit.**

So:

| | |
|---|---|
| an **old** stored run | keeps its old output and its old hash. Both still consistent. **`verify_replay_bundle` still passes** |
| a **new** run | produces a richer output and a different hash. Both consistent. Correct — it genuinely computed more |
| rows rewritten by this change | ⛔ **ZERO** |

**What `contracts/reasoning.py:845` actually warns about is a different operation.** Read it again:

> *"Without it `canonicalize` walks the dataclass fields, `"value_bp": null` enters the canonical JSON
> of **every finding ever emitted**, and that propagates … so every trace in `reasoning_runs` would
> fail replay verification **against a run that computed the identical result**."*

That is about changing **`to_semantic_dict`** — the *hashing function*. Change how a finding is hashed
and every stored hash stops matching a re-hash of its own stored content. **Adding a field to a unit's
output is not that.** I conflated the two and refused a fix on the strength of it.

⛔ **The lesson is the one this session keeps paying for:** I read a warning that *names* the thing I
was about to do, and did not follow it to the code that implements it. Same shape as believing the
corpus comment in Plane D.

---

# PART 1 · THE AUDIT — what, how, why, in what manner

## 1.1 · WHAT is missing

`core.tradeoff` declares **6** source units (`AXIS_SOURCES`, 3 plugins × 2 sides). Measured on
production:

```
axis_count:  1 on 63%   ·  2 on 37%   ·  3 on 0%
tradeoff.speed_vs_certainty   1,163 firings
tradeoff.risk_vs_reward         597
tradeoff.cost_vs_benefit      ⛔   0 firings in 1,200 rows
```

`axis_count` is the honest signal and it **is** published. ⛔ **What is missing is WHICH axis was lost
and WHY.** `axis_count: 1` tells a reader two comparisons failed; it does not say they were
`cost_vs_benefit` and `risk_vs_reward`, nor that `core.impact.impact_bp` was the absent metric.

## 1.2 · HOW a side goes absent

`_side_bp(view, key)` resolves the unit from `AXIS_SOURCES`, reads `view.prior_metric(unit, metric,
_ABSENT)`, and returns `None` when it is absent. Each plugin then returns `()`.

⛔ **The plugin knows exactly which side failed and throws that knowledge away.** The unit sees only
"no observation", which is indistinguishable from "the axis was not contested".

## 1.3 · WHY not have the plugin report it

A plugin reporting an absence would emit an **observation**, and `axis_count = len(ranked)` counts
observations. An absence counted as an axis would make `axis_count` report comparisons that did not
happen — breaking the one honest number the unit already publishes.

⛔ **So the unit must ask, not the plugin tell.** `evaluate_meaning` already receives `view`, and
`_side_bp` is module-level: the unit can re-read each side and name what was absent, **calling the same
helper** rather than restating its rule.

## 1.4 · IN WHAT MANNER — the four constraints this must satisfy

| | |
|---|---|
| **one publisher per metric** | `tests/test_unit_roster.py::test_no_unit_publishes_a_metric_another_unit_owns`. `axes_unavailable` is owned by nobody — checked |
| **declared in `publishes`** | nothing validates output-vs-`publishes` at runtime, so an undeclared metric would work and would be a lie. `UNDECLARED_METRICS` exists for a name collision, which this is not |
| **conditional inclusion** | emit it **only when an axis is actually lost**, so a run with all six sources present is byte-identical to before. Measured at ~0% of runs today — and the principle costs nothing and is the house rule |
| **no version bump** | `REASONER_VERSION` is one shared constant across 17 units in `deal_cooling_v2`. Nothing in the framework requires a bump for an additive output, and bumping would move 17 units to add one receipt |

⛔ **So no version bump, no migration, no stored row touched.** The cost I quoted in `08` does not exist.

---

# PART 2 · THE PLAN — 3 units, bottom-up

```
level 0 ·  U01  _side_bp also says WHICH source was absent        tradeoff_unit.py
level 1 ·  U02  the unit names the lost axes, conditionally       tradeoff_unit.py
level 2 ·  U03  the guard                                          tests/
```

## `U01` · `_side_bp` reports the absent source, not just `None`

A second helper beside it — `_absent_side(view, key) -> str | None` returning `"core.impact.impact_bp"`
when that side could not be read, `None` when it could.

⛔ **Derived from `AXIS_SOURCES`, like everything else in this module.** `_AXIS_BY_KEY` already holds
`(unit, metric)` per key; the helper formats it. A retyped string would be a third copy of a fact that
already lives in one tuple.

## `U02` · the unit names what it lost — conditionally

In `evaluate_meaning`, for each of the three axes, if the axis produced no observation, ask which side
was absent and emit:

- a reason code `unavailable.<axis>` — which comparison did not happen
- a reason code `absent_source.<unit>.<metric>` — ⛔ **the mover.** `absent_source.core.impact.impact_bp`
  tells a reader exactly which unit to go and look at, which `axis_count: 1` never could
- a metric `axes_unavailable: N`, **present only when N > 0**

⛔ **`axis_count` is NOT changed.** It still counts comparisons that happened. The new number counts
the ones that could not, and the two must sum to 3 — which `U03` asserts.

## `U03` · the guard

1. `axis_count + axes_unavailable == 3`, always — two numbers that must agree, compared
2. with all six priors present: `axes_unavailable` is **absent from the output**, not zero — the
   conditional-inclusion rule, asserted
3. with `core.impact.impact_bp` absent: the codes name **`core.impact`** and **`impact_bp`**
4. `axes_unavailable` is published by no other unit, and IS declared in `publishes`
5. the absent-source string is **derived from `AXIS_SOURCES`**, not retyped

---

# PART 3 · WHAT THIS DOES NOT DO

| | Why |
|---|---|
| bump `REASONER_VERSION` | not required for an additive output; blast radius 17 units |
| change `axis_count` | it is correct. It counts comparisons that happened |
| make a plugin report an absence | an absence counted as an observation would corrupt `axis_count` |
| fix `core.impact` | its silence is correct — *"a fabricated zero silently lies"*. `ALARM B3`, Harsh's |
| touch any stored row | ⛔ **nothing is rewritten.** Old bundles keep verifying |

---
---

# PART 4 · EXECUTED — 2026-10-01

**3 units, bottom-up. 14 tests. No migration. No version bump. ⛔ No stored row touched.**

| unit | artifact |
|---|---|
| `U01` | `_AXES` + `_absent_side()` in `tradeoff_unit.py` — derived from `AXIS_SOURCES` |
| `U02` | `evaluate_meaning` names the lost axes; `axes_unavailable` declared in `publishes` |
| `U03` | `tests/reason/test_the_lost_axis_names_itself.py` |

## ⛔ What the receipt says on real production data

Replayed over **2,681 production runs**, read-only, by reading what each source unit actually
published:

```
unavailable.cost_vs_benefit        2,681 runs   ← every single one
unavailable.risk_vs_reward         1,593
unavailable.speed_vs_certainty       784

absent_source.core.impact.impact_bp            2,681   ← ONE mover, unambiguous
absent_source.core.opportunity.opportunity_bp  1,593
absent_source.core.temporal.urgency_bp           784
absent_source.core.risk.risk_bp                  708   ← legacy-lane runs
absent_source.core.cost.effort_bp                708
```

⛔ **`axis_count: 1` becomes `unavailable.cost_vs_benefit` + `absent_source.core.impact.impact_bp`.**
A number that said *"something was missing"* becomes a sentence naming the unit and the metric a reader
has to open. **That is B6 closed.**

## The five decisions, each defended

⛔ **1 · The unit asks; the plugin does not tell.** A plugin reporting an absence would emit an
*observation*, and `axis_count = len(ranked)` counts observations — so an absence counted as an axis
would corrupt the one honest number the unit already published. `evaluate_meaning` re-reads each side
through the **same** `_side_bp` machinery instead.

⛔ **2 · `axis_count` does not move.** Its docstring: *"`axis_count` says how many comparisons were
possible at all, which is how a reviewer tells 'nothing was contested' apart from 'nothing was
measurable'."* `axes_unavailable` is the complement, and a test asserts **the two sum to 3 on every
input** — two numbers that must agree, compared, because this programme has found five times that two
expressions of one fact which are never compared eventually disagree.

⛔ **3 · Conditionally included.** With all six sources present, `axes_unavailable` is **absent from the
output, not zero** — so such a run hashes exactly as it did before this seam existed. A test asserts
the absence rather than a zero.

⛔ **4 · The absent-source string is DERIVED.** `_absent_side` reads `_AXIS_BY_KEY[key]`, which is built
from `AXIS_SOURCES`. A formatted literal would be a **third** copy of a fact living in one tuple — and
the seventh axis somebody adds would leave it behind, which is the defect `AXIS_SOURCES`' own comment
records this unit already shipping once. A test asserts no unit id is hard-coded in the body.

⛔ **5 · A capability's override is named, not the default.** `_absent_side` resolves through
`_config_id`, so a manifest appointing its own authority gets **its** unit in the receipt. Naming the
default would send a reader to a unit that manifest never scheduled. Driven by a test with
`benefit_source: core.resource`.

## The false positive it must not produce

⛔ **An axis whose two sides were both readable and which still said nothing is NOT reported as
unavailable.** That is not an availability problem, and reporting it as one would send a reader hunting
for a unit that ran perfectly well. The code `continue`s on `if not absent`, and a test covers it.

## What this cost — the audit's own numbers, corrected

| `08` claimed | Actual |
|---|---|
| rehashes ~100% of 12,170 traces | ⛔ **0 rows rewritten.** `_verify_replay_bundle` hashes stored content against its stored hash and never re-runs a unit |
| needs a `REASONER_VERSION` bump — 17 units | ⛔ **no bump.** Nothing in the framework requires one for an additive output |
| breaks the replay guarantee | ⛔ **old bundles still verify.** The warning in `contracts/reasoning.py:845` is about changing `to_semantic_dict`, the hashing FUNCTION — a different operation |

⛔ **I refused a correct fix on a false reading, and the false reading came from believing a warning
without following it to the code that implements it.** Same shape as the stale corpus comment in
Plane D. Recorded in `PART 0` rather than edited away.

## What is still open

| | |
|---|---|
| 🔴 **B3** | `core.relationship` has never completed; `deal.status` has no writer. **Harsh.** The receipt now names `core.impact.impact_bp` on every run, which is one step closer to that root |
| 🟠 **B4** | `core.policy` has never completed — the unit the Organisation-Brain lever works through |
| 🟠 **B5** | `core.signal_composition` never appears in the table at all |
| ✅ **B1 / B2 / B6** | the silence is **declared** (`unit_health`) and the lost axis **names its mover**. Both watched, neither invisible |
