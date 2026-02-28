"""
L1.1 — Execution Result Normalizer

Normalize tool outputs + user feedback into a canonical OutcomeRecord.
"""

from core.contracts.decision_packet import DecisionPacket
from core.contracts.learning_report import OutcomeRecord


def normalize_outcome(
    decision: DecisionPacket,
    execution_result: str,
    user_feedback: str = "",
    user_comment: str = "",
    tool_errors: list = None,
    latency_ms: float = 0.0,
) -> OutcomeRecord:
    """
    Build a normalized OutcomeRecord from raw execution data.

    Args:
        decision: DecisionPacket from Layer 3.
        execution_result: Raw result string.
        user_feedback: approve | edit | reject | "".
        user_comment: Optional user comment.
        tool_errors: List of error dicts.
        latency_ms: End-to-end latency.

    Returns:
        Normalized OutcomeRecord.
    """
    # Determine side effects from plan
    side_effects = []
    for tc in decision.action_plan.tool_calls:
        if execution_result in ("approved", "auto_executed"):
            side_effects.append(f"{tc.tool_name}.{tc.method}")

    # Count retries from errors
    errors = tool_errors or []
    retries = sum(1 for e in errors if e.get("retried", False))

    # Token usage estimate from metrics
    token_usage = decision.decision_metrics.steps_planned * 50

    return OutcomeRecord(
        execution_result=execution_result,
        user_feedback=user_feedback,
        user_comment=user_comment,
        tool_errors=errors,
        retries=retries,
        side_effects=side_effects,
        latency_ms=latency_ms,
        token_usage=token_usage,
        tool_call_count=len(decision.action_plan.tool_calls),
    )
