"""
Live activity feed (Phase 5).

Dashboard polls this to show what agents are doing right now. Data is pulled
from the blackboard Redis keys + agent_activity_log + recent action_ledger.
Polling (2s-5s interval from the client) is fine at our scale; SSE can be
bolted on later if needed.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()


def _jwt_org(request: Request) -> str:
    oid = getattr(request.state, "jwt_org_id", None)
    if not oid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return oid


# ── Display status derivation ────────────────────────────────────────────────
# `outcome` in the ledger is truthful (pending/success/failed/reverted).
# For operators looking at Live, we translate that into a category that
# reflects INTENT — locks + policy gates aren't failures, they're the system
# doing its job. Real failures (external API errors, bugs) stay highlighted.

def _display_status(outcome: str, outcome_detail: str, policy_decision: str) -> str:
    if outcome == "success":
        return "success"
    if outcome == "pending":
        return "awaiting_approval" if policy_decision == "require_approval" else "running"
    if outcome == "reverted":
        return "reverted"
    # outcome == 'failed' below — decide if it's an error or a designed skip
    detail = (outcome_detail or "").lower()
    if policy_decision == "block" or detail.startswith("policy_block"):
        return "blocked_by_policy"
    if "contact_locked" in detail:
        return "skipped_locked"
    if "awaiting_approval" in detail or "awaiting approval" in detail:
        return "awaiting_approval"
    if detail.startswith("expired") or "expired_without_decision" in detail:
        return "expired"
    if detail.startswith("rejected"):
        return "rejected"
    return "error"


DISPLAY_ALLOWED_MINUTES = {15, 60, 1440}  # 15 min, 1 h, 24 h


def _scan_active_locks(org_id: str, limit: int = 50) -> list:
    """
    Walk the blackboard locks for this org. Keys shape: agent:lock:<org>:<contact>.
    SCAN is O(N) on keyspace size — fine for small orgs. If we ever grow, move
    to a Redis stream/sorted-set index.
    """
    locks = []
    try:
        cursor = 0
        while True:
            cursor, keys = redis_client.scan(
                cursor=cursor, match=f"agent:lock:{org_id}:*", count=200
            )
            for key in keys:
                value = redis_client.get(key)
                if not value:
                    continue
                ttl = redis_client.ttl(key)
                contact = key.split(":", 3)[-1] if ":" in key else None
                # value format "<agent>|<action>|<lock_id>"
                parts = value.split("|") if isinstance(value, str) else []
                locks.append({
                    "contact_ref": contact,
                    "agent_id": parts[0] if len(parts) > 0 else None,
                    "action": parts[1] if len(parts) > 1 else None,
                    "ttl_seconds": int(ttl) if ttl and ttl > 0 else None,
                })
                if len(locks) >= limit:
                    return locks
            if cursor == 0:
                break
    except Exception as e:
        logger.debug(f"live.scan_active_locks error: {e}")
    return locks


@router.get("/api/org/{org_id}/live")
def live_activity(
    org_id: str,
    request: Request,
    minutes: int = 15,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    if minutes not in DISPLAY_ALLOWED_MINUTES:
        # Don't let callers DoS us with arbitrary windows; Live is for recent state.
        minutes = 15

    active_locks = _scan_active_locks(org_id)

    recent_audit = db.execute(
        text("""
            SELECT agent_id, action, status, started_at, ended_at, contact_id, metadata
            FROM agent_activity_log
            WHERE org_id = :org
              AND started_at > NOW() - (:mins || ' minutes')::interval
            ORDER BY started_at DESC
            LIMIT 100
        """),
        {"org": org_id, "mins": str(minutes)},
    ).fetchall()

    recent_actions = db.execute(
        text("""
            SELECT id, agent_id, action_type, risk_tier, target_ref,
                   policy_decision, outcome, outcome_detail, created_at
            FROM action_ledger
            WHERE org_id = :org
              AND created_at > NOW() - (:mins || ' minutes')::interval
            ORDER BY created_at DESC
            LIMIT 100
        """),
        {"org": org_id, "mins": str(minutes)},
    ).fetchall()

    pending_approvals = db.execute(
        text("""
            SELECT COUNT(*) FROM approvals_queue
            WHERE org_id = :org AND status = 'pending'
        """),
        {"org": org_id},
    ).scalar() or 0

    return {
        "active_locks": active_locks,
        "recent_audit": [
            {
                "agent_id": r.agent_id, "action": r.action, "status": r.status,
                "contact_id": str(r.contact_id) if r.contact_id else None,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "metadata": r.metadata,
            }
            for r in recent_audit
        ],
        "recent_actions": [
            {
                "id": int(r.id), "agent_id": r.agent_id,
                "action_type": r.action_type, "risk_tier": r.risk_tier,
                "target_ref": r.target_ref,
                "policy_decision": r.policy_decision,
                "outcome": r.outcome,
                "outcome_detail": r.outcome_detail,
                "display_status": _display_status(
                    r.outcome, r.outcome_detail or "", r.policy_decision or ""
                ),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in recent_actions
        ],
        "pending_approvals": int(pending_approvals),
        "window_minutes": minutes,
    }
