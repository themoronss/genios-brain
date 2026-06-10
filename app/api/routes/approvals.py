"""
Approvals queue — inbox of actions that matched a `require_approval` rule.

Agents DO NOT execute until the queue entry is approved (or expires).
Dashboard operators pick them up via these routes.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.actions import ledger as action_ledger
from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _jwt_org(request: Request) -> str:
    oid = getattr(request.state, "jwt_org_id", None)
    if not oid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return oid


def _acting_user(db: Session, org_id: str) -> str:
    """
    The JWT only carries org_id — look up the org's contact email so
    approved_by / rejected_by reads as a human identifier, not a UUID.
    Falls back to the org_id if lookup fails.
    """
    try:
        row = db.execute(
            text("SELECT email FROM orgs WHERE id = :id"),
            {"id": org_id},
        ).fetchone()
        if row and row[0]:
            return row[0]
    except Exception:
        pass
    return org_id


class ApprovalDecision(BaseModel):
    reason: Optional[str] = None


# ── Create (called internally by enforcement path) ──────────────────────────

def enqueue(
    db: Session,
    org_id: str,
    agent_id: str,
    action_type: str,
    risk_tier: str,
    target_ref: Optional[str],
    payload: dict,
    action_ledger_id: Optional[int] = None,
    triggered_rule_id: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[str]:
    """Insert a pending approval row. Returns its id (UUID str)."""
    import json
    try:
        row = db.execute(
            text("""
                INSERT INTO approvals_queue
                    (org_id, action_ledger_id, agent_id, action_type, risk_tier,
                     target_ref, payload, triggered_rule_id, reason)
                VALUES
                    (:org, :lid, :agent, :atype, :rtier,
                     :target, CAST(:payload AS jsonb), :rule, :reason)
                RETURNING id
            """),
            {
                "org": org_id, "lid": action_ledger_id, "agent": agent_id,
                "atype": action_type, "rtier": risk_tier,
                "target": target_ref,
                "payload": json.dumps(payload or {}, default=str),
                "rule": triggered_rule_id,
                "reason": (reason[:500] if reason else None),
            },
        ).fetchone()
        db.commit()
        return str(row[0]) if row else None
    except Exception as e:
        logger.warning(f"approvals.enqueue failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


# ── Routes ───────────────────────────────────────────────────────────────────

_ALLOWED_LIST_STATUSES = {"pending", "approved", "rejected", "expired", "auto_executed"}


@router.get("/api/org/{org_id}/approvals")
def list_approvals(
    org_id: str,
    request: Request,
    status: str = "pending",
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    if status not in _ALLOWED_LIST_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_STATUS", "allowed": sorted(_ALLOWED_LIST_STATUSES)},
        )

    rows = db.execute(
        text("""
            SELECT id, agent_id, action_type, risk_tier, target_ref, payload,
                   triggered_rule_id, status, reason, created_at, expires_at,
                   approved_by, approved_at
            FROM approvals_queue
            WHERE org_id = :org AND status = :status
            ORDER BY created_at DESC
            LIMIT 100
        """),
        {"org": org_id, "status": status},
    ).fetchall()

    return {
        "approvals": [
            {
                "id": str(r.id),
                "agent_id": r.agent_id,
                "action_type": r.action_type,
                "risk_tier": r.risk_tier,
                "target_ref": r.target_ref,
                "payload": r.payload,
                "triggered_rule_id": str(r.triggered_rule_id) if r.triggered_rule_id else None,
                "status": r.status,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "approved_by": r.approved_by,
                "approved_at": r.approved_at.isoformat() if r.approved_at else None,
            }
            for r in rows
        ]
    }


@router.post("/api/org/{org_id}/approvals/{approval_id}/approve")
def approve(
    org_id: str,
    approval_id: str,
    body: ApprovalDecision,
    request: Request,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")

    actor = _acting_user(db, org_id)
    row = db.execute(
        text("""
            UPDATE approvals_queue
            SET status='approved', approved_by=:by, approved_at=NOW(), reason=COALESCE(:r, reason)
            WHERE org_id = :org AND id = :id AND status = 'pending'
            RETURNING action_ledger_id
        """),
        {"by": actor, "r": body.reason, "org": org_id, "id": approval_id},
    ).fetchone()
    db.commit()
    if not row:
        raise HTTPException(status_code=404, detail="not pending or already resolved")

    # Operator-side semantics: approval = "done". Flip the ledger to success.
    # If a downstream executor re-runs the action later, it writes a new ledger row.
    if row[0]:
        action_ledger.update_outcome(db, int(row[0]), "success", f"approved by {actor}")
    return {"status": "approved", "approval_id": approval_id}


@router.post("/api/org/{org_id}/approvals/{approval_id}/reject")
def reject(
    org_id: str,
    approval_id: str,
    body: ApprovalDecision,
    request: Request,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")

    actor = _acting_user(db, org_id)
    row = db.execute(
        text("""
            UPDATE approvals_queue
            SET status='rejected', approved_by=:by, approved_at=NOW(), reason=COALESCE(:r, reason)
            WHERE org_id = :org AND id = :id AND status = 'pending'
            RETURNING action_ledger_id
        """),
        {"by": actor, "r": body.reason, "org": org_id, "id": approval_id},
    ).fetchone()
    db.commit()
    if not row:
        raise HTTPException(status_code=404, detail="not pending or already resolved")

    if row[0]:
        action_ledger.update_outcome(db, int(row[0]), "failed", f"rejected by {actor}: {body.reason or ''}")
    return {"status": "rejected", "approval_id": approval_id}
