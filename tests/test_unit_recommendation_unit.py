"""Executable contract for the Recommendation Unit (`core.recommendation`).

The unit sits on the most dangerous boundary in Layer 4: it prepares everything needed to choose,
and must never choose. These tests pin the properties that keep it on the safe side of that line,
and the properties that make the case it assembles worth relying on:

* **It assembles, it never selects.** No metric names a play, no reason code names a winner, and
  the findings come back in play-id order — never in support order.
* **Linkage is declared, never inferred.** With no capability wiring the unit reports no support at
  all rather than guessing which observation argues for which play.
* **Absence is not zero.** A unit that failed, a finding its own author marked unmatched, and a
  capability that declared nothing all produce silence, not manufactured support.
* **The case names its sources and its evidence.** An explanation that cannot say who argued for a
  play, and on what, is an explanation nobody can check.
* **Metric authority is respected.** It never publishes confidence, urgency, or a priority override.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    EvidenceRef,
    Finding,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.recommendation_unit import (
    SUPPORT_ADJUSTMENT_REASON,
    ActionReadinessPlugin,
    EvidenceLinkagePlugin,
    PlaySupportPlugin,
    RecommendationUnit,
)
from genios_engine.reason.unit import UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)

INBOUND_AT = "2026-08-01T09:00:00+00:00"


# ---------------------------------------------------------------------------------------------
# Fixtures: a real capability, a real snapshot, real prior results
# ---------------------------------------------------------------------------------------------

def _play(play_id: str, *, tags=(), preconditions=()) -> PlayDefinition:
    return PlayDefinition(
        play_id=play_id,
        version="1",
        label=play_id.replace("_", " ").title(),
        steps=("Prepare a grounded draft",),
        tags=tuple(tags),
        preconditions=tuple(preconditions),
    )


def _request(*, plays=None, config=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.recommendation", "1.0.0", config=config or {}),
                   ReasonerSpec("core.constraint", "1.0.0")),
        plays=tuple(plays or (_play("reply_to_buyer", tags=("inbound_awaiting_reply",)),)),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts={"deal.status": "open",
               "deal.last_inbound": INBOUND_AT,
               "legal.review_status": "pending"},
        evidence=(
            EvidenceRef("ev_inbound", "deal.last_inbound", INBOUND_AT),
            EvidenceRef("ev_status", "deal.status", "open"),
            EvidenceRef("ev_gate", "legal.review_status", "pending"),
        ),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _completed(reasoner_id: str, *, findings=(), checks=(), matched=True, **metrics
               ) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1",
                          status=ResultStatus.COMPLETED, matched=matched, metrics=metrics,
                          findings=tuple(findings), checks=tuple(checks),
                          reason_codes=tuple({code for item in findings
                                              for code in item.reason_codes}))


def _claim(reasoner_id: str, *codes: str, evidence=(), matched=True) -> ReasonerResult:
    """A prior unit that published one finding carrying `codes` — the normal shape."""
    return _completed(reasoner_id, findings=(Finding(
        finding_id=f"{reasoner_id}.claim", kind="observation", matched=matched,
        evidence_ids=tuple(evidence), reason_codes=codes),))


def _view(prior=(), *, plays=None, config=None) -> UnitView:
    request = _request(plays=plays, config=config)
    return UnitView(request=request, spec=request.capability.reasoners[0],
                    prior={item.reasoner_id: item for item in prior})


def _codes(observation) -> set[str]:
    return set(observation.reason_codes)


def _by_play(observations):
    return {code[len("play:"):]: item for item in observations
            for code in item.reason_codes if code.startswith("play:")}


# ---------------------------------------------------------------------------------------------
# Support aggregation — the join nothing else in the layer builds
# ---------------------------------------------------------------------------------------------

def test_a_capability_with_no_declared_linkage_reports_no_support_at_all():
    """Guessing which observation argues for which play would be confident and wrong."""
    view = _view([_claim("core.opportunity", "inbound_awaiting_reply")],
                 plays=(_play("reply_to_buyer"),))

    assert PlaySupportPlugin().contribute(view) == ()
    assert EvidenceLinkagePlugin().contribute(view) == ()


def test_a_play_tag_is_enough_to_join_a_published_finding_to_a_play():
    """Layer 3 authors the join on the play; Layer 4 only measures what it joined."""
    view = _view([_claim("core.opportunity", "inbound_awaiting_reply", evidence=("ev_inbound",))])

    observation, = PlaySupportPlugin().contribute(view)

    assert observation.metrics["support_bp"] == 5_000        # the unpriced default weight
    assert observation.metrics["supporting_unit_count"] == 1
    assert {"play:reply_to_buyer", "inbound_awaiting_reply", "support.single_source"} \
        <= _codes(observation)


def test_two_independent_units_argue_more_strongly_than_one():
    """Corroboration is the whole point of a multi-unit layer, and must show up in the number."""
    view = _view([_claim("core.opportunity", "inbound_awaiting_reply"),
                  _claim("core.temporal", "inbound_awaiting_reply")])

    observation, = PlaySupportPlugin().contribute(view)

    assert observation.metrics["support_bp"] == 6_250        # 5000 + 5000/4, bounded lift
    assert observation.metrics["supporting_unit_count"] == 2
    assert "support.corroborated" in _codes(observation)


def test_one_unit_matching_several_codes_is_still_one_voice():
    """Otherwise a verbose reasoner could out-argue a second independent source by itself."""
    loud = _completed("core.opportunity", findings=(
        Finding("opportunity.a", "opportunity", True, reason_codes=("inbound_awaiting_reply",)),
        Finding("opportunity.b", "opportunity", True,
                reason_codes=("open_deal_without_momentum",))))
    view = _view([loud], plays=(_play("reply_to_buyer", tags=(
        "inbound_awaiting_reply", "open_deal_without_momentum")),))

    observation, = PlaySupportPlugin().contribute(view)

    assert observation.metrics["supporting_claim_count"] == 2
    assert observation.metrics["supporting_unit_count"] == 1
    assert observation.metrics["support_bp"] == 5_000        # no corroboration lift from one unit


def test_a_finding_its_own_author_marked_unmatched_is_not_support():
    """A unit that declined to make a claim must never have that absence argue for a play."""
    view = _view([_claim("core.opportunity", "inbound_awaiting_reply", matched=False)])

    observation, = PlaySupportPlugin().contribute(view)

    assert observation.metrics["support_bp"] == 0
    assert "support.absent" in _codes(observation)


def test_a_unit_that_did_not_complete_contributes_nothing():
    """A crashed reasoner has no opinion; reading its codes anyway would fabricate a case."""
    view = _view([ReasonerResult("core.opportunity", "1", ResultStatus.FAILED,
                                 reason_codes=("reasoner_failure",))])

    observation, = PlaySupportPlugin().contribute(view)

    assert observation.metrics["supporting_claim_count"] == 0


def test_a_reasoner_that_publishes_codes_without_findings_still_counts():
    """The older corpus publishes result-level codes only; dropping it would un-support half of it."""
    view = _view([ReasonerResult("core.risk", "1", ResultStatus.COMPLETED, matched=True,
                                 evidence_ids=("ev_status",),
                                 reason_codes=("inbound_awaiting_reply",))])

    observation, = PlaySupportPlugin().contribute(view)

    assert observation.metrics["supporting_unit_count"] == 1


def test_a_capability_can_price_the_arguments_it_cares_about():
    """Not every observation is the same size of argument, and only the author knows which."""
    prior = [_claim("core.opportunity", "inbound_awaiting_reply")]

    default, = PlaySupportPlugin().contribute(_view(prior))
    priced, = PlaySupportPlugin().contribute(
        _view(prior, config={"support_weight_bp": {"inbound_awaiting_reply": 9_000}}))

    assert default.metrics["support_bp"] == 5_000
    assert priced.metrics["support_bp"] == 9_000


def test_a_malformed_support_price_is_a_manifest_fault():
    with pytest.raises(ValueError, match="basis points"):
        PlaySupportPlugin().contribute(_view(
            [_claim("core.opportunity", "inbound_awaiting_reply")],
            config={"support_weight_bp": {"inbound_awaiting_reply": 25_000}}))


def test_an_unwired_play_is_distinguished_from_an_unsupported_one():
    """One is an authoring gap and one is a fact about the deal; the operator fixes them differently."""
    view = _view([_claim("core.opportunity", "inbound_awaiting_reply")],
                 plays=(_play("reply_to_buyer", tags=("inbound_awaiting_reply",)),
                        _play("escalate", tags=("relationship_single_threaded",)),
                        _play("unwired")))

    cases = _by_play(PlaySupportPlugin().contribute(view))

    assert "support.absent" in _codes(cases["escalate"])
    assert "support.unlinked" in _codes(cases["unwired"])


# ---------------------------------------------------------------------------------------------
# Evidence linkage — what the case actually stands on
# ---------------------------------------------------------------------------------------------

def test_the_case_carries_the_snapshot_rows_it_stands_on():
    """A card that cannot cite its sources cannot be checked by the person reading it."""
    view = _view([_claim("core.opportunity", "inbound_awaiting_reply", evidence=("ev_inbound",)),
                  _claim("core.temporal", "inbound_awaiting_reply", evidence=("ev_status",))])

    observation, = EvidenceLinkagePlugin().contribute(view)

    assert observation.metrics["evidence_count"] == 2
    assert observation.evidence_ids == ("ev_inbound", "ev_status")
    assert "evidence_linked" in _codes(observation)


def test_support_that_cites_nothing_is_disclosed_rather_than_hidden():
    """Two units agreeing about nothing citable is a different situation from two sourced claims."""
    view = _view([_claim("core.opportunity", "inbound_awaiting_reply", evidence=("ev_inbound",)),
                  _claim("core.temporal", "inbound_awaiting_reply")])

    observation, = EvidenceLinkagePlugin().contribute(view)

    assert observation.metrics["unevidenced_support_count"] == 1
    assert "support_without_evidence" in _codes(observation)


def test_a_play_with_no_support_has_no_evidence_to_trace():
    """Reporting '0 evidence' would double-count the absence the support plugin already reported."""
    view = _view([], plays=(_play("escalate", tags=("relationship_single_threaded",)),))

    assert EvidenceLinkagePlugin().contribute(view) == ()


# ---------------------------------------------------------------------------------------------
# Readiness — could this actually be started?
# ---------------------------------------------------------------------------------------------

def test_a_play_that_declares_no_preconditions_is_fully_ready():
    """The play is the authority on what it needs; inventing requirements would be fabrication."""
    observation, = ActionReadinessPlugin().contribute(_view(plays=(_play("reply_to_buyer"),)))

    assert observation.metrics["readiness_bp"] == 10_000
    assert "readiness.unconditional" in _codes(observation)


def test_a_precondition_on_a_fact_layer_two_never_supplied_lowers_readiness():
    """A strong case for work whose inputs are absent must not read as ready to run."""
    play = _play("reply_to_buyer", preconditions=(
        {"field": "deal.last_inbound", "op": "exists"},
        {"field": "contact.email", "op": "exists"}))

    observation, = ActionReadinessPlugin().contribute(_view(plays=(play,)))

    assert observation.metrics["precondition_count"] == 2
    assert observation.metrics["observable_precondition_count"] == 1
    assert observation.metrics["readiness_bp"] == 5_000
    assert "readiness.inputs_missing" in _codes(observation)
    assert observation.evidence_ids == ("ev_inbound",)


def test_a_play_already_eliminated_upstream_is_never_presented_as_ready():
    """Showing a human a ready play that a constraint unit already ruled out is a contradiction."""
    blocked = _completed("core.constraint", checks=(CandidateCheck(
        play_id="reply_to_buyer", stage="policy", outcome=CheckOutcome.ELIMINATE,
        reason_code="tenant_policy_block", evaluator_id="core.constraint",
        evaluator_version="1"),))

    observation, = ActionReadinessPlugin().contribute(_view([blocked]))

    assert observation.metrics["readiness_bp"] == 0
    assert observation.metrics["blocked"] == 1
    assert "readiness.blocked_upstream" in _codes(observation)


def test_readiness_cannot_exceed_the_freedom_the_dependency_unit_measured():
    """Readable preconditions are no comfort when a named blocker sits in front of the work."""
    observation, = ActionReadinessPlugin().contribute(
        _view([_completed("core.dependency", unblocked_bp=3_000)]))

    assert observation.metrics["readiness_bp"] == 3_000
    assert "readiness.limited_by_dependency" in _codes(observation)


def test_an_absent_dependency_unit_is_not_read_as_total_blockage():
    """A unit that never ran is a blind spot; treating it as zero freedom would freeze every play."""
    observation, = ActionReadinessPlugin().contribute(_view())

    assert observation.metrics["readiness_bp"] == 10_000


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_the_unit_satisfies_the_reasoner_protocol():
    assert isinstance(RecommendationUnit(), Reasoner)


def test_a_run_with_no_linkage_publishes_no_support_metric_rather_than_a_zero():
    """A published `support_strength_bp = 0` would read as 'nothing supports anything here'."""
    result = RecommendationUnit().evaluate(_request(plays=(_play("reply_to_buyer"),)), {})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is None                 # no opinion, not a negative opinion
    assert "support_strength_bp" not in result.metrics
    assert result.metrics["declared_play_count"] == 1


def test_every_declared_play_keeps_a_finding_even_when_nothing_supports_it():
    """What was considered and found wanting is part of an honest explanation."""
    request = _request(plays=(_play("reply_to_buyer", tags=("inbound_awaiting_reply",)),
                              _play("escalate", tags=("relationship_single_threaded",))))
    prior = {"core.opportunity": _claim("core.opportunity", "inbound_awaiting_reply")}

    result = RecommendationUnit().evaluate(request, prior)
    by_id = {item.finding_id: item for item in result.findings}

    assert set(by_id) == {"recommendation.reply_to_buyer", "recommendation.escalate"}
    assert by_id["recommendation.escalate"].matched is False
    assert by_id["recommendation.escalate"].metrics["support_bp"] == 0


def test_findings_are_ordered_by_play_id_and_never_by_strength():
    """Ordering output by strength would be a ranking, whatever the docstring claimed."""
    request = _request(plays=(
        _play("zeta_play", tags=("inbound_awaiting_reply",)),
        _play("alpha_play", tags=("relationship_single_threaded",)),
        _play("mid_play", tags=("open_deal_without_momentum",))))
    prior = {item.reasoner_id: item for item in (
        _claim("core.opportunity", "inbound_awaiting_reply"),
        _claim("core.temporal", "inbound_awaiting_reply"),
        _claim("core.risk", "open_deal_without_momentum"))}

    result = RecommendationUnit().evaluate(request, prior)

    assert [item.finding_id for item in result.findings] == [
        "recommendation.alpha_play", "recommendation.mid_play", "recommendation.zeta_play"]
    # zeta holds the strongest case and is still reported last — position carries no meaning.
    assert result.findings[-1].metrics["support_bp"] == 6_250
    assert result.metrics["support_strength_bp"] == 6_250


def test_the_unit_never_names_a_winner():
    """The single boundary this unit exists to respect: it prepares the choice, it never makes it."""
    request = _request(plays=(_play("reply_to_buyer", tags=("inbound_awaiting_reply",)),
                              _play("escalate", tags=("relationship_single_threaded",))))
    result = RecommendationUnit().evaluate(
        request, {"core.opportunity": _claim("core.opportunity", "inbound_awaiting_reply")})

    # No metric names a play, so no consumer can read a selection out of the published numbers.
    for name in result.metrics:
        assert "reply_to_buyer" not in name and "escalate" not in name
    # No unit-level reason code names a play or recommends one.
    assert not any(code.startswith("play:") for code in result.reason_codes)
    assert all(not code.startswith(("recommend", "select", "winner", "rank"))
               for code in result.reason_codes)
    # And nothing here assigns a rank or eliminates a candidate.
    assert all(check.outcome == CheckOutcome.ADJUST for check in result.checks)


def test_a_well_supported_play_moves_only_the_nudge_its_author_declared():
    """The author supplies the judgement; this unit supplies only the measured magnitude."""
    request = _request(config={"play_success_bp": {"reply_to_buyer": 2_000}})
    prior = {item.reasoner_id: item for item in (
        _claim("core.opportunity", "inbound_awaiting_reply"),
        _claim("core.temporal", "inbound_awaiting_reply"))}

    result = RecommendationUnit().evaluate(request, prior)

    adjustment, = result.adjustments
    assert adjustment.play_id == "reply_to_buyer"
    assert adjustment.component == "success"
    assert adjustment.delta_bp == 1_250           # 2000 scaled by the 6250bp case
    assert adjustment.reason_code == SUPPORT_ADJUSTMENT_REASON
    check, = result.checks
    assert (check.stage, check.outcome) == ("cost_benefit", CheckOutcome.ADJUST)


def test_a_capability_that_declares_no_nudge_leaves_every_candidate_untouched():
    """Support alone must never move a score — that would be an unauthored decision authority."""
    prior = {item.reasoner_id: item for item in (
        _claim("core.opportunity", "inbound_awaiting_reply"),
        _claim("core.temporal", "inbound_awaiting_reply"))}

    result = RecommendationUnit().evaluate(_request(), prior)

    assert result.matched is True
    assert result.adjustments == ()
    assert result.checks == ()


def test_an_eliminated_play_is_never_boosted_however_strong_its_case():
    """Raising the score of a play that is out of the contest only pollutes the audit trail."""
    request = _request(config={"play_success_bp": {"reply_to_buyer": 5_000}})
    prior = {item.reasoner_id: item for item in (
        _claim("core.opportunity", "inbound_awaiting_reply"),
        _claim("core.temporal", "inbound_awaiting_reply"),
        _completed("core.constraint", checks=(CandidateCheck(
            play_id="reply_to_buyer", stage="policy", outcome=CheckOutcome.ELIMINATE,
            reason_code="tenant_policy_block", evaluator_id="core.constraint",
            evaluator_version="1"),)))}

    result = RecommendationUnit().evaluate(request, prior)

    assert result.adjustments == ()
    assert result.findings[0].metrics["support_bp"] == 6_250   # the case is still on the record


def test_a_weak_case_does_not_reach_the_authored_nudge():
    """The threshold is what stops a single unpriced hint from tilting the contest."""
    request = _request(config={"play_success_bp": {"reply_to_buyer": 4_000},
                               "support_threshold_bp": 8_000})

    result = RecommendationUnit().evaluate(
        request, {"core.opportunity": _claim("core.opportunity", "inbound_awaiting_reply")})

    assert result.metrics["supported_play_count"] == 0
    assert result.matched is False
    assert result.adjustments == ()


def test_the_unit_never_publishes_a_reserved_shared_metric():
    """Only core.confidence and core.priority own those; a second publisher re-scores everything."""
    published = set(RecommendationUnit().publishes)

    assert published.isdisjoint({"confidence_bp", "urgency_bp", "priority_override_bp"})

    result = RecommendationUnit().evaluate(
        _request(), {"core.opportunity": _claim("core.opportunity", "inbound_awaiting_reply")})

    assert set(result.metrics) <= published


def test_the_same_situation_reasons_identically_twice():
    """Replayability is the whole promise: no clock, no randomness, no iteration order."""
    request = _request(plays=(_play("zeta_play", tags=("inbound_awaiting_reply",)),
                              _play("alpha_play", tags=("inbound_awaiting_reply",))),
                       config={"play_success_bp": {"alpha_play": 1_500}})
    prior = {item.reasoner_id: item for item in (
        _claim("core.opportunity", "inbound_awaiting_reply", evidence=("ev_inbound",)),
        _claim("core.temporal", "inbound_awaiting_reply", evidence=("ev_status",)))}
    unit = RecommendationUnit()

    first = unit.evaluate(request, prior)
    second = unit.evaluate(request, prior)

    assert dict(first.metrics) == dict(second.metrics)
    assert first.reason_codes == second.reason_codes
    assert first.semantic_hash == second.semantic_hash


# ---------------------------------------------------------------------------------------------
# One real scenario, end to end
# ---------------------------------------------------------------------------------------------

def test_the_stalled_enterprise_renewal_assembles_three_cases_and_chooses_none():
    """A real situation, end to end.

    A renewal has gone quiet. The buyer wrote on 1 August and nobody answered; the deal is still
    open; legal review is pending. Three plays are declared:

      * `reply_to_buyer`  — tagged with the unanswered-inbound and stalled-deal observations,
      * `wait_for_legal`  — tagged with the pending-gate observation,
      * `escalate_to_exec`— tagged with single-threading, which nothing in this run observed.

    `core.opportunity` published both of its observations, `core.risk` published the stalled-deal
    observation without findings (the older result-level shape), and `core.dependency` published the
    pending gate plus 3,000bp of freedom to proceed. The capability prices the unanswered inbound
    at 8,000bp and the gate at 4,000bp.

    What must come out: the reply has the strongest case (two independent units, priced high), the
    gate play has a modest single-source case, the escalation has none — and *nothing is ready*,
    because the dependency unit says the work is 70% blocked. The unit reports all of that and
    still refuses to say which play to run.
    """
    request = _request(
        plays=(
            _play("reply_to_buyer",
                  tags=("inbound_awaiting_reply", "open_deal_without_momentum"),
                  preconditions=({"field": "deal.last_inbound", "op": "exists"},)),
            _play("wait_for_legal", tags=("gate_awaiting_decision",)),
            _play("escalate_to_exec", tags=("relationship_single_threaded",)),
        ),
        config={"support_weight_bp": {"inbound_awaiting_reply": 8_000,
                                      "gate_awaiting_decision": 4_000}},
    )
    prior = {item.reasoner_id: item for item in (
        _completed("core.opportunity", findings=(
            Finding("opportunity.unanswered_inbound", "opportunity", True,
                    metrics={"strength_bp": 8_200}, evidence_ids=("ev_inbound",),
                    reason_codes=("inbound_awaiting_reply",)),
            Finding("opportunity.stalled_but_open", "opportunity", True,
                    reason_codes=("open_deal_without_momentum",)))),
        ReasonerResult("core.risk", "1", ResultStatus.COMPLETED, matched=True,
                       evidence_ids=("ev_status",),
                       reason_codes=("open_deal_without_momentum",)),
        _completed("core.dependency", unblocked_bp=3_000, findings=(
            Finding("dependency.approval_gate", "dependency", True,
                    evidence_ids=("ev_gate",), reason_codes=("gate_awaiting_decision",)),)),
    )}

    result = RecommendationUnit().evaluate(request, prior)
    cases = {item.finding_id: item for item in result.findings}

    # The reply: opportunity priced at 8000 leads, risk corroborates at the 5000 default.
    reply = cases["recommendation.reply_to_buyer"]
    assert reply.metrics["support_bp"] == 9_250        # 8000 + 5000/4
    assert reply.metrics["supporting_unit_count"] == 2
    assert reply.metrics["supporting_claim_count"] == 3
    assert reply.metrics["evidence_count"] == 2
    assert reply.evidence_ids == ("ev_inbound", "ev_status")
    assert {"inbound_awaiting_reply", "open_deal_without_momentum", "support.corroborated"} \
        <= set(reply.reason_codes)

    # Waiting on legal is a real but single-source case; escalation has no case at all.
    assert cases["recommendation.wait_for_legal"].metrics["support_bp"] == 4_000
    assert cases["recommendation.escalate_to_exec"].metrics["support_bp"] == 0
    assert cases["recommendation.escalate_to_exec"].matched is False

    # The shape of the field, with no play named anywhere in it.
    assert result.metrics["declared_play_count"] == 3
    assert result.metrics["supported_play_count"] == 2
    assert result.metrics["support_strength_bp"] == 9_250
    assert result.metrics["support_coverage_bp"] == 6_667      # two of three, rounded half up
    assert result.metrics["evidence_linked_count"] == 3
    # Nothing can be started: the dependency unit caps every play's readiness at 3000bp.
    assert result.metrics["ready_play_count"] == 0
    assert reply.metrics["readiness_bp"] == 3_000

    assert result.matched is True
    assert "play_case_assembled" in result.reason_codes
    assert result.adjustments == ()                   # the capability authored no nudge
    assert result.evidence_ids == ("ev_gate", "ev_inbound", "ev_status")
