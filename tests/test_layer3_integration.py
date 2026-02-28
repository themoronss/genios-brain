"""
Integration test — Full Layer 3 pipeline.

Tests the complete decision engine with Layer 1 + Layer 2 outputs
for multiple intent types.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from layers.layer3_decision.decision_engine import DecisionEngine


def _run_full(intent: str):
    """Run Layer 1 → 2 → 3."""
    retrieval = RetrievalEngine()
    judgement = JudgementEngine()
    decision = DecisionEngine()
    bundle = retrieval.run(intent=intent, workspace_id="w1", actor_id="u1")
    report = judgement.run(bundle)
    packet = decision.run(bundle, report)
    return packet


# --- Full Pipeline Tests ---

def test_follow_up_vip_full():
    packet = _run_full("Follow up with Investor X tomorrow")

    # Intent
    assert packet.intent_type == "follow_up"
    assert "who" in packet.intent_slots

    # Execution mode: VIP → needs_approval
    assert packet.execution_mode == "needs_approval"
    assert len(packet.execution_detail.approvals_required) > 0

    # Plan
    assert len(packet.action_plan.steps) >= 3
    assert len(packet.action_plan.tool_calls) > 0

    # Trace
    assert len(packet.decision_trace.why) > 0
    assert len(packet.decision_trace.policies) > 0
    assert len(packet.decision_trace.rejected_options) > 0

    # Brain response
    assert len(packet.brain_response.user_message) > 0
    assert len(packet.brain_response.ui_blocks) > 0

    # Meta
    assert packet.decision_version == "v1"
    assert packet.decision_metrics.steps_planned > 0


def test_schedule_meeting_full():
    packet = _run_full("Schedule a meeting with John next week")

    assert packet.intent_type == "schedule_meeting"
    assert packet.intent_slots.get("channel") == "calendar"
    assert len(packet.action_plan.steps) >= 2
    assert any("calendar" in tc.tool_name for tc in packet.action_plan.tool_calls)


def test_cold_outreach_full():
    packet = _run_full("Cold outreach to potential investors")

    assert packet.intent_type == "cold_outreach"
    assert packet.execution_mode in ("needs_approval", "propose_only")
    assert len(packet.action_plan.steps) >= 3


def test_general_intent_full():
    packet = _run_full("What is the current status?")

    assert packet.intent_type == "general"
    assert packet.execution_mode in ("auto_execute", "propose_only", "needs_approval")
    assert len(packet.action_plan.steps) >= 1


def test_backward_compat_with_orchestrator():
    """Ensure old fields that orchestrator + Layer 4 use still work."""
    packet = _run_full("Follow up with Investor X")

    # Orchestrator uses these
    assert hasattr(packet, "intent_type")
    assert hasattr(packet, "execution_mode")
    assert hasattr(packet, "action_plan")
    assert hasattr(packet, "reasons")

    # Layer 4 uses decision.intent_type
    assert isinstance(packet.intent_type, str)
    assert isinstance(packet.reasons, list)
    assert hasattr(packet.action_plan, "steps")
    assert len(packet.action_plan.steps) > 0
