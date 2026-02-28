"""
J5.4 — Constraint Compiler

Produce must/must-not/should constraints for the Decision Layer.
Derived from factors + policies + risk.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import (
    RankedFactor,
    PolicyVerdict,
    RiskReport,
    MultiFactorReport,
)
from layers.layer2_judgement.j5_multifactor.factor_extractors import extract_all_factors
from layers.layer2_judgement.j5_multifactor.ranker import rank_factors


def evaluate_multifactor(
    bundle: ContextBundle,
    intent_type: str,
    policy: PolicyVerdict,
    risk: RiskReport,
) -> MultiFactorReport:
    """
    Full J5 pipeline: extract → rank → compile constraints.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: Canonical intent type.
        policy: PolicyVerdict from J2.
        risk: RiskReport from J3.

    Returns:
        MultiFactorReport with ranked factors, constraints, confidence.
    """
    # Extract all factors
    all_factors = extract_all_factors(bundle, intent_type)

    # Rank top factors
    ranked, confidence = rank_factors(all_factors, top_n=5)

    # Compile constraints from policy + risk + factors
    constraints = _compile_constraints(
        policy=policy,
        risk=risk,
        ranked_factors=ranked,
        intent_type=intent_type,
    )

    return MultiFactorReport(
        ranked_factors=ranked,
        constraints=constraints,
        confidence=confidence,
    )


def _compile_constraints(
    policy: PolicyVerdict,
    risk: RiskReport,
    ranked_factors: list[RankedFactor],
    intent_type: str,
) -> list[str]:
    """
    Derive must/must-not/should constraints.

    These are instructions the Decision Layer MUST obey.
    """
    constraints = []

    # From policy
    constraints.extend(policy.constraints)
    if policy.status == "needs_approval":
        constraints.append("MUST: Do not send without approval")
    if policy.status == "deny":
        constraints.append("MUST NOT: Do not execute this action")

    # From risk
    if risk.level == "high":
        constraints.append("SHOULD: Use conservative tone and template")
    if risk.reversibility == "irreversible":
        constraints.append("SHOULD: Double-check content before execution")

    # From factors
    for factor in ranked_factors:
        if factor.name == "preferred_tone" and factor.value:
            constraints.append(f"SHOULD: Use {factor.value} tone")
        if factor.name.startswith("entity_tier_") and factor.value == "VIP":
            constraints.append("SHOULD: Use VIP communication template")

    return constraints
