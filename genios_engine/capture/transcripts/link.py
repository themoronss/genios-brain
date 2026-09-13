"""P5 · which meeting was this? — a transcript → the calendar meeting node, or honest candidates.

Order (plan §3): an explicit `meeting_node_id` → a `calendar_event_id` → a Drive file attached to
the calendar event → the SEAT's own meetings that day matched by title (±45 min when a start time
is known). One match links; several come back as `candidates` and the transcript stays UNLINKED
(so its audience is the uploader alone until a person picks); none is unlinked.

Meeting nodes are the calendar's own (`gcal.event.v1`, canonical key `gcal:<event id>`), with
`meeting.start_at` / `meeting.title` facts and `attended` edges to person nodes keyed by email.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import text

WINDOW = timedelta(minutes=45)
RECENT_DAYS = 14
_STOP = frozenset({"the", "a", "an", "and", "with", "of", "for", "to", "on", "call", "meeting",
                   "sync", "transcript", "x", "vs", "re"})


@dataclass(frozen=True)
class MeetingRef:
    meeting_node_id: str
    calendar_event_id: str | None
    title: str
    start_at: datetime | None
    end_at: datetime | None = None
    attendees: tuple[dict, ...] = ()           # {name, email|null, person_node_id|null}

    @property
    def attendee_emails(self) -> tuple[str, ...]:
        return tuple(a["email"] for a in self.attendees if a.get("email"))

    def candidate(self) -> dict:
        return {"meeting_node_id": self.meeting_node_id, "title": self.title,
                "start_at": _iso(self.start_at)}

    def view(self) -> dict:
        """The §3 `/v1/meetings/recent` row."""
        return {"meeting_node_id": self.meeting_node_id,
                "calendar_event_id": self.calendar_event_id, "title": self.title,
                "start_at": _iso(self.start_at), "end_at": _iso(self.end_at),
                "attendees": [dict(a) for a in self.attendees]}


@dataclass(frozen=True)
class LinkResult:
    meeting: MeetingRef | None
    candidates: tuple[MeetingRef, ...] = ()
    calendar_event_id: str | None = None       # as supplied, even when no node carries it


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v is not None else None


def _ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value
        try:
            s = json.loads(value) if value.startswith('"') else value
        except ValueError:
            pass
        try:
            dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except ValueError:
            try:
                d = date.fromisoformat(str(s)[:10])
            except ValueError:
                return None
            dt = datetime.combine(d, time.min)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _tokens(title: str | None) -> set[str]:
    return {t for t in re.findall(r"[\w]+", (title or "").casefold()) if t not in _STOP}


def title_matches(a: str | None, b: str | None) -> bool:
    """Token overlap ≥ half of the shorter title, or one title contains the other."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    na, nb = " ".join(sorted(ta)), " ".join(sorted(tb))
    if ta <= tb or tb <= ta or na == nb:
        return True
    return len(ta & tb) * 2 >= min(len(ta), len(tb)) and len(ta & tb) >= 1


def org_timezone(conn, org_id: str):
    from zoneinfo import ZoneInfo
    try:
        tz = conn.execute(text("select timezone from orgs where id=:o"), {"o": org_id}).scalar()
    except Exception:                          # noqa: BLE001 — a schema without the column: UTC
        tz = None
    try:
        return ZoneInfo(tz) if tz else timezone.utc
    except Exception:                          # noqa: BLE001 — an unknown zone name: UTC
        return timezone.utc


_MEETING_SELECT = (
    "select m.node_id, m.canonical_key, m.display_name, "
    " (select f.value from graph_facts f where f.org_id=m.org_id and f.subject_node_id=m.node_id "
    "   and f.field='meeting.start_at' and f.valid_to is null and f.status='active' "
    "   order by f.occurred_at desc nulls last limit 1) as start_v, "
    " (select f.value from graph_facts f where f.org_id=m.org_id and f.subject_node_id=m.node_id "
    "   and f.field='meeting.end_at' and f.valid_to is null and f.status='active' "
    "   order by f.occurred_at desc nulls last limit 1) as end_v, "
    " (select f.value from graph_facts f where f.org_id=m.org_id and f.subject_node_id=m.node_id "
    "   and f.field='meeting.title' and f.valid_to is null and f.status='active' "
    "   order by f.occurred_at desc nulls last limit 1) as title_v "
    "from graph_nodes m where m.org_id=:o and m.node_type='meeting' and m.valid_to is null ")


def _attendees(conn, org_id: str, node_ids: list[str]) -> dict[str, tuple[dict, ...]]:
    if not node_ids:
        return {}
    rows = conn.execute(text(
        "select m.node_id as meeting, p.node_id, lower(p.canonical_key) as email, p.display_name "
        "from graph_nodes m join graph_edges e on e.org_id=m.org_id and e.edge_type='attended' "
        " and e.valid_to is null and (e.from_node_id=m.node_id or e.to_node_id=m.node_id) "
        "join graph_nodes p on p.org_id=m.org_id and p.valid_to is null and p.node_type='person' "
        " and p.node_id = case when e.from_node_id=m.node_id then e.to_node_id "
        "                      else e.from_node_id end "
        "where m.org_id=:o and m.node_id = any(:n) order by p.display_name"),
        {"o": org_id, "n": node_ids}).fetchall()
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        email = r.email if r.email and "@" in r.email else None
        name = r.display_name if r.display_name and "@" not in r.display_name else None
        out.setdefault(r.meeting, {})[r.node_id] = {
            "name": name or email or "", "email": email, "person_node_id": r.node_id}
    return {k: tuple(v.values()) for k, v in out.items()}


