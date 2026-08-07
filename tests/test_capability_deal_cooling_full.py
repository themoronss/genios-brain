"""Executable contract for ``sales.deal_cooling_full`` — the roster deployed on real expertise.

The seventeen units are only worth building if a real capability can actually reason through them.
These tests prove that, and pin the properties that make v2 safe to run beside v1:

* it reaches the same decision as v1 on a clear-cut situation — more units must not mean a
  different answer, only a better-explained one;
* it sees things v1 is structurally blind to, and can say what they are;
* it inherits v1's expertise rather than re-deriving it, so tuning a threshold cannot drift;
* it degrades instead of blocking when a situation cannot feed an optional unit;
* it still fails closed on the things that must fail closed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    FailurePolicy,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.packs.capabilities.deal_cooling_v2 import DEAL_COOLING_FULL_V2
from genios_engine.reason.decision_maker import CONFIDENCE_FLOOR_KEY
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.plan import LATENCY_CEILING_KEY
from genios_engine.reason.publication import build_native_publication
from genios_engine.reason.reasoners import CORE_UNITS, default_registry

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
INBOUND = (NOW - timedelta(days=10)).isoformat()


def _bundle() -> dict:
    """The shape `persist_execution` returns — enough of it for the publication projection."""
    return {"run": {"run_id": "run_1"},
            "output": {"selected_candidate_id": "cand_1", "decision_hash": "hash_1"}}


def _context(*, with_evidence: bool = True) -> ContextSnapshot:
    """A $500k deal, open, engagement halved, buyer silent for ten days."""
    facts = {
        "deal.status": {"value": "open"},
        "deal.value": {"value": 500_000},
        "derived.engagement": {"value_bp": 4_000},
        "thread.last_inbound": {"value": INBOUND},
        "relationship.verified_stakeholder_count": {"value": 2},
    }
    evidence = (
        EvidenceRef("ev_status", "deal.status", "open", source_ref_id="crm_1",
                    occurred_at=NOW - timedelta(days=1), confidence_bp=9_500,
                    authority_rank=3, independence_group="crm"),
        EvidenceRef("ev_value", "deal.value", 500_000, source_ref_id="crm_1",
                    occurred_at=NOW - timedelta(days=1), confidence_bp=9_500,
                    authority_rank=3, independence_group="crm"),
        EvidenceRef("ev_engagement", "derived.engagement", 4_000, source_ref_id="derived_1",
                    occurred_at=NOW - timedelta(hours=6), confidence_bp=8_500,
                    authority_rank=2, independence_group="derived"),
        EvidenceRef("ev_inbound", "thread.last_inbound", INBOUND, source_ref_id="gmail_1",
                    occurred_at=NOW - timedelta(days=10), confidence_bp=9_000,
                    authority_rank=3, independence_group="gmail"),
        EvidenceRef("ev_stakeholders", "relationship.verified_stakeholder_count", 2,
                    source_ref_id="crm_1", occurred_at=NOW - timedelta(days=2),
                    confidence_bp=9_000, authority_rank=3, independence_group="crm"),
    ) if with_evidence else ()
    return ContextSnapshot(
        org_id="org_1", graph_version=21, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="deal_cooling.selector.v1",
        facts=facts, evidence=evidence,
        neighbor_facts={"deal.status": "open", "contact.verified_recipient": True,
                        "account.alternate_stakeholder_verified": True},
        edge_count=2)


def _request(capability, context=None) -> ReasoningRequest:
    return ReasoningRequest(
        org_id="org_1", capability=capability, context=context or _context(),
        evaluation_time=NOW, trigger_kind="email.received", config_snapshot_id="cfg_1")


@pytest.fixture(scope="module")
def orchestrator():
    return ReasoningOrchestrator(default_registry())


@pytest.fixture(scope="module")
def v2(orchestrator):
    return orchestrator.execute(_request(DEAL_COOLING_FULL_V2))


@pytest.fixture(scope="module")
def v1(orchestrator):
    return orchestrator.execute(_request(DEAL_COOLING_V1))


def test_the_capability_names_the_whole_roster():
    named = {spec.reasoner_id for spec in DEAL_COOLING_FULL_V2.reasoners}
    roster = {unit().spec.reasoner_id for unit in CORE_UNITS}

    assert roster <= named, f"roster units the capability never schedules: {sorted(roster - named)}"


def test_more_units_do_not_change_a_clear_cut_answer(v1, v2):
    """The point of the extra twelve is better reasoning, not a different verdict on an easy call.
    A roster that flipped obvious decisions would be a regression, however sophisticated."""
    assert v1.decision.outcome == v2.decision.outcome == DecisionOutcome.DECISION
    assert v1.selected_candidate.play_id == v2.selected_candidate.play_id == "restore_momentum"
    assert v2.selected_candidate.rank_position == 1


def test_v2_sees_what_v1_is_blind_to(v1, v2):
    """Name the gain concretely: these readings simply do not exist in the seven-unit run."""
    added = set(v2.result_by_id) - set(v1.result_by_id)

    assert {"core.opportunity", "core.scheduling", "core.validation",
            "core.tradeoff", "core.cost", "core.timeline"} <= added
    # And they actually produced readings rather than sitting inert.
    assert v2.result_by_id["core.opportunity"].metrics["opportunity_bp"] > 0
    assert v2.result_by_id["core.tradeoff"].metrics["tension_bp"] > 0
    assert v2.result_by_id["core.timeline"].metrics["elapsed_hours"] == 240


def test_the_new_units_move_the_score_they_were_authored_to_move(v1, v2):
    """core.impact and core.cost carry authored per-play adjustments; if the wiring were dead the
    utilities would be identical and nobody would notice."""
    by_play_v1 = {item.play_id: item.utility_bp for item in v1.candidates}
    by_play_v2 = {item.play_id: item.utility_bp for item in v2.candidates}

    assert by_play_v2["restore_momentum"] > by_play_v1["restore_momentum"]


def test_expertise_is_inherited_not_re_derived():
    """Two sources of truth for one threshold is how tuning silently half-lands."""
    v1_specs = {spec.reasoner_id: spec.config for spec in DEAL_COOLING_V1.reasoners}
    v2_specs = {spec.reasoner_id: spec.config for spec in DEAL_COOLING_FULL_V2.reasoners}

    for reasoner_id, config in v1_specs.items():
        assert v2_specs[reasoner_id] == config, f"{reasoner_id} config drifted from v1"
    assert DEAL_COOLING_FULL_V2.plays == DEAL_COOLING_V1.plays
    assert DEAL_COOLING_FULL_V2.policies == DEAL_COOLING_V1.policies
    assert DEAL_COOLING_FULL_V2.ranking_weights == DEAL_COOLING_V1.ranking_weights


def test_the_added_units_degrade_rather_than_block(v2):
    """Only judgement the decision cannot honestly proceed without is REQUIRED. Everything else
    must be able to fail without denying the buyer an answer they are waiting for."""
    by_id = {spec.reasoner_id: spec for spec in DEAL_COOLING_FULL_V2.reasoners}

    assert by_id["core.opportunity"].failure_policy == FailurePolicy.OPTIONAL
    assert by_id["core.scheduling"].failure_policy == FailurePolicy.OPTIONAL
    assert by_id["core.validation"].failure_policy == FailurePolicy.REQUIRED
    assert by_id["core.risk"].failure_policy == FailurePolicy.REQUIRED


def test_the_plan_fits_the_declared_ceiling(v2):
    ceiling = DEAL_COOLING_FULL_V2.metadata[LATENCY_CEILING_KEY]

    assert v2.plan.sequential_budget_ms <= ceiling
    assert v2.plan.critical_path_budget_ms < v2.plan.sequential_budget_ms
    assert v2.plan.stage_count >= 4               # understand → evaluate → optimise → support


def test_understanding_is_scheduled_before_what_consumes_it(v2):
    stage = {step.reasoner_id: step.stage for step in v2.plan.steps}

    assert stage["core.temporal"] < stage["core.risk"]
    assert stage["core.risk"] < stage["core.tradeoff"]
    assert stage["core.validation"] < stage["core.recommendation"]


def test_every_scheduled_unit_completes(v2):
    incomplete = [item.reasoner_id for item in v2.ordered_results
                  if item.status != ResultStatus.COMPLETED]

    assert not incomplete, f"units did not complete: {incomplete}"


def test_advice_without_evidence_is_refused(orchestrator):
    """The capability declares `evidence_required`; an ungrounded run must produce no winner."""
    execution = orchestrator.execute(
        _request(DEAL_COOLING_FULL_V2, _context(with_evidence=False)))

    assert execution.decision.outcome == DecisionOutcome.BLOCKED
    assert execution.decision.selected_candidate_id is None
    assert execution.authorizes_delivery is False


def test_the_capability_declares_a_confidence_floor():
    """Without a floor the ASK path is unreachable, so the declaration is the feature."""
    floor = DEAL_COOLING_FULL_V2.metadata[CONFIDENCE_FLOOR_KEY]

    assert isinstance(floor, int) and 0 < floor <= 10_000


def test_the_capability_is_activated_for_delivery(v2):
    """v2 is the live roster now. The flag lives in the frozen manifest bytes the authority
    predicate reads, so it is asserted on the manifest and on the execution that derives from it."""
    assert DEAL_COOLING_FULL_V2.live_delivery_enabled is True
    assert v2.request.mode == ExecutionMode.LIVE
    assert v2.decision.outcome == DecisionOutcome.DECISION
    assert v2.authorizes_delivery is True


def test_a_shadow_run_of_the_same_capability_still_cannot_deliver(orchestrator):
    """Activation is per run, not per capability. A shadow sweep of a delivery-enabled capability
    must stay silent — otherwise there is no way left to observe it without publishing."""
    shadow = orchestrator.execute(
        ReasoningRequest(org_id="org_1", capability=DEAL_COOLING_FULL_V2, context=_context(),
                         evaluation_time=NOW, trigger_kind="email.received",
                         config_snapshot_id="cfg_1", mode=ExecutionMode.SHADOW))

    assert shadow.decision.outcome == DecisionOutcome.DECISION
    assert shadow.authorizes_delivery is False
    assert build_native_publication(execution=shadow, audit_bundle=_bundle()) is None


def test_delivery_never_means_permission_to_mutate_anything(v2):
    """The one authority GeniOS v1 does not grant, at any confidence, in any mode."""
    assert v2.authorizes_external_mutation is False


def test_the_run_is_replayable(orchestrator, v2):
    again = orchestrator.execute(_request(DEAL_COOLING_FULL_V2))

    assert again.decision.semantic_hash == v2.decision.semantic_hash
    assert again.trace.semantic_hash == v2.trace.semantic_hash
