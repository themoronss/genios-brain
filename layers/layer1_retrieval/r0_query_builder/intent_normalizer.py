"""
R0.1 — Intent Normalizer

Classify raw intent text into a canonical intent_type.
Uses keyword matching for MVP (no LLM call).
"""

from enum import Enum
from typing import Tuple


class IntentType(str, Enum):
    FOLLOW_UP = "follow_up"
    SCHEDULE_MEETING = "schedule_meeting"
    REPLY_EMAIL = "reply_email"
    COLD_OUTREACH = "cold_outreach"
    SEND_EMAIL = "send_email"
    GENERAL = "general"


# Keywords → intent type mapping (checked in order, first match wins)
_INTENT_KEYWORDS: list[Tuple[list[str], IntentType]] = [
    (["follow up", "follow-up", "followup", "chase", "nudge"], IntentType.FOLLOW_UP),
    (["schedule", "meeting", "calendar", "book a call", "set up a call"], IntentType.SCHEDULE_MEETING),
    (["reply", "respond", "answer", "get back to"], IntentType.REPLY_EMAIL),
    (["cold", "outreach", "introduce myself", "reach out", "first email"], IntentType.COLD_OUTREACH),
    (["send email", "send mail", "write email", "draft email", "compose"], IntentType.SEND_EMAIL),
]


def normalize_intent(raw_intent: str) -> IntentType:
    """
    Convert raw user text into a canonical IntentType.

    Args:
        raw_intent: The user's original prompt/intent text.

    Returns:
        Canonical IntentType enum value.
    """
    text = raw_intent.lower().strip()

    for keywords, intent_type in _INTENT_KEYWORDS:
        if any(kw in text for kw in keywords):
            return intent_type

    return IntentType.GENERAL
