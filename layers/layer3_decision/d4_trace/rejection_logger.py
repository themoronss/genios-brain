"""
D4.3 — Rejection Logger

Log 1-2 rejected alternatives and why.
Shows "what we chose NOT to do" for transparency.
"""

from core.contracts.judgement_report import JudgementReport


# Alternative actions per intent type that were considered but rejected
_ALTERNATIVES = {
    "follow_up": [
        {
            "option": "Auto-send without approval",
            "rejection_reason": "VIP recipient requires human oversight",
        },
        {
            "option": "Delay follow-up to next week",
            "rejection_reason": "Urgency score indicates timely action needed",
        },
    ],
    "reply_email": [
        {
            "option": "Generate reply without user review",
            "rejection_reason": "External communication requires review",
        },
    ],
    "cold_outreach": [
        {
            "option": "Send batch outreach",
            "rejection_reason": "Cold outreach policy requires individual review",
        },
        {
            "option": "Skip compliance check",
            "rejection_reason": "Compliance check is mandatory per org policy",
        },
    ],
    "schedule_meeting": [
        {
            "option": "Auto-schedule without confirmation",
            "rejection_reason": "Meeting requires participant confirmation",
        },
    ],
    "general": [],
}


def log_rejections(
    intent_type: str,
    judgement: JudgementReport,
) -> list[dict[str, str]]:
    """
    Generate rejected alternatives for the decision trace.

    Args:
        intent_type: The chosen intent type.
        judgement: JudgementReport for context.

    Returns:
        List of rejected option dicts.
    """
    rejections = list(_ALTERNATIVES.get(intent_type, []))

    # Add dynamic rejections based on judgement
    if judgement.risk.level == "high" and intent_type != "general":
        rejections.append({
            "option": "Proceed with auto-execution",
            "rejection_reason": f"Risk level '{judgement.risk.level}' exceeds auto-execution threshold",
        })

    return rejections[:3]  # limit to 3 alternatives
