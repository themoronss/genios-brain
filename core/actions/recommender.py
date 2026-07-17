"""Next-Best-Action recommender — PURE, deterministic. Given a fired rule's
`recommend` key + the subject's signals, produce a concrete prescription:
verb + subject + timing + channel + angle. The LLM only drafts the body later.

Generic across founder (investor/customer/hire/partner) and sales — the angle is
chosen by the subject's `domain` signal, so one policy serves both.
"""

from __future__ import annotations

from dataclasses import dataclass

# recommend-key → (action_type, base verb)
_VERB = {
    "reply_now": ("reply", "Reply to"),
    "book_meeting_now": ("schedule", "Book a call with"),
    "follow_up": ("follow_up", "Follow up with"),
    "send_update": ("update", "Send an update to"),
}

# domain → the angle that actually lands with that kind of relationship
_ANGLE = {
    "investor": "lead with your latest traction / momentum metric",
    "customer": "reference the ROI / value they cared about and remove the blocker",
    "hire": "reaffirm the mission and answer their open question",
    "partner": "restate the mutual win and propose concrete scope",
    "vendor": "confirm terms and the timeline",
    "team": "close the loop on your commitment",
    "advisor": "share the specific ask and recent progress",
}
_ANGLE_DEFAULT = "reference your last exchange and propose one clear next step"

_TIMING_TEXT = {"today": "today", "within_48h": "within 48h", "this_week": "this week"}


@dataclass(frozen=True)
class ActionRecommendation:
    subject: str
    action_type: str
    channel: str  # "call" | "email"
    timing: str  # "today" | "within_48h" | "this_week"
    prescription: str  # human, specific
    reason: str
    draft_needed: bool  # whether to generate a message draft via the draft engine


def build_next_best_action(
    *, subject_name: str, recommend: str, signals: dict, reason: str
) -> ActionRecommendation:
    importance = float(signals.get("importance") or 0.0)
    momentum = float(signals.get("momentum") or 0.0)
    domain = str(signals.get("domain") or "").lower()

    action_type, verb = _VERB.get(recommend, ("reach_out", "Reach out to"))

    # A cooling, important relationship deserves a call, not another email.
    channel = "call" if (momentum <= -0.5 and importance >= 0.7) else "email"
    # Important now; otherwise this week.
    timing = "today" if importance >= 0.7 else ("within_48h" if recommend == "book_meeting_now" else "this_week")

    angle = _ANGLE.get(domain, _ANGLE_DEFAULT)
    prescription = f"{verb} {subject_name} {_TIMING_TEXT[timing]} — {angle} (via {channel})."

    return ActionRecommendation(
        subject=subject_name,
        action_type=action_type,
        channel=channel,
        timing=timing,
        prescription=prescription,
        reason=reason,
        draft_needed=action_type in ("reply", "follow_up", "update"),
    )
