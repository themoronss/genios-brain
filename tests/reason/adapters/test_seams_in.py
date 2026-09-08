"""WAVE Z5 · THE INBOUND SEAMS, END TO END — L2 reaches a unit, L3 removes an option.

Two acceptance rows from doc 06, run against the SHIPPED corpus and the real Layer 4 kernel:

  IN-1 (DLG-06)  a BSO carrying a DECLINING trend produces a snapshot fact a unit reads and
                 CITES, and UNKNOWABLE facts project as unknown-typed, never as values.
  IN-2 (DLG-07)  a corpus blocking rule eliminates a candidate and the elimination is attributed
                 to the rule that performed it — never to a rule that merely covered the play.

Nothing here is a stub. The package is compiled from `Domain Expertise/` by `DomainCompiler`, the
importance is composed by `compose_situation_importance`, the manifest is built by the adapter the
live pass calls, and the decision comes out of `reason_native_capability` — the same entry
`domain_shadow` uses. The live-database half of IN-2 (the rule id in the `signals` row that the
API renders as `alternatives_rejected`) is `test_seams_in_reach_a_signal.py`.
"""

from __future__ import annotations

import pytest

from genios_engine.context.importance import (
    ImportanceBase,
    ModifierInputs,
    TrendInput,
    compose_situation_importance,
)
from genios_engine.contracts.reasoning import CheckOutcome, ExecutionMode, ResultStatus
from genios_engine.reason.adapters import situation_projection as sp
from genios_engine.reason.adapters.expertise import expertise_capability_manifest
from genios_engine.reason.adapters.native import native_context_snapshot, reason_native_capability
from genios_engine.reason.adapters.rule_compiler import POLICY_BLOCK_REASON
from genios_engine.reason.domain_shadow import _rejected_candidates
from genios_engine.reason.engine import NodeContext

from .conftest import (CLOSING_PLAY, DEAL_FACTS, DEAL_OBSERVATIONS, NOW, URGENCY_RULE,
                       compile_situation)

pytestmark = pytest.mark.unit

#: A registered trended metric — `importance.METRIC_POLARITY`'s vocabulary. An invented name is
#: refused by the projection by design, which would make this test pass for the wrong reason.
TREND_METRIC = "engagement.touch_count_28d"

#: The fact path this fixture types UNKNOWABLE. It is a path the corpus's sales rules actually
#: read (`first-touch-unanswered` and friends test `{absent: thread.last_inbound}`), which is why
#: it is the one worth proving does not become a chaseable prerequisite.
UNKNOWABLE_PATH = "thread.last_inbound"


def _declining_trend():
    """The REAL composition, over a real declining trend. `compose_situation_importance` decides
    whether the term fires; this fixture supplies the observation and never the verdict."""
    return compose_situation_importance(
        base=ImportanceBase(importance_bp=6_000, source="l1_qualified_signals",
                            signal_id="sig_1", version="alg17@1"),
        signals=(),
        modifiers=ModifierInputs(
            trends=(TrendInput(metric=TREND_METRIC, subject_node_id="node_1",
                               direction="declining", trend_confidence_bp=8_200, point_count=7,
                               fact_version_id="fv_trend_1"),),
            coverage_ready=True, coverage_domain="sales"),
        eval_time=NOW)


@pytest.fixture(scope="module")
def compiled():
    """One compiled situation carrying BOTH inbound seams: a declining trend for IN-1 and the
    typed absence that makes the corpus's blocking closing rule fire for IN-2."""
    return compile_situation(absent=("commitment.due_at",), unknowable=(UNKNOWABLE_PATH,),
                             composed=_declining_trend())


@pytest.fixture(scope="module")
def projection(compiled):
    return sp.project_situation(situation=compiled.situation, context=compiled.context,
                                root_entity_id="node_1")


def _node_context() -> NodeContext:
    return NodeContext(
        node_id="node_1", node_type="company",
        facts={path: {"value": value, "confidence": 900, "authority_rank": 3}
               for path, value in DEAL_FACTS.items()},
        obs=[{"kind": kind, "occurred_at": NOW} for kind in DEAL_OBSERVATIONS])


def _manifest(compiled, projection, **kwargs):
    return expertise_capability_manifest(
        compiled.package, root_entity_type="company",
        situation=compiled.situation, context=compiled.context,
        roster_v2=True, projection=projection, **kwargs)


def _execute(compiled, projection):
    manifest = _manifest(compiled, projection)
    execution = reason_native_capability(
        org_id="org_weld", context=_node_context(), capability=manifest,
        evaluation_time=NOW, graph_version=1, config_snapshot_id=None,
        mode=ExecutionMode.SHADOW, projection=projection)
    return manifest, execution


# =================================================================================================
# IN-1 · the BSO reaches the snapshot, and a unit reads and cites it
# =================================================================================================

