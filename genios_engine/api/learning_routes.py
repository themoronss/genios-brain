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

from genios_engine.contracts.learning import BrainTarget, LearningState, LearningTarget
from genios_engine.contracts.validators import require_identifier
from genios_engine.contracts.visibility import ORG, PRIVATE, Visibility
from genios_engine.feedback.governance import lifecycle_path, preflight_learning
from genios_engine.feedback.orchestrator import (
    preview_learning,
    review_learning,
    rollback_learning,
)
from genios_engine.feedback.store import (
    apply_path,
    ensure_policy,
    load_policy,
    lock_learning_tenant,
    persist_object,
    persist_preflight_rejection,
)
from genios_engine.feedback.units import EnterpriseFact, LearningBatch, temporary_memory
from genios_engine.platform.auth import AuthCtx, get_current_org, require_owner, require_scope
from genios_engine.platform.canonical import canonical_dumps, stable_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter(prefix="/v1/learning", tags=["learning"])
_graph = make_graph_store()

_VISIBLE_SQL = (
    "(visibility->>'scope' in ('public','org') or "
    "(visibility->>'scope' in ('participants','private') "
    "and coalesce(visibility->'principals','[]'::jsonb) ? :viewer))"
)


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


def _can_view(value: Any, actor_id: str | None) -> bool:
    raw = value
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return False
    if (not isinstance(raw, dict)
            or not {"scope", "principals", "derived_from"} <= set(raw)):
        return False
    try:
        visibility = Visibility.model_validate(raw)
    except (TypeError, ValueError):
        return False
    if not str(visibility.derived_from or "").strip():
        return False
    return visibility.can_view(actor_id, org_member=True)


def _viewer(conn, ctx: AuthCtx) -> str:
    actor = str(ctx.actor_id or ctx.agent_id or "")
    if "@" in actor:
        return actor.strip().lower()
    seat = conn.execute(text(
        "select lower(email) as email from org_seats where org_id=:o and seat_id=:actor "
        "and active"), {"o": ctx.org_id, "actor": actor}).first()
    if seat is not None and seat.email:
        return str(seat.email)
    if ctx.scopes is None:
        owner = conn.execute(text("select lower(email) as email from orgs where id=:o"),
                             {"o": ctx.org_id}).first()
        if owner is not None and owner.email:
            return str(owner.email)
    # A non-email actor can still read org/public state, but cannot pass a constrained ACL.
    return actor.lower() or "unresolved_principal"


def _bounded_semantic_json(value: dict[str, Any]) -> str:
    encoded = canonical_dumps(value)
    if len(encoded.encode("utf-8")) > 16_384:
        raise ValueError("memory value is too large")
    count = 0
    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        current, depth = stack.pop()
        count += 1
        if count > 512 or depth > 12:
            raise ValueError("memory value is too deeply nested or complex")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend((item, depth + 1) for item in current)
    return encoded


@router.get("/overview")
def overview(ctx: AuthCtx = Depends(require_scope("learning.read"))) -> dict:
    _require_db()
    org_id = ctx.org_id
    with _graph.engine.connect() as conn:
        viewer = _viewer(conn, ctx)
        params = {"o": org_id, "viewer": viewer}
        states = conn.execute(text(
            "select current_state,count(*) as count from learning_objects where org_id=:o "
            "and " + _VISIBLE_SQL + " "
            "group by current_state order by current_state"), params).all()
        brains = conn.execute(text(
            "select brain,count(*) as count from learned_brain_entries where org_id=:o and active "
            "and " + _VISIBLE_SQL + " group by brain order by brain"), params).all()
        pending = conn.execute(text(
            "select count(*) from knowledge_suggestions where org_id=:o and status='pending' "
            "and " + _VISIBLE_SQL), params).scalar_one()
        memories = conn.execute(text(
            "select count(*) from temporary_memories where org_id=:o and expired_at is null "
            "and expires_at>now() and " + _VISIBLE_SQL), params).scalar_one()
    return {"states": {row.current_state: int(row.count) for row in states},
            "active_brains": {row.brain: int(row.count) for row in brains},
            "pending_knowledge_suggestions": int(pending), "active_memories": int(memories),
            "expert_brain_publisher": False}


