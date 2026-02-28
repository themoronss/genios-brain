"""
J4.3 — Importance Scorer + Distraction Filter

Score importance based on entity tier and org alignment.
Detect distraction (low-leverage tasks in focused mode).
Produces final PriorityReport.
"""

from core.contracts.context_bundle import ContextBundle
from core.contracts.judgement_report import PriorityReport
from layers.layer2_judgement.j4_priority.urgency_scorer import score_urgency


# Entity tier → importance boost
_TIER_IMPORTANCE = {
    "VIP": 0.3,
    "key": 0.2,
    "standard": 0.0,
}

# Intent alignment with org modes
_ORG_MODE_ALIGNMENT = {
    "fundraising": {
        "follow_up": 0.3,
        "cold_outreach": 0.2,
        "reply_email": 0.2,
        "schedule_meeting": 0.1,
        "send_email": 0.1,
        "general": -0.1,
    },
    "hiring": {
        "follow_up": 0.1,
        "cold_outreach": 0.1,
        "reply_email": 0.2,
        "schedule_meeting": 0.2,
        "send_email": 0.1,
        "general": -0.1,
    },
    "default": {},
}


def score_priority(
    bundle: ContextBundle, intent_type: str, org_mode: str = "default"
) -> PriorityReport:
    """
    Full J4 pipeline: urgency + importance + distraction detection.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: Canonical intent type.
        org_mode: Current org focus mode.

    Returns:
        PriorityReport with score, reasons, distraction flag.
    """
    reasons = []

    # 1. Urgency component (0.5 weight)
    urgency, urgency_reasons = score_urgency(bundle, intent_type)
    reasons.extend(urgency_reasons)

    # 2. Importance component (0.5 weight)
    importance = 0.5  # baseline
    importance_reasons = []

    # Entity tier boost
    for entity_name, data in bundle.memory.entity_data.items():
        if isinstance(data, dict):
            tier = data.get("tier", "standard")
            boost = _TIER_IMPORTANCE.get(tier, 0.0)
            if boost > 0:
                importance += boost
                importance_reasons.append(f"{entity_name} is {tier} tier (+{boost})")

    # Org mode alignment
    mode_boosts = _ORG_MODE_ALIGNMENT.get(org_mode, {})
    alignment_boost = mode_boosts.get(intent_type, 0.0)
    if alignment_boost != 0:
        importance += alignment_boost
        importance_reasons.append(f"Org mode '{org_mode}' alignment: {alignment_boost:+.1f}")

    reasons.extend(importance_reasons)

    # 3. Combined score
    combined = round((urgency * 0.5 + min(1.0, importance) * 0.5), 2)

    # 4. Distraction detection
    distraction_flag = combined < 0.3
    if distraction_flag:
        reasons.append("⚠ Low priority — possible distraction from org goals")

    return PriorityReport(
        score=combined,
        reasons=reasons,
        org_mode=org_mode,
        distraction_flag=distraction_flag,
    )
