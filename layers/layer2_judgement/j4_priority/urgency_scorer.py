"""
J4.2 — Urgency Scorer

Score urgency based on:
- Time since last interaction
- Follow-up windows
- Pending deadlines
"""

from core.contracts.context_bundle import ContextBundle


# Intent → base urgency score
_INTENT_URGENCY = {
    "follow_up": 0.7,       # time-sensitive
    "reply_email": 0.8,     # someone is waiting
    "cold_outreach": 0.4,   # proactive, not urgent
    "send_email": 0.5,      # moderate
    "schedule_meeting": 0.6, # coordination needed
    "general": 0.2,         # read-only, low urgency
}


def score_urgency(bundle: ContextBundle, intent_type: str) -> tuple[float, list[str]]:
    """
    Score urgency for the current intent.

    Args:
        bundle: ContextBundle from Layer 1.
        intent_type: Canonical intent type.

    Returns:
        Tuple of (urgency_score 0-1, list of reasons).
    """
    score = _INTENT_URGENCY.get(intent_type, 0.3)
    reasons = []

    # Boost urgency if tool data shows waiting time
    gmail_data = bundle.tools.snapshots.get("gmail", {})
    days_since_reply = gmail_data.get("last_reply_days_ago", 0)

    if days_since_reply > 7:
        score = min(1.0, score + 0.2)
        reasons.append(f"No reply in {days_since_reply} days — urgent follow-up")
    elif days_since_reply > 3:
        score = min(1.0, score + 0.1)
        reasons.append(f"No reply in {days_since_reply} days")

    # Base reason
    reasons.insert(0, f"Intent '{intent_type}' base urgency: {_INTENT_URGENCY.get(intent_type, 0.3)}")

    return round(score, 2), reasons
