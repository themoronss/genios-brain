"""
Decision Packet — Full Layer 3 output contract.

Expanded from the original to include:
- ToolCallDraft (planned tool invocations)
- DecisionTrace (audit trail)
- BrainResponse (user-facing output)
- SaveInstruction (what to persist)
- DecisionMetrics
- decision_version tag
- fallbacks on ActionPlan

All new fields are optional with defaults for backward compatibility.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


# --- Action Plan ---

class ActionStep(BaseModel):
    description: str
    tool: str = ""          # tool to invoke (empty = no tool)
    depends_on: int = -1    # index of step this depends on (-1 = none)
    order: int = 0


class ToolCallDraft(BaseModel):
    tool_name: str
    method: str = "execute"
    payload: Dict[str, Any] = {}
    fallback: str = ""      # what to do if this call fails


class ActionPlan(BaseModel):
    steps: List[ActionStep] = []
    tool_calls: List[ToolCallDraft] = []
    fallbacks: List[str] = []


# --- Execution Mode ---

class ExecutionMode(BaseModel):
    mode: str = "propose_only"  # auto_execute | needs_approval | propose_only | ask_clarifying
    approvals_required: List[str] = []
    questions: List[str] = []
    rationale: List[str] = []


# --- Decision Trace ---

class DecisionTrace(BaseModel):
    why: List[str] = []
    policies: List[str] = []
    factors: List[str] = []
    sources: List[str] = []
    rejected_options: List[Dict[str, str]] = []


# --- Brain Response ---

class UIBlock(BaseModel):
    block_type: str  # draft | reason | action_button | info
    title: str = ""
    content: str = ""


class SaveInstruction(BaseModel):
    store: str            # decision_log | memory | outcome
    key: str
    value: Any = None


class BrainResponse(BaseModel):
    user_message: str = ""
    ui_blocks: List[UIBlock] = []
    tool_instructions: List[ToolCallDraft] = []
    save_instructions: List[SaveInstruction] = []


# --- Metrics ---

class DecisionMetrics(BaseModel):
    decision_time_ms: float = 0.0
    steps_planned: int = 0
    tool_calls_drafted: int = 0
    constraints_applied: int = 0


# --- Final Packet ---

class DecisionPacket(BaseModel):
    # Original fields (backward compat)
    intent_type: str = "general"
    execution_mode: str = "propose_only"    # kept as str for backward compat
    action_plan: ActionPlan = ActionPlan()
    reasons: List[str] = []

    # New fields (all optional with defaults)
    intent_slots: Dict[str, str] = {}
    execution_detail: ExecutionMode = ExecutionMode()
    decision_trace: DecisionTrace = DecisionTrace()
    brain_response: BrainResponse = BrainResponse()
    decision_metrics: DecisionMetrics = DecisionMetrics()
    decision_version: str = "v1"