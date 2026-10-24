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


def _refs(evidence: Any) -> tuple[str, ...]:
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except ValueError:
            return ()
    if isinstance(evidence, dict):
        evidence = evidence.get("refs") or evidence.get("evidence") or []
    return tuple(str(e) for e in evidence or () if isinstance(e, (str, int)) and str(e).strip())


def _goal_of(org_id: str, line: Any, superseded: set[str]) -> G.Goal:
    status = G.SUPERSEDED if line.line_id in superseded else _STATUS_OF_LINE.get(str(line.status), G.PROPOSED)
    accepted = str(line.status) == "accepted"
    founder = str(line.proposed_by or "") == _BY_FOUNDER
    source = (G.FOUNDER if founder else G.BRIEF) if accepted or founder else G.INFERRED
    words = str(line.text or line.proposed_text or "").strip()[:G.MAX_STATEMENT_CHARS]
    approver = (line.decided_by or (_BY_FOUNDER if founder else None)) if status in G.LIVE else None
    when = (line.accepted_at or line.decided_at) if status in G.LIVE else None
    refs = _refs(line.evidence)
    return G.Goal(goal_id=goal_id_for(org_id, line.line_id), org_id=org_id, statement=words, status=status,
                  source=source, line_id=line.line_id, evidence_refs=refs,
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


__all__ = ["goal_id_for", "goals", "live_goals", "sync_from_brief"]
