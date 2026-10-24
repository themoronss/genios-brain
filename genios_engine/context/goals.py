"""The goals L3 owns, synced from the company brief every sweep (GeniOS-012 S28.U1).

The brief is the one door (D11, `speedrun008/GeniOS-008/00-ARCHITECTURE.md` "Goals"): a `goals` line the founder
ACCEPTED is an approved goal, a pending one a proposed goal, a rejected or removed one a cancelled goal, and a line an
edit replaced a superseded goal. The goal's id is its line's — so the one approval path
(`POST /v1/company-brief/proposals/{line_id}/decide`) is the goal's, and every surface can call it in one click.

`sync_from_brief` writes a NEW REVISION only when a goal changed (`Goal.same_as`): running it every sweep writes nothing
on a quiet day. Approved means a human approved it — the line's `decided_by` and its acceptance time — never code.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts import goals as G
from genios_engine.platform.company_brief_store import SERVES

#: The brief's line states (`platform/company_brief_store`) → the goal's status.
_STATUS_OF_LINE = {"proposed": G.PROPOSED, "accepted": G.APPROVED, "rejected": G.CANCELLED, "removed": G.CANCELLED}
#: Who a line said proposed it when the founder added it themselves (`company_brief_store.BY_FOUNDER`).
_BY_FOUNDER = "founder"

_LINES = text(
    "select line_id, text, proposed_text, status, proposed_by, evidence, decided_by, decided_at, accepted_at, "
    "       replaces "
    "  from company_brief_lines where org_id = :o and section = 'goals' order by line_id")
_LATEST = text(
    "select distinct on (goal_id) * from company_goals where org_id = :o order by goal_id, revision desc")
_INSERT = text(
    "insert into company_goals (org_id, goal_id, revision, statement, status, source, line_id, department, category, "
    "  owner_seat, metric, target, deadline, parent_goal_id, subject_ref, evidence_refs, approved_by, approved_at, "
    "  created_at) values (:org_id, :goal_id, :revision, :statement, :status, :source, :line_id, :department, "
    "  :category, :owner_seat, :metric, :target, :deadline, :parent_goal_id, :subject_ref, cast(:evidence_refs as jsonb), "
    "  :approved_by, :approved_at, :created_at)")


def goal_id_for(org_id: str, line_id: str) -> str:
    """A goal's stable id, from the brief line it was born from."""
    return "goal_" + hashlib.sha1(f"{org_id}:{line_id}".encode()).hexdigest()[:16]


def _items(evidence: Any) -> list:
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except ValueError:
            return []
    if isinstance(evidence, dict):
        evidence = evidence.get("refs") or evidence.get("evidence") or []
    return list(evidence or ())


def _refs(evidence: Any) -> tuple[str, ...]:
    """What a line was proposed on: the work it was born from and the lines it cites."""
    out: list[str] = []
    for e in _items(evidence):
        if isinstance(e, dict):                  # the drafter's line: the work it rests on, by its file id
            if e.get("file_id"):
                out.append(f"file:{e['file_id']}")
        elif isinstance(e, (str, int)) and str(e).strip():
            out.append(str(e))
    return tuple(dict.fromkeys(out))


def _served(evidence: Any) -> tuple[str, ...]:
    """G012 H-19 · the pieces of work L3 found SERVE the goal (`company_brief_store.add_work`)."""
    return tuple(dict.fromkeys(str(e[SERVES]) for e in _items(evidence) if isinstance(e, dict) and e.get(SERVES)))


def _goal_of(org_id: str, line: Any, superseded: set[str]) -> G.Goal:
    status = G.SUPERSEDED if line.line_id in superseded else _STATUS_OF_LINE.get(str(line.status), G.PROPOSED)
    accepted = str(line.status) == "accepted"
    founder = str(line.proposed_by or "") == _BY_FOUNDER
    source = (G.FOUNDER if founder else G.BRIEF) if accepted or founder else G.INFERRED
    words = str(line.text or line.proposed_text or "").strip()[:G.MAX_STATEMENT_CHARS]
    approver = (line.decided_by or (_BY_FOUNDER if founder else None)) if status in G.LIVE else None
    when = (line.accepted_at or line.decided_at) if status in G.LIVE else None
    refs = _refs(line.evidence)
    # G012 H-19 · the work a goal was born from is its subject; the work that serves it is in its evidence too, so a
    # card on any of it carries the goal (`deliver/goal_line`).
    return G.Goal(goal_id=goal_id_for(org_id, line.line_id), org_id=org_id, statement=words, status=status,
                  source=source, line_id=line.line_id,
                  evidence_refs=tuple(dict.fromkeys((*refs, *_served(line.evidence)))),
                  subject_ref=next((r for r in refs if r.startswith("file:")), None),
                  approved_by=approver, approved_at=when)