def test_a_declining_bso_trend_arrives_in_the_snapshot_as_a_declared_fact(compiled, projection):
    manifest = _manifest(compiled, projection)
    snapshot = native_context_snapshot(
        org_id="org_weld", context=_node_context(), capability=manifest,
        evaluation_time=NOW, graph_version=1, projection=projection)

    name = f"{sp.TREND_PREFIX}{TREND_METRIC}"
    assert name in snapshot.facts, sorted(snapshot.facts)
    assert name not in snapshot.missing_fields
    # DECLARED, not merely carried: `core.context`'s spec names it, which is what puts it in the
    # completeness denominator and in front of the Unit Selector.
    context_spec = next(spec for spec in manifest.reasoners if spec.reasoner_id == "core.context")
    assert name in context_spec.required_fields
    # And it did not enter the capability's own gate set — a capability vetoed for want of a trend
    # would be the projection making the engine quieter, not better informed.
    assert name not in manifest.required_fields


def test_core_context_reads_the_projected_trend_and_cites_its_evidence(compiled, projection):
    """Doc 06's IN-1 acceptance row, with a REGISTERED unit rather than a fixture one.

    `FactCoveragePlugin` counts declared fields it can see and cites their evidence, so the trend
    Layer 2 composed is now inside a finding a decision was built from — the first time anything
    under `reason/` has read the analytic stratum at all.
    """
    _, execution = _execute(compiled, projection)
    result = execution.result_by_id["core.context"]
    assert result.status == ResultStatus.COMPLETED

    name = f"{sp.TREND_PREFIX}{TREND_METRIC}"
    evidence_id = next(ref.evidence_id for ref in projection.evidence if ref.field == name)
    coverage = next(item for item in result.findings if item.finding_id == "context.fact_coverage")
    assert evidence_id in coverage.evidence_ids, "the unit read the trend and did not cite it"
    assert coverage.metrics["declared_field_count"] >= len(projection.declared_fields)


def test_an_unknowable_axis_reaches_the_snapshot_as_missing_and_never_as_a_number(
        compiled, projection):
    """Three-state all the way through. `confidence_analytic` is unassessed on this row, so it is
    a NAME in `missing_fields` — a value there would rank an unassessed situation below every
    assessed one, and a 0 would rank it below a bad one."""
    manifest = _manifest(compiled, projection)
    snapshot = native_context_snapshot(
        org_id="org_weld", context=_node_context(), capability=manifest,
        evaluation_time=NOW, graph_version=1, projection=projection)

    axis = f"{sp.CONFIDENCE_PREFIX}analytic"
    assert axis in snapshot.missing_fields
    assert axis not in snapshot.facts
    assert not any(ref.field == axis for ref in snapshot.evidence)


def test_an_unknowable_fact_path_stops_being_a_chaseable_prerequisite(compiled, projection):
    """`core.dependency`'s `PrerequisiteAbsencePlugin` reports a declared-and-absent fact as a
    blocker the workflow can go and clear. For a path Layer 2 typed UNKNOWABLE there is nothing to
    go to, and reporting one is the negative inference `context.quality.missing` refuses.

    The withholding is NAMED in the roster receipt, so a shorter prerequisite list can never be
    mistaken for an expertise that reads fewer facts.
    """
    manifest = _manifest(compiled, projection)
    assert UNKNOWABLE_PATH in projection.unknowable_paths
    dependency = next((spec for spec in manifest.reasoners
                       if spec.reasoner_id == "core.dependency"), None)
    assert dependency is not None, "the roster declined core.dependency; the seam is untested"
    assert UNKNOWABLE_PATH not in dependency.config["prerequisite_fields"]

    receipt = manifest.metadata["roster"]["situation_projection"]
    withheld = receipt["prerequisites_withheld_unknowable"]
    # The path is withheld only when the expertise actually reads it; either way the receipt says
    # which, and the plain absence of a claim is never how it is communicated.
    assert tuple(withheld) == tuple(sorted(set(projection.unknowable_paths)
                                           & set(manifest.selection_fields)))
    assert withheld, "the fixture's UNKNOWABLE path is not one this expertise reads"
    # And the absence itself still reaches the snapshot, TYPED — withheld from one consumer is
    # not withheld from the record.
    assert f"{sp.ABSENCE_PREFIX}{UNKNOWABLE_PATH}" in projection.facts


def test_a_manifest_that_declares_a_projection_refuses_a_snapshot_without_one(
        compiled, projection):
    """The manifest DECLARES and the snapshot SUPPLIES. A caller that builds one from the
    projection and the other without it would report Layer 2's own readings as missing and drop
    every unit that declared them — loudly refused rather than reasoned through."""
    manifest = _manifest(compiled, projection)
    with pytest.raises(ValueError, match="no projection was supplied"):
        native_context_snapshot(org_id="org_weld", context=_node_context(), capability=manifest,
                                evaluation_time=NOW, graph_version=1)


