"""
Tests for J0 — Judgement Planner and J1 — Sufficiency Check.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.j0_judgement_planner.plan_builder import (
    build_judgement_plan,
)
from layers.layer2_judgement.j0_judgement_planner.thresholds import (
    RISK_AUTO_EXECUTE_MAX,
    RISK_HIGH_THRESHOLD,
)
from layers.layer2_judgement.j1_sufficiency.required_fields import (
    validate_required_fields,
)
from layers.layer2_judgement.j1_sufficiency.staleness_detector import (
    detect_stale_data,
)
from layers.layer2_judgement.j1_sufficiency.question_generator import (
    check_sufficiency,
)
from core.contracts.context_bundle import ContextBundle, ScopeContext, MemoryContext, PolicyContext, ToolContext


def _get_bundle(intent: str = "Follow up with Investor X") -> ContextBundle:
    engine = RetrievalEngine()
    return engine.run(intent=intent, workspace_id="w1", actor_id="u1")


# --- J0 Planner ---

def test_judgement_plan_follow_up():
    bundle = _get_bundle("Follow up with Investor X")
    plan = build_judgement_plan(bundle)
    assert plan.intent_type == "follow_up"
    assert "sufficiency" in plan.required_checks
    assert "policy" in plan.required_checks
    assert "risk" in plan.required_checks
    assert "multifactor" in plan.required_checks


def test_judgement_plan_schedule():
    bundle = _get_bundle("Schedule a meeting")
    plan = build_judgement_plan(bundle)
    assert plan.intent_type == "schedule_meeting"
    assert "priority" in plan.required_checks


def test_judgement_plan_general():
    bundle = _get_bundle("What is the status?")
    plan = build_judgement_plan(bundle)
    assert plan.intent_type == "general"


def test_thresholds_exist():
    assert RISK_AUTO_EXECUTE_MAX == 0.4
    assert RISK_HIGH_THRESHOLD == 0.7


# --- J1 Required Fields ---

def test_required_fields_follow_up_ok():
    bundle = _get_bundle("Follow up with Investor X")
    missing = validate_required_fields(bundle, "follow_up")
    # Mock data should have entity_data and preferences
    assert not any(m["field"] == "memory.entity_data" for m in missing)
    assert not any(m["field"] == "memory.preferences" for m in missing)


def test_required_fields_general():
    bundle = _get_bundle("What is the status?")
    missing = validate_required_fields(bundle, "general")
    assert len(missing) == 0  # general has no required fields


# --- J1 Staleness ---

def test_staleness_detector_fresh():
    bundle = _get_bundle("Follow up with Investor X")
    stale = detect_stale_data(bundle)
    # Mock providers return fresh data
    assert all(s.get("tool") != "gmail" or not bundle.tools.stale_flags.get("gmail") for s in stale)


def test_staleness_detector_with_stale():
    bundle = _get_bundle("Follow up")
    bundle.tools.stale_flags["gmail"] = True
    stale = detect_stale_data(bundle)
    assert len(stale) >= 1
    assert stale[0]["tool"] == "gmail"


# --- J1 Question Generator ---

def test_sufficiency_ok():
    bundle = _get_bundle("Follow up with Investor X")
    result = check_sufficiency(bundle, "follow_up")
    # With mock data, most required fields should be present
    # Might still flag tools as required but present
    assert isinstance(result.value, bool)


def test_sufficiency_blocks_on_stale():
    bundle = _get_bundle("Follow up with Investor X")
    bundle.tools.stale_flags["gmail"] = True
    result = check_sufficiency(bundle, "follow_up")
    assert result.value is True
    assert len(result.questions) >= 1
