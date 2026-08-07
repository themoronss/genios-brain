"""Atlas Layer 6 control and transparency surface.

Reads show exactly what was observed, held, reviewed and published. Mutations require the tenant
owner because approving organization-wide learning or rolling it back changes future decisions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, Field
from sqlalchemy import text

from genios_engine.contracts.learning import BrainTarget, LearningState
from genios_engine.feedback.governance import lifecycle_path
from genios_engine.feedback.orchestrator import (
    preview_learning,
    review_learning,
    rollback_learning,
)
from genios_engine.feedback.store import apply_path, load_policy, persist_object
from genios_engine.feedback.units import EnterpriseFact, LearningBatch, temporary_memory
from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner
from genios_engine.platform.wiring import make_graph_store

router = APIRouter(prefix="/v1/learning", tags=["learning"])
_graph = make_graph_store()


def _require_db() -> None:
    if _graph is None:
        raise HTTPException(400, "learning needs a configured database")


def _public(row: Any) -> dict[str, Any]:
    value = dict(row)
    for key, item in list(value.items()):
        if isinstance(item, datetime):
            value[key] = item.isoformat()
        elif key in {"payload", "value", "suggestion", "evidence", "result"}:
            if isinstance(item, str):
                try:
                    value[key] = json.loads(item)
                except (TypeError, ValueError):
                    pass
    return jsonable_encoder(value)


@router.get("/overview")
def overview(org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as conn:
        states = conn.execute(text(
            "select current_state,count(*) as count from learning_objects where org_id=:o "
            "group by current_state order by current_state"), {"o": org_id}).all()
        brains = conn.execute(text(
            "select brain,count(*) as count from learned_brain_entries where org_id=:o and active "
            "group by brain order by brain"), {"o": org_id}).all()
        pending = conn.execute(text(
            "select count(*) from knowledge_suggestions where org_id=:o and status='pending'"),
            {"o": org_id}).scalar_one()
        memories = conn.execute(text(
            "select count(*) from temporary_memories where org_id=:o and expired_at is null "
            "and expires_at>now()"), {"o": org_id}).scalar_one()
    return {"states": {row.current_state: int(row.count) for row in states},
            "active_brains": {row.brain: int(row.count) for row in brains},
            "pending_knowledge_suggestions": int(pending), "active_memories": int(memories),
            "expert_brain_publisher": False}


@router.get("/objects")
def objects(state: str | None = None, target: str | None = None,
            limit: int = Query(100, ge=1, le=500),
            org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    if state is not None:
        try:
            LearningState(state)
        except ValueError as exc:
            raise HTTPException(422, "invalid learning state") from exc
    if target is not None:
        try:
            BrainTarget(target)
        except ValueError as exc:
            raise HTTPException(422, "invalid learning target") from exc
    clauses = ["org_id=:o"]
    params: dict[str, Any] = {"o": org_id, "limit": limit}
    if state:
        clauses.append("current_state=:state")
        params["state"] = state
    if target:
        clauses.append("target_brain=:target")
        params["target"] = target
    with _graph.engine.connect() as conn:
        rows = conn.execute(text(
            "select learning_id,unit_name,target_brain,subject_key,current_state,confidence_bp,"
            "observations,distinct_days,requires_review,observed_at,expires_at,published_at,payload "
            "from learning_objects where " + " and ".join(clauses) +
            " order by observed_at desc,learning_id limit :limit"), params).mappings().all()
    return {"objects": [_public(row) for row in rows]}


@router.get("/brains")
def brains(brain: str | None = None, include_history: bool = False,
           org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    allowed = {"organization", "behavior", "adaptive"}
    if brain is not None and brain not in allowed:
        raise HTTPException(422, f"brain must be one of {sorted(allowed)}")
    where = ["org_id=:o"]
    params: dict[str, Any] = {"o": org_id}
    if brain:
        where.append("brain=:brain")
        params["brain"] = brain
    if not include_history:
        where.append("active")
    with _graph.engine.connect() as conn:
        rows = conn.execute(text(
            "select entry_id,brain,subject_key,version,value,confidence_bp,learning_id,active,"
            "effective_at,ended_at,ended_reason from learned_brain_entries where " +
            " and ".join(where) + " order by brain,subject_key,version desc"), params).mappings().all()
    return {"brains": [_public(row) for row in rows], "expert_brain_included": False}


@router.get("/suggestions")
def suggestions(status: str = "pending", org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    if status not in {"pending", "approved", "rejected", "withdrawn"}:
        raise HTTPException(422, "invalid suggestion status")
    with _graph.engine.connect() as conn:
        rows = conn.execute(text(
            "select suggestion_id,learning_id,subject_key,suggestion,evidence,status,decided_by,"
            "decided_at,decision_note,created_at from knowledge_suggestions "
            "where org_id=:o and status=:status order by created_at desc"),
            {"o": org_id, "status": status}).mappings().all()
    return {"suggestions": [_public(row) for row in rows],
            "approval_edits_expert_brain": False}


@router.get("/memories")
def memories(include_expired: bool = False,
             org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    clause = "" if include_expired else " and expired_at is null and expires_at>now()"
    with _graph.engine.connect() as conn:
        rows = conn.execute(text(
            "select memory_id,subject_key,value,learning_id,confidence_bp,observed_at,expires_at,"
            "expired_at from temporary_memories where org_id=:o" + clause +
            " order by expires_at"), {"o": org_id}).mappings().all()
    return {"memories": [_public(row) for row in rows]}


@router.get("/preview")
def preview(org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    return preview_learning(_graph, org_id)


class MemoryRequest(BaseModel):
    subject_key: str = Field(min_length=1, max_length=192)
    value: dict
    expires_at: datetime
    source_ref: str = Field(min_length=1, max_length=192)


@router.post("/memories", status_code=201)
def create_memory(body: MemoryRequest, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Create explicit leased context. It cannot become a permanent brain value."""
    _require_db()
    now = datetime.now(timezone.utc)
    if body.expires_at.tzinfo is None or body.expires_at.utcoffset() is None:
        raise HTTPException(422, "expires_at must carry a UTC offset")
    if body.expires_at <= now:
        raise HTTPException(422, "expires_at must be in the future")
    fact = EnterpriseFact(
        event_id=body.source_ref, pattern_key=body.subject_key, kind="temporary_memory",
        occurred_at=now, value=body.value, explicit_memory=True,
        expires_at=body.expires_at)
    batch = LearningBatch(org_id=ctx.org_id, evaluated_at=now, events=(fact,))
    item = temporary_memory(batch)[0]
    try:
        with _graph.engine.begin() as conn:
            policy = load_policy(conn, ctx.org_id)
            if not persist_object(conn, item, None):
                return {"learning_id": item.learning_id, "created": False}
            state = apply_path(conn, item, lifecycle_path(item, policy), now)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"learning_id": item.learning_id, "created": True, "state": state.value,
            "expires_at": item.expires_at.isoformat() if item.expires_at else None}


