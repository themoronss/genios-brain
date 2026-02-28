"""
Tests for R3 — Tool State Retrieval sub-modules.
Tests providers, tool orchestrator, and freshness guard.
"""

from datetime import datetime, timezone, timedelta

from layers.layer1_retrieval.r3_tools.provider_base import (
    MockGmailProvider,
    MockCalendarProvider,
)
from layers.layer1_retrieval.r3_tools.freshness_guard import check_freshness
from layers.layer1_retrieval.r3_tools.tool_orchestrator import ToolOrchestrator
from core.contracts.query_plan import QueryPlan, RetrievalBudget


# --- Providers ---

def test_gmail_provider_supports_follow_up():
    provider = MockGmailProvider()
    assert provider.supports("follow_up") is True
    assert provider.tool_name == "gmail"


def test_gmail_provider_not_supports_schedule():
    provider = MockGmailProvider()
    assert provider.supports("schedule_meeting") is False


def test_calendar_provider_supports_schedule():
    provider = MockCalendarProvider()
    assert provider.supports("schedule_meeting") is True
    assert provider.supports("follow_up") is False


def test_gmail_fetch_returns_expected_keys():
    provider = MockGmailProvider()
    result = provider.fetch(["Investor X"], "w1")
    assert "tool_name" in result
    assert "result_summary" in result
    assert "fetched_at" in result
    assert result["result_summary"]["thread_exists"] is True


# --- Freshness Guard ---

def test_freshness_fresh():
    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": 120,
    }
    checked, is_stale = check_freshness(result)
    assert is_stale is False
    assert checked["is_stale"] is False


def test_freshness_stale():
    old_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    result = {
        "fetched_at": old_time,
        "ttl_seconds": 60,
    }
    checked, is_stale = check_freshness(result)
    assert is_stale is True
    assert checked["is_stale"] is True


def test_freshness_no_timestamp():
    result = {"ttl_seconds": 60}
    checked, is_stale = check_freshness(result)
    assert is_stale is True


# --- Tool Orchestrator ---

def test_tool_orchestrator_follow_up():
    orchestrator = ToolOrchestrator()
    plan = QueryPlan(
        intent_type="follow_up",
        raw_intent="Follow up Investor X",
        required_contexts=["tools"],
    )
    tools, sources = orchestrator.retrieve(plan, "w1")
    assert "gmail" in tools.snapshots
    assert len(sources) >= 1


def test_tool_orchestrator_schedule():
    orchestrator = ToolOrchestrator()
    plan = QueryPlan(
        intent_type="schedule_meeting",
        raw_intent="Schedule meeting",
        required_contexts=["tools"],
    )
    tools, sources = orchestrator.retrieve(plan, "w1")
    assert "calendar" in tools.snapshots


def test_tool_orchestrator_budget_limit():
    orchestrator = ToolOrchestrator()
    plan = QueryPlan(
        intent_type="follow_up",
        raw_intent="Follow up",
        required_contexts=["tools"],
        budget=RetrievalBudget(max_tool_calls=0),
    )
    tools, sources = orchestrator.retrieve(plan, "w1")
    assert len(tools.snapshots) == 0
