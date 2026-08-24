"""Governance — Approvals (dashboard → Settings → Approvals). The human queue for actions a policy
decided need approval before executing. Ported from genios-brain (app/api/routes/approvals.py) to
the engine's raw-SQL + `_org` conventions. `enqueue()` is the module-level entry the policy
enforcement path calls to park an action; the routes are the dashboard read/decide surface.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.ids import new_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

_COLS = ("id, agent_id, action_type, risk_tier, target_ref, payload, triggered_rule_id, status, "
         "reason, approved_by, approved_at, created_at, expires_at")


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _ser(r) -> dict:
    payload = r.payload if isinstance(r.payload, dict) else (json.loads(r.payload) if r.payload else {})
    return {"id": r.id, "agent_id": r.agent_id, "action_type": r.action_type, "risk_tier": r.risk_tier,
            "target_ref": r.target_ref, "payload": payload, "triggered_rule_id": r.triggered_rule_id,
            "status": r.status, "reason": r.reason, "approved_by": r.approved_by,
            "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None}


def enqueue(org_id: str, *, action_type: str, agent_id: str | None = None, risk_tier: str | None = None,
            target_ref: str | None = None, payload: dict | None = None, triggered_rule_id: str | None = None,
            reason: str | None = None, expires_at: datetime | None = None) -> str:
    """Park an action pending human approval. Returns the approval id. Called from the policy
    enforcement path (a require_approval decision). Kept importable for that wiring."""
    aid = new_id("apr")
    with _graph.engine.begin() as c:
        c.execute(text(
            "insert into approvals_queue (id, org_id, agent_id, action_type, risk_tier, target_ref, "
            "payload, triggered_rule_id, reason, expires_at) values "
            "(:i,:o,:ag,:at,:rt,:tr,cast(:pl as jsonb),:rule,:rsn,:exp)"),
            {"i": aid, "o": org_id, "ag": agent_id, "at": action_type, "rt": risk_tier, "tr": target_ref,
             "pl": json.dumps(payload or {}), "rule": triggered_rule_id, "rsn": reason, "exp": expires_at})
    return aid


@router.get("/api/org/{org_id}/approvals")
def list_approvals(org_id: str, status: str = "pending", org: str = Depends(_org)) -> dict:
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            f"select {_COLS} from approvals_queue where org_id=:o and status=:s "
            "order by created_at desc"), {"o": org, "s": status}).fetchall()
    return {"approvals": [_ser(r) for r in rows]}


class ApprovalDecision(BaseModel):
    reason: str | None = None


def _acting_user(c, org: str) -> str:
    return c.execute(text("select email from orgs where id=:o"), {"o": org}).scalar() or "owner"


def _decide(org: str, approval_id: str, to_status: str, reason: str | None) -> dict:
    now = datetime.now(timezone.utc)
    with _graph.engine.begin() as c:
        cur = c.execute(text("select status from approvals_queue where org_id=:o and id=:i"),
                        {"o": org, "i": approval_id}).first()
        if cur is None:
            raise HTTPException(404, {"error": "not_found", "message": "approval not found"})
        if cur.status != "pending":
            raise HTTPException(409, {"error": "already_decided", "message": f"already {cur.status}"})
        who = _acting_user(c, org)
        c.execute(text("update approvals_queue set status=:s, reason=coalesce(:r, reason), "
                       "approved_by=:by, approved_at=:t where org_id=:o and id=:i"),
                  {"s": to_status, "r": reason, "by": who, "t": now, "o": org, "i": approval_id})
    return {"status": to_status, "id": approval_id}


@router.post("/api/org/{org_id}/approvals/{approval_id}/approve")
def approve(org_id: str, approval_id: str, body: ApprovalDecision | None = None,
            org: str = Depends(_org)) -> dict:
    return _decide(org, approval_id, "approved", (body.reason if body else None))


@router.post("/api/org/{org_id}/approvals/{approval_id}/reject")
def reject(org_id: str, approval_id: str, body: ApprovalDecision | None = None,
           org: str = Depends(_org)) -> dict:
    return _decide(org, approval_id, "rejected", (body.reason if body else None))
