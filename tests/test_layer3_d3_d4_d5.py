"""
Tests for D3 Execution Mode, D4 Trace, and D5 Packaging.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from layers.layer3_decision.d0_router.route_builder import resolve_route
from layers.layer3_decision.d3_execution_mode.mode_gate_engine import (
    determine_execution_mode,
)
from layers.layer3_decision.d3_execution_mode.approval_chain import (
    resolve_approval_chain,
)
from layers.layer3_decision.d4_trace.reason_graph import build_reason_graph
from layers.layer3_decision.d4_trace.rejection_logger import log_rejections
from layers.layer3_decision.d5_packaging.brain_response_builder import (
    build_brain_response,
)
from layers.layer3_decision.d5_packaging.save_instruction_compiler import (
    compile_save_instructions,
)
from core.contracts.decision_packet import ActionPlan, ActionStep, ExecutionMode


def _get_context(intent="Follow up with Investor X"):
    r = RetrievalEngine()
    j = JudgementEngine()
    bundle = r.run(intent=intent, workspace_id="w1", actor_id="u1")
    judgement = j.run(bundle)
    return bundle, judgement


# --- D3 Execution Mode ---

def test_mode_needs_approval_vip():
    _, judgement = _get_context()
    mode = determine_execution_mode(judgement)
    assert mode.mode == "needs_approval"
    assert len(mode.rationale) > 0


def test_mode_general_low_risk():
    _, judgement = _get_context("What is the status?")
    mode = determine_execution_mode(judgement)
    assert mode.mode in ("auto_execute", "propose_only", "needs_approval")


def test_mode_ask_clarifying_on_stale():
    _, judgement = _get_context()
    judgement.need_more_info.value = True
    judgement.need_more_info.questions = []
    mode = determine_execution_mode(judgement)
    assert mode.mode == "ask_clarifying"


def test_approval_chain_resolver():
    _, judgement = _get_context()
    mode = ExecutionMode(mode="needs_approval")
    enriched = resolve_approval_chain(mode, judgement)
    assert len(enriched.approvals_required) > 0


# --- D4 Trace ---

def test_reason_graph():
    bundle, judgement = _get_context()
    route = resolve_route(bundle, judgement)
    execution = determine_execution_mode(judgement)
    trace = build_reason_graph(bundle, judgement, execution, "follow_up", {"who": "X"})
    assert len(trace.why) > 0
    assert len(trace.policies) > 0
    assert len(trace.factors) > 0
    assert len(trace.sources) > 0


def test_rejection_logger():
    _, judgement = _get_context()
    rejections = log_rejections("follow_up", judgement)
    assert len(rejections) > 0
    assert "option" in rejections[0]
    assert "rejection_reason" in rejections[0]


# --- D5 Packaging ---

def test_brain_response_approval():
    plan = ActionPlan(steps=[ActionStep(description="Draft email")])
    execution = ExecutionMode(mode="needs_approval")
    response = build_brain_response("follow_up", {"who": "X"}, execution, plan, ["VIP rule"])
    assert "approve" in response.user_message.lower() or any(
        b.block_type == "action_button" for b in response.ui_blocks
    )
    assert len(response.ui_blocks) > 0


def test_brain_response_clarify():
    plan = ActionPlan(steps=[ActionStep(description="Process")])
    execution = ExecutionMode(mode="ask_clarifying", questions=["What is the topic?"])
    response = build_brain_response("general", {}, execution, plan, [])
    assert any(b.block_type == "info" for b in response.ui_blocks)


def test_save_instructions():
    instructions = compile_save_instructions("follow_up", "needs_approval", {"who": "Investor X"})
    stores = [i.store for i in instructions]
    assert "decision_log" in stores
    assert "outcome" in stores
    assert "memory" in stores