@router.get("/objects")
def objects(state: str | None = None, target: str | None = None,
            limit: int = Query(100, ge=1, le=500),
            ctx: AuthCtx = Depends(require_scope("learning.read"))) -> dict:
    _require_db()
    org_id = ctx.org_id
    if state is not None:
        try:
            LearningState(state)
        except ValueError as exc:
            raise HTTPException(422, "invalid learning state") from exc
    if target is not None:
        try:
            LearningTarget(target)
        except ValueError as exc:
            raise HTTPException(422, "invalid learning target") from exc
    clauses = ["org_id=:o", _VISIBLE_SQL]
    if state:
        clauses.append("current_state=:state")
    if target:
        clauses.append("target_brain=:target")
    with _graph.engine.connect() as conn:
        viewer = _viewer(conn, ctx)
        params: dict[str, Any] = {"o": org_id, "limit": limit, "viewer": viewer}
        if state:
            params["state"] = state
        if target:
            params["target"] = target
        rows = conn.execute(text(
            "select learning_id,unit_name,target_brain,subject_key,current_state,confidence_bp,"
            "observations,distinct_days,requires_review,observed_at,expires_at,published_at,payload "
            ",visibility "
            "from learning_objects where " + " and ".join(clauses) +
            " order by observed_at desc,learning_id limit :limit"), params).mappings().all()
    return {"objects": [_public(row) for row in rows
                        if _can_view(row.get("visibility"), viewer)]}


@router.get("/brains")
def brains(brain: str | None = None, include_history: bool = False,
           ctx: AuthCtx = Depends(require_scope("learning.read"))) -> dict:
    _require_db()
    org_id = ctx.org_id
    allowed = {"organization", "behavior", "adaptive"}
    if brain is not None and brain not in allowed:
        raise HTTPException(422, f"brain must be one of {sorted(allowed)}")
    where = ["org_id=:o", _VISIBLE_SQL]
    if brain:
        where.append("brain=:brain")
    if not include_history:
        where.append("active")
    with _graph.engine.connect() as conn:
        viewer = _viewer(conn, ctx)
        params: dict[str, Any] = {"o": org_id, "viewer": viewer}
        if brain:
            params["brain"] = brain
        rows = conn.execute(text(
            "select entry_id,brain,subject_key,version,value,confidence_bp,learning_id,active,"
            "effective_at,ended_at,ended_reason,visibility from learned_brain_entries where " +
            " and ".join(where) + " order by brain,subject_key,version desc"), params).mappings().all()
    return {"brains": [_public(row) for row in rows
                       if _can_view(row.get("visibility"), viewer)],
            "expert_brain_included": False}


@router.get("/suggestions")
def suggestions(status: str = "pending",
                ctx: AuthCtx = Depends(require_scope("learning.read"))) -> dict:
    _require_db()
    org_id = ctx.org_id
    if status not in {"pending", "approved", "rejected", "withdrawn"}:
        raise HTTPException(422, "invalid suggestion status")
    with _graph.engine.connect() as conn:
        viewer = _viewer(conn, ctx)
        rows = conn.execute(text(
            "select suggestion_id,learning_id,subject_key,suggestion,evidence,status,decided_by,"
            "decided_at,decision_note,created_at,visibility from knowledge_suggestions "
            "where org_id=:o and status=:status and " + _VISIBLE_SQL +
            " order by created_at desc"),
            {"o": org_id, "status": status, "viewer": viewer}).mappings().all()
    return {"suggestions": [_public(row) for row in rows
                            if _can_view(row.get("visibility"), viewer)],
            "approval_edits_expert_brain": False}


