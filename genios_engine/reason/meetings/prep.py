"""`moment.meeting_prep` (P-15) — a meeting the seat attends is about to start: what is open?

DETERMINISTIC, NO LLM (SCREEN_INTEL_P5 §3, frozen). For one meeting node:
  * per known attendee (not the seat itself): role / company, last touch, the top 2 open
    commitments EITHER WAY (theirs = commitments their node `owns`; ours = the seat's own
    commitments whose `commitment.owed_to` names them), and their company's deal stage;
  * the still-open commitments `raised_in` the most recent earlier meeting that shares at least
    one of these attendees;
  * the relevant `recent_changes` (P4 slice helper) on those nodes.

SEAT-VISIBLE ONLY. Facts pass `common.VISIBLE_FACT_SQL` (the P3 spelling of P2's
`context/fact_visibility.viewer_may_read`); an edge (`attended`, `owns`, `works_at`, `raised_in`)
counts only when its source event is readable by the seat (`VISIBLE_EVENT_SQL`) — a commitment
extracted from a transcript private to other attendees is not this seat's. A commitment is named
only through a READABLE `commitment.text`, never its node's display name (which is derived from
the same text). Another seat's private fact therefore never reaches the prep.

204 unless the seat attends: the seat's person node (its email alias) must hold a visible
`attended` edge to the meeting. The moment lives until start + 10 min.

CACHE. `passes.run` precomputes preps for device seats' meetings in the next 3 h into
`moment_cache` under a PRECOMPUTE key of its own; the dedupe key (`store.persist`'s) is separate,
so a suppressed twin can never answer with a stale precomputed headline. The headline's
"in N min" is re-rendered from the cached `prep` meta at evaluate time. Both keys carry the
meeting's graph version (meeting + attendees + the seat + every commitment they own), so any
change to what the prep reads misses the cache.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.platform.identity import norm_email, person_name_key
from genios_engine.reason.moments import store as M
from genios_engine.reason.moments.common import (VISIBLE_EVENT_SQL, VISIBLE_FACT_SQL, aware,
                                                 fact_rows_to_map, iso, parse_ts, text_of,
                                                 viewer_key)

CAPABILITY_ID = "moment.meeting_prep"
CAPABILITY_VERSION = "1"
AFTER_START = timedelta(minutes=10)
PRIOR_DAYS = 120
TOUCH_DAYS = 365
MAX_LINES = 4
PER_ATTENDEE = 2
MAX_EVIDENCE = 20
OPEN_STATUSES = ("open", "pending", "in_progress")
_MEETING_FIELDS = ("meeting.title", "meeting.start_at", "meeting.end_at", "meeting.status")
_CHANGE_LABEL = {"deal.stage": "deal stage", "deal.status": "deal status",
                 "deal.value": "deal value", "deal.amount": "deal amount",
                 "deal.close_date": "close date", "commitment.due_at": "due date",
                 "commitment.status": "status", "meeting.start_at": "start",
                 "person.title": "title", "contract.status": "contract status",
                 "contract.end_date": "contract end"}


@dataclass(frozen=True)
class Attendance:
    meeting_node_id: str
    me: str
    attendees: tuple[str, ...]                     # the OTHER attendees' person nodes
    names: dict = field(default_factory=dict)      # node → display name
    title: str = "Your meeting"
    start_at: datetime | None = None
    end_at: datetime | None = None
    cancelled: bool = False


@dataclass
class Loop:
    node_id: str
    text: str
    due: datetime | None
    ours: bool                                     # True = the seat owes it

    def sort_key(self, now: datetime):
        overdue = self.due is not None and self.due < now
        return (not overdue, self.due or datetime.max.replace(tzinfo=now.tzinfo), self.text)


@dataclass
class PrepRead:
    att: Attendance
    facts: dict = field(default_factory=dict)      # node → field → (value, valid_from)
    nodes: dict = field(default_factory=dict)      # node → (type, display name)
    employer: dict = field(default_factory=dict)   # person → company
    company_deal: dict = field(default_factory=dict)
    theirs: dict = field(default_factory=dict)     # person → [commitment]
    mine: list = field(default_factory=list)       # the seat's own commitments
    emails: dict = field(default_factory=dict)     # person → {emails}
    last_touch: dict = field(default_factory=dict)
    internal: set = field(default_factory=set)     # attendees who are our own seats
    prior: tuple | None = None                     # (meeting node, title, start)
    prior_items: list = field(default_factory=list)
    changes: list = field(default_factory=list)


@dataclass(frozen=True)
class Prep:
    key: str
    content: dict
    subject_ids: list
    duplicate: bool = False


# ── reads ─────────────────────────────────────────────────────────────────────────────────────
_ATTENDANCE = text(
    "with me as (select node_id from graph_aliases where org_id = :o and alias_type = 'email' "
    " and alias_key = :email limit 1) "
    "select p.node_id, p.display_name, (p.node_id = (select node_id from me)) as is_me "
    "from graph_edges e "
    "join graph_nodes m on m.org_id = e.org_id and m.node_id = :m and m.valid_to is null "
    " and m.node_type = 'meeting' "
    "join graph_nodes p on p.org_id = e.org_id and p.valid_to is null and p.node_type = 'person' "
    " and p.node_id = case when e.to_node_id = :m then e.from_node_id else e.to_node_id end "
    "left join source_events se on se.org_id = e.org_id and se.event_id = e.created_by_event_id "
    "where e.org_id = :o and e.edge_type = 'attended' and e.valid_to is null "
    " and (e.to_node_id = :m or e.from_node_id = :m) and " + VISIBLE_EVENT_SQL + " "
    "order by p.node_id")

_FACTS = ("select f.subject_node_id, f.field, f.value, f.valid_from from graph_facts f "
          "where f.org_id = :o and f.subject_node_id = any(:ids) and f.valid_to is null "
          "and f.status = 'active' and " + VISIBLE_FACT_SQL + " "
          "order by f.subject_node_id, f.field, (f.visibility_scope = 'private') desc, "
          "f.occurred_at desc nulls last, f.fact_version_id")


def attendance(conn, *, org_id: str, meeting_node_id: str, email: str | None
               ) -> Attendance | None:
    """The seat's attendance of the meeting, or None (not a meeting / the seat does not attend).
    Two statements."""
    viewer = viewer_key(email)
    key = norm_email(email) or viewer
    if not key or not meeting_node_id:
        return None
    rows = conn.execute(_ATTENDANCE, {"o": org_id, "m": meeting_node_id, "email": key,
                                      "viewer": viewer}).fetchall()
    me = next((r.node_id for r in rows if r.is_me), None)
    if me is None:
        return None
    facts = fact_rows_to_map(conn.execute(text(_FACTS.replace(
        "f.valid_to is null", "f.field = any(:fields) and f.valid_to is null")),
        {"o": org_id, "ids": [meeting_node_id], "fields": list(_MEETING_FIELDS),
         "viewer": viewer}).fetchall()).get(meeting_node_id, {})

    def fv(name):
        hit = facts.get(name)
        return hit[0] if hit else None

    title_row = conn.execute(text("select display_name from graph_nodes where org_id = :o "
                                  "and node_id = :m and valid_to is null"),
                             {"o": org_id, "m": meeting_node_id}).scalar()
    others = tuple(r.node_id for r in rows if not r.is_me)
    return Attendance(
        meeting_node_id=meeting_node_id, me=me, attendees=others,
        names={r.node_id: r.display_name for r in rows},
        title=text_of(fv("meeting.title")) or title_row or "Your meeting",
        start_at=parse_ts(fv("meeting.start_at")), end_at=parse_ts(fv("meeting.end_at")),
        cancelled=(text_of(fv("meeting.status")) or "").lower() == "cancelled")


def live(att: Attendance | None, now: datetime) -> bool:
    """A prep is worth showing from before the start until start + 10 min."""
    return (att is not None and not att.cancelled and att.start_at is not None
            and now < att.start_at + AFTER_START)


def version(conn, *, org_id: str, att: Attendance) -> str:
    """The meeting's graph version: newest fact / edge / observation / loop change on the meeting,
    its attendees, the seat, and every commitment any of them owns. One statement."""
    ids = sorted({att.meeting_node_id, att.me, *att.attendees})
    r = conn.execute(text(
        "with cm as (select to_node_id as nid from graph_edges where org_id = :o "
        " and from_node_id = any(:ids) and edge_type = 'owns' and valid_to is null), "
        "allids as (select unnest(cast(:ids as text[])) as nid union select nid from cm) "
        "select greatest("
        "(select max(valid_from) from graph_facts where org_id = :o "
        " and subject_node_id in (select nid from allids)), "
        "(select max(greatest(valid_from, coalesce(valid_to, valid_from))) from graph_edges "
        " where org_id = :o and (from_node_id in (select nid from allids) "
        " or to_node_id in (select nid from allids))), "
        "(select max(created_at) from graph_observations where org_id = :o "
        " and subject_node_id = any(:ids)), "
        "(select max(greatest(last_seen_at, coalesce(closed_at, last_seen_at))) from open_loops "
        " where org_id = :o and subject_node_id = any(:ids))) as v"),
        {"o": org_id, "ids": ids}).first()
    return iso(aware(r.v)) if r is not None and r.v is not None else "0"


def _edges_from(conn, *, org_id: str, ids, types, viewer):
    if not ids:
        return []
    return conn.execute(text(
        "select e.from_node_id, e.to_node_id, e.edge_type, n.node_type, n.display_name "
        "from graph_edges e join graph_nodes n on n.org_id = e.org_id "
        "and n.node_id = e.to_node_id and n.valid_to is null "
        "left join source_events se on se.org_id = e.org_id and se.event_id = e.created_by_event_id "
        "where e.org_id = :o and e.from_node_id = any(:ids) and e.edge_type = any(:t) "
        "and e.valid_to is null and " + VISIBLE_EVENT_SQL + " order by e.valid_from desc"),
        {"o": org_id, "ids": sorted(set(ids)), "t": list(types), "viewer": viewer}).fetchall()


def _prior_meeting(conn, *, org_id: str, att: Attendance, viewer, now: datetime):
    """(meeting node, title, start) of the most recent earlier meeting sharing an attendee."""
    if not att.attendees or att.start_at is None:
        return None
    rows = conn.execute(text(
        "select distinct m.node_id, m.display_name, f.value from graph_edges e "
        "join graph_nodes m on m.org_id = e.org_id and m.valid_to is null "
        " and m.node_type = 'meeting' and m.node_id <> :m "
        " and m.node_id = case when e.from_node_id = any(:ids) then e.to_node_id "
        " else e.from_node_id end "
        "join graph_facts f on f.org_id = e.org_id and f.subject_node_id = m.node_id "
        " and f.field = 'meeting.start_at' and f.valid_to is null and f.status = 'active' "
        " and " + VISIBLE_FACT_SQL + " "
        "left join source_events se on se.org_id = e.org_id and se.event_id = e.created_by_event_id "
        "where e.org_id = :o and e.edge_type = 'attended' and e.valid_to is null "
        " and (e.from_node_id = any(:ids) or e.to_node_id = any(:ids)) "
        " and " + VISIBLE_EVENT_SQL + " limit 500"),
        {"o": org_id, "m": att.meeting_node_id, "ids": list(att.attendees),
         "viewer": viewer}).fetchall()
    floor = att.start_at - timedelta(days=PRIOR_DAYS)
    best = None
    for r in rows:
        start = parse_ts(r.value)
        if start is None or not (floor <= start < min(att.start_at, now)):
            continue
        if best is None or start > best[2]:
            best = (r.node_id, r.display_name, start)
    return best


def read(conn, *, org_id: str, att: Attendance, email: str | None, now: datetime) -> PrepRead:
    """Everything the prep says, seat-visible (≈ 8 statements)."""
    from genios_engine.reason.moments.slice import _deals, recent_changes
    viewer = viewer_key(email)
    out = PrepRead(att=att)
    people = list(att.attendees)
    for r in _edges_from(conn, org_id=org_id, ids=people + [att.me], types=("works_at", "owns"),
                         viewer=viewer):
        out.nodes.setdefault(r.to_node_id, (r.node_type, r.display_name))
        if r.edge_type == "works_at" and r.node_type == "company" and r.from_node_id != att.me:
            out.employer.setdefault(r.from_node_id, r.to_node_id)
        elif r.edge_type == "owns" and r.node_type == "commitment":
            if r.from_node_id == att.me:
                out.mine.append(r.to_node_id)
            else:
                out.theirs.setdefault(r.from_node_id, []).append(r.to_node_id)
    for r in _deals(conn, org_id, sorted(set(out.employer.values()))):
        out.company_deal.setdefault(r.company, r.deal)
        out.nodes.setdefault(r.deal, ("deal", None))
    out.prior = _prior_meeting(conn, org_id=org_id, att=att, viewer=viewer, now=now)
    if out.prior is not None:
        for r in conn.execute(text(
                "select e.from_node_id, n.node_type, n.display_name from graph_edges e "
                "join graph_nodes n on n.org_id = e.org_id and n.node_id = e.from_node_id "
                "and n.valid_to is null and n.node_type = 'commitment' "
                "left join source_events se on se.org_id = e.org_id "
                "and se.event_id = e.created_by_event_id "
                "where e.org_id = :o and e.to_node_id = :m and e.edge_type = 'raised_in' "
                "and e.valid_to is null and " + VISIBLE_EVENT_SQL + " order by e.from_node_id"),
                {"o": org_id, "m": out.prior[0], "viewer": viewer}):
            out.nodes.setdefault(r.from_node_id, (r.node_type, r.display_name))
            out.prior_items.append(r.from_node_id)
    fact_ids = sorted(set(people) | set(out.nodes) | {att.meeting_node_id})
    out.facts = fact_rows_to_map(conn.execute(text(_FACTS), {
        "o": org_id, "ids": fact_ids, "viewer": viewer}).fetchall())
    seats = {r.e for r in conn.execute(text(
        "select lower(email) as e from org_seats where org_id = :o and email is not null"),
        {"o": org_id})}
    for r in conn.execute(text(
            "select node_id, alias_key from graph_aliases where org_id = :o "
            "and alias_type = 'email' and node_id = any(:ids)"), {"o": org_id, "ids": people}):
        out.emails.setdefault(r.node_id, set()).add(r.alias_key.lower())
        if r.alias_key.lower() in seats:
            out.internal.add(r.node_id)
    if people:
        for r in conn.execute(text(
                "select o.subject_node_id, max(o.occurred_at) as at from graph_observations o "
                "left join source_events se on se.org_id = o.org_id "
                "and se.event_id = o.created_by_event_id "
                "where o.org_id = :o and o.subject_node_id = any(:ids) and o.status = 'active' "
                "and o.occurred_at <= :now and o.occurred_at > :cut and " + VISIBLE_EVENT_SQL +
                " group by 1"),
                {"o": org_id, "ids": people, "now": now, "cut": now - timedelta(days=TOUCH_DAYS),
                 "viewer": viewer}):
            out.last_touch[r.subject_node_id] = aware(r.at)
    change_ids = sorted(set(people) | set(out.employer.values()) | set(out.company_deal.values())
                        | {att.meeting_node_id})
    out.changes = recent_changes(conn, org_id=org_id, node_ids=change_ids, viewer=viewer,
                                 now=now, limit=10)
    return out


# ── compose (pure) ────────────────────────────────────────────────────────────────────────────
def _fact(read_: PrepRead, node: str | None, name: str):
    hit = read_.facts.get(node or "", {}).get(name)
    return hit[0] if hit else None


def _open_loop(read_: PrepRead, node: str, *, ours: bool) -> Loop | None:
    """A commitment as a loop, or None: closed, or its text is not readable by the seat."""
    what = text_of(_fact(read_, node, "commitment.text"))
    status = (text_of(_fact(read_, node, "commitment.status")) or "open").lower()
    if not what or status not in OPEN_STATUSES:
        return None
    return Loop(node_id=node, text=what, due=parse_ts(_fact(read_, node, "commitment.due_at")),
                ours=ours)


def _day(dt: datetime) -> str:
    return f"{dt.day} {dt.strftime('%b')}"


def _loop_text(loop: Loop, now: datetime) -> str:
    who = "You owe" if loop.ours else "They owe"
    if loop.due is not None and loop.due < now:
        return f"{who}: {loop.text} (overdue since {_day(loop.due)})"
    return f"{who}: {loop.text}" + (f" (due {_day(loop.due)})" if loop.due else "")


def _ago(then: datetime, now: datetime) -> str:
    days = (now.date() - then.astimezone(now.tzinfo).date()).days
    if days <= 0:
        return "last touch today"
    return "last touch yesterday" if days == 1 else f"last touch {days} d ago"


def _first(name: str | None) -> str:
    return (name or "").split()[0] if (name or "").split() else "them"


def lead(title: str, start: datetime, now: datetime) -> str:
    """"Acme review in 15 min" / "in 1 h 20 min" / "now" / "started 4 min ago"."""
    mins = int((start - now).total_seconds() // 60)
    if (start - now).total_seconds() > mins * 60:
        mins += 1                                   # 14 min 10 s away reads "in 15 min"
    if mins > 0:
        h, m = divmod(mins, 60)
        span = f"{h} h {m} min" if h and m else (f"{h} h" if h else f"{m} min")
        return f"{title} in {span}"
    if mins == 0:
        return f"{title} now"
    return f"{title} started {-mins} min ago"


def open_meeting_action(meeting_node_id: str) -> dict:
    """Pinned P5 §3: `{"id": "open_meeting", "payload": {"meeting_node_id", "url"}}`. The
    dashboard has no page for a meeting yet, so `url` is null and the desktop opens its own
    panel."""
    return {"id": "open_meeting", "payload": {"meeting_node_id": meeting_node_id, "url": None}}


def ttl_for(start: datetime, now: datetime) -> int:
    return max(60, min(int((start + AFTER_START - now).total_seconds()), 86400))


def compose(read_: PrepRead, *, now: datetime) -> dict | None:
    """The moment content (+ a `prep` meta for re-timing), or None when there is nothing to say.
    Body ≤ 4 lines."""
    att = read_.att
    if att.start_at is None:
        return None
    my_name_keys: dict[str, str] = {}
    for p in att.attendees:
        k = person_name_key(att.names.get(p))
        if k:
            my_name_keys.setdefault(k, p)
    ours_for: dict[str, list[Loop]] = {}
    for c in read_.mine:
        owed = text_of(_fact(read_, c, "commitment.owed_to"))
        if not owed:
            continue
        target = my_name_keys.get(person_name_key(owed)) or next(
            (p for p in att.attendees if owed.strip().lower() in read_.emails.get(p, ())), None)
        loop = _open_loop(read_, c, ours=True) if target else None
        if loop is not None:
            ours_for.setdefault(target, []).append(loop)
    evidence: list[dict] = []
    shown_loops: set[str] = set()
    lines_by_person: list[tuple[tuple, str, list[Loop]]] = []
    for p in att.attendees:
        name = att.names.get(p)
        if not name:
            continue                                # an unnamed node is not a "known attendee"
        loops = [lp for lp in (_open_loop(read_, c, ours=False) for c in read_.theirs.get(p, ()))
                 if lp is not None] + ours_for.get(p, [])
        loops = sorted({lp.node_id: lp for lp in loops}.values(), key=lambda lp: lp.sort_key(now))
        top = loops[:PER_ATTENDEE]
        role = text_of(_fact(read_, p, "person.title"))
        comp = read_.employer.get(p)
        comp_name = (text_of(_fact(read_, comp, "company.name"))
                     or read_.nodes.get(comp, (None, None))[1]) if comp else None
        who = ", ".join(x for x in (role, comp_name) if x)
        parts = [name + (f" ({who})" if who else "")]
        lt = read_.last_touch.get(p)
        if lt is not None:
            parts.append(_ago(lt, now))
        parts.extend(_loop_text(lp, now) for lp in top)
        deal = read_.company_deal.get(comp) if comp else None
        stage = text_of(_fact(read_, deal, "deal.stage")) or text_of(_fact(read_, deal, "deal.status"))
        if stage and p not in read_.internal:
            parts.append(f"Deal: {stage}")
        rank = (-len(loops), p in read_.internal,
                -(lt.timestamp() if lt is not None else 0.0), name)
        lines_by_person.append((rank, " · ".join(parts), top))
    lines_by_person.sort(key=lambda t: t[0])
    prior_line = None
    prior_loops: list[Loop] = []
    if read_.prior is not None:
        pid, ptitle, pstart = read_.prior
        person_loops = {lp.node_id for _, _, top in lines_by_person for lp in top}
        prior_loops = sorted(
            (lp for lp in (_open_loop(read_, c, ours=c in read_.mine) for c in read_.prior_items)
             if lp is not None and lp.node_id not in person_loops),
            key=lambda lp: lp.sort_key(now))
        if prior_loops:
            label = text_of(_fact(read_, pid, "meeting.title")) or ptitle or "last meeting"
            prior_line = (f"Still open from {label} ({_day(pstart)}): "
                          + "; ".join(lp.text for lp in prior_loops[:3])
                          + (f" +{len(prior_loops) - 3}" if len(prior_loops) > 3 else ""))
    change_line = None
    names = {**{n: nm for n, (_, nm) in read_.nodes.items()}, **att.names}
    for ch in read_.changes:
        label = _CHANGE_LABEL.get(ch["field"])
        old, new = text_of(ch["old"]), text_of(ch["new"])
        if label is None or not old or not new:
            continue
        subject = (text_of(_fact(read_, ch["node_id"], "company.name"))
                   or names.get(ch["node_id"]))
        if ch["node_id"] == att.meeting_node_id:
            subject = "Meeting"
        if ch["node_id"] in read_.company_deal.values():
            comp = next((c for c, d in read_.company_deal.items() if d == ch["node_id"]), None)
            subject = (text_of(_fact(read_, comp, "company.name"))
                       or read_.nodes.get(comp, (None, None))[1]) if comp else subject
        change_line = f"Changed: {subject + ' ' if subject else ''}{label} {old} → {new}"
        evidence.append({"node_id": ch["node_id"], "field": ch["field"], "source": "graph",
                         "at": ch["changed_at"]})
        break
    if not lines_by_person and prior_line is None:
        return None
    extra = [x for x in (prior_line, change_line) if x]
    capacity = MAX_LINES - len(extra)
    if capacity < 1 and change_line:
        extra.remove(change_line)
        capacity += 1
    people_lines = [line for _, line, _ in lines_by_person]
    if len(people_lines) > capacity:
        rest = len(people_lines) - capacity + 1
        people_lines = people_lines[:capacity - 1] + [f"+{rest} more attendees"] \
            if capacity > 1 else [people_lines[0] + f" · +{rest - 1} more"]
    body = "\n".join(people_lines + extra)
    all_loops = [lp for _, _, top in lines_by_person for lp in top] + prior_loops
    for lp in all_loops:
        evidence.append({"node_id": lp.node_id, "field": "commitment.text", "source": "graph"})
    for p in att.attendees:
        if read_.last_touch.get(p) is not None:
            evidence.append({"node_id": p, "field": "last_touch_at", "source": "graph",
                             "at": iso(read_.last_touch[p])})
    if read_.prior is not None and prior_loops:
        evidence.append({"node_id": read_.prior[0], "field": "raised_in", "source": "graph"})
    evidence.insert(0, {"node_id": att.meeting_node_id, "field": "meeting.start_at",
                        "source": "graph", "at": iso(att.start_at)})
    who = [rank[-1] for rank, _, top in lines_by_person if top]     # most loops first
    if all_loops:
        n = len(all_loops)
        tail = f" — {n} open loop{'s' if n != 1 else ''}"
        if who:
            tail += f" with {_first(who[0])}" + (f" +{len(who) - 1}" if len(who) > 1 else "")
    else:
        named = [att.names[p] for p in att.attendees if att.names.get(p)]
        tail = (f" — with {_first(named[0])}" + (f" +{len(named) - 1}" if len(named) > 1 else "")
                if named else "")
    meta = {"meeting_node_id": att.meeting_node_id, "title": att.title,
            "start_at": iso(att.start_at), "tail": tail}
    return {"kind": "advice", "priority": "high",
            "headline": (lead(att.title, att.start_at, now) + tail)[:300],
            "body": body[:2000],
            "actions": [open_meeting_action(att.meeting_node_id)],
            "evidence": evidence[:MAX_EVIDENCE], "ttl_seconds": ttl_for(att.start_at, now),
            "capability_id": CAPABILITY_ID, "capability_version": CAPABILITY_VERSION,
            "prep": meta}


def retime(cached: dict, now: datetime) -> dict | None:
    """A precomputed prep re-rendered for `now` (headline + TTL), or None when unusable."""
    meta = cached.get("prep") if isinstance(cached, dict) else None
    start = parse_ts(meta.get("start_at")) if isinstance(meta, dict) else None
    if start is None or now >= start + AFTER_START:
        return None
    keys = ("kind", "priority", "body", "actions", "evidence", "capability_id",
            "capability_version")
    out = {k: cached.get(k) for k in keys}
    out.update({"headline": (lead(meta.get("title") or "Your meeting", start, now)
                             + (meta.get("tail") or ""))[:300],
                "ttl_seconds": ttl_for(start, now), "prep": meta})
    return out


# ── keys + the evaluate / precompute entry points ─────────────────────────────────────────────
def keys(*, seat_id: str, att: Attendance, graph_version: str, now: datetime) -> tuple[str, str]:
    """(dedupe key — `store.persist`'s, precompute key — the pass's). "Last touch N d ago"
    changes daily, so the day is part of both."""
    trig = M.trigger_digest(CAPABILITY_ID, att.meeting_node_id, iso(att.start_at),
                            now.date().isoformat())
    dedupe = M.cache_key(seat_id=seat_id, capability_id=CAPABILITY_ID,
                         subject_ids=[att.meeting_node_id], trigger=trig,
                         subject_version=graph_version)
    pre = M.cache_key(seat_id=seat_id, capability_id=CAPABILITY_ID + ".precomputed",
                      subject_ids=[att.meeting_node_id], trigger=trig,
                      subject_version=graph_version)
    return dedupe, pre


def subject_ids(att: Attendance) -> list[str]:
    return [att.meeting_node_id, *list(att.attendees)[:19]]


def lookup(conn, *, org_id: str, seat_id: str, email: str | None, meeting_node_id: str,
           now: datetime) -> Prep | None:
    """The evaluate read: None (→ 204) unless the seat attends a live meeting and there is
    something to say; a SHOWN twin → `duplicate`; else the precomputed prep re-timed, or a fresh
    one built."""
    att = attendance(conn, org_id=org_id, meeting_node_id=meeting_node_id, email=email)
    if not live(att, now):
        return None
    dedupe, pre = keys(seat_id=seat_id, att=att,
                       graph_version=version(conn, org_id=org_id, att=att), now=now)
    hit = M.cached(conn, dedupe, now)
    if hit is not None and hit.get("displayed"):
        return Prep(key=dedupe, content=M._public(hit), subject_ids=subject_ids(att),
                    duplicate=True)
    pre_hit = M.cached(conn, pre, now)
    content = retime(pre_hit, now) if pre_hit is not None else None
    if content is None:
        content = compose(read(conn, org_id=org_id, att=att, email=email, now=now), now=now)
    if content is None:
        return None
    content = with_delegate(conn, org_id=org_id, att=att, content=content, now=now)
    return Prep(key=dedupe, content=content, subject_ids=subject_ids(att))


# ── P6 §3.5 · "Ask my agent" to reschedule ────────────────────────────────────────────────────
_CALENDAR_PROVIDER = {"gcal": "google", "outlook": "microsoft", "msgraph": "microsoft"}


def delegate_reschedule(conn, *, org_id: str, att: Attendance, now: datetime) -> dict | None:
    """The `delegate` action for `email.reschedule` — only when an active agent runs that play
    and the meeting carries a provider event id (a `gcal:<id>` node). The windows and message are
    deterministic starting points the person edits before approving; nothing is sent here."""
    from zoneinfo import ZoneInfo

    from genios_engine.contracts import plays as PL
    from genios_engine.platform.agent_plays import select_agent
    if att.start_at is None:
        return None
    agent = select_agent(conn, org_id, PL.PLAY_RESCHEDULE)
    if agent is None:
        return None
    key = conn.execute(text(
        "select canonical_key from graph_nodes where org_id = :o and node_id = :m "
        "and valid_to is null"), {"o": org_id, "m": att.meeting_node_id}).scalar()
    source, _, event_id = str(key or "").partition(":")
    provider = _CALENDAR_PROVIDER.get(source)
    if provider is None or not event_id:
        return None
    emails = sorted({str(r.alias_key).strip().lower() for r in conn.execute(text(
        "select alias_key from graph_aliases where org_id = :o and alias_type = 'email' "
        "and node_id = any(:ids)"), {"o": org_id, "ids": list(att.attendees)}) if r.alias_key})
    tz_name = conn.execute(text("select timezone from orgs where id = :o"),
                           {"o": org_id}).scalar() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:              # noqa: BLE001 — an unknown stored zone falls back to UTC
        tz_name, tz = "UTC", ZoneInfo("UTC")
    windows = PL.reschedule_windows(att.start_at, att.end_at, now=now)

    def local(v: str) -> str:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(tz).strftime(
            "%a %d %b %H:%M")
    offer = "; ".join(f"{local(w['start'])}–{local(w['end'])[-5:]}" for w in windows)
    params = {"meeting_ref": {"provider": provider, "event_id": event_id},
              "attendees": emails, "current_start": PL.iso_utc(att.start_at),
              "proposed_windows": windows,
              "message_draft": (f"Hi — could we move “{att.title}”? Would one of these work "
                                f"instead: {offer} ({tz_name})? Thanks."),
              "timezone": tz_name}
    return PL.delegate_action(PL.PLAY_RESCHEDULE, params, agent)


def with_delegate(conn, *, org_id: str, att: Attendance, content: dict | None,
                  now: datetime) -> dict | None:
    """`content` + the §3.5 delegate action when one applies (never twice). A failed lookup never
    costs the prep itself."""
    if content is None or any(isinstance(a, dict) and a.get("id") == "delegate"
                              for a in content.get("actions") or ()):
        return content
    try:
        action = delegate_reschedule(conn, org_id=org_id, att=att, now=now)
    except Exception:              # noqa: BLE001 — the prep is worth more than the extra button
        return content
    if action is None:
        return content
    return {**content, "actions": [*(content.get("actions") or []), action]}


def precompute(engine, *, org_id: str, seat_id: str, email: str | None, meeting_node_id: str,
               now: datetime) -> bool:
    """Store the prep under its precompute key unless it is already there. True when written."""
    import json
    with engine.connect() as c:
        att = attendance(c, org_id=org_id, meeting_node_id=meeting_node_id, email=email)
        if not live(att, now):
            return False
        _, pre = keys(seat_id=seat_id, att=att,
                      graph_version=version(c, org_id=org_id, att=att), now=now)
        if M.cached(c, pre, now) is not None:
            return False
        content = compose(read(c, org_id=org_id, att=att, email=email, now=now), now=now)
        content = with_delegate(c, org_id=org_id, att=att, content=content, now=now)
    if content is None:
        return False
    with engine.begin() as c:
        return c.execute(text(
            "insert into moment_cache (key, org_id, seat_id, moment, expires_at) "
            "values (:k, :o, :s, cast(:m as jsonb), :exp) on conflict (key) do nothing "
            "returning 1"),
            {"k": pre, "o": org_id, "s": seat_id,
             "m": json.dumps({**content, "displayed": False}, default=str),
             "exp": att.start_at + AFTER_START}).first() is not None


__all__ = ["AFTER_START", "Attendance", "CAPABILITY_ID", "CAPABILITY_VERSION", "Loop", "Prep",
           "PrepRead", "attendance", "compose", "keys", "lead", "live", "lookup", "precompute",
           "read", "retime", "subject_ids", "ttl_for", "version"]
