"""Layer 6 · Phase 7 — the /v1/learning API (Part 8).

Reads take `learning.read` (here: an org-scoped credential) and apply the ACL predicate in SQL
before LIMIT, so a hidden row can never distort a count or starve a page. Review and rollback are
owner operations. Owners hold full tenant learning authority; the Expert Brain is never editable
from this surface — there is no such endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import text

from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org != org_id:
        raise HTTPException(403, "org mismatch")
    return org


def _db():
    if _graph is None:
        raise HTTPException(400, "learning store not configured (needs DATABASE_URL)")


@router.get("/v1/learning/overview")
def overview(org: str = Depends(get_current_org)) -> dict:
    _db()
    with _graph.engine.connect() as c:
        by_state = {r[0]: r[1] for r in c.execute(text(
            "select state, count(*) from learning_objects where org_id = :o group by state"),
            {"o": org})}
        by_target = {r[0]: r[1] for r in c.execute(text(
            "select target, count(*) from learning_objects where org_id = :o group by target"),
            {"o": org})}
        brains = c.execute(text("select count(*) from learned_brain_entries "
                                "where org_id = :o and active"), {"o": org}).scalar()
        suggestions = c.execute(text("select count(*) from knowledge_suggestions "
                                     "where org_id = :o and state = 'human_review'"), {"o": org}).scalar()
        memories = c.execute(text("select count(*) from temporary_memories "
                                  "where org_id = :o and active"), {"o": org}).scalar()
    return {"by_state": by_state, "by_target": by_target, "active_brains": brains,
            "pending_suggestions": suggestions, "active_memories": memories}


@router.get("/v1/learning/objects")
def objects(org: str = Depends(get_current_org), state: str | None = Query(None),
            target: str | None = Query(None), limit: int = Query(50, le=200)) -> dict:
    _db()
    where = "org_id = :o"
    params: dict = {"o": org, "l": limit}
    if state:
        where += " and state = :st"; params["st"] = state
    if target:
        where += " and target = :tg"; params["tg"] = target
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            f"select learning_id, unit, target, subject, state, visibility_scope, created_at "
            f"from learning_objects where {where} order by created_at desc limit :l"),
            params).mappings().all()
    return {"count": len(rows), "objects": [_iso(dict(r)) for r in rows]}


@router.get("/v1/learning/brains")
def brains(org: str = Depends(get_current_org), subject: str | None = Query(None)) -> dict:
    _db()
    where = "org_id = :o"
    params: dict = {"o": org}
    if subject:
        where += " and subject = :s"; params["s"] = subject
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            f"select brain, subject, version, active, supersedes, created_at "
            f"from learned_brain_entries where {where} order by brain, subject, version desc"),
            params).mappings().all()
    return {"brains": [_iso(dict(r)) for r in rows]}   # no 'expert' vocabulary exists


@router.get("/v1/learning/suggestions")
def suggestions(org: str = Depends(get_current_org)) -> dict:
    _db()
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select suggestion_id, subject, state, created_at, reviewed_at from knowledge_suggestions "
            "where org_id = :o order by created_at desc limit 100"), {"o": org}).mappings().all()
    return {"suggestions": [_iso(dict(r)) for r in rows], "expert_brain_changed": False}


@router.get("/v1/learning/memories")
def memories(org: str = Depends(get_current_org)) -> dict:
    _db()
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select memory_id, subject, expires_at, active, created_at from temporary_memories "
            "where org_id = :o order by created_at desc limit 100"), {"o": org}).mappings().all()
    return {"memories": [_iso(dict(r)) for r in rows]}


@router.post("/v1/learning/objects/{learning_id}/rollback")
def rollback(learning_id: str, brain: str = Body(..., embed=True),
             subject: str = Body(..., embed=True), ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Restore the exact verified predecessor of a published brain value, else roll to empty."""
    _db()
    from genios_engine.feedback.publisher import rollback_brain
    now = datetime.now(timezone.utc)
    with _graph.engine.begin() as c:
        result = rollback_brain(c, org_id=ctx.org_id, brain=brain, subject=subject, at=now,
                                actor=ctx.actor_id)
    return {"result": result, "brain": brain, "subject": subject}


@router.post("/v1/learning/objects/{learning_id}/review")
def review(learning_id: str, approve: bool = Body(..., embed=True),
           ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Approve or reject a human-review object. Approving a knowledge suggestion records the handoff
    and STILL reports expert_brain_changed: false — Layer 6 never edits the Expert Brain."""
    _db()
    now = datetime.now(timezone.utc)
    to_state = "promoted" if approve else "rejected"
    with _graph.engine.begin() as c:
        row = c.execute(text("select state from learning_objects "
                             "where org_id = :o and learning_id = :l for update"),
                        {"o": ctx.org_id, "l": learning_id}).mappings().first()
        if row is None:
            raise HTTPException(404, "no such learning object")
        if row["state"] != "human_review":
            raise HTTPException(409, f"object is {row['state']}, not human_review")
        c.execute(text("update learning_objects set state = :st where org_id = :o and learning_id = :l"),
                  {"st": to_state, "o": ctx.org_id, "l": learning_id})
        c.execute(text(
            "insert into learning_transitions (id, org_id, learning_id, from_state, to_state, "
            "reason_code, actor, occurred_at) values (:id, :o, :l, 'human_review', :st, "
            "'human_reviewed', :a, :at)"),
            {"id": f"ltr_{learning_id}_{to_state}", "o": ctx.org_id, "l": learning_id,
             "st": to_state, "a": ctx.actor_id, "at": now})
    return {"learning_id": learning_id, "state": to_state, "expert_brain_changed": False}


@router.get("/v1/learning/policy")
def get_policy(org: str = Depends(get_current_org)) -> dict:
    _db()
    with _graph.engine.connect() as c:
        row = c.execute(text(
            "select * from learning_policies where org_id = :o order by revision desc limit 1"),
            {"o": org}).mappings().first()
    if row is None:
        return {"policy": None, "note": "no policy yet — a protective default applies on first run"}
    return {"policy": _iso(dict(row))}


def _iso(row: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}


__all__ = ["router"]
