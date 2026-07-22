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


def _f(v: object) -> float | None:
    """Safe float — None when absent or non-numeric (so 'signal missing' and
    'signal is 0' stay distinguishable for the cue logic)."""
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def build_next_best_action(
    *, subject_name: str, recommend: str, signals: dict, reason: str
) -> ActionRecommendation:
    importance = float(signals.get("importance") or 0.0)
    momentum = float(signals.get("momentum") or 0.0)
    domain = str(signals.get("domain") or "").lower()
    # Neural signals (populated at ingest by the extractor — Step 1b). Optional:
    # absent on symbolic-only subjects, in which case the cue clause is omitted.
    sentiment = _f(signals.get("sentiment"))
    buying_intent = _f(signals.get("buying_intent"))
    ball_in_court = _f(signals.get("ball_in_court"))

    # Known relationship verbs get natural "{verb} {name}" phrasing; ANY other
    # module's action key (e.g. sales "get_meeting_with_economic_buyer") is
    # humanized into a real instruction instead of a generic "Reach out to".
    known = recommend in _VERB
    action_type, verb = _VERB[recommend] if known else (recommend, "")

    # A cooling, important relationship deserves a call, not another email.
    channel = "call" if (momentum <= -0.5 and importance >= 0.7) else "email"
    # Important now; otherwise this week.
    timing = "today" if importance >= 0.7 else ("within_48h" if recommend == "book_meeting_now" else "this_week")

    angle = _ANGLE.get(domain, _ANGLE_DEFAULT)

    # Best-in-class specificity: name the ACTUAL commitment / objection / competitor
    # (from the entity's graph facts, joined in for sales) instead of the generic
    # domain angle. This is the core anti-"name-only" move.
    _commitment = signals.get("commitment")
    _objection = signals.get("objection")
    _competitor = signals.get("competitor")
    if isinstance(_commitment, str) and _commitment.strip():
        focus = f"deliver on what you owe them: {_commitment.strip()}"
    elif isinstance(_objection, str) and _objection.strip():
        focus = f'address their "{_objection.strip()}" objection head-on'
    else:
        focus = angle
    if isinstance(_competitor, str) and _competitor.strip():
        focus += f" — {_competitor.strip()} is in the deal, differentiate hard"

    # Situation cue — WHY now, read from the neural signals. This is what makes
    # the prescription specific to THIS relationship's real state instead of a
    # generic nudge (the anti-"name-only" clause). Deterministic, no LLM.
    cues: list[str] = []
    if ball_in_court is not None and ball_in_court >= 1.0:
        cues.append("you owe the next reply")
    if sentiment is not None and sentiment <= -0.3:
        cues.append("their tone has cooled")
    if buying_intent is not None and buying_intent >= 0.6:
        cues.append("they're leaning in — move fast")
    cue = f" [{'; '.join(cues)}]" if cues else ""

    if known:
        prescription = f"{verb} {subject_name} {_TIMING_TEXT[timing]} — {focus} (via {channel}).{cue}"
    else:
        action_label = recommend.replace("_", " ").strip().capitalize()
        prescription = f"{subject_name} — {action_label} ({_TIMING_TEXT[timing]}, via {channel}) — {focus}.{cue}"

    return ActionRecommendation(
        subject=subject_name,
        action_type=action_type,
        channel=channel,
        timing=timing,
        prescription=prescription,
        reason=reason,
        draft_needed=(
            action_type in ("reply", "follow_up", "update")
            or any(w in recommend for w in ("reengage", "check_in", "meeting", "outreach", "thread", "next_step", "differentiation"))
        ),
    )
