"""Executable contract for Layer 4 · Part 3 — the Decision Maker.

Part 3 is the only place in GeniOS where synthesis happens. These tests fix the properties that
make that safe to rely on:

* **Metric authority.** Several units observe confidence and urgency; exactly one publishes the
  value the decision uses. This is the rule that stops Part 2 from silently re-scoring the whole
  system every time a unit is added, so it is pinned here in detail.
* **Elimination precedes ranking.** A blocked play leaves the contest; it never wins on score and
  gets demoted afterwards.
* **Total ordering.** No tie is ever broken by iteration order.
* **Terminal runs publish nothing.** A run that ended early has no candidate field to rank.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CandidateAdjustment,
    CandidateCheck,
    CandidateDisposition,
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    DecisionOutcome,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.decision_maker import (
    BELOW_FLOOR_REASON,
    CONFIDENCE_FLOOR_KEY,
    CONFIDENCE_AUTHORITY,
    CONFIDENCE_AUTHORITY_KEY,
    PRIORITY_AUTHORITY,
    PRIORITY_AUTHORITY_KEY,
    DecisionMaker,
    aggregate_evidence,
    build_candidates,
    build_candidate_objects,
    calculate_confidence,
    evaluate_candidates,
    rank_candidates,
    synthesize_candidates,
    priority_metrics,
)
from genios_engine.reason.protocols import OrchestrationError

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _play(play_id: str, *, impact=6_000, success=6_000, effort=2_000, risk=1_000) -> PlayDefinition:
    return PlayDefinition(
        play_id=play_id,
        version="1",
        label=play_id.replace("_", " ").title(),
        steps=("Prepare a grounded draft",),
        impact_bp=impact,
        success_probability_bp=success,
        effort_bp=effort,
        risk_bp=risk,
    )


def _request(*, plays=None, metadata=None, specs=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=tuple(specs or (ReasonerSpec("core.confidence", "1"),)),
        plays=tuple(plays or (_play("restore_momentum"),)),
        policies=(),
        metadata=metadata or {},
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts={"deal.status": "open"},
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _completed(reasoner_id: str, **metrics) -> ReasonerResult:
    return ReasonerResult(
        reasoner_id=reasoner_id,
        reasoner_version="1",
        status=ResultStatus.COMPLETED,
        matched=True,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------------------------
# Metric authority — the rule that protects every future unit addition
# ---------------------------------------------------------------------------------------------

def test_the_confidence_authority_overrides_every_earlier_observer():
    """legacy.rule and legacy.score_gate both observe confidence; core.confidence publishes it."""
    results = [
        _completed("legacy.rule", confidence_bp=3_000),
        _completed("legacy.score_gate", confidence_bp=4_000),
        _completed(CONFIDENCE_AUTHORITY, confidence_bp=9_100),
    ]

    assert calculate_confidence(results, _request(), False) == 9_100


def test_a_unit_running_after_the_authority_cannot_move_confidence():
    """This is what makes Part 2 safe: appending units cannot re-score existing decisions."""
    results = [
        _completed(CONFIDENCE_AUTHORITY, confidence_bp=9_100),
        _completed("core.planning", confidence_bp=100),
    ]

    assert calculate_confidence(results, _request(), False) == 9_100


def test_without_an_authority_the_last_observer_stands():
    results = [_completed("legacy.rule", confidence_bp=3_000),
               _completed("legacy.score_gate", confidence_bp=4_200)]

    assert calculate_confidence(results, _request(), False) == 4_200


def test_a_failed_authority_does_not_publish_a_value():
    """A unit that did not complete has no opinion; its absence must not be read as agreement."""
    results = [
        _completed("legacy.rule", confidence_bp=3_000),
        ReasonerResult(CONFIDENCE_AUTHORITY, "1", ResultStatus.FAILED,
                       reason_codes=("reasoner_failure",)),
    ]

    assert calculate_confidence(results, _request(), False) == 3_000


def test_capability_declared_default_holds_when_nobody_publishes():
    request = _request(metadata={"default_confidence_bp": 2_500})

    assert calculate_confidence([], request, False) == 2_500


def test_a_degraded_run_cannot_present_itself_as_fully_evidenced():
    """An optional unit failed, so a blind spot exists — confidence is capped regardless of claim."""
    results = [_completed(CONFIDENCE_AUTHORITY, confidence_bp=9_900)]
    request = _request(metadata={"optional_failure_confidence_cap_bp": 5_000})

    assert calculate_confidence(results, request, True) == 5_000
    assert calculate_confidence(results, request, False) == 9_900


def test_a_capability_may_appoint_its_own_confidence_authority():
    results = [_completed("core.momentum", confidence_bp=7_777),
               _completed(CONFIDENCE_AUTHORITY, confidence_bp=1_000)]
    request = _request(
        specs=(ReasonerSpec("core.momentum", "1"), ReasonerSpec("core.confidence", "1")),
        metadata={CONFIDENCE_AUTHORITY_KEY: "core.momentum"})

    assert calculate_confidence(results, request, False) == 7_777


def test_a_blank_authority_is_a_manifest_fault():
    request = _request(metadata={CONFIDENCE_AUTHORITY_KEY: "   "})

    with pytest.raises(OrchestrationError, match="must name a reasoner"):
        calculate_confidence([], request, False)


def test_only_the_priority_authority_may_override_ranking():
    """An override replaces weighted utility outright — no unit may seize that by emitting it."""
    results = [_completed("core.risk", urgency_bp=1_000, priority_override_bp=10_000),
               _completed(PRIORITY_AUTHORITY, urgency_bp=8_000)]

    urgency, override = priority_metrics(results, _request())

    assert urgency == 8_000
    assert override is None


def test_the_priority_authority_override_is_honoured():
    results = [_completed(PRIORITY_AUTHORITY, urgency_bp=8_000, priority_override_bp=6_500)]

    assert priority_metrics(results, _request()) == (8_000, 6_500)


def test_urgency_defaults_to_neutral_when_unobserved():
    assert priority_metrics([], _request()) == (5_000, None)


# ---------------------------------------------------------------------------------------------
# Synthesis, evaluation, ranking
# ---------------------------------------------------------------------------------------------

def test_elimination_happens_before_ranking():
    blocked = _play("blocked_high_value", impact=10_000, success=10_000, effort=0, risk=0)
    allowed = _play("allowed_lower_value", impact=2_000, success=2_000, effort=8_000, risk=8_000)
    results = [ReasonerResult(
        reasoner_id="core.constraint", reasoner_version="1", status=ResultStatus.COMPLETED,
        matched=True,
        checks=(CandidateCheck(play_id=blocked.play_id, stage="policy",
                               outcome=CheckOutcome.ELIMINATE, reason_code="tenant_policy_block",
                               evaluator_id="core.constraint", evaluator_version="1"),))]

    candidates, _ = build_candidates(_request(plays=(blocked, allowed)), results, False)
    by_play = {item.play_id: item for item in candidates}

    assert by_play[blocked.play_id].disposition == CandidateDisposition.ELIMINATED
    assert by_play[blocked.play_id].rank_position is None
    assert by_play[allowed.play_id].rank_position == 1
    # The reason it lost is preserved on the candidate, not discarded with it.
    assert by_play[blocked.play_id].checks[0].reason_code == "tenant_policy_block"


def test_effort_and_risk_are_costs_not_merits():
    cheap = _play("cheap", impact=5_000, success=5_000, effort=0, risk=0)
    costly = _play("costly", impact=5_000, success=5_000, effort=10_000, risk=10_000)

    candidates, _ = build_candidates(_request(plays=(cheap, costly)), [], False)
    by_play = {item.play_id: item for item in candidates}

    assert by_play["cheap"].utility_bp > by_play["costly"].utility_bp
    assert by_play["cheap"].rank_position == 1


def test_an_adjustment_moves_a_component_and_is_clamped():
    results = [ReasonerResult(
        reasoner_id="core.risk", reasoner_version="1", status=ResultStatus.COMPLETED, matched=True,
        adjustments=(CandidateAdjustment(play_id="restore_momentum", component="risk",
                                         delta_bp=-10_000, reason_code="play_mitigates_risk"),))]

    candidates, _ = build_candidates(_request(), results, False)

    assert candidates[0].score_components["risk"] == 0     # clamped at the floor, never negative


def test_equal_utility_is_broken_by_play_id_not_iteration_order():
    candidates, _ = build_candidates(
        _request(plays=(_play("zeta_play"), _play("alpha_play"))), [], False)

    assert [item.play_id for item in candidates] == ["alpha_play", "zeta_play"]
    assert [item.rank_position for item in candidates] == [1, 2]


def test_every_candidate_carries_the_whole_evidential_basis():
    """A candidate cites what the run stood on, not one unit's slice of it."""
    results = [
        ReasonerResult("core.temporal", "1", ResultStatus.COMPLETED, matched=True,
                       evidence_ids=("ev_b",)),
        ReasonerResult("core.relationship", "1", ResultStatus.COMPLETED, matched=True,
                       evidence_ids=("ev_a",)),
    ]

    assert aggregate_evidence(results) == ("ev_a", "ev_b")


