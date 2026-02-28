"""
J3.4 — Risk Aggregator

Weighted risk formula combining:
  - Sensitive entity presence
  - Reversibility
  - External contact flag
  - Tool context (existing thread reduces risk)

Produces final RiskReport.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import RiskReport
from layers.layer2_judgement.j3_risk.sensitive_entity_detector import (
    detect_sensitive_entities,
)
from layers.layer2_judgement.j3_risk.reversibility_scorer import score_reversibility
from layers.layer2_judgement.j0_judgement_planner.thresholds import (
    RISK_HIGH_THRESHOLD,
    RISK_MEDIUM_THRESHOLD,
    RISK_WEIGHTS,
)


def assess_risk(bundle: ContextBundle, intent_type: str) -> RiskReport:
    """
    Full J3 pipeline: detect sensitive entities + reversibility → aggregate risk.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: Canonical intent type.

    Returns:
        RiskReport with score, level, reasons, sensitive_entities, reversibility.
    """
    score = 0.0
    reasons = []

    # 1. Sensitive entity detection
    sensitive = detect_sensitive_entities(bundle, intent_type)
    if any(s.startswith("VIP:") for s in sensitive):
        score += RISK_WEIGHTS["vip_recipient"]
        reasons.append("VIP recipient detected")

    if "external_communication" in sensitive:
        score += RISK_WEIGHTS["external_contact"]
        reasons.append("External communication")

    if any(s.split(":")[0] in ("legal", "finance", "security") for s in sensitive):
        score += RISK_WEIGHTS["sensitive_topic"]
        reasons.append("Sensitive topic detected")

    # 2. Reversibility
    reversibility, rev_penalty = score_reversibility(intent_type)
    score += rev_penalty
    if reversibility == "irreversible":
        reasons.append("Action is irreversible (email)")

    # 3. Existing thread context (reduces risk)
    gmail_data = bundle.tools.snapshots.get("gmail", {})
    if gmail_data.get("thread_exists"):
        score += RISK_WEIGHTS["existing_thread"]
        reasons.append("Existing thread context (risk reduced)")

    # Clamp score
    score = max(0.0, min(1.0, round(score, 3)))

    # Determine level
    if score >= RISK_HIGH_THRESHOLD:
        level = "high"
    elif score >= RISK_MEDIUM_THRESHOLD:
        level = "medium"
    else:
        level = "low"

    return RiskReport(
        score=score,
        level=level,
        reasons=reasons,
        sensitive_entities=sensitive,
        reversibility=reversibility,
    )