def _refs(conn, org_id: str, rows) -> list[MeetingRef]:
    att = _attendees(conn, org_id, [r.node_id for r in rows])
    out = []
    for r in rows:
        key = str(r.canonical_key or "")
        title = r.title_v if isinstance(r.title_v, str) else (
            str(r.title_v) if r.title_v is not None else "")
        out.append(MeetingRef(
            meeting_node_id=r.node_id,
            calendar_event_id=key.split(":", 1)[1] if key.startswith("gcal:") else None,
            title=title or (r.display_name or ""), start_at=_ts(r.start_v), end_at=_ts(r.end_v),
            attendees=att.get(r.node_id, ())))
    return out


def load_meeting(conn, org_id: str, meeting_node_id: str) -> MeetingRef | None:
    rows = conn.execute(text(_MEETING_SELECT + "and m.node_id=:n"),
                        {"o": org_id, "n": meeting_node_id}).fetchall()
    refs = _refs(conn, org_id, rows)
    return refs[0] if refs else None


def meeting_by_calendar_event(conn, org_id: str, calendar_event_id: str) -> MeetingRef | None:
    rows = conn.execute(text(_MEETING_SELECT + "and m.canonical_key=:k"),
                        {"o": org_id, "k": f"gcal:{calendar_event_id}"}).fetchall()
    refs = _refs(conn, org_id, rows)
    return refs[0] if refs else None


def meeting_by_drive_file(conn, org_id: str, file_id: str) -> MeetingRef | None:
    """The calendar event a Drive transcript Doc is ATTACHED to (Meet attaches it; the calendar
    connector carries `meeting.attachment_file_ids`). Exactly one, or nothing."""
    if not file_id:
        return None
    rows = conn.execute(text(
        "select distinct subject_node_id from graph_facts where org_id=:o "
        "and field='meeting.attachment_file_ids' and valid_to is null and status='active' "
        "and position(:f in cast(value as text)) > 0"), {"o": org_id, "f": file_id}).fetchall()
    if len(rows) != 1:
        return None
    return load_meeting(conn, org_id, rows[0][0])


def seat_meetings(conn, org_id: str, seat_email: str, start: datetime,
                  end: datetime) -> list[MeetingRef]:
    """Meetings the seat attended starting in [start, end), soonest first."""
    email = (seat_email or "").strip().lower()
    if not email:
        return []
    rows = conn.execute(text(
        _MEETING_SELECT +
        "and exists (select 1 from graph_edges e join graph_nodes p on p.org_id=e.org_id "
        " and p.valid_to is null and p.node_type='person' and lower(p.canonical_key)=:e "
        " and (p.node_id=e.from_node_id or p.node_id=e.to_node_id) "
        " where e.org_id=m.org_id and e.edge_type='attended' and e.valid_to is null "
        " and (e.from_node_id=m.node_id or e.to_node_id=m.node_id))"),
        {"o": org_id, "e": email}).fetchall()
    refs = [r for r in _refs(conn, org_id, rows)
            if r.start_at is not None and start <= r.start_at < end]
    return sorted(refs, key=lambda r: r.start_at)


def _day_bounds(day: date, tz) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def link_meeting(conn, org_id: str, *, seat_email: str | None,
                 meeting_node_id: str | None = None, calendar_event_id: str | None = None,
                 drive_file_id: str | None = None, title: str | None = None,
                 day: date | None = None, started_at: datetime | None = None) -> LinkResult:
    if meeting_node_id:
        m = load_meeting(conn, org_id, meeting_node_id)
        return LinkResult(meeting=m, calendar_event_id=(m.calendar_event_id if m else None)
                          or calendar_event_id)
    if calendar_event_id:
        return LinkResult(meeting=meeting_by_calendar_event(conn, org_id, calendar_event_id),
                          calendar_event_id=calendar_event_id)
    if drive_file_id:
        m = meeting_by_drive_file(conn, org_id, drive_file_id)
        if m is not None:
            return LinkResult(meeting=m, calendar_event_id=m.calendar_event_id)
    if day is None and started_at is not None:
        day = started_at.astimezone(org_timezone(conn, org_id)).date()
    if day is None or not seat_email:
        return LinkResult(meeting=None)
    start, end = _day_bounds(day, org_timezone(conn, org_id))
    pool = seat_meetings(conn, org_id, seat_email, start, end)
    if started_at is not None:
        pool = [m for m in pool if m.start_at and abs(m.start_at - started_at) <= WINDOW]
    hits = [m for m in pool if title_matches(title, m.title)] if title else list(pool)
    if title and not hits:
        return LinkResult(meeting=None)
    if len(hits) == 1 and (title or started_at is not None):
        return LinkResult(meeting=hits[0], calendar_event_id=hits[0].calendar_event_id)
    return LinkResult(meeting=None, candidates=tuple(hits))


def recent_meetings(conn, org_id: str, *, seat_email: str, q: str | None = None,
                    day: date | None = None, now: datetime | None = None,
                    days: int = RECENT_DAYS) -> list[MeetingRef]:
    """The upload picker: the seat's meetings in the last `days` days (or on `day`), newest
    first, optionally filtered by a title substring."""
    now = now or datetime.now(timezone.utc)
    if day is not None:
        start, end = _day_bounds(day, org_timezone(conn, org_id))
    else:
        start, end = now - timedelta(days=days), now + timedelta(hours=12)
    refs = seat_meetings(conn, org_id, seat_email, start, end)
    if q:
        needle = q.casefold().strip()
        refs = [r for r in refs if needle in r.title.casefold()]
    return sorted(refs, key=lambda r: r.start_at, reverse=True)


__all__ = ["LinkResult", "MeetingRef", "RECENT_DAYS", "WINDOW", "link_meeting", "load_meeting",
           "meeting_by_calendar_event", "meeting_by_drive_file", "org_timezone",
           "recent_meetings", "seat_meetings", "title_matches"]
