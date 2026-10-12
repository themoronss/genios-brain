"""The meetings of a day, for a seat — today's and tomorrow's, and the ones nobody followed up (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.4 item 1, tree `yc2_w27_s15` M44.C2.L-data.V0.U04 (`03` s15-F11). Meeting prep
was a desktop moment: precomputed only for a seat with a live device and a meeting in the next three hours, and
nothing composed the day's meetings. The brief needs two things a calendar holds and nothing read:

  THE DAY'S MEETINGS — every meeting the seat attends whose start falls today or tomorrow in the org's timezone,
    cancelled ones out; each with its title, its times and the OTHER attendees by name (never an address).
  NO FOLLOW-UP (F54) — every EXTERNAL meeting of the last fourteen days whose follow-up week has passed with no
    mail of ours to any attendee: *"the Bluebay mixer of 20 Aug — no follow-up to anyone you met"*. External: at
    least one attendee is not us (`platform/self_identity`). Never a gathering of more than ten, nor a session of
    a series (another meeting of the tenant carries its title) — F31: a cohort session is not an obligation.

SEAT-VISIBLE. The seat attends a meeting through an `attended` edge whose source event it may read — the rule of
`context/fact_visibility` (a private event reads only to its principals), written into each statement as a literal
so the SQL census reads each as the one statement it is — and a meeting's facts and attendees pass the same rule. Read over one connection, as of an instant; no model, nothing written.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from genios_engine.context.coverage_receipt import MAILBOX_SOURCES
from genios_engine.platform.self_identity import identity_for, spoken_name

#: More attendees than this is a gathering, not a meeting anybody owes a follow-up (F31).
GATHERING_OVER = 10
#: How far back a meeting may still be owed a follow-up, and how long the follow-up week is.
LOOKBACK_DAYS = 14
FOLLOW_UP_DAYS = 7

#: Every meeting the seat attends, with its time, title and status facts — readable by the seat.
_MINE = text(
    "with me as (select node_id from graph_aliases where org_id = :o and alias_type = 'email' "
    "            and alias_key = any(:mine)), "
    "attends as (select distinct e.to_node_id as meeting_id from graph_edges e "
    "  left join source_events se on se.org_id = e.org_id and se.event_id = e.created_by_event_id "
    " where e.org_id = :o and e.edge_type = 'attended' and e.valid_to is null "
    "   and e.from_node_id in (select node_id from me) and "
    "(se.event_id is null or se.visibility_scope is distinct from 'private' or "
    "coalesce(cast(:viewer as text) = any(coalesce(se.visibility_principals, cast('{}' as text[]))), false)) "
    ") "
    "select m.node_id, m.display_name, f.field, f.value #>> '{}' as value "
    "  from graph_nodes m join attends a on a.meeting_id = m.node_id "
    "  left join graph_facts f on f.org_id = m.org_id and f.subject_node_id = m.node_id "
    "       and f.valid_to is null and f.status = 'active' and (f.visibility_scope is distinct from 'private' or "
    "       coalesce(cast(:viewer as text) = any(coalesce(f.visibility_principals, cast('{}' as text[]))), false)) "
    "       and f.field in ('meeting.title', 'meeting.start_at', 'meeting.end_at', 'meeting.status') "
    " where m.org_id = :o and m.node_type = 'meeting' and m.valid_to is null "
    " order by m.node_id, f.field, f.occurred_at desc nulls last")

#: Each of these meetings' attendees — the person, their name, their addresses — through a readable edge.
_ATTENDEES = text(
    "select e.to_node_id as meeting_id, p.node_id, p.display_name, p.canonical_key, a.alias_key as email "
    "  from graph_edges e "
    "  join graph_nodes p on p.org_id = e.org_id and p.node_id = e.from_node_id and p.valid_to is null "
    "  left join graph_aliases a on a.org_id = p.org_id and a.node_id = p.node_id and a.alias_type = 'email' "
    "  left join source_events se on se.org_id = e.org_id and se.event_id = e.created_by_event_id "
    " where e.org_id = :o and e.edge_type = 'attended' and e.valid_to is null "
    "   and e.to_node_id = any(:ids) and "
    "(se.event_id is null or se.visibility_scope is distinct from 'private' or "
    "coalesce(cast(:viewer as text) = any(coalesce(se.visibility_principals, cast('{}' as text[]))), false)) "
    " order by e.to_node_id, p.node_id")

#: How many meetings of the tenant carry each title — a title two meetings share is a series.
_SERIES = text(
    "select lower(f.value #>> '{}') as title, count(distinct f.subject_node_id) as n from graph_facts f "
    "  join graph_nodes m on m.org_id = f.org_id and m.node_id = f.subject_node_id and m.valid_to is null "
    "       and m.node_type = 'meeting' "
    " where f.org_id = :o and f.field = 'meeting.title' and f.valid_to is null and f.status = 'active' "
    "   and lower(f.value #>> '{}') = any(:titles) "
    " group by 1")

#: The mail that went to any of the given addresses in a window — whose it was is asked of the identity.
_MAIL_TO = text(
    "select lower(se.actor->>'email') as sender, se.recipients, se.occurred_at from source_events se "
    " where se.org_id = :o and se.source = any(:mail) and se.occurred_at > :since and se.occurred_at <= :now "
    "   and se.recipients && cast(:to as text[])")


@dataclass(frozen=True, slots=True)
class DayMeeting:
    meeting_id: str
    title: str
    start_at: datetime
    end_at: datetime | None
    attendees: tuple[str, ...]           # the other attendees, by name — the unnamed are counted, not named
    unnamed: int                          # other attendees with no name to say
    size: int                             # everyone on it, us included
    external: bool


@dataclass(frozen=True, slots=True)
class MeetingDay:
    local_date: date
    today: tuple[DayMeeting, ...]
    tomorrow: tuple[DayMeeting, ...]
    no_follow_up: tuple[DayMeeting, ...]


def _instant(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def meetings_of_day(conn, org_id: str, *, emails: Iterable[str], now: datetime, tz: str) -> MeetingDay:
    """The seat's meetings of today and tomorrow in `tz`, and the external meetings nobody followed up — as of
    `now`. `emails` are the seat's addresses (the first is the viewer whose private events it may read)."""
    given = list(dict.fromkeys(str(e).strip().lower() for e in emails if str(e or "").strip()))
    mine = sorted(given)
    zone = ZoneInfo(tz)
    local = now.astimezone(zone).date()
    if not mine:
        return MeetingDay(local_date=local, today=(), tomorrow=(), no_follow_up=())
    viewer = given[0]                       # the seat's own address, as given first — never the alphabet's first
    facts: dict[str, dict] = {}
    for r in conn.execute(_MINE, {"o": org_id, "mine": mine, "viewer": viewer}):
        held = facts.setdefault(r.node_id, {"name": r.display_name})
        if r.field and r.field not in held:
            held[r.field] = r.value
    meetings = {m: f for m, f in facts.items()
                if _instant(f.get("meeting.start_at")) is not None
                and str(f.get("meeting.status") or "").lower() != "cancelled"}
    us = identity_for(conn, org_id)
    people: dict[str, dict[str, tuple]] = {}
    for r in conn.execute(_ATTENDEES, {"o": org_id, "ids": sorted(meetings), "viewer": viewer}):
        person = people.setdefault(r.meeting_id, {}).setdefault(r.node_id, (r.display_name, r.canonical_key, set()))
        if r.email:
            person[2].add(r.email.lower())
    titles = sorted({str(f.get("meeting.title") or f["name"] or "").lower() for f in meetings.values()} - {""})
    series = {r.title: int(r.n) for r in conn.execute(_SERIES, {"o": org_id, "titles": titles})} if titles else {}

    def build(meeting_id: str) -> tuple[DayMeeting, set[str], bool]:
        f = meetings[meeting_id]
        title = str(f.get("meeting.title") or f["name"] or "a meeting")
        named, unnamed, addresses, external = [], 0, set(), False
        everyone = people.get(meeting_id, {})
        for node, (display, key, emails_of) in sorted(everyone.items()):
            ours = us.is_us_node("person", key) or any(us.is_us(e) for e in emails_of)
            if ours:
                continue
            external = True
            addresses |= emails_of | ({str(key).lower()} if key and "@" in str(key) else set())
            said = spoken_name(display, key)
            if said:
                named.append(said)
            else:
                unnamed += 1
        series_of = series.get(title.lower(), 1) > 1
        return (DayMeeting(meeting_id=meeting_id, title=title, start_at=_instant(f["meeting.start_at"]),
                           end_at=_instant(f.get("meeting.end_at")), attendees=tuple(dict.fromkeys(named)),
                           unnamed=unnamed, size=len(everyone), external=external),
                addresses, series_of)

    built = {m: build(m) for m in meetings}
    today = tuple(sorted((b[0] for b in built.values() if b[0].start_at.astimezone(zone).date() == local),
                         key=lambda d: (d.start_at, d.meeting_id)))
    tomorrow = tuple(sorted((b[0] for b in built.values()
                             if b[0].start_at.astimezone(zone).date() == local + timedelta(days=1)),
                            key=lambda d: (d.start_at, d.meeting_id)))

    owed = {m: b for m, b in built.items()
            if b[0].external and not b[2] and b[0].size <= GATHERING_OVER and b[1]
            and now - timedelta(days=LOOKBACK_DAYS) <= b[0].start_at <= now - timedelta(days=FOLLOW_UP_DAYS)}
    followed: set[str] = set()
    if owed:
        to = sorted(set().union(*(b[1] for b in owed.values())))
        since = min(b[0].start_at for b in owed.values())
        sent = [(r.recipients or (), r.occurred_at) for r in conn.execute(
            _MAIL_TO, {"o": org_id, "mail": sorted(MAILBOX_SOURCES), "since": since, "now": now, "to": to})
            if us.is_us(r.sender)]
        for m, (meeting, addresses, _series) in owed.items():
            end = meeting.start_at + timedelta(days=FOLLOW_UP_DAYS)
            if any(meeting.start_at < at <= end and addresses & {str(x).lower() for x in recipients}
                   for recipients, at in sent):
                followed.add(m)
    no_follow_up = tuple(sorted((owed[m][0] for m in owed if m not in followed),
                                key=lambda d: (d.start_at, d.meeting_id)))
    return MeetingDay(local_date=local, today=today, tomorrow=tomorrow, no_follow_up=no_follow_up)


__all__ = ["DayMeeting", "FOLLOW_UP_DAYS", "GATHERING_OVER", "LOOKBACK_DAYS", "MeetingDay", "meetings_of_day"]
