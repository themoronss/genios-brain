"""
Tests for R0 — Query Builder sub-modules.
Tests intent normalization, requirements generation, plan composition, and budgets.
Covers 3 intent types: follow_up, schedule_meeting, reply_email.
"""

from layers.layer1_retrieval.r0_query_builder.intent_normalizer import (
    normalize_intent,
    IntentType,
)
from layers.layer1_retrieval.r0_query_builder.requirements_generator import (
    get_required_contexts,
)
from layers.layer1_retrieval.r0_query_builder.plan_composer import (
    build_query_plan,
    extract_entities,
)
from layers.layer1_retrieval.r0_query_builder.budgets import (
    get_ttl_for_tool,
    MAX_TOOL_CALLS,
)


# --- Intent Normalizer ---

def test_normalize_follow_up():
    assert normalize_intent("Follow up with Investor X") == IntentType.FOLLOW_UP


def test_normalize_schedule():
    assert normalize_intent("Schedule a meeting tomorrow") == IntentType.SCHEDULE_MEETING


def test_normalize_reply():
    assert normalize_intent("Reply to the email from John") == IntentType.REPLY_EMAIL


def test_normalize_cold_outreach():
    assert normalize_intent("Cold outreach to new investor") == IntentType.COLD_OUTREACH


def test_normalize_general():
    assert normalize_intent("What is the status?") == IntentType.GENERAL


def test_normalize_case_insensitive():
    assert normalize_intent("FOLLOW UP with investor") == IntentType.FOLLOW_UP


# --- Requirements Generator ---

def test_follow_up_requires_all_contexts():
    contexts = get_required_contexts(IntentType.FOLLOW_UP)
    assert "scope" in contexts
    assert "memory" in contexts
    assert "tools" in contexts
    assert "policies" in contexts
    assert "precedents" in contexts


def test_schedule_does_not_require_precedents():
    contexts = get_required_contexts(IntentType.SCHEDULE_MEETING)
    assert "precedents" not in contexts


def test_general_requires_minimal():
    contexts = get_required_contexts(IntentType.GENERAL)
    assert "scope" in contexts
    assert "policies" in contexts
    assert "tools" not in contexts


def test_mandatory_contexts_always_present():
    for intent_type in IntentType:
        contexts = get_required_contexts(intent_type)
        assert "scope" in contexts
        assert "policies" in contexts


# --- Plan Composer ---

def test_build_query_plan_follow_up():
    plan = build_query_plan("Follow up with Investor X")
    assert plan.intent_type == "follow_up"
    assert plan.raw_intent == "Follow up with Investor X"
    assert "scope" in plan.required_contexts
    assert plan.budget.max_tool_calls == MAX_TOOL_CALLS


def test_build_query_plan_schedule():
    plan = build_query_plan("Schedule meeting with John")
    assert plan.intent_type == "schedule_meeting"


def test_build_query_plan_reply():
    plan = build_query_plan("Reply to email from recruiter")
    assert plan.intent_type == "reply_email"


def test_extract_entities_investor():
    entities = extract_entities("Follow up with Investor X tomorrow")
    assert "Investor X" in entities


def test_extract_entities_person():
    entities = extract_entities("Email John Smith about the deal")
    assert "John Smith" in entities


def test_extract_entities_none():
    entities = extract_entities("what is the status?")
    assert len(entities) == 0


# --- Budgets ---

def test_ttl_gmail():
    assert get_ttl_for_tool("gmail") == 60


def test_ttl_calendar():
    assert get_ttl_for_tool("calendar") == 120


def test_ttl_unknown():
    assert get_ttl_for_tool("slack") == 120  # default