@router.get("/memories")
def memories(include_expired: bool = False,
             ctx: AuthCtx = Depends(require_scope("learning.read"))) -> dict:
    _require_db()
    org_id = ctx.org_id
    clause = "" if include_expired else " and expired_at is null and expires_at>now()"
    with _graph.engine.connect() as conn:
        viewer = _viewer(conn, ctx)
        rows = conn.execute(text(
            "select memory_id,subject_key,value,learning_id,confidence_bp,observed_at,expires_at,"
            "expired_at,visibility from temporary_memories where org_id=:o" + clause +
            " and " + _VISIBLE_SQL + " order by expires_at"),
            {"o": org_id, "viewer": viewer}).mappings().all()
    return {"memories": [_public(row) for row in rows
                         if _can_view(row.get("visibility"), viewer)]}


@router.get("/preview")
def preview(ctx: AuthCtx = Depends(require_scope("learning.read"))) -> dict:
    _require_db()
    result = preview_learning(_graph, ctx.org_id)
    with _graph.engine.connect() as conn:
        viewer = _viewer(conn, ctx)
    result["objects"] = [item for item in result["objects"]
                         if _can_view(item.pop("visibility", None), viewer)]
    return result


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
    actor = ctx.actor_id or "org_owner"
    event_id = stable_id("levent", {"org_id": ctx.org_id, "actor": actor,
                                     "source_ref": body.source_ref})
    trace_id = stable_id("ltrace", {"org_id": ctx.org_id, "actor": actor,
                                     "source_ref": body.source_ref})
    independence_key = stable_id("lind", {"org_id": ctx.org_id, "actor": actor,
                                           "source_ref": body.source_ref})
    refusal_reason = collision_reason = None
    created = False
    state = None
    item = None
    try:
        encoded_value = _bounded_semantic_json(body.value)
        with _graph.engine.begin() as conn:
            lock_learning_tenant(conn, ctx.org_id)
            viewer = _viewer(conn, ctx)
            visibility = Visibility(
                scope=PRIVATE, principals=[viewer],
                derived_from="owner:explicit-memory").model_dump()
            policy = ensure_policy(conn, ctx.org_id, for_share=True)
            provisional_fact = EnterpriseFact(
                event_id=event_id, pattern_key=body.subject_key, kind="temporary_memory",
                occurred_at=now, value=body.value, explicit_memory=True,
                expires_at=body.expires_at, actor_key=actor, trace_id=trace_id,
                independence_key=independence_key, visibility=visibility,
                lineage_complete=True)
            provisional = temporary_memory(LearningBatch(
                org_id=ctx.org_id, evaluated_at=now, events=(provisional_fact,)))[0]
            refusal = preflight_learning(provisional, policy)
            if refusal is not None:
                persist_preflight_rejection(conn, provisional, None, refusal.reason_code, now)
                refusal_reason = refusal.reason_code
            else:
                held = conn.execute(text(
                    "insert into learning_event_inbox (org_id,event_id,pattern_key,kind,actor_key,"
                    "value,explicit_memory,occurred_at,expires_at,trace_id,visibility,"
                    "independence_key) values (:o,:id,:pattern,'temporary_memory',:actor,"
                    "cast(:value as jsonb),true,:at,:expires,:trace,cast(:visibility as jsonb),"
                    ":independence) on conflict (org_id,event_id) do nothing returning *"),
                    {"o": ctx.org_id, "id": event_id, "pattern": body.subject_key,
                     "actor": actor, "value": encoded_value, "at": now,
                     "expires": body.expires_at, "trace": trace_id,
                     "visibility": canonical_dumps(visibility),
                     "independence": independence_key}).mappings().first()
                if held is None:
                    held = conn.execute(text(
                        "select * from learning_event_inbox where org_id=:o and event_id=:id "
                        "for share"), {"o": ctx.org_id, "id": event_id}).mappings().first()
                if held is None:
                    raise RuntimeError("memory input was not observable")
                held_value = held["value"] if isinstance(held["value"], dict) else json.loads(
                    held["value"])
                held_visibility = (held["visibility"] if isinstance(held["visibility"], dict)
                                   else json.loads(held["visibility"]))
                requested = {
                    "pattern_key": body.subject_key, "kind": "temporary_memory",
                    "actor_key": actor, "value": body.value, "explicit_memory": True,
                    "expires_at": body.expires_at, "trace_id": trace_id,
                    "visibility": visibility, "independence_key": independence_key,
                }
                stored = {
                    "pattern_key": held["pattern_key"], "kind": held["kind"],
                    "actor_key": held["actor_key"], "value": held_value,
                    "explicit_memory": bool(held["explicit_memory"]),
                    "expires_at": held["expires_at"], "trace_id": held["trace_id"],
                    "visibility": held_visibility,
                    "independence_key": held["independence_key"],
                }
                if canonical_dumps(requested) != canonical_dumps(stored):
                    collision_reason = "source_ref is already bound to different memory semantics"
                else:
                    fact = EnterpriseFact(
                        event_id=event_id, pattern_key=str(held["pattern_key"]),
                        kind=str(held["kind"]), occurred_at=held["occurred_at"],
                        value=held_value, explicit_memory=True, expires_at=held["expires_at"],
                        actor_key=held["actor_key"], trace_id=str(held["trace_id"]),
                        independence_key=str(held["independence_key"]),
                        visibility=held_visibility, lineage_complete=True)
                    item = temporary_memory(LearningBatch(
                        org_id=ctx.org_id, evaluated_at=now, events=(fact,)))[0]
                    if persist_object(conn, item, None, policy.revision, actor=actor):
                        created = True
                        state = apply_path(
                            conn, item, lifecycle_path(item, policy, eval_time=now), now,
                            actor=actor)
                    else:
                        existing = conn.execute(text(
                            "select current_state from learning_objects where org_id=:o "
                            "and learning_id=:id"),
                            {"o": ctx.org_id, "id": item.learning_id}).first()
                        if existing is None:
                            raise RuntimeError("idempotent memory object was not observable")
                        state = LearningState(str(existing.current_state))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    if refusal_reason:
        raise HTTPException(409, refusal_reason)
    if collision_reason:
        raise HTTPException(409, collision_reason)
    if item is None:
        raise HTTPException(409, "memory could not be materialized")
    return {"learning_id": item.learning_id, "created": created,
            "state": state.value if state is not None else "temporary",
            "expires_at": item.expires_at.isoformat() if item.expires_at else None}


