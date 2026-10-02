# S1 — DONE · a unit may not write a durable brain from a measurement

**Unit:** `M14.C2.S1` · **Owner:** me · ✅ **2026-10-02** · **27 tests · 4/4 mutations caught**
**Found by:** [`07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md`](07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md) §2
**Plan:** [`08-PLAN-v2-from-the-atlas.md`](08-PLAN-v2-from-the-atlas.md) §2

---

## 1 · What was wrong

`units.ALL_ANALYSIS_UNITS` runs **eleven** analysis units and each one picks a `LearningTarget`.
That choice decides the **sink**:

```
METRICS               → publish_metric        a measurement, published, never reviewed
RUNTIME               → publish_runtime       temporary_memories, expires_at NOT NULL
ORGANIZATION
BEHAVIOR              → publish_brain         ⛔ learned_brain_entries — durable, versioned,
ADAPTIVE                                         active, and NO expiry column at all
KNOWLEDGE_SUGGESTION  → publish_knowledge     always stops at human review
```

⛔ **Nothing asserted which unit may choose which**, so a unit's sink could change in a one-word
edit and no build would notice.

## 2 · ⛔⛔ And one pair was already wrong

| Unit | `proposed_value` | Target |
|---|---|---|
| `unit_feedback_learning` | rates and counts | `METRICS` |
| `unit_outcome_analysis` | `success_rate_bp`, counts, attention | `METRICS` |
| `unit_actor_outcome_analysis` | rates and counts | `METRICS` |
| `unit_performance_optimization` | rates and counts | `METRICS` |
| ⛔ **`unit_recommendation_learning`** | **`success_rate_bp`, `attention_per_outcome_bp`, `efficacy_bp`** | ⛔⛔ **`ADAPTIVE`** |

The full chain, verified:

```
units.py:452    → LearningObject(target=ADAPTIVE, visibility=_org_visibility())   ⛔ not a stub
governance:53   → preflight: "Behavior/Adaptive without a resolved subject are org-derived
                   — ALLOWED"           ⛔ THREE expiry checks for RUNTIME, NONE for ADAPTIVE
governance:112  → govern: PROMOTED, "auto_promote"                   ⛔ no human review
publisher:210   → target in _BRAIN_TARGETS → publish_brain, state = PUBLISHED
publisher:95    → insert into learned_brain_entries … active = true  ⛔ no expiry column
contracts:226   → expires_at raises unless target is RUNTIME
```

⛔ **It breaks an Atlas authority boundary outright.** The Atlas's boundary for Recommendation
Learning is **"No self-training from recommendation score."**
`packs/compiler/runtime_brains.py:497` selects `brain in ('organization','behavior','adaptive')`
**into the compiled expertise package**, and the recommender reasons from that package. **The score
trains the thing that produced it.**

And `api/brain_routes.py:106` tells the user the adaptive brain *"Moves this current signal forward
in the executive brief **while it applies**"* — ⛔ **the product promises an expiry the durable half
cannot express.**

## 3 · What I built, and what I deliberately did not

⛔ **I did not fix it.** All three repairs — add TTL/decay to `ADAPTIVE`, prohibit durable `ADAPTIVE`
publication, retarget the unit to `METRICS` — change what the Adaptive brain **contains**, and the
pack compiler reads it. That is a contract decision, recorded in the Atlas check §2 as Rohit's.

What I built is the thing that needs no decision: **the mapping as data, checked against the code.**

```
genios_engine/feedback/target_policy.py      UNIT_TARGETS — 11 units, target + why
                                             DURABLE_FROM_A_MEASUREMENT — ⛔ the declared violation
                                             DURABLE_BRAIN_TARGETS — asserted == publisher's
tests/feedback/test_a_unit_may_not_write_a_durable_brain_from_a_measurement.py   27 tests
genios_engine/feedback/feedback_health.py    +4 declared silences (build-time property guards)
```

⛔ **`target_policy.py` imports nothing from the engine** — only `ast` and `pathlib` — and
**deliberately does not import `platform/reachability.py`**, because `_is_declaration_module`
treats any importer as a declared-silence module and would quietly exclude this file from a guard
it should be subject to. `test_this_module_does_not_import_the_reachability_machinery` asserts both.

### The checks, and which one has teeth

| | Check | What it catches |
|---|---|---|
| 1 | `undeclared_units()` | a **new** unit picking a sink without declaring it |
| 2 | `missing_units()` | a declaration naming a unit the registry no longer runs |
| 3 | ⛔ **`drifted_units()`** | **a declared target that no longer matches the code** — the one with teeth |
| 4 | `durable_from_a_measurement()` | derived; asserted as a **SET** equal to the declaration, both ways |
| 5 | `DURABLE_BRAIN_TARGETS` | asserted `== publisher._BRAIN_TARGETS` — *a copy that can disagree with the thing it copies is worse than no copy* |

