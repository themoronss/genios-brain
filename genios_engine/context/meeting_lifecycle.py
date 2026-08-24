"""Five independent meeting facts that no rule may alias into one.

`meeting.status` was carrying five separate questions at once, and `packs/general_v1`'s
`meeting_no_followup` rule read it as though it answered all of them:

    when meeting.status = 'confirmed' and hours_since(start_at) >= 24 and no_obs followup_sent
      → "send a recap"

`confirmed` is an INVITATION state. Google sets it the moment an event exists; it says the event
was not cancelled, and says nothing about whether it happened, whether the founder was there, or
whether there was anyone on the other side to send a recap TO.

Live consequence, on real data: three cards told the founder to send a recap of cohort workshops
he attended as one participant among twenty — `[Session] Building Your MVP | Launchpad 30`,
`[Session] Early Finance AMA | Launchpad 30`, `[Session] Building Early Metrics Stack`. A
group-wide "recap" there is not merely useless: it discloses the cohort attendee list to the
cohort. Replay 05's assertion 3 forbids exactly this aliasing.

So the five questions get five fields, and the rule has to name the one it means:

    meeting.scheduled              — an event exists and is not cancelled
    meeting.occurred               — its end time is in the past
    meeting.attended               — we have positive evidence the tenant was there
    meeting.external_counterparty  — at least one attendee is outside the tenant
    meeting.open_loop              — it ended with something unresolved

Deterministic. No model. Every field is derivable from what the calendar already gives us.
"""
from __future__ import annotations

from datetime import datetime, timezone

#: An event with more attendees than this is a broadcast, not a conversation. A "recap" to a
#: cohort webinar is addressed to people who were all in the same room, and the recipient list
#: itself is information the tenant does not own.
BROADCAST_ATTENDEES = 8

#: Statuses that mean the event is off. Everything else means an event exists.
CANCELLED = frozenset({"cancelled", "canceled", "declined"})


def _parse(ts) -> datetime | None:
    if isinstance(ts, datetime):
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None


def reduce_meeting(*, status: str | None, start_at, end_at, attendees: list[str] | None,
                   organizer: str | None, internal: set[str], now: datetime,
                   followed_up: bool = False) -> dict:
    """The five fields, plus the evidence for each. Pure."""
    attendees = [a for a in (attendees or []) if a]
    internal_lc = {e.lower() for e in internal if e}
    external = [a for a in attendees if a.lower() not in internal_lc]

    scheduled = (status or "").lower() not in CANCELLED
    end = _parse(end_at) or _parse(start_at)
    occurred = bool(scheduled and end and end < now)

    # ATTENDANCE IS NOT SCHEDULING. Google's `confirmed` is set on the event, not on the person,
    # so it can never distinguish "the founder was there" from "the founder was invited". Without
    # per-attendee responseStatus we have no positive evidence, and the honest answer is None —
    # NOT False (which would read as "he skipped it") and emphatically not True.
    attended: bool | None = None
    if organizer and organizer.lower() in internal_lc:
        attended = True                       # you do not miss the meeting you called

    # A cohort webinar has no counterparty in the sense a follow-up needs: everyone external is
    # a fellow participant, not a person on the other side of a deal.
    external_counterparty = bool(external) and len(attendees) <= BROADCAST_ATTENDEES

    open_loop = bool(occurred and external_counterparty and not followed_up)

    return {
        "meeting.scheduled": scheduled,
        "meeting.occurred": occurred,
        "meeting.attended": attended,
        "meeting.external_counterparty": external_counterparty,
        "meeting.open_loop": open_loop,
        "meeting.attendee_count": len(attendees),
        "meeting.external_count": len(external),
        # Why, in the row itself — so a card that did NOT fire can explain its own absence, which
        # is the half of this that support tickets are actually about.
        "meeting.shape": ("broadcast" if len(attendees) > BROADCAST_ATTENDEES
                          else "one_to_one" if len(attendees) <= 2
                          else "small_group"),
    }


__all__ = ["BROADCAST_ATTENDEES", "CANCELLED", "reduce_meeting"]
