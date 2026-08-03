"""Governance — Audit (dashboard → Settings → Audit). Read side of the append-only audit_log:
filterable, paginated event list + the action enum for the filter dropdown. Ported from
genios-brain (core/api/audit). Writes happen via platform/audit.record().
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import text

from genios_engine.platform.audit import ACTIONS
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


@router.get("/v1/audit/actions")
def list_action_types(org_id: str = Depends(get_current_org)) -> list:
    return ACTIONS


@router.get("/v1/audit/events")
def list_events(action: str | None = None, target_type: str | None = None,
                target_id: str | None = None, actor_id: str | None = None,
                since: str | None = None, until: str | None = None,
                limit: int = 50, offset: int = 0,
                org_id: str = Depends(get_current_org)) -> dict:
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    where = ["org_id = :o"]
    params: dict = {"o": org_id}
    for col, val in (("action", action), ("target_type", target_type), ("target_id", target_id),
                     ("actor_id", actor_id)):
        if val:
            where.append(f"{col} = :{col}"); params[col] = val
    if since:
        where.append("timestamp >= :since"); params["since"] = since
    if until:
        where.append("timestamp <= :until"); params["until"] = until
    clause = " and ".join(where)
    with _graph.engine.connect() as c:
        total = int(c.execute(text(f"select count(*) from audit_log where {clause}"), params).scalar() or 0)
        rows = c.execute(text(
            f"select id, actor_type, actor_id, action, target_type, target_id, metadata_jsonb, "
            f"timestamp from audit_log where {clause} order by timestamp desc limit :l offset :off"),
            {**params, "l": limit, "off": offset}).fetchall()
    events = [{
        "id": int(r.id), "actor_type": r.actor_type, "actor_id": r.actor_id, "action": r.action,
        "target_type": r.target_type, "target_id": r.target_id,
        "metadata": r.metadata_jsonb if isinstance(r.metadata_jsonb, dict)
        else (json.loads(r.metadata_jsonb) if r.metadata_jsonb else {}),
        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
    } for r in rows]
    return {"events": events, "total": total, "limit": limit, "offset": offset,
            "has_more": offset + len(events) < total}
