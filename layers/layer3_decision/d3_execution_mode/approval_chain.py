"""
D3.2 — Approval Chain Resolver

Resolve who needs to approve + the interaction strategy.
"""

from core.contracts.judgement_report import JudgementReport
from core.contracts.decision_packet import ExecutionMode


def resolve_approval_chain(
    mode: ExecutionMode,
    judgement: JudgementReport,
) -> ExecutionMode:
    """
    Enrich execution mode with approval chain details.

    Args:
        mode: ExecutionMode from mode_gate_engine.
        judgement: JudgementReport from Layer 2.

    Returns:
        Enriched ExecutionMode.
    """
    if mode.mode != "needs_approval":
        return mode

    # Pull approvers from J2
    if judgement.policy.approvals_required:
        mode.approvals_required = list(judgement.policy.approvals_required)
    else:
        # Default: founder approves
        mode.approvals_required = ["founder"]

    mode.rationale.append(
        f"Approval chain: {', '.join(mode.approvals_required)}"
    )

    return mode
