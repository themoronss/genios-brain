"""
Integration test — Full Layer 1 pipeline with mock stores.

Tests the complete retrieval engine with all sub-modules
for 3 intents: follow_up, schedule_meeting, reply_email.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine


def _run_engine(intent: str) -> dict:
    """Helper: run engine with no external stores (all mocks)."""
    engine = RetrievalEngine()
    bundle = engine.run(
        intent=intent,
        workspace_id="w1",
        actor_id="u1",
    )
    return bundle


# --- Full Pipeline Tests ---

def test_follow_up_pipeline():
    bundle = _run_engine("Follow up with Investor X tomorrow")

    # Scope
    assert bundle.scope.workspace_id == "w1"
    assert bundle.scope.role == "founder"
    assert len(bundle.scope.permissions) > 0

    # Memory (mock)
    assert bundle.memory.preferences.get("tone") == "confident"
    assert "Investor X" in bundle.memory.entity_data

    # Tools (mock Gmail should trigger for follow_up)
    assert "gmail" in bundle.tools.snapshots

    # Policies (VIP should match)
    assert len(bundle.policy.rules) > 0
    assert len(bundle.policy.trace) > 0

    # Precedents (follow_up precedents should exist)
    assert len(bundle.precedents.past_decisions) > 0

    # Metrics
    assert bundle.metrics.retrieval_time_ms >= 0
    assert bundle.metrics.estimated_tokens > 0

    # Version
    assert bundle.context_bundle_version == "v1"

    # Source map
    assert len(bundle.source_map) > 0


def test_schedule_meeting_pipeline():
    bundle = _run_engine("Schedule a meeting with John next week")

    assert bundle.scope.workspace_id == "w1"
    assert bundle.memory.preferences.get("tone") == "confident"

    # Calendar should trigger for schedule
    assert "calendar" in bundle.tools.snapshots

    # schedule_meeting doesn't require precedents in its required_contexts

    assert bundle.context_bundle_version == "v1"


def test_reply_email_pipeline():
    bundle = _run_engine("Reply to the email from the recruiter")

    assert bundle.scope.workspace_id == "w1"

    # Gmail should trigger for reply
    assert "gmail" in bundle.tools.snapshots

    # Policies should always be present
    assert len(bundle.policy.trace) > 0

    assert bundle.context_bundle_version == "v1"


def test_general_intent_minimal():
    bundle = _run_engine("What is the current status?")

    # General intent should still resolve scope
    assert bundle.scope.workspace_id == "w1"

    # Tools should NOT be fetched for general
    assert len(bundle.tools.snapshots) == 0

    # Policies always present
    assert len(bundle.policy.trace) > 0


def test_bundle_backward_compat():
    """Ensure the bundle still has the old fields for Layer 2/3/4 compatibility."""
    bundle = _run_engine("Follow up with Investor X")

    # These are the fields Layer 2/3/4 depend on
    assert hasattr(bundle, "scope")
    assert hasattr(bundle, "memory")
    assert hasattr(bundle, "policy")
    assert hasattr(bundle, "tools")

    # Old-style access should still work
    assert bundle.scope.workspace_id == "w1"
    assert isinstance(bundle.memory.preferences, dict)
    assert isinstance(bundle.policy.rules, list)
    assert isinstance(bundle.tools.snapshots, dict)
