"""
L4 — Eval Aggregator

Compute quality score, detect drift, count red flags.
Produces EvalMetrics for observability and debugging.
"""

from core.contracts.decision_packet import DecisionPacket
from core.contracts.learning_report import OutcomeRecord, EvalMetrics, MemoryUpdate


def compute_eval_metrics(
    decision: DecisionPacket,
    outcome: OutcomeRecord,
    memory_updates: list[MemoryUpdate],
) -> EvalMetrics:
    """
    Compute evaluation metrics for this run.

    Args:
        decision: DecisionPacket from Layer 3.
        outcome: OutcomeRecord from L1.
        memory_updates: Gated updates from L2.

    Returns:
        EvalMetrics.
    """
    red_flags = []
    drift_details = []

    # --- Quality Score ---
    # Base: 0.5 (neutral)
    # +0.3 for approval/auto-exec
    # -0.3 for rejection
    # -0.1 per tool error
    # -0.1 for user edit (indicates imperfect output)
    quality = 0.5

    if outcome.execution_result in ("approved", "auto_executed"):
        quality += 0.3
    elif outcome.execution_result == "rejected":
        quality -= 0.3
    elif outcome.execution_result == "failed":
        quality -= 0.4

    if outcome.user_feedback == "edit":
        quality -= 0.1

    quality -= min(0.3, len(outcome.tool_errors) * 0.1)
    quality = round(max(0.0, min(1.0, quality)), 2)

    # --- Red Flags ---
    # Policy violations attempted
    if decision.decision_trace.rejected_options:
        for opt in decision.decision_trace.rejected_options:
            if "violation" in str(opt.get("rejection_reason", "")).lower():
                red_flags.append(f"Policy violation attempted: {opt.get('option', 'unknown')}")

    # Missing info loops
    if outcome.execution_result == "failed" and outcome.tool_errors:
        red_flags.append("Failed execution with tool errors")

    # High latency
    if outcome.latency_ms > 5000:
        red_flags.append(f"High latency: {outcome.latency_ms}ms")

    # Too many retries
    if outcome.retries > 2:
        red_flags.append(f"Excessive retries: {outcome.retries}")

    # --- Drift Detection ---
    # MVP: flag if too many updates are queued for review (unusual)
    review_count = sum(1 for u in memory_updates if u.review_required)
    if review_count > 3:
        drift_details.append(f"{review_count} memory updates queued for review — potential behavior shift")

    # Success rate (single-run estimate for MVP, rolling in future)
    success_rate = 1.0 if outcome.execution_result in ("approved", "auto_executed") else 0.0

    return EvalMetrics(
        quality_score=quality,
        drift_detected=len(drift_details) > 0,
        drift_details=drift_details,
        red_flag_count=len(red_flags),
        red_flags=red_flags,
        success_rate=success_rate,
        avg_latency_ms=outcome.latency_ms,
    )