class ReviewRequest(BaseModel):
    decision: str
    note: str | None = Field(None, max_length=2_000)


@router.post("/objects/{learning_id}/review")
def review(learning_id: str, body: ReviewRequest,
           ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    try:
        with _graph.engine.begin() as conn:
            return review_learning(conn, org_id=ctx.org_id, learning_id=learning_id,
                                   decision=body.decision,
                                   actor=ctx.actor_id or "org_owner",
                                   at=datetime.now(timezone.utc), note=body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


class RollbackRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@router.post("/objects/{learning_id}/rollback")
def rollback(learning_id: str, body: RollbackRequest,
             ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    try:
        with _graph.engine.begin() as conn:
            return rollback_learning(conn, org_id=ctx.org_id, learning_id=learning_id,
                                     actor=ctx.actor_id or "org_owner",
                                     at=datetime.now(timezone.utc), reason=body.reason)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


class PolicyUpdate(BaseModel):
    learning_enabled: bool = True
    min_observations: int = Field(3, ge=1, le=10_000)
    min_distinct_days: int = Field(2, ge=1, le=365)
    min_confidence_bp: int = Field(6_500, ge=0, le=10_000)
    max_noise_bp: int = Field(2_500, ge=0, le=10_000)
    max_conflict_bp: int = Field(2_500, ge=0, le=10_000)
    min_business_value_bp: int = Field(1_000, ge=0, le=10_000)
    max_temporary_ttl_hours: int = Field(720, ge=1, le=8_760)
    require_human_targets: list[str] = Field(
        default_factory=lambda: ["knowledge_suggestion", "organization"])
    blocked_subject_prefixes: list[str] = Field(default_factory=list)


@router.get("/policy")
def get_policy(org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as conn:
        policy = load_policy(conn, org_id)
    return {"learning_enabled": policy.enabled, "min_observations": policy.min_observations,
            "min_distinct_days": policy.min_distinct_days,
            "min_confidence_bp": policy.min_confidence_bp,
            "max_noise_bp": policy.max_noise_bp, "max_conflict_bp": policy.max_conflict_bp,
            "min_business_value_bp": policy.min_business_value_bp,
            "max_temporary_ttl_hours": policy.max_temporary_ttl_hours,
            "require_human_targets": sorted(target.value for target in policy.require_human_targets),
            "blocked_subject_prefixes": list(policy.blocked_subject_prefixes)}


@router.put("/policy")
def put_policy(body: PolicyUpdate, ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    try:
        targets = sorted({BrainTarget(item).value for item in body.require_human_targets})
    except ValueError as exc:
        raise HTTPException(422, "require_human_targets contains an invalid target") from exc
    # Knowledge changes are non-negotiably reviewed even if a caller omits the target.
    if BrainTarget.KNOWLEDGE_SUGGESTION.value not in targets:
        targets.append(BrainTarget.KNOWLEDGE_SUGGESTION.value)
        targets.sort()
    with _graph.engine.begin() as conn:
        conn.execute(text(
            "insert into learning_policies (org_id,policy_key,learning_enabled,min_observations,"
            "min_distinct_days,min_confidence_bp,max_noise_bp,max_conflict_bp,"
            "min_business_value_bp,max_temporary_ttl_hours,require_human_targets,"
            "blocked_subject_prefixes,updated_by) values "
            "(:o,'default',:enabled,:observations,:days,:confidence,:noise,:conflict,:value,"
            ":ttl,:targets,:blocked,:actor) on conflict (org_id,policy_key) do update set "
            "learning_enabled=excluded.learning_enabled,min_observations=excluded.min_observations,"
            "min_distinct_days=excluded.min_distinct_days,"
            "min_confidence_bp=excluded.min_confidence_bp,max_noise_bp=excluded.max_noise_bp,"
            "max_conflict_bp=excluded.max_conflict_bp,"
            "min_business_value_bp=excluded.min_business_value_bp,"
            "max_temporary_ttl_hours=excluded.max_temporary_ttl_hours,"
            "require_human_targets=excluded.require_human_targets,"
            "blocked_subject_prefixes=excluded.blocked_subject_prefixes,"
            "updated_by=excluded.updated_by,updated_at=now()"),
            {"o": ctx.org_id, "enabled": body.learning_enabled,
             "observations": body.min_observations, "days": body.min_distinct_days,
             "confidence": body.min_confidence_bp, "noise": body.max_noise_bp,
             "conflict": body.max_conflict_bp, "value": body.min_business_value_bp,
             "ttl": body.max_temporary_ttl_hours, "targets": targets,
             "blocked": body.blocked_subject_prefixes,
             "actor": ctx.actor_id or "org_owner"})
    return {**body.model_dump(), "require_human_targets": targets}


__all__ = ["router"]
