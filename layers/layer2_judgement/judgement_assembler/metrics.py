"""
Judgement Assembler — Metrics

Compute timing and count metrics for the judgement phase.
"""

from core.contracts.judgement_report import (
    JudgementReport,
    JudgementMetrics,
)


def compute_judgement_metrics(
    report: JudgementReport,
    judging_time_ms: float = 0.0,
    policies_evaluated: int = 0,
) -> JudgementMetrics:
    """
    Compute metrics from a completed JudgementReport.

    Args:
        report: The assembled report.
        judging_time_ms: Total time spent in Layer 2.
        policies_evaluated: Number of policy rules checked.

    Returns:
        JudgementMetrics.
    """
    checks_run = 0
    if report.need_more_info is not None:
        checks_run += 1
    if report.policy.status:
        checks_run += 1
    if report.risk.level:
        checks_run += 1
    if report.priority.score > 0:
        checks_run += 1
    if report.multi_factor.ranked_factors:
        checks_run += 1

    return JudgementMetrics(
        judging_time_ms=round(judging_time_ms, 2),
        checks_run=checks_run,
        policies_evaluated=policies_evaluated,
        factors_extracted=len(report.multi_factor.ranked_factors),
    )
