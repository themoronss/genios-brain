"""
Decision Assembler — Main Assembler

Combine all D-module outputs into the final DecisionPacket.
"""

from core.contracts.decision_packet import (
    DecisionPacket,
    ActionPlan,
    ExecutionMode,
    DecisionTrace,
    BrainResponse,
)
from layers.layer3_decision.decision_assembler.metrics import (
    compute_decision_metrics,
)


def assemble_decision(
    intent_type: str,
    intent_slots: dict[str, str],
    action_plan: ActionPlan,
    execution: ExecutionMode,
    trace: DecisionTrace,
    brain_response: BrainResponse,
    decision_time_ms: float = 0.0,
    constraints_applied: int = 0,
) -> DecisionPacket:
    """
    Assemble the final DecisionPacket from all D-module outputs.

    Args:
        intent_type: Final intent type from D1.
        intent_slots: Extracted slots from D1.
        action_plan: From D2.
        execution: From D3.
        trace: From D4.
        brain_response: From D5.
        decision_time_ms: Elapsed time.
        constraints_applied: Count from D2.

    Returns:
        Complete DecisionPacket.
    """
    # Combine reasons from trace
    reasons = list(trace.why)

    packet = DecisionPacket(
        intent_type=intent_type,
        execution_mode=execution.mode,
        action_plan=action_plan,
        reasons=reasons,
        intent_slots=intent_slots,
        execution_detail=execution,
        decision_trace=trace,
        brain_response=brain_response,
        decision_version="v1",
    )

    # Compute and attach metrics
    packet.decision_metrics = compute_decision_metrics(
        packet,
        decision_time_ms=decision_time_ms,
        constraints_applied=constraints_applied,
    )

    return packet
