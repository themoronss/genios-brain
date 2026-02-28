"""
D3.1 — Mode Gate Engine

Deterministic if/else rules to decide execution mode:
  auto_execute | needs_approval | propose_only | ask_clarifying

Fail-closed: when in doubt, do NOT auto-execute.
"""

from core.contracts.judgement_report import JudgementReport
from core.contracts.decision_packet import ExecutionMode


def determine_execution_mode(
    judgement: JudgementReport,
    route_overrides: dict = None,
) -> ExecutionMode:
    """
    Decide execution mode using judgement signals.

    Priority (highest to lowest):
        1. If need_more_info → ask_clarifying
        2. If policy denies → propose_only (show plan but don't execute)
        3. If needs_approval → needs_approval
        4. If risk high → propose_only
        5. If ok_to_act and low risk → auto_execute
        6. Default → propose_only (fail-closed)

    Args:
        judgement: JudgementReport from Layer 2.
        route_overrides: Optional overrides from D0 router.

    Returns:
        ExecutionMode with mode, rationale, approval info.
    """
    overrides = route_overrides or {}
    rationale = []

    # Check for forced mode from router
    if overrides.get("force_mode"):
        mode = overrides["force_mode"]
        rationale.append(f"Forced to '{mode}' by router override")
        return ExecutionMode(
            mode=mode,
            rationale=rationale,
        )

    # 1. Missing info → ask clarifying
    if judgement.need_more_info.value:
        questions = [q.question for q in judgement.need_more_info.questions]
        rationale.append("Missing required info — asking clarifying questions")
        return ExecutionMode(
            mode="ask_clarifying",
            questions=questions,
            rationale=rationale,
        )

    # 2. Policy denies → propose only
    if judgement.policy.status == "deny":
        rationale.append(f"Policy denies execution: {judgement.policy.violations}")
        return ExecutionMode(
            mode="propose_only",
            rationale=rationale,
        )

    # 3. Needs approval → needs_approval
    if judgement.needs_approval:
        rationale.append("Approval required by policy or risk threshold")
        rationale.extend(judgement.policy.reasons)
        return ExecutionMode(
            mode="needs_approval",
            approvals_required=judgement.policy.approvals_required,
            rationale=rationale,
        )

    # 4. High risk → propose only
    if judgement.risk.level == "high":
        rationale.append(f"Risk too high ({judgement.risk.score}) — proposing only")
        return ExecutionMode(
            mode="propose_only",
            rationale=rationale,
        )

    # 5. OK to act and low/medium risk → auto execute
    if judgement.ok_to_act:
        rationale.append("All checks passed — safe for auto-execution")
        return ExecutionMode(
            mode="auto_execute",
            rationale=rationale,
        )

    # 6. Default: fail-closed
    rationale.append("Default fail-closed — proposing only")
    return ExecutionMode(
        mode="propose_only",
        rationale=rationale,
    )