def test_all_candidates_eliminated_blocks_rather_than_decides():
    play = _play("only_option")
    results = [ReasonerResult(
        "core.constraint", "1", ResultStatus.COMPLETED, matched=True,
        checks=(CandidateCheck(play_id=play.play_id, stage="policy",
                               outcome=CheckOutcome.ELIMINATE, reason_code="tenant_policy_block",
                               evaluator_id="core.constraint", evaluator_version="1"),))]

    synthesis = DecisionMaker().decide(
        _request(plays=(play,)), results, terminal=None, uncertainty=(), degraded=False)

    assert synthesis.decision.outcome == DecisionOutcome.BLOCKED
    assert synthesis.decision.selected_candidate_id is None


# ---------------------------------------------------------------------------------------------
# Terminal runs
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("terminal", [
    DecisionOutcome.NO_ACTION,
    DecisionOutcome.FAILED,
    DecisionOutcome.INSUFFICIENT_CONTEXT,
])
def test_a_terminal_run_publishes_no_candidate_field(terminal):
    """Ranking plays no unit ever validated would be exactly the fabrication L4 exists to prevent."""
    synthesis = DecisionMaker().decide(
        _request(), [], terminal=terminal, uncertainty=("deal.owner",), degraded=False)

    assert synthesis.candidates == ()
    assert synthesis.decision.outcome == terminal
    assert synthesis.decision.selected_candidate_id is None
    assert synthesis.decision.uncertainty == ("deal.owner",)