def _stored(row: Any) -> G.Goal:
    return G.Goal(goal_id=row.goal_id, org_id=row.org_id, statement=row.statement, status=row.status,
                  source=row.source, revision=row.revision, line_id=row.line_id, department=row.department,
                  category=row.category, owner_seat=row.owner_seat, metric=row.metric, target=row.target,
                  deadline=row.deadline, parent_goal_id=row.parent_goal_id, subject_ref=row.subject_ref,
                  evidence_refs=tuple(row.evidence_refs or ()), approved_by=row.approved_by,
                  approved_at=row.approved_at)


def goals(conn, org_id: str) -> list[G.Goal]:
    """Every goal of the org, its latest revision."""
    return [_stored(r) for r in conn.execute(_LATEST, {"o": org_id})]


def live_goals(conn, org_id: str) -> list[G.Goal]:
    """The goals a human made real — the ones a model is shown as the company's (block G)."""
    return [g for g in goals(conn, org_id) if g.live]


def sync_from_brief(conn, org_id: str, *, at: datetime) -> dict[str, int]:
    """Bring `company_goals` up to the brief's `goals` lines, on the caller's transaction. A new revision only for a
    goal that changed. Returns the counts written, by status."""
    lines = conn.execute(_LINES, {"o": org_id}).fetchall()
    superseded = {str(r.replaces) for r in lines if r.replaces}
    latest = {g.goal_id: g for g in goals(conn, org_id)}
    written: dict[str, int] = {}
    for line in lines:
        goal = _goal_of(org_id, line, superseded)
        before = latest.get(goal.goal_id)
        if before is not None and before.same_as(goal):
            continue
        revision = (before.revision + 1) if before is not None else 1
        conn.execute(_INSERT, {
            "org_id": org_id, "goal_id": goal.goal_id, "revision": revision, "statement": goal.statement,
            "status": goal.status, "source": goal.source, "line_id": goal.line_id, "department": goal.department,
            "category": goal.category, "owner_seat": goal.owner_seat, "metric": goal.metric, "target": goal.target,
            "deadline": goal.deadline, "parent_goal_id": goal.parent_goal_id, "subject_ref": goal.subject_ref,
            "evidence_refs": json.dumps(list(goal.evidence_refs)), "approved_by": goal.approved_by,
            "approved_at": goal.approved_at, "created_at": at})
        written[goal.status] = written.get(goal.status, 0) + 1
    return written


_LINK = text(
    "insert into goal_situation_links (org_id, goal_id, situation_id, relation, why, evidence, result_fingerprint, "
    "  linked_at) values (:o, :g, :s, :rel, :why, cast(:ev as jsonb), :fp, :at) "
    "on conflict (org_id, goal_id, situation_id) do update set relation = excluded.relation, why = excluded.why, "
    "  evidence = excluded.evidence, result_fingerprint = excluded.result_fingerprint, linked_at = excluded.linked_at")


def link_impacts(conn, org_id: str, *, impacts, situation_ids, fingerprint: str | None, at: datetime) -> int:
    """GeniOS-012 S30.U1 · each `GoalImpact` of a judgment linked to each situation L3 ADMITTED for it — only to a goal
    still live (a human made it real; block G printed no other). Latest wins per goal and situation. Returns the rows."""
    live = {g.ref: g.goal_id for g in live_goals(conn, org_id)}
    rows = [{"o": org_id, "g": live[i.goal_ref], "s": sid, "rel": i.relation, "why": i.why,
             "ev": json.dumps(list(i.evidence)), "fp": fingerprint, "at": at}
            for i in impacts if i.goal_ref in live for sid in situation_ids]
    if rows:
        conn.execute(_LINK, rows)
    return len(rows)


#: G012 H-19 · the statuses a goal may still gather work in — a waiting one (the founder has not decided) or a live one.
_GATHERS = (G.PROPOSED, *G.LIVE)


def cover_work(conn, org_id: str, *, impacts, subject_ref: str, at: datetime) -> int:
    """G012 H-19 · each `GoalImpact` of a judgment that bears on a goal (`unclear` does not), waiting or live: the
    judged work SERVES it, kept on the goal's brief line, so the card of that work carries the goal once a human made
    it real — with no new judgment. Block G prints the waiting goals with their ids for this: on the design partner's
    org (24 Oct) 262 judgments wrote 0 impacts, because every goal was still waiting and printed with none. Returns the
    lines that changed. Shown to no one as the company's goal until it is live (`deliver/goal_line` reads live only)."""
    from genios_engine.platform.company_brief_store import add_work

    if not str(subject_ref or "").startswith("file:"):
        return 0
    lines = {g.ref: g.line_id for g in goals(conn, org_id) if g.status in _GATHERS and g.line_id}
    changed = 0
    for i in impacts:
        if i.relation != G.UNCLEAR and i.goal_ref in lines:
            changed += add_work(conn, org_id=org_id, line_id=lines[i.goal_ref], work_ref=subject_ref, at=at,
                                why=i.why)
    return changed


__all__ = ["cover_work", "goal_id_for", "goals", "link_impacts", "live_goals", "sync_from_brief"]
