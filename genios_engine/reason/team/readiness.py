"""P-12 · milestone readiness — done / pending / away before a dated goal. Template text only (the
LLM narrative is cut, SCREEN_INTEL_P4 §2).

A milestone (`team_milestones`, 0151) is measured on read and in the team pass:

    done / pending  the owner's commitments due in the `COMMITMENT_LOOKBACK_DAYS` before the date
                    (owned by or owed to the owner seat; with a scope: owned by the scope's seats)
                    + tracker `task` nodes matching `task_filter.query` (Linear, `linear.issue.v1`)
    away            every active seat with an absence window between today and the due date
                    (a scope narrows the work counted, not who is counted away)

The report goes to the milestone owner once the date is within `READINESS_HORIZON_DAYS`, and again
only when a count or the set of away seats changes (the digest).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.context.correlation_people import (PeopleDirectory, answering_for,
                                                      commitment_links, load_directory,
                                                      org_visible_windows)
from genios_engine.reason.team.common import (Situation, TeamContext, day, digest, span,
                                              window_evidence)

CAPABILITY = "team.readiness"
READINESS_HORIZON_DAYS = 14
COMMITMENT_LOOKBACK_DAYS = 60
QUERY_MAX = 200
#: Tracker states. Linear's `state.type` is the reliable one (completed / canceled); the free-text
#: state name is the fallback for trackers that only have names.
DONE_TASK_STATES = frozenset({"completed", "done", "closed", "resolved", "shipped", "merged"})
DROPPED_TASK_STATES = frozenset({"canceled", "cancelled", "duplicate", "won't do", "wont do"})
_TASK_TEXT_FIELDS = ("task.title", "task.identifier", "task.project", "task.team", "task.labels")


def normalize_task_filter(value: Any) -> dict | None:
    """The pinned shape: `{"query": "<text>"}` or null. Raises ValueError on anything else."""
    if value is None or value == {}:
        return None
    if not isinstance(value, dict) or set(value) - {"query"}:
        raise ValueError('task_filter must be {"query": "<text>"} or null')
    q = value.get("query")
    if q is None or (isinstance(q, str) and not q.strip()):
        return None
    if not isinstance(q, str) or len(q.strip()) > QUERY_MAX:
        raise ValueError(f"task_filter.query must be text of at most {QUERY_MAX} characters")
    return {"query": q.strip()}


@dataclass(frozen=True)
class Milestone:
    milestone_id: str
    title: str
    due_at: datetime
    owner_seat_id: str
    scope_kind: str | None
    scope_key: str | None
    task_filter: dict | None

    @property
    def due(self) -> date:
        return self.due_at.date()

    @property
    def query(self) -> str | None:
        return (self.task_filter or {}).get("query") or None

    @property
    def scoped(self) -> bool:
        return bool(self.scope_kind and self.scope_key)


def load_milestones(conn, org_id: str, *, milestone_id: str | None = None) -> list[Milestone]:
    rows = conn.execute(text(
        "select milestone_id, title, due_at, owner_seat_id, scope_kind, scope_key, task_filter "
        "from team_milestones where org_id = :o and archived_at is null "
        "and (cast(:m as text) is null or milestone_id = cast(:m as text)) "
        "order by due_at, milestone_id"), {"o": org_id, "m": milestone_id}).all()
    return [Milestone(r.milestone_id, r.title, r.due_at, r.owner_seat_id, r.scope_kind,
                      r.scope_key, r.task_filter if isinstance(r.task_filter, dict) else None)
            for r in rows]


def load_tasks(conn, org_id: str) -> list[dict]:
    """Every tracker task node with its org-visible `task.*` facts. One statement."""
    rows = conn.execute(text(
        "select n.node_id, n.display_name, f.field, f.value from graph_nodes n "
        "join graph_facts f on f.org_id = n.org_id and f.subject_node_id = n.node_id "
        "and f.valid_to is null and f.status = 'active' "
        "and f.visibility_scope is distinct from 'private' "
        "where n.org_id = :o and n.node_type = 'task' and n.valid_to is null "
        "and left(f.field, 5) = 'task.'"), {"o": org_id}).all()
    tasks: dict[str, dict] = {}
    for r in rows:
        tasks.setdefault(r.node_id, {"node_id": r.node_id, "name": r.display_name})[r.field] = r.value
    return [tasks[k] for k in sorted(tasks)]


def task_state(task: dict) -> str:
    """done | pending | dropped."""
    kind = str(task.get("task.state_type") or "").strip().lower()
    name = str(task.get("task.status") or "").strip().lower()
    if kind in DROPPED_TASK_STATES or name in DROPPED_TASK_STATES:
        return "dropped"
    if kind in DONE_TASK_STATES or name in DONE_TASK_STATES:
        return "done"
    return "pending"


def task_matches(task: dict, query: str) -> bool:
    hay = " ".join(str(task.get(f) or "") for f in _TASK_TEXT_FIELDS) + " " + str(
        task.get("name") or "")
    return query.casefold() in hay.casefold()


def counts(conn, org_id: str, m: Milestone, *, now: datetime,
           directory: PeopleDirectory | None = None, links=None,
           tasks: list[dict] | None = None) -> dict:
    directory = directory or load_directory(conn, org_id)
    links = links if links is not None else commitment_links(conn, org_id, directory)
    today = now.date()
    seats = set(directory.seat_ids)
    if m.scoped:
        team = {a.seat_id for a in answering_for(conn, org_id, [(m.scope_kind, m.scope_key)], now)}
        team = (team | {m.owner_seat_id}) & seats
    else:
        team = seats
    away: list[tuple] = []
    if m.due >= today:
        # CAPACITY IS THE WHOLE TEAM: anyone away before the date is a person the audit cannot
        # lean on. A scope narrows which WORK counts (below), never who is counted as away.
        windows = org_visible_windows(conn, org_id, today, m.due)
        for seat in sorted(seats):
            person = directory.for_seat(seat)
            hit = sorted((w for w in directory.windows_of(person, windows)
                          if w.overlaps(today, m.due)), key=lambda w: w.start)
            if person is not None and hit:
                away.append((person, hit[0]))
    away.sort(key=lambda pw: (pw[0].label.casefold(), pw[0].seat_id or ""))
    done = pending = task_n = 0
    lo = m.due - timedelta(days=COMMITMENT_LOOKBACK_DAYS)
    for link in links:
        if link.dropped or link.due is None or not lo <= link.due <= m.due:
            continue
        owner = link.owner.seat_id if link.owner else None
        owed = link.beneficiary.seat_id if link.beneficiary else None
        if not (owner in team if m.scoped else m.owner_seat_id in (owner, owed)):
            continue
        done, pending = (done + 1, pending) if link.done else (done, pending + 1)
    if m.query:
        for t in (tasks if tasks is not None else load_tasks(conn, org_id)):
            if not task_matches(t, m.query):
                continue
            state = task_state(t)
            if state == "dropped":
                continue
            task_n += 1
            done, pending = (done + 1, pending) if state == "done" else (done, pending + 1)
    return {"done": done, "pending": pending, "away": len(away),
            "away_names": [p.label for p, _ in away], "away_windows": away, "tasks": task_n}


def milestone_out(m: Milestone, c: dict, directory: PeopleDirectory) -> dict:
    """The pinned `GET /v1/team/milestones` item (SCREEN_INTEL_P4 §3.2)."""
    owner = directory.for_seat(m.owner_seat_id)
    due = m.due_at if m.due_at.tzinfo else m.due_at.replace(tzinfo=timezone.utc)
    return {"milestone_id": m.milestone_id, "title": m.title,
            "due_at": due.isoformat().replace("+00:00", "Z"), "owner_seat_id": m.owner_seat_id,
            "owner_name": owner.label if owner else None, "scope_kind": m.scope_kind,
            "scope_key": m.scope_key, "done": c["done"], "pending": c["pending"],
            "away": c["away"], "away_names": list(c["away_names"])}


def situations(conn, ctx: TeamContext) -> list[Situation]:
    out: list[Situation] = []
    tasks: list[dict] | None = None
    for m in load_milestones(conn, ctx.org_id):
        if not ctx.today <= m.due <= ctx.today + timedelta(days=READINESS_HORIZON_DAYS):
            continue
        if ctx.directory.for_seat(m.owner_seat_id) is None:
            continue
        if m.query and tasks is None:
            tasks = load_tasks(conn, ctx.org_id)
        c = counts(conn, ctx.org_id, m, now=ctx.now, directory=ctx.directory, links=ctx.links,
                   tasks=tasks)
        names = ", ".join(f"{p.label} ({span(w)})" for p, w in c["away_windows"]) or "nobody"
        source = " incl. tracker tasks" if c["tasks"] else ""
        out.append(Situation(
            key=f"readiness:{m.milestone_id}", seat_id=m.owner_seat_id, capability_id=CAPABILITY,
            subject_node_ids=(),
            headline=f"{m.title} on {day(m.due)}: {c['away']} away, {c['pending']} pending",
            body=(f"Done {c['done']} · pending {c['pending']}{source}. "
                  f"Away before {day(m.due)}: {names}."),
            actions=(),
            evidence=(
                {"kind": "milestone", "milestone_id": m.milestone_id, "title": m.title,
                 "due": m.due.isoformat()},
                {"kind": "readiness", "done": c["done"], "pending": c["pending"],
                 "tasks": c["tasks"]},
                *(window_evidence(p, w) for p, w in c["away_windows"])),
            digest=digest(m.milestone_id, m.title, m.due, c["done"], c["pending"],
                          sorted(p.seat_id or "" for p, _ in c["away_windows"])),
            expires_at=datetime.combine(m.due + timedelta(days=1), time.min, timezone.utc),
            ttl_seconds=8 * 3600))
    return out


__all__ = ["CAPABILITY", "Milestone", "counts", "load_milestones", "load_tasks", "milestone_out",
           "normalize_task_filter", "situations", "task_matches", "task_state"]
