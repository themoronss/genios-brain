"""
Decision Assembler — Metrics

Compute timing and count metrics for the decision phase.
"""

from core.contracts.decision_packet import DecisionMetrics, DecisionPacket


def compute_decision_metrics(
    packet: DecisionPacket,
    decision_time_ms: float = 0.0,
    constraints_applied: int = 0,
) -> DecisionMetrics:
    """
    Compute metrics from a completed DecisionPacket.

    Args:
        packet: The assembled packet.
        decision_time_ms: Total time in Layer 3.
        constraints_applied: Number of J5 constraints enforced.

    Returns:
        DecisionMetrics.
    """
    return DecisionMetrics(
        decision_time_ms=round(decision_time_ms, 2),
        steps_planned=len(packet.action_plan.steps),
        tool_calls_drafted=len(packet.action_plan.tool_calls),
        constraints_applied=constraints_applied,
    )
