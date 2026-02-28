"""
Tests for D0 Router, D1 Intent, and D2 Planning.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from layers.layer3_decision.d0_router.route_builder import resolve_route
from layers.layer3_decision.d1_intent.slot_extractor import extract_slots
from layers.layer3_decision.d1_intent.intent_finalizer import finalize_intent
from layers.layer3_decision.d2_planning.plan_templates import get_template, PLAN_TEMPLATES
from layers.layer3_decision.d2_planning.step_builder import build_plan
from layers.layer3_decision.d2_planning.constraint_enforcer import enforce_constraints


def _get_context(intent="Follow up with Investor X"):
    r = RetrievalEngine()
    j = JudgementEngine()
    bundle = r.run(intent=intent, workspace_id="w1", actor_id="u1")
    judgement = j.run(bundle)
    return bundle, judgement


# --- D0 Router ---

def test_route_follow_up():
    bundle, judgement = _get_context()
    route = resolve_route(bundle, judgement)
    assert route["intent_type"] == "follow_up"
    assert route["template_key"] == "follow_up"


def test_route_general():
    bundle, judgement = _get_context("What is the status?")
    route = resolve_route(bundle, judgement)
    assert route["intent_type"] == "general"


# --- D1 Intent ---

def test_slot_extractor_follow_up():
    bundle, _ = _get_context()
    slots = extract_slots(bundle, "follow_up")
    assert "who" in slots
    assert slots["channel"] == "email"
    assert "template" in slots


def test_intent_finalizer():
    bundle, judgement = _get_context()
    route = resolve_route(bundle, judgement)
    intent, slots = finalize_intent(bundle, judgement, route)
    assert intent == "follow_up"
    assert "who" in slots


# --- D2 Planning ---

def test_template_exists_for_all():
    for intent in ["follow_up", "reply_email", "cold_outreach", "schedule_meeting", "general"]:
        tmpl = get_template(intent)
        assert len(tmpl["steps"]) > 0


def test_build_plan_follow_up():
    slots = {"who": "Investor X", "what": "Follow up", "channel": "email", "template": "vip_follow_up_template"}
    plan = build_plan("follow_up", slots)
    assert len(plan.steps) >= 3
    assert len(plan.tool_calls) > 0
    assert plan.tool_calls[0].payload.get("recipient") == "Investor X"


def test_constraint_enforcer():
    bundle, judgement = _get_context()
    plan = build_plan("follow_up", {"who": "Investor X"})
    plan, applied = enforce_constraints(plan, judgement)
    assert applied > 0
    # Should have injected constraints from J5
