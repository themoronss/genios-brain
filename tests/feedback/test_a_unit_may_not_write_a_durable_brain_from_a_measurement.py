r"""Which analysis unit may propose which learning target — asserted against the code, both ways.

⛔ WHAT WAS WRONG. `units.ALL_ANALYSIS_UNITS` runs eleven units and each picks a `LearningTarget`,
which decides its SINK: `METRICS` is published as a measurement, `RUNTIME` becomes an expiring
lease, and `ORGANIZATION`/`BEHAVIOR`/`ADAPTIVE` are written by `publisher.publish_brain` into
`learned_brain_entries` as a durable, versioned, active row **with no expiry column at all**.
Nothing asserted the mapping, so a unit's sink could change in a one-word edit and no build would
notice.

⛔ AND ONE PAIR IS ALREADY WRONG. Four units whose `proposed_value` is rates and counts target
`METRICS`. `unit_recommendation_learning` emits `success_rate_bp`, `attention_per_outcome_bp` and
`efficacy_bp` — the same shape — and targets `ADAPTIVE`, which `governance.govern` AUTO-PROMOTES
with no human review, and which `packs/compiler/runtime_brains.py` reads back into the compiled
expertise package the recommender reasons from. The Atlas's authority boundary for this exact unit
is **"No self-training from recommendation score."**

⛔ THIS FILE DOES NOT FIX THAT. Every repair — adding TTL/decay to `ADAPTIVE`, prohibiting durable
`ADAPTIVE` publication, or retargeting the unit to `METRICS` — changes what the Adaptive brain
CONTAINS, and the pack compiler reads it. That is a contract decision. **The violation is held as
data so it cannot ship silently**, and the decision is recorded in
`speedrun008/YCW27/layer-6-learning/07-ATLAS-CHECK-layer-7-learning-claim-by-claim.md` §2.

⛔ THREE OF MY OWN FAULTS ARE PINNED HERE AS REGRESSIONS, because each one produced a confident
wrong answer first:
  1 · `grep 'target=LearningTarget'` finds NINE of eleven — two units pass their target as a
      keyword argument *through* `_cohort_candidate`. **A grep for a keyword argument misses the
      call that passes it through.**
  2 · `ALL_ANALYSIS_UNITS` is an `ast.AnnAssign`, not an `ast.Assign`. The first resolver matched
      only `Assign`, found zero units, and `missing_units()` reported all eleven declarations as
      stale. **The second direction caught the first direction's resolver.**
  3 · `_proposes_something` first detected only delegation to a `[]`-returning helper, so it called
      `unit_preference_learning` — whose own body IS `return []` — a proposer.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from genios_engine.feedback import target_policy as T
from genios_engine.feedback.publisher import _BRAIN_TARGETS

_MEASUREMENT_SIBLINGS = ("unit_feedback_learning", "unit_outcome_analysis",
                         "unit_actor_outcome_analysis", "unit_performance_optimization")
_STUBS = ("unit_preference_learning", "unit_temporary_memory")


# ---------------------------------------------------------------------------------------------
# 1 · both directions, and the one with teeth
# ---------------------------------------------------------------------------------------------

def test_every_registered_unit_declares_its_target() -> None:
    """A new unit cannot pick a sink silently: the registry is the source, this is the declaration."""
    assert T.undeclared_units() == (), (
        f"units ALL_ANALYSIS_UNITS runs with no declared target: {T.undeclared_units()}")


def test_no_declaration_names_a_unit_that_is_gone() -> None:
    """⛔ The second direction. An entry naming a retired unit is as much a lie as a missing one."""
    assert T.missing_units() == (), f"declared units the registry no longer runs: {T.missing_units()}"


def test_no_declared_target_has_drifted_from_the_code() -> None:
    """⛔ THE CHECK WITH TEETH. A one-word edit to a unit's target fails this, which is the whole
    point: the sink decides whether a proposal expires, waits for a human, or becomes permanent."""
    assert T.drifted_units() == (), (
        "declared target no longer matches the code — (unit, declared, measured): "
        f"{T.drifted_units()}")


def test_the_registry_is_eleven_units() -> None:
    """⛔ Regression on fault 2: an `AnnAssign` resolver that found zero. `units.py:569` says
    'Eleven analysis units' in prose; this asserts it against the tuple."""
    assert len(T.registered_units()) == 11


# ---------------------------------------------------------------------------------------------
# 2 · the durable set is not allowed to disagree with the publisher
# ---------------------------------------------------------------------------------------------

def test_the_durable_set_matches_the_publisher() -> None:
    """⛔ `DURABLE_BRAIN_TARGETS` is a copy of `publisher._BRAIN_TARGETS`, and **a copy that can
    disagree with the thing it copies is worse than no copy.** Asserted rather than trusted."""
    assert T.DURABLE_BRAIN_TARGETS == frozenset(t.name for t in _BRAIN_TARGETS)


def test_a_durable_target_has_no_expiry_in_the_contract() -> None:
    """The reason a durable brain matters: `expires_at` is refused unless the target is RUNTIME, so
    a durable proposal cannot carry a TTL even if its author wanted one."""
    from datetime import datetime, timezone

    from genios_engine.contracts.learning import (
        LearningEvidence,
        LearningObject,
        LearningTarget,
        Visibility,
        VisibilityScope,
    )
    now = datetime.now(timezone.utc)
    with pytest.raises(Exception):
        LearningObject(
            org_id="o", unit="probe", target=LearningTarget.ADAPTIVE, subject="adaptive:probe",
            proposed_value={"x": 1},
            evidence=LearningEvidence(observations=3, independent_refs=3, distinct_days=2,
                                      positive=3, negative=0, confidence_bp=9000,
                                      business_value_bp=9000),
            visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
            first_seen_at=now, last_seen_at=now, policy_key="k",
            expires_at=now)


# ---------------------------------------------------------------------------------------------
# 3 · the declared violation, and that it is exactly one
# ---------------------------------------------------------------------------------------------

def test_the_measured_violation_set_is_the_declared_one() -> None:
    """⛔ Derived from the code, compared with the declaration — in BOTH directions, so a NEW unit
    routing a measurement into a durable brain fails the build, and a declaration that is no
    longer true fails it too.

    ⛔ Asserted as a SET, never a count: *a membership list shrinks every time the work succeeds;
    an invariant does not*, and this programme broke three tests on correct code learning that."""
    assert set(T.durable_from_a_measurement()) == set(T.DURABLE_FROM_A_MEASUREMENT)


def test_the_violation_is_recommendation_learning() -> None:
    assert T.durable_from_a_measurement() == ("unit_recommendation_learning",)


def test_the_violation_names_the_atlas_boundary_it_breaks() -> None:
    """A declared violation with no named boundary is a shrug with paperwork."""
    why, mover = T.DURABLE_FROM_A_MEASUREMENT["unit_recommendation_learning"]
    assert "No self-training from recommendation score" in why
    assert "runtime_brains" in why or "compiled expertise package" in why
    assert "MOVES WHEN" in mover


def test_the_violating_unit_can_actually_emit_a_proposal() -> None:
    """⛔ The violation is LIVE, not latent. `behavior_evolution` and `adaptive_evolution` also
    declare durable brains and are excluded because `_cohort_candidate` returns `[]` — so this
    asserts the distinction that makes the finding worth reporting at all.

    ⛔ COMPLETED 2026-10-02 BY `S4`, BECAUSE HALF THIS SENTENCE READS AS A GAP. Those two units
    propose nothing **and the work they name is built and wired one package down** —
    `packs/brains/behavior_distill.distill` and `packs/brains/adaptive_lease.lease_proposals`,
    appended to the same weekly run by `feedback/brain_pipeline.brain_pipeline_proposals`. Stating
    only the first half is how the GeniOS Atlas came to record Layer 7 gap #2 as *"direct
    personalization evolution is missing"*, and how this programme repeated that verdict before
    reading the driver. See `target_policy.DELEGATED` and
    `tests/feedback/test_a_silent_unit_names_the_producer_that_does_its_job.py`."""
    assert T._proposes_something("unit_recommendation_learning") is True
    assert T._proposes_something("unit_adaptive_evolution") is False
    assert T._proposes_something("unit_behavior_evolution") is False


def test_the_measurement_siblings_all_target_metrics() -> None:
    """The comparison the finding rests on: four units of the same shape, one different."""
    for unit in _MEASUREMENT_SIBLINGS:
        assert T.UNIT_TARGETS[unit][0] == "METRICS", unit
    assert T.UNIT_TARGETS["unit_recommendation_learning"][0] == "ADAPTIVE"


def test_pattern_learning_is_excluded_as_a_claim_not_a_measurement() -> None:
    """⛔ The one unit that targets a durable brain legitimately, and the exclusion is reasoned in
    its own entry rather than hidden in the filter."""
    assert T.UNIT_TARGETS["unit_pattern_learning"][0] == "ORGANIZATION"
    assert "unit_pattern_learning" not in T.durable_from_a_measurement()
    why = T.UNIT_TARGETS["unit_pattern_learning"][1]
    assert "CLAIM" in why and "not a measurement" in why


# ---------------------------------------------------------------------------------------------
# 4 · the three resolver faults, pinned
# ---------------------------------------------------------------------------------------------

def test_the_ast_walk_finds_a_target_passed_as_a_keyword_argument() -> None:
    """⛔ Regression on fault 1. These two units contain no `LearningObject(` call at all — their
    target travels as a keyword into `_cohort_candidate` — so a constructor-only walk, or a grep
    for `target=LearningTarget`, reports them as choosing nothing."""
    measured = T.measured_unit_targets()
    assert measured["unit_behavior_evolution"] == ("BEHAVIOR",)
    assert measured["unit_adaptive_evolution"] == ("ADAPTIVE",)

    src = pathlib.Path("genios_engine/feedback/units.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for name in ("unit_behavior_evolution", "unit_adaptive_evolution"):
        node = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == name)
        constructs = [c for c in ast.walk(node)
                      if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                      and c.func.id == "LearningObject"]
        assert constructs == [], f"{name} now builds a LearningObject directly — re-check the walk"


def test_a_stub_declares_no_target_and_names_none() -> None:
    """⛔ Regression on fault 3, from the declaration side: a unit that returns `[]` declares `None`,
    and `drifted_units()` fails if it ever starts naming one without the declaration catching up."""
    for unit in _STUBS:
        declared, why = T.UNIT_TARGETS[unit]
        assert declared is None, unit
        assert T.measured_unit_targets()[unit] == (), unit
        assert T._proposes_something(unit) is False, unit
        assert "Empty until the inbox lands" in why, unit


def test_four_of_eleven_units_cannot_emit_a_proposal() -> None:
    """⛔ The measured state of the loop, asserted as a SET so a unit becoming live fails here and
    is read rather than discovered. Two are declared stubs; two are Atlas gap #2."""
    silent = {u for u in T.registered_units() if not T._proposes_something(u)}
    assert silent == {"unit_preference_learning", "unit_temporary_memory",
                      "unit_behavior_evolution", "unit_adaptive_evolution"}


# ---------------------------------------------------------------------------------------------
# 5 · the declaration is readable, and this module is not a declared-silence module
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("unit", sorted(T.UNIT_TARGETS))
def test_every_entry_carries_a_usable_reason(unit: str) -> None:
    """A mapping with no reason per row teaches a reader to skip the rows that have one."""
    _declared, why = T.UNIT_TARGETS[unit]
    assert len(why) >= 40, f"{unit}'s reason says nothing usable: {why!r}"


def test_this_module_does_not_import_the_reachability_machinery() -> None:
    """⛔ `platform/reachability._is_declaration_module` treats any importer as a declared-silence
    module and excludes it from the engine-wide scan. This module is not one, so importing that
    machinery here would quietly remove it from a guard it should be subject to."""
    src = pathlib.Path("genios_engine/feedback/target_policy.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any("reachability" in m for m in imported), sorted(imported)
    assert not any(m.startswith("genios_engine") for m in imported), (
        f"target_policy.py must import nothing from the engine: {sorted(imported)}")