def test_a_decision_records_what_happens_if_it_is_ignored():
    synthesis = DecisionMaker().decide(
        _request(), [_completed(CONFIDENCE_AUTHORITY, confidence_bp=8_000)],
        terminal=None, uncertainty=(), degraded=False)

    assert synthesis.decision.outcome == DecisionOutcome.DECISION
    assert synthesis.decision.do_nothing_consequence
    assert synthesis.decision.expires_at > NOW


# ---------------------------------------------------------------------------------------------
# The confidence floor — where GeniOS stops recommending and starts asking
# ---------------------------------------------------------------------------------------------

def _decide(confidence_bp: int, floor_bp: int | None):
    metadata = {} if floor_bp is None else {CONFIDENCE_FLOOR_KEY: floor_bp}
    return DecisionMaker().decide(
        _request(metadata=metadata),
        [_completed(CONFIDENCE_AUTHORITY, confidence_bp=confidence_bp)],
        terminal=None, uncertainty=(), degraded=False)


def test_a_weakly_evidenced_winner_becomes_a_question_not_a_recommendation():
    synthesis = _decide(confidence_bp=4_000, floor_bp=6_500)

    assert synthesis.decision.outcome == DecisionOutcome.DEFER
    assert synthesis.decision.selected_candidate_id is None
    assert any(item.startswith(BELOW_FLOOR_REASON)
               for item in synthesis.decision.uncertainty)


def test_an_ask_still_shows_what_was_considered():
    """A human asked to decide needs the candidate field; withholding it just hides the reasoning."""
    synthesis = _decide(confidence_bp=4_000, floor_bp=6_500)

    assert len(synthesis.candidates) == 1
    assert synthesis.candidates[0].disposition == CandidateDisposition.ELIGIBLE
    assert synthesis.candidates[0].rank_position == 1


def test_confidence_at_the_floor_still_decides():
    """The floor is a minimum, not a margin — exactly meeting it is meeting it."""
    assert _decide(confidence_bp=6_500, floor_bp=6_500).decision.outcome \
        == DecisionOutcome.DECISION


def test_a_capability_without_a_floor_is_unchanged():
    """Absent declaration disables the gate entirely, so existing capabilities keep their behavior."""
    assert _decide(confidence_bp=1, floor_bp=None).decision.outcome == DecisionOutcome.DECISION


def test_the_floor_cannot_manufacture_a_decision_from_a_terminal_run():
    synthesis = DecisionMaker().decide(
        _request(metadata={CONFIDENCE_FLOOR_KEY: 9_000}), [],
        terminal=DecisionOutcome.NO_ACTION, uncertainty=(), degraded=False)

    assert synthesis.decision.outcome == DecisionOutcome.NO_ACTION