def test_a_projection_anchored_elsewhere_is_refused(compiled, projection):
    from dataclasses import replace as _replace

    manifest = _manifest(compiled, projection)
    with pytest.raises(ValueError, match="anchored on"):
        native_context_snapshot(
            org_id="org_weld", context=_node_context(), capability=manifest,
            evaluation_time=NOW, graph_version=1,
            projection=_replace(projection, root_entity_id="node_2"))


def test_the_six_unit_lane_is_byte_identical_without_a_projection(compiled):
    """An unactivated tenant's manifest, and therefore its content-addressed version, cannot move
    because this wave landed. The projection is refused there rather than ignored, so it cannot
    arrive by accident either."""
    plain = expertise_capability_manifest(
        compiled.package, root_entity_type="company",
        situation=compiled.situation, context=compiled.context)
    assert not any(name.startswith(sp.SITUATION_NAMESPACE)
                   for name in plain.selection_fields + plain.required_fields)
    snapshot = native_context_snapshot(
        org_id="org_weld", context=_node_context(), capability=plain,
        evaluation_time=NOW, graph_version=1)
    assert not any(name.startswith(sp.SITUATION_NAMESPACE) for name in snapshot.facts)
    assert "situation_projection" not in snapshot.metadata

    with pytest.raises(ValueError, match="without roster_v2"):
        expertise_capability_manifest(
            compiled.package, root_entity_type="company", situation=compiled.situation,
            context=compiled.context,
            projection=sp.project_situation(situation=compiled.situation,
                                            context=compiled.context, root_entity_id="node_1"))


# =================================================================================================
# IN-2 · the corpus blocking rule, and the attribution that carries its id
# =================================================================================================

def test_a_corpus_blocking_rule_eliminates_the_candidate_through_the_policy_seam(
        compiled, projection):
    """The elimination the rule id has to travel with. `core.constraint` stamps
    `tenant_policy_block` on exactly the eliminations it performs from `blocked_play_ids`, which
    is where `expertise._roster_specs` puts the corpus's blocking doctrine.

    This also pins the reason code itself: `rule_compiler.POLICY_BLOCK_REASON` is restated rather
    than imported from the unit, and the day it drifts every corpus elimination would silently
    stop being attributable.
    """
    _, execution = _execute(compiled, projection)
    eliminated = next(item for item in execution.decision.candidates
                      if item.play_id == CLOSING_PLAY)
    assert eliminated.disposition.value == "eliminated"
    blocking = [check for check in eliminated.checks
                if check.outcome == CheckOutcome.ELIMINATE
                and check.reason_code == POLICY_BLOCK_REASON]
    assert blocking, [check.reason_code for check in eliminated.checks]
    assert blocking[0].evaluator_id == "core.constraint"


def test_the_rule_id_travels_into_alternatives_rejected(compiled, projection):
    """`_rejected_candidates` is what `domain_shadow` stores in `signals.rejected_candidates`,
    which the API renders as `alternatives_rejected`. The authored rule id and its byte-identical
    statement are on the losing candidate."""
    _, execution = _execute(compiled, projection)
    decision = execution.decision
    selected = next((item for item in decision.candidates
                     if item.candidate_id == decision.selected_candidate_id), None)
    rejected = _rejected_candidates(decision, selected)
    named = [row for row in rejected if row["eliminated_by"]]
    assert len(named) == 1
    assert named[0]["play_id"] == CLOSING_PLAY
    assert named[0]["eliminated_by"][0]["rule_id"] == URGENCY_RULE
    assert named[0]["eliminated_by"][0]["severity"] == "blocking"
    assert "buyer" in named[0]["eliminated_by"][0]["statement"].lower()


def test_a_rule_only_claims_what_the_policy_seam_removed(compiled, projection):
    """Attribution, proven on the real decision rather than on a stub: every candidate a corpus
    rule names carries the check that removed it, and every eliminated candidate that carries no
    such check is named by nobody."""
    _, execution = _execute(compiled, projection)
    decision = execution.decision
    claimed = {candidate_id
               for applied in decision.constraints_applied
               for candidate_id in applied.get("eliminated_candidate_ids") or ()}
    by_id = {item.candidate_id: item for item in decision.candidates}
    assert claimed
    for candidate_id in claimed:
        candidate = by_id[candidate_id]
        assert any(check.outcome == CheckOutcome.ELIMINATE
                   and check.reason_code == POLICY_BLOCK_REASON
                   for check in candidate.checks), candidate.play_id
    for candidate in decision.candidates:
        if candidate.disposition.value != "eliminated":
            continue
        if not any(check.outcome == CheckOutcome.ELIMINATE
                   and check.reason_code == POLICY_BLOCK_REASON
                   for check in candidate.checks):
            assert candidate.candidate_id not in claimed, (
                f"{candidate.play_id} was removed by something else and a corpus rule claimed it")
