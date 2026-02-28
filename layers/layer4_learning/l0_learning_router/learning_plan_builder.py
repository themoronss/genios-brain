"""
L0 — Learning Plan Builder

Choose which learning modules to run based on:
  - execution outcome
  - risk level
  - user feedback type
"""

from core.contracts.decision_packet import DecisionPacket


# Learning modules
MODULES = ["outcomes", "memory_writeback", "policy_suggestions", "eval"]


def build_learning_plan(
    decision: DecisionPacket,
    execution_result: str,
    user_feedback: str = "",
) -> dict:
    """
    Build a learning plan: which modules to run.

    Args:
        decision: DecisionPacket from Layer 3.
        execution_result: What happened (approved, rejected, auto_executed, failed).
        user_feedback: User action (approve, edit, reject, "").

    Returns:
        Plan dict with modules list and metadata.
    """
    modules = ["outcomes"]  # always capture outcomes

    # Memory writeback: only on approval or auto-execution
    if execution_result in ("approved", "auto_executed"):
        modules.append("memory_writeback")

    # Policy suggestions: on rejection or repeated approval patterns
    if user_feedback == "reject" or execution_result == "approved":
        modules.append("policy_suggestions")

    # Eval: always run
    modules.append("eval")

    return {
        "modules": modules,
        "execution_result": execution_result,
        "user_feedback": user_feedback,
        "intent_type": decision.intent_type,
        "execution_mode": decision.execution_mode,
    }
