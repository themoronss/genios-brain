"""Layer 4 end to end: all three parts, on one real situation.

Unit tests prove each part in isolation. This proves the parts compose — that a capability naming
seventeen units gets scheduled correctly, that each unit's output actually reaches the units that
depend on it, and that the whole thing resolves to one explainable decision.

The situation: an open $250k deal. The buyer wrote nine days ago and nobody replied; our last
outbound was three weeks ago. Engagement has collapsed to 1,800bp. Two plays are on the table —
re-engage the champion, or escalate to an executive sponsor.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    DecisionOutcome,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.decision_maker import CONFIDENCE_FLOOR_KEY
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _spec(reasoner_id: str, dependencies: tuple[str, ...] = (), **kwargs) -> ReasonerSpec:
    return ReasonerSpec(reasoner_id, "1.0.0", dependencies=dependencies, **kwargs)


#: A capability naming every unit of the roster, wired the way a real one would be: understanding
#: first, evaluation on top of it, optimisation on top of that, decision support last.
FULL_ROSTER = (
    _spec("core.context"),
    _spec("core.timeline"),
    _spec("core.dependency"),
    _spec("core.temporal", config={"engagement_field": "derived.engagement_bp",
                                   "timestamp_field": "deal.last_inbound"}),
    _spec("core.relationship"),
    _spec("core.risk", ("core.temporal", "core.relationship")),
    _spec("core.opportunity", ("core.temporal",)),
    _spec("core.impact"),
    _spec("core.constraint"),
    _spec("core.policy"),
    _spec("core.resource"),
    _spec("core.scheduling"),
    _spec("core.cost"),
    _spec("core.tradeoff", ("core.risk", "core.opportunity", "core.impact", "core.cost")),
    _spec("core.priority", ("core.risk",)),
    _spec("core.confidence", ("core.context",)),
    _spec("core.alternative", ("core.constraint", "core.cost")),
    _spec("core.validation", ("core.risk", "core.opportunity", "core.impact")),
    _spec("core.recommendation", ("core.validation", "core.dependency")),
)

PLAYS = (
    PlayDefinition(play_id="reengage_champion", version="1", label="Re-engage the champion",
                   steps=("Draft a grounded check-in",), impact_bp=7_000,
                   success_probability_bp=6_000, effort_bp=2_000, risk_bp=1_500, window_days=7),
    PlayDefinition(play_id="escalate_to_exec", version="1", label="Executive escalation",
                   steps=("Brief the exec sponsor",), impact_bp=9_000,
                   success_probability_bp=4_000, effort_bp=6_000, risk_bp=5_000, window_days=14),
)


def _capability(metadata=None) -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="sales.deal_at_risk", version="1.0.0", domain="sales",
        root_entity_type="deal",
        goal=Goal("save_deal", "Keep a winnable deal alive"),
        reasoners=FULL_ROSTER, plays=PLAYS, policies=("read_only",),
        metadata=metadata or {},
    )


def _request(capability: CapabilityManifest, *, facts=None) -> ReasoningRequest:
    context = ContextSnapshot(
        org_id="org_1", graph_version=42, root_entity_id="deal_9", root_entity_type="deal",
        evaluation_time=NOW, selector_version="sales.v1",
        facts=facts if facts is not None else {
            "deal.status": "open",
            "deal.value": 250_000,
            "deal.owner": "rohit",
            "derived.engagement_bp": 1_800,
            "deal.last_inbound": (NOW - timedelta(days=9)).isoformat(),
            "deal.last_outbound": (NOW - timedelta(days=21)).isoformat(),
        },
    )
    return ReasoningRequest(
        org_id="org_1", capability=capability, context=context, evaluation_time=NOW,
        trigger_kind="schedule.sweep", config_snapshot_id="cfg_1")


@pytest.fixture(scope="module")
def execution():
    return ReasoningOrchestrator(default_registry()).execute(_request(_capability()))


def test_every_declared_unit_runs_and_completes(execution):
    assert len(execution.ordered_results) == len(FULL_ROSTER)
    incomplete = [item.reasoner_id for item in execution.ordered_results
                  if item.status != ResultStatus.COMPLETED]
    assert not incomplete, f"units did not complete: {incomplete}"


def test_the_situation_resolves_to_one_explainable_decision(execution):
    """A cooling deal with an unanswered buyer should produce an action, not a shrug."""
    assert execution.decision.outcome == DecisionOutcome.DECISION
    assert execution.selected_candidate.play_id == "reengage_champion"
    assert execution.selected_candidate.rank_position == 1
    assert execution.authorizes_delivery is True


def test_the_losing_option_is_kept_and_ranked_not_discarded(execution):
    """An executive always sees the alternative they did not take."""
    ranked = [(item.play_id, item.rank_position) for item in execution.candidates]

    assert ranked == [("reengage_champion", 1), ("escalate_to_exec", 2)]


def test_the_units_actually_feed_each_other(execution):
    """The point of a DAG: collapsed engagement must travel into risk and opportunity."""
    by_id = execution.result_by_id

    assert by_id["core.temporal"].metrics["drop_bp"] > 8_000        # engagement collapsed
    assert by_id["core.risk"].metrics["risk_bp"] > 8_000            # which raised risk
    assert by_id["core.opportunity"].metrics["opportunity_bp"] > 8_000   # and left headroom
    assert by_id["core.opportunity"].matched is True


def test_the_plan_schedules_independent_work_together(execution):
    plan = execution.plan

    assert len(plan.steps) == len(FULL_ROSTER)
    assert plan.parallelizable is True
    assert plan.critical_path_budget_ms < plan.sequential_budget_ms
    # Understanding must precede the evaluation that consumes it.
    stage_of = {step.reasoner_id: step.stage for step in plan.steps}
    assert stage_of["core.temporal"] < stage_of["core.risk"] < stage_of["core.tradeoff"]
    assert stage_of["core.validation"] < stage_of["core.recommendation"]


def test_the_run_is_replayable(execution):
    """Same situation, same bytes — the property every audit depends on."""
    again = ReasoningOrchestrator(default_registry()).execute(_request(_capability()))

    assert again.decision.semantic_hash == execution.decision.semantic_hash
    assert again.trace.semantic_hash == execution.trace.semantic_hash
    assert again.decision.decision_id == execution.decision.decision_id


def test_a_starved_situation_fails_closed_rather_than_guessing():
    """Remove the engagement reading and the whole run must stop, not invent a number."""
    execution = ReasoningOrchestrator(default_registry()).execute(
        _request(_capability(), facts={"deal.status": "open", "deal.owner": "rohit"}))

    assert execution.decision.outcome == DecisionOutcome.INSUFFICIENT_CONTEXT
    assert execution.candidates == ()
    assert execution.authorizes_delivery is False


def test_a_high_floor_turns_the_same_winner_into_a_question():
    """Identical situation, stricter standard: GeniOS asks instead of recommending."""
    execution = ReasoningOrchestrator(default_registry()).execute(
        _request(_capability({CONFIDENCE_FLOOR_KEY: 9_500})))

    assert execution.decision.outcome == DecisionOutcome.DEFER
    assert execution.decision.selected_candidate_id is None
    assert execution.candidates, "the human still needs to see what was considered"
    assert execution.authorizes_delivery is False