def test_an_asked_decision_can_never_authorize_delivery():
    """DEFER is not DECISION, so the delivery authority boundary refuses it by construction."""
    synthesis = _decide(confidence_bp=4_000, floor_bp=6_500)

    assert synthesis.decision.outcome != DecisionOutcome.DECISION
    assert synthesis.decision.selected_candidate_id is None


def test_a_malformed_floor_is_a_manifest_fault():
    with pytest.raises(OrchestrationError, match="integer basis points"):
        _decide(confidence_bp=5_000, floor_bp=20_000)


def test_decision_maker_requires_a_version():
    with pytest.raises(ValueError, match="version is required"):
        DecisionMaker(version="   ")


# ---------------------------------------------------------------------------------------------
# The six components, exercised individually — the point of separating them
# ---------------------------------------------------------------------------------------------

def test_the_synthesizer_scores_every_exposed_operation():
    """Law 02: domain expertise exposes operations, the Decision Maker judges them."""
    request = _request(plays=(_play("alpha"), _play("zeta")))

    proposals = synthesize_candidates(request, [], urgency_bp=5_000, priority_override=None)

    assert [item.play.play_id for item in proposals] == ["alpha", "zeta"]
    assert all(item.utility_bp > 0 for item in proposals)


def test_a_unit_moves_a_candidate_only_through_a_typed_adjustment():
    request = _request()
    adjustment = CandidateAdjustment(play_id="restore_momentum", component="impact",
                                     delta_bp=3_000, reason_code="high_value_account")

    plain = synthesize_candidates(request, [], 5_000, None)[0]
    moved = synthesize_candidates(request, [adjustment], 5_000, None)[0]

    assert moved.components["impact"] == plain.components["impact"] + 3_000
    assert moved.utility_bp > plain.utility_bp


def test_an_override_replaces_the_formula_entirely():
    request = _request()

    assert synthesize_candidates(request, [], 5_000, 7_777)[0].utility_bp == 7_777


def test_the_evaluator_eliminates_without_reordering():
    request = _request(plays=(_play("alpha"), _play("zeta")))
    check = CandidateCheck(play_id="alpha", stage="policy", outcome=CheckOutcome.ELIMINATE,
                           reason_code="blocked", evaluator_id="core.policy",
                           evaluator_version="1")

    judged = evaluate_candidates(synthesize_candidates(request, [], 5_000, None), [check])
    by_play = {item.play.play_id: item for item in judged}

    assert by_play["alpha"].disposition == CandidateDisposition.ELIMINATED
    assert by_play["zeta"].disposition == CandidateDisposition.ELIGIBLE
    assert [item.play.play_id for item in judged] == ["alpha", "zeta"]   # order untouched


def test_the_ranker_puts_survivors_first_and_the_eliminated_last():
    request = _request(plays=(_play("weak", impact=1_000), _play("strong", impact=9_000),
                              _play("blocked", impact=10_000)))
    check = CandidateCheck(play_id="blocked", stage="policy", outcome=CheckOutcome.ELIMINATE,
                           reason_code="blocked", evaluator_id="core.policy",
                           evaluator_version="1")
    judged = evaluate_candidates(synthesize_candidates(request, [], 5_000, None), [check])

    ranked = rank_candidates(judged)

    assert [item.play.play_id for item in ranked] == ["strong", "weak", "blocked"]
    assert [item.rank_position for item in ranked] == [1, 2, None]


def test_the_object_builder_carries_the_delivery_authority_bit():
    request = _request()
    ranked = rank_candidates(evaluate_candidates(
        synthesize_candidates(request, [], 5_000, None), []))

    candidates = build_candidate_objects(ranked, confidence_bp=8_000, evidence=("ev_1",))

    assert candidates[0].parameters["read_only"] is True
    assert candidates[0].confidence_bp == 8_000
    assert candidates[0].evidence_ids == ("ev_1",)


def test_the_pipeline_and_its_parts_agree():
    """store.py re-runs this exact pipeline to verify audit rows; the parts must compose to it."""
    request = _request(plays=(_play("alpha"), _play("zeta")))
    results = [_completed(CONFIDENCE_AUTHORITY, confidence_bp=8_000)]

    whole, confidence = build_candidates(request, results, False)
    piecewise = build_candidate_objects(
        rank_candidates(evaluate_candidates(
            synthesize_candidates(request, [], 5_000, None), [])),
        confidence, ())

    assert [item.semantic_hash for item in whole] == [item.semantic_hash for item in piecewise]
