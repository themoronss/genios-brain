"""
D4.1 — Reason Graph Builder

Build the authority trace: why this plan, which policies, which factors, what sources.
This is the "audit trail" that survives scrutiny.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import JudgementReport
from core.contracts.decision_packet import DecisionTrace, ExecutionMode


def build_reason_graph(
    bundle: ContextBundle,
    judgement: JudgementReport,
    execution: ExecutionMode,
    intent_type: str,
    slots: dict[str, str],
) -> DecisionTrace:
    """
    Build the complete decision trace.

    Args:
        bundle: ContextBundle from Layer 1.
        judgement: JudgementReport from Layer 2.
        execution: ExecutionMode from D3.
        intent_type: Final intent type.
        slots: Extracted slots.

    Returns:
        DecisionTrace with why, policies, factors, sources.
    """
    # Why: combine risk reasons + policy reasons + priority reasons
    why = []
    why.extend(judgement.risk.reasons)
    why.extend(judgement.policy.reasons)
    why.extend(judgement.priority.reasons[:3])  # limit priority reasons
    why.extend(execution.rationale)

    # Policies: list matched policy IDs + effects
    policies = []
    for rule in bundle.policy.rules:
        policy_id = rule.get("id", "unknown")
        effect = rule.get("effect", {})
        policies.append(f"{policy_id}: {effect}")

    # Factors: top ranked factors from J5
    factors = []
    for f in judgement.multi_factor.ranked_factors:
        factors.append(f"{f.name} ({f.category}): {f.value} [w={f.weight}]")

    # Sources: from bundle source map
    sources = []
    for src in bundle.source_map[:10]:  # limit to 10
        sources.append(f"{src.source_type}/{src.source_id} (conf={src.confidence})")

    return DecisionTrace(
        why=why,
        policies=policies,
        factors=factors,
        sources=sources,
    )