class ReviewRequest(BaseModel):
    decision: str
    note: str | None = Field(None, max_length=2_000)


@router.post("/objects/{learning_id}/review")
def review(learning_id: str, body: ReviewRequest,
           ctx: AuthCtx = Depends(require_scope("learning.review"))) -> dict:
    _require_db()
    try:
        with _graph.engine.begin() as conn:
            viewer = _viewer(conn, ctx)
            return review_learning(conn, org_id=ctx.org_id, learning_id=learning_id,
                                   decision=body.decision,
                                   actor=ctx.actor_id or "org_owner",
                                   at=datetime.now(timezone.utc), note=body.note,
                                   viewer=viewer, owner_authorized=ctx.scopes is None)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


class RollbackRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@router.post("/objects/{learning_id}/rollback")
def rollback(learning_id: str, body: RollbackRequest,
             ctx: AuthCtx = Depends(require_scope("learning.rollback"))) -> dict:
    _require_db()
    try:
        with _graph.engine.begin() as conn:
            viewer = _viewer(conn, ctx)
            return rollback_learning(conn, org_id=ctx.org_id, learning_id=learning_id,
                                     actor=ctx.actor_id or "org_owner",
                                     at=datetime.now(timezone.utc), reason=body.reason,
                                     viewer=viewer, owner_authorized=ctx.scopes is None)
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
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
    # The current default lease is 168h; the ceiling cannot be lower than the lease it governs.
    max_temporary_ttl_hours: int = Field(720, ge=168, le=8_760)
    require_human_targets: list[str] = Field(
        default_factory=lambda: ["knowledge_suggestion", "organization"])
    blocked_subject_prefixes: list[str] = Field(default_factory=list)
    blocked_targets: list[str] = Field(default_factory=list)
    require_review_for_constrained_visibility: bool = True


