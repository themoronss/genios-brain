"""
J3.3 — Reversibility Scorer

Score how reversible/irreversible an action is.
Emails can't be unsent. Meetings can be rescheduled. Internal notes can be edited.
"""


# Intent → reversibility mapping
_REVERSIBILITY_MAP = {
    "follow_up": "irreversible",       # email sent, can't unsend
    "reply_email": "irreversible",     # email sent
    "send_email": "irreversible",      # email sent
    "cold_outreach": "irreversible",   # first contact, can't undo
    "schedule_meeting": "reversible",  # can reschedule/cancel
    "general": "reversible",           # queries are read-only
}

# Reversibility → numeric penalty
_REVERSIBILITY_PENALTY = {
    "irreversible": 0.25,
    "partial": 0.10,
    "reversible": 0.0,
}


def score_reversibility(intent_type: str) -> tuple[str, float]:
    """
    Determine how reversible the action is.

    Args:
        intent_type: Canonical intent type.

    Returns:
        Tuple of (reversibility_label, risk_penalty).
    """
    reversibility = _REVERSIBILITY_MAP.get(intent_type, "partial")
    penalty = _REVERSIBILITY_PENALTY.get(reversibility, 0.1)
    return reversibility, penalty
