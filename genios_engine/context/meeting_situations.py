"""L2 · the Admin reading of a meeting — did the follow-through happen.

**FIFTY MEETINGS, ZERO SITUATIONS.** Everything this reading needs has been in the graph the
whole time and nothing turned it into a claim:

  * `capture/connectors/calendar.py` fetches with `showDeleted`, in its own words "so a
    cancellation is an event we RECEIVE rather than an absence we infer";
  * `capture/structured/registry.py` maps `start` to `meeting.start_at` and `status` to
    `meeting.status`, so a cancellation lands as a fact;
  * `context/meeting_lifecycle.py` writes `meeting.external_counterparty`;
  * `context/meeting_touch._MEETINGS` already joins the `attended` edge to find who was there —
    a query whose comments record three separate bugs found and fixed in it, including two that
    reported the wrong counterparty entirely;
  * and `domain_spec.py` declares `meeting_follow_through` in full, field by field, with each
    field's meaning spelled out.

What did not exist was the reading. `outreach_situations.READINGS` had six entries and `meeting`
was not one of them. Sales has had a meeting reading for some time — `meeting_touch.
refresh_channel_touch_situations`, typed `channel_touch` — but that answers a different question
(which channels has this account been reached through), and Admin, the only domain this tenant
switched on, never got its own. So fifty calendar events produced nodes, facts and edges, and
Layer 3 had nothing to compile because Layer 2 had nothing to route on.

**THE ONE CLAIM THIS MAY NEVER MAKE.** `meeting.recap_sent` has no writer anywhere in the engine,
and `domain_spec` states the reason rather than treating it as a gap to fill: *"an outbound after
a meeting is not necessarily a recap of it — so a card can say the follow-up is not visible and
never that it was not sent."* Every finding therefore DECLARES that field missing instead of
inferring it from the absence of a later message. A card built on this may say "no follow-up is
visible"; it may not say "you did not follow up". That distinction is the whole reason this
module reports rather than concludes.

**WHAT REBOOKED MEANS, AND WHY IT IS NARROW.** A cancellation is only worth a card while it is
still unresolved, and the only evidence of resolution this layer can see is another meeting with
the SAME counterparty, later. Meeting somebody else is not rebooking this, and a card that said
otherwise would be telling a founder to chase a call they have already put back in the diary.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone

#: The anchor. One situation per meeting, because a meeting is the thing that did or did not
#: happen — grouping by counterparty would merge two separate calls into one claim about a person.
ANCHOR_MEETING = "meeting"

#: Statuses that mean the meeting is not going to happen as booked. Matched on a normalised form
#: because a provider writes `cancelled`, `CANCELLED` and `canceled` for the same thing.
_CANCELLED: frozenset[str] = frozenset({"cancelled", "canceled", "declined"})


def _as_utc(value) -> datetime | None:
    """A stored timestamp, or None. Never raises: a malformed date is an absent date, and an
    absent date means this reading has no claim to make about elapsed time."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _counterparties(row: Mapping) -> list[str]:
    """The external attendees, cleaned. `array_agg` yields `[None]` for a row with none."""
    return [str(name).strip() for name in (row.get("counterparties") or []) if str(name or "").strip()]


def read_meeting_follow_through(rows: Iterable[Mapping], now: datetime) -> list:
    """One finding per meeting whose follow-through is an open question.

    `rows` is `meeting_touch._MEETINGS`' own result shape — `node_id`, `display_name`, `start_at`,
    `status`, `counterparties` — reused deliberately rather than re-queried. That query has been
    corrected three times for things this reading would have got wrong in exactly the same way,
    and a second, subtly different copy of it is the trap `_Finding`'s own docstring warns about.

    Two shapes qualify, and both are the same question — *is this meeting finished?*

      * **cancelled and not rebooked** — the strongest, because the cancellation is a stored fact
        rather than an inference, and the only resolution this layer can see is another meeting
        with the same counterparty later;
      * **held, and now in the past** — reported with its elapsed days so a reader can see how
        long ago, with the recap declared missing rather than assumed absent.

    A future meeting yields nothing: nothing has happened, so nothing can have failed to follow.
    A meeting with no external attendee yields nothing either — an internal calendar block is not
    an outside commitment, and `meeting_touch` records what it cost to learn that the owner's own
    person node carries `meeting.external_counterparty` too.
    """
    from genios_engine.context.outreach_situations import _Finding

    meetings = [row for row in rows if row]
    #: Every (counterparty, start) pair in the whole set, so "was this rebooked" is answered
    #: against the tenant's actual diary rather than against one row at a time.
    booked: list[tuple[str, datetime]] = []
    for row in meetings:
        start = _as_utc(row.get("start_at"))
        if start is None or str(row.get("status") or "").strip().lower() in _CANCELLED:
            continue
        for name in _counterparties(row):
            booked.append((name.lower(), start))

    findings: list = []
    for row in meetings:
        node_id = str(row.get("node_id") or "").strip()
        start = _as_utc(row.get("start_at"))
        parties = _counterparties(row)
        if not node_id or start is None or not parties:
            continue

        status = str(row.get("status") or "").strip().lower()
        cancelled = status in _CANCELLED
        # A cancelled call is rebooked when ANY of its counterparties has a live meeting after
        # the one that fell through. Any, not all: a two-person call put back with one of them is
        # back in the diary, and telling the founder to chase it would be wrong.
        rebooked = any(name.lower() == party and when > start
                       for party in (p.lower() for p in parties)
                       for name, when in booked)

        if cancelled and rebooked:
            continue                      # already resolved; a card here is noise
        if not cancelled and start > now:
            continue                      # nothing has happened yet

        days_since = max(0, int((now - start).total_seconds() // 86400))
        facts: list[tuple[str, object, str]] = [
            ("meeting.start_at", start.isoformat(), "timestamp"),
            ("meeting.status", status or "unknown", "enum"),
            ("meeting.external_counterparty", parties[0], "string"),
            ("meeting.days_since", days_since, "number"),
            ("meeting.rebooked", rebooked, "bool"),
        ]
        # EVERY attendee travels, not just the one the card names. `meeting_touch` learned this
        # the expensive way: aggregating with `max()` picked the alphabetically-last name and
        # four unrelated meetings all reported the same counterparty.
        if len(parties) > 1:
            facts.append(("meeting.attendees", list(parties), "list"))

        display = (f"{parties[0]} — meeting cancelled, not rebooked" if cancelled
                   else f"{parties[0]} — met {days_since}d ago")
        findings.append(_Finding(
            anchor=ANCHOR_MEETING,
            canonical_key=f"meeting:{node_id}",
            display_name=display,
            facts=facts,
            concerns_node=node_id,
            correlation_id=f"meeting:{node_id}",
            # DECLARED, NOT INFERRED. `meeting.recap_sent` has no writer, and its absence is not
            # evidence that nothing was sent — `domain_spec` says so in its own comment. Naming
            # it here is what makes the coverage score report "not observed" instead of scoring
            # this reading as complete, so the card can say the follow-up is not VISIBLE.
            missing=["meeting.recap_sent"],
            inputs={"reading": ANCHOR_MEETING,
                    "derived_from": "the calendar's own status and start time; "
                                    "no completion receipt exists"},
        ))
    return findings