@router.get("/policy")
def get_policy(org_id: str = Depends(get_current_org)) -> dict:
    _require_db()
    with _graph.engine.connect() as conn:
        policy = load_policy(conn, org_id)
    return {"revision": policy.revision, "learning_enabled": policy.enabled,
            "min_observations": policy.min_observations,
            "min_distinct_days": policy.min_distinct_days,
            "min_confidence_bp": policy.min_confidence_bp,
            "max_noise_bp": policy.max_noise_bp, "max_conflict_bp": policy.max_conflict_bp,
            "min_business_value_bp": policy.min_business_value_bp,
            "max_temporary_ttl_hours": policy.max_temporary_ttl_hours,
            "require_human_targets": sorted(target.value for target in policy.require_human_targets),
            "blocked_targets": sorted(target.value for target in policy.blocked_targets),
            "blocked_subject_prefixes": list(policy.blocked_subject_prefixes),
            "require_review_for_constrained_visibility":
                policy.require_review_for_constrained_visibility}


@router.put("/policy")
def put_policy(body: PolicyUpdate, ctx: AuthCtx = Depends(require_owner)) -> dict:
    _require_db()
    try:
        targets = sorted({LearningTarget(item).value for item in body.require_human_targets})
        blocked_targets = sorted({LearningTarget(item).value for item in body.blocked_targets})
        blocked_prefixes = sorted({require_identifier(item, "blocked subject prefix")
                                   for item in body.blocked_subject_prefixes})
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if LearningTarget.RUNTIME.value in targets:
        raise HTTPException(
            422, "runtime memory cannot require human review; it is an explicit expiring lease")
    # Knowledge changes are non-negotiably reviewed even if a caller omits the target.
    if LearningTarget.KNOWLEDGE_SUGGESTION.value not in targets:
        targets.append(LearningTarget.KNOWLEDGE_SUGGESTION.value)
        targets.sort()
    try:
        with _graph.engine.begin() as conn:
            lock_learning_tenant(conn, ctx.org_id)
            ensure_policy(conn, ctx.org_id, for_share=False)
            current = conn.execute(text(
                "select revision from learning_policies where org_id=:o and policy_key='default' "
                "for update"), {"o": ctx.org_id}).first()
            revision = int(current.revision) + 1
            changed = conn.execute(text(
                "update learning_policies set learning_enabled=:enabled,"
                "min_observations=:observations,min_distinct_days=:days,"
                "min_confidence_bp=:confidence,max_noise_bp=:noise,max_conflict_bp=:conflict,"
                "min_business_value_bp=:value,max_temporary_ttl_hours=:ttl,"
                "require_human_targets=:targets,blocked_targets=:blocked_targets,"
                "blocked_subject_prefixes=:blocked,"
                "require_review_for_constrained_visibility=:review_visibility,updated_by=:actor,"
                "revision=:revision,updated_at=now() where org_id=:o and policy_key='default' "
                "and revision=:current returning revision"),
                {"o": ctx.org_id, "enabled": body.learning_enabled,
                 "observations": body.min_observations, "days": body.min_distinct_days,
                 "confidence": body.min_confidence_bp, "noise": body.max_noise_bp,
                 "conflict": body.max_conflict_bp, "value": body.min_business_value_bp,
                 "ttl": body.max_temporary_ttl_hours, "targets": targets,
                 "blocked_targets": blocked_targets, "blocked": blocked_prefixes,
                 "review_visibility": body.require_review_for_constrained_visibility,
                 "revision": revision, "current": int(current.revision),
                 "actor": ctx.actor_id or "org_owner"})
            if changed.first() is None:
                raise RuntimeError("learning policy update lost serialization race")
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {**body.model_dump(), "revision": revision,
            "require_human_targets": targets, "blocked_targets": blocked_targets,
            "blocked_subject_prefixes": blocked_prefixes}


__all__ = ["router"]
