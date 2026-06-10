"""
Agent Blackboard — shared coordination layer (Phase 1.1).

Redis is the live truth. Postgres (`agent_activity_log`) is the audit trail
that dashboards read. Agents call `claim()` before touching a contact and
`release()` after; `peek()` lets any agent see who else is currently active.

Key layout (DB 0, shared with context cache):
  agent:lock:<org>:<contact>    → "<agent_id>|<action>"   (NX, TTL=ttl_seconds)
  agent:recent:<org>:<contact>  → LIST of json blobs      (LTRIM to last 10)

Nothing here raises on Redis outage — coordination degrades to "no awareness",
which is the same as today's behaviour.
"""

import json
import logging
import time
import uuid
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.redis_client import redis_client

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 60
RECENT_LIST_MAX = 10


# ── Key builders ─────────────────────────────────────────────────────────────

def _lock_key(org_id: str, contact_ref: str) -> str:
    return f"agent:lock:{org_id}:{contact_ref}"


def _recent_key(org_id: str, contact_ref: str) -> str:
    return f"agent:recent:{org_id}:{contact_ref}"


# ── Public API ───────────────────────────────────────────────────────────────

def claim(
    org_id: str,
    contact_ref: str,
    agent_id: str,
    action: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> dict:
    """
    Try to acquire an exclusive lock on (org, contact).

    Returns:
        {"acquired": True,  "lock_id": "<uuid>", "holder": None}
        {"acquired": False, "lock_id": None,     "holder": "<agent_id>|<action>"}
    """
    if not contact_ref:
        # Without a contact reference there is nothing to lock — no-op claim.
        return {"acquired": True, "lock_id": None, "holder": None}

    lock_id = str(uuid.uuid4())
    payload = f"{agent_id}|{action}|{lock_id}"
    key = _lock_key(org_id, contact_ref)

    try:
        acquired = redis_client.set(key, payload, nx=True, ex=ttl_seconds)
    except Exception as e:
        logger.warning(f"blackboard.claim redis error ({key}): {e}")
        # Fail-open: coordination unavailable, let the action proceed.
        return {"acquired": True, "lock_id": None, "holder": None}

    if acquired:
        return {"acquired": True, "lock_id": lock_id, "holder": None}

    try:
        current = redis_client.get(key)
    except Exception:
        current = None
    return {"acquired": False, "lock_id": None, "holder": current}


def release(org_id: str, contact_ref: str, lock_id: Optional[str]) -> bool:
    """
    Release the lock only if we still own it (compare lock_id).
    Safe to call with lock_id=None — becomes a no-op.
    """
    if not contact_ref or not lock_id:
        return False

    key = _lock_key(org_id, contact_ref)
    try:
        current = redis_client.get(key)
        if current and current.endswith(f"|{lock_id}"):
            redis_client.delete(key)
            return True
    except Exception as e:
        logger.warning(f"blackboard.release redis error ({key}): {e}")
    return False


def log(
    org_id: str,
    contact_ref: str,
    agent_id: str,
    action: str,
    status: str = "completed",
    metadata: Optional[dict] = None,
) -> None:
    """
    Append an event to the per-contact recent list (in Redis).
    Never raises — coordination is best-effort.
    """
    if not contact_ref:
        return

    entry = {
        "agent_id": agent_id,
        "action": action,
        "status": status,
        "ts": int(time.time()),
        "metadata": metadata or {},
    }
    key = _recent_key(org_id, contact_ref)
    try:
        redis_client.lpush(key, json.dumps(entry))
        redis_client.ltrim(key, 0, RECENT_LIST_MAX - 1)
        redis_client.expire(key, 86400)  # 24h retention
    except Exception as e:
        logger.warning(f"blackboard.log redis error ({key}): {e}")


def peek(org_id: str, contact_ref: str) -> dict:
    """
    Snapshot of current + recent activity on a contact.

    Returns:
        {
          "locked_by": "agent_x|action|lock_id" or None,
          "recent": [ {agent_id, action, status, ts, metadata}, ... ]
        }
    """
    if not contact_ref:
        return {"locked_by": None, "recent": []}

    try:
        holder = redis_client.get(_lock_key(org_id, contact_ref))
    except Exception:
        holder = None

    try:
        raw = redis_client.lrange(_recent_key(org_id, contact_ref), 0, RECENT_LIST_MAX - 1)
        recent = [json.loads(r) for r in raw if r]
    except Exception:
        recent = []

    return {"locked_by": holder, "recent": recent}


# ── Audit persistence (Postgres) ────────────────────────────────────────────

def audit(
    db: Session,
    org_id: str,
    agent_id: str,
    action: str,
    status: str,
    contact_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    ended: bool = False,
) -> None:
    """
    Best-effort insert into agent_activity_log. Swallow errors so coordination
    never fails a request.
    """
    try:
        db.execute(
            text("""
                INSERT INTO agent_activity_log
                    (org_id, agent_id, contact_id, action, status,
                     started_at, ended_at, metadata)
                VALUES
                    (:org_id, :agent_id, :contact_id, :action, :status,
                     NOW(), CASE WHEN :ended THEN NOW() ELSE NULL END,
                     CAST(:metadata AS jsonb))
            """),
            {
                "org_id": org_id,
                "agent_id": agent_id,
                "contact_id": contact_id,
                "action": action,
                "status": status,
                "ended": ended,
                "metadata": json.dumps(metadata or {}),
            },
        )
        db.commit()
    except Exception as e:
        logger.warning(f"blackboard.audit insert failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
