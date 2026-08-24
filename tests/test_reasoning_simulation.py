from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    ReasoningRequest,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.simulation import SimulationScenario, simulate

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _request() -> ReasoningRequest:
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=22,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="deal_cooling.selector.v1",
        facts={
            "deal.status": {"value": "open", "confidence_bp": 9_500, "src_count": 2},
            "deal.value": {"value": 500_000, "confidence_bp": 9_500, "src_count": 2},
            "derived.engagement": {"value_bp": 4_000, "confidence_bp": 8_500,
                                   "src_count": 2},
            "thread.last_inbound": {"value": (NOW - timedelta(days=10)).isoformat(),
                                    "confidence_bp": 9_000, "src_count": 2},
            "relationship.verified_stakeholder_count": {"value": 2},
        },
        neighbor_facts={
            "contact.verified_recipient": True,
            "account.alternate_stakeholder_verified": True,
        },
        edge_count=2,
        evidence=(
            EvidenceRef("ev_status", "deal.status", "open", confidence_bp=9_500,
                        authority_rank=3),
            EvidenceRef("ev_engagement", "derived.engagement", 4_000,
                        confidence_bp=8_500, authority_rank=2),
            EvidenceRef("ev_inbound", "thread.last_inbound",
                        (NOW - timedelta(days=10)).isoformat(), confidence_bp=9_000,
                        authority_rank=2),
        ),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=DEAL_COOLING_V1,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        trigger_ref="event_1",
        mode=ExecutionMode.LIVE,
    )


def test_counterfactual_gate_change_is_explicit_and_never_authorizes_delivery():
    orchestrator = ReasoningOrchestrator(default_registry())
    baseline = orchestrator.execute(_request())
    scenario = SimulationScenario(
        "engagement_recovers",
        fact_overrides={
            "derived.engagement": {"value_bp": 9_000, "confidence_bp": 8_500,
                                   "src_count": 2},
        },
    )

    result = simulate(baseline=baseline, scenarios=(scenario,),
                      orchestrator=orchestrator)[0]

    assert baseline.decision.outcome == DecisionOutcome.DECISION
    assert result.execution.decision.outcome == DecisionOutcome.NO_ACTION
    assert result.execution.request.mode == ExecutionMode.SIMULATION
    assert result.execution.authorizes_delivery is False
    assert result.outcome_changed is True


def test_scenarios_are_stably_ordered_and_report_integer_utility_deltas():
    orchestrator = ReasoningOrchestrator(default_registry())
    baseline = orchestrator.execute(_request())
    results = simulate(
        baseline=baseline,
        scenarios=(SimulationScenario(
                       "z_more_concentrated",
                       fact_overrides={"relationship.verified_stakeholder_count": {"value": 0}}),
                   SimulationScenario(
                       "a_same",
                       fact_overrides={"relationship.verified_stakeholder_count": {"value": 2}})),
        orchestrator=orchestrator,
    )

    assert [item.scenario.scenario_id for item in results] == ["a_same", "z_more_concentrated"]
    assert all(type(delta) is int for item in results
               for delta in item.utility_delta_bp.values())
    assert all(item.execution.authorizes_delivery is False for item in results)
    assert any(delta != 0 for delta in results[1].utility_delta_bp.values())


def test_scenario_inputs_are_deeply_frozen_and_duplicate_ids_are_rejected():
    source = {"derived.engagement": {"value_bp": 4_000}}
    scenario = SimulationScenario("stable", fact_overrides=source)
    source["derived.engagement"]["value_bp"] = 9_000

    assert scenario.fact_overrides["derived.engagement"]["value_bp"] == 4_000
    baseline = ReasoningOrchestrator(default_registry()).execute(_request())
    with pytest.raises(ValueError, match="unique"):
        simulate(baseline=baseline, scenarios=(scenario, scenario),
                 orchestrator=ReasoningOrchestrator(default_registry()))
