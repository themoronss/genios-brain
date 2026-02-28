"""
Judgement Assembler — Main Assembler

Combine all J-module outputs into the final JudgementReport.
Compute ok_to_act and needs_approval from derived logic.
"""

from core.contracts.judgement_report import (
    JudgementReport,
    NeedMoreInfo,
    PolicyVerdict,
    RiskReport,
    PriorityReport,
    MultiFactorReport,
)
from layers.layer2_judgement.j0_judgement_planner.thresholds import (
    RISK_AUTO_EXECUTE_MAX,
    APPROVAL_REQUIRED_RISK_THRESHOLD,
)
from layers.layer2_judgement.judgement_assembler.metrics import (
    compute_judgement_metrics,
)


def assemble_judgement(
    need_more_info: NeedMoreInfo,
    policy: PolicyVerdict,
    risk: RiskReport,
    priority: PriorityReport,
    multi_factor: MultiFactorReport,
    judging_time_ms: float = 0.0,
    policies_evaluated: int = 0,
) -> JudgementReport:
    """
    Assemble the final JudgementReport from all J-module outputs.

    Derived fields:
        ok_to_act = True only if:
            - need_more_info.value == False
            - policy.status != "deny"
            - risk.score < auto-execute threshold

        needs_approval = True if:
            - policy.status == "needs_approval"
            - OR risk.score >= approval threshold

    Args:
        need_more_info: From J1.
        policy: From J2.
        risk: From J3.
        priority: From J4.
        multi_factor: From J5.
        judging_time_ms: Elapsed time.
        policies_evaluated: Count.

    Returns:
        Complete JudgementReport.
    """
    # --- Derived: needs_approval ---
    needs_approval = (
        policy.status == "needs_approval"
        or risk.score >= APPROVAL_REQUIRED_RISK_THRESHOLD
    )

    # --- Derived: ok_to_act ---
    ok_to_act = (
        not need_more_info.value
        and policy.status != "deny"
        and risk.score <= RISK_AUTO_EXECUTE_MAX
    )

    # If approval is required, allow execution to proceed (but routed to approval)
    if needs_approval and not need_more_info.value and policy.status != "deny":
        ok_to_act = True

    # Build report
    report = JudgementReport(
        need_more_info=need_more_info,
        policy=policy,
        risk=risk,
        priority=priority,
        multi_factor=multi_factor,
        ok_to_act=ok_to_act,
        needs_approval=needs_approval,
        judgement_version="v1",
    )

    # Compute and attach metrics
    report.metrics = compute_judgement_metrics(
        report,
        judging_time_ms=judging_time_ms,
        policies_evaluated=policies_evaluated,
    )

    return report