## 4 · ⛔ The mutation run — baseline first, this time

```
✅ baseline clean: undeclared=() missing=() drifted=()

  M1 · retarget recommendation_learning ADAPTIVE -> METRICS   ✅ CAUGHT  drifted
  M2 · drop a unit from the registry                          ✅ CAUGHT  missing
  M3 · add an UNDECLARED unit to the registry                 ✅ CAUGHT  undeclared
  M4 · a stub starts naming a target                          ✅ CAUGHT  drifted

✅ baseline clean again after 4 mutations
4 caught · 0 survived
```

⛔ **And the harness refused to count two mutations it could not apply.** M2 and M3's first anchors
had the wrong comment spacing, and the run printed *"ANCHOR MISSING — mutation not applied, counts
nothing"* rather than scoring them. That is the direct repair of `STEP-14`, where a stale anchor let
a surviving mutation be reported as caught. **The baseline is asserted before AND after.**

## 5 · ⛔ Three faults of my own, each caught and each pinned as a regression test

| | Fault | How it was caught |
|---|---|---|
| 1 | ⛔ **a grep for a keyword argument misses the call that passes it through** — `grep 'target=LearningTarget'` finds **nine of eleven**; `behavior_evolution` and `adaptive_evolution` pass their target as a keyword *into* `_cohort_candidate` | by writing the resolver as an AST walk over the whole function body rather than over `LearningObject(...)` calls. `test_the_ast_walk_finds_a_target_passed_as_a_keyword_argument` asserts those two units contain **no** `LearningObject` call at all |
| 2 | ⛔ `ALL_ANALYSIS_UNITS` is an **`ast.AnnAssign`**, not an `ast.Assign`. My first `registered_units()` matched only `Assign`, returned `()`, and **`missing_units()` then reported all eleven declarations as stale** | ⛔ **the second direction caught the first direction's resolver.** *A totality guard that runs one way is half a guard* — and the half I nearly skipped is the half that found the bug |
| 3 | ⛔ `_proposes_something` first detected only *delegation* to a `[]`-returning helper, so it called `unit_preference_learning` — whose own body **is** `return []` — a proposer | by reading its own output. **A helper that answers a narrower question than its name asks** is the defect this module exists to catch, reproduced inside the module |

## 6 · ⛔ A measurement this produced, and nothing had recorded it

```
eleven analysis units run every weekly pass
⛔ FOUR of them cannot emit a proposal at all:
      unit_preference_learning     return []      "Empty until the inbox lands"  — declared
      unit_temporary_memory        return []      "Empty until the inbox lands"  — declared
      unit_behavior_evolution      → _cohort_candidate → return []   ⛔ see below
      unit_adaptive_evolution      → _cohort_candidate → return []   ⛔ see below

⛔ **CORRECTED 2026-10-02 BY `S4`: those two are NOT Atlas gap #2.** They propose nothing,
and the work they name is **built and wired one package down** — `packs/brains/behavior_distill`
and `packs/brains/adaptive_lease`, appended to the same weekly run. A placeholder, not a gap.
→ [`STEP-S4-DONE-a-silent-unit-names-its-producer.md`](STEP-S4-DONE-a-silent-unit-names-its-producer.md)
```

`test_four_of_eleven_units_cannot_emit_a_proposal` asserts that **set**, so a unit becoming live is
**read** rather than discovered.

⛔ **And it narrows the durable-brain finding to one unit rather than three.** `behavior_evolution`
and `adaptive_evolution` also declare durable brains; they are excluded because they propose
nothing. **Without that distinction the report would have named three violations where there is
one**, which is the difference between a finding and an alarm.

## 7 · Verify

```bash
.venv/bin/pytest tests/feedback/test_a_unit_may_not_write_a_durable_brain_from_a_measurement.py -q
.venv/bin/pytest tests/platform/test_every_package_says_what_it_does_not_call.py tests/feedback -q
.venv/bin/pytest -q                                      # ⛔ the FULL suite
```

## 8 · Doctrine

| Rule |
|---|
| ⛔ **a grep for a keyword argument misses the call that passes it through** |
| ⛔ **a totality guard that runs one way is half a guard — and the second direction caught the first's resolver** |
| ⛔ **a helper that answers a narrower question than its name asks is the defect, not the tool** |
| ⛔ **a copy that can disagree with the thing it copies is worse than no copy** |
| ⛔ **a mutation whose anchor did not match counts nothing — and the harness must say so** |
| **hold a violation as data when the repair is not yours to make** |
| **a unit that proposes nothing cannot violate a sink rule — the distinction turns three alarms into one finding** |
