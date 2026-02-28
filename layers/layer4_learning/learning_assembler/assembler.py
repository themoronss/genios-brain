"""
Learning Assembler — Main Assembler

Combine all L-module outputs into the final LearningReport.
"""

from core.contracts.learning_report import (
    LearningReport,
    OutcomeRecord,
    MemoryUpdate,
    PolicySuggestion,
    EvalMetrics,
    LearningMetrics,
)


def assemble_learning(
    outcome_record: OutcomeRecord,
    memory_updates: list[MemoryUpdate],
    policy_suggestions: list[PolicySuggestion],
    eval_metrics: EvalMetrics,
    learning_time_ms: float = 0.0,
) -> LearningReport:
    """
    Assemble the final LearningReport from all L-module outputs.

    Args:
        outcome_record: From L1.
        memory_updates: Gated updates from L2.
        policy_suggestions: From L3.
        eval_metrics: From L4.
        learning_time_ms: Elapsed time.

    Returns:
        Complete LearningReport.
    """
    # Backward compat: set top-level outcome field
    outcome = outcome_record.execution_result

    # Compute learning metrics
    auto_approved = sum(1 for u in memory_updates if u.auto_approved)
    review_queued = sum(1 for u in memory_updates if u.review_required)

    metrics = LearningMetrics(
        learning_time_ms=round(learning_time_ms, 2),
        updates_proposed=len(memory_updates),
        updates_auto_approved=auto_approved,
        updates_queued_review=review_queued,
        suggestions_generated=len(policy_suggestions),
    )

    return LearningReport(
        outcome=outcome,
        memory_updates=memory_updates,
        outcome_record=outcome_record,
        policy_suggestions=policy_suggestions,
        eval_metrics=eval_metrics,
        learning_metrics=metrics,
        learning_version="v1",
    )
