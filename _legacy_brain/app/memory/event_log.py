"""
Event log — immutable, append-only source of truth.

Every inbound fact lands here first (via `append`). Downstream consumers
(projection tasks, re-extraction, replay) read from here rather than from
connector-specific paths. Idempotency is enforced by payload_hash, so
webhook retries never double-count.
"""

import hashlib
import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _hash_payload(org_id: str, source: str, verb: str, object_id: Optional[str], payload: dict) -> str:
    """
    Stable content hash. Including (org, source, verb, object_id) in the
    hash domain means the same body from different sources is not collapsed.
    """
    key = json.dumps(
        {"org": org_id, "src": source, "verb": verb, "obj": object_id or "", "p": payload},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def append(
    db: Session,
    org_id: str,
    source: str,
    verb: str,
    payload: dict,
    actor: Optional[str] = None,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
) -> Optional[int]:
    """
    Append an event. Returns the event id, or None if deduped (retry-safe).
    """
    payload_hash = _hash_payload(org_id, source, verb, object_id, payload)
    try:
        row = db.execute(
            text("""
                INSERT INTO event_log
                    (org_id, source, verb, actor, object_type, object_id,
                     payload, payload_hash, observed_at)
                VALUES
                    (:org_id, :source, :verb, :actor, :otype, :oid,
                     CAST(:payload AS jsonb), :hash, NOW())
                ON CONFLICT (org_id, payload_hash) DO NOTHING
                RETURNING id
            """),
            {
                "org_id": org_id,
                "source": source,
                "verb": verb,
                "actor": actor,
                "otype": object_type,
                "oid": object_id,
                "payload": json.dumps(payload, default=str),
                "hash": payload_hash,
            },
        ).fetchone()
        db.commit()
        return int(row[0]) if row else None
    except Exception as e:
        logger.warning(f"event_log.append failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def mark_projected(db: Session, event_id: int, status: str = "projected", error: Optional[str] = None) -> None:
    """Mark an event as processed by its downstream projector."""
    try:
        db.execute(
            text("""
                UPDATE event_log
                SET processed_status = :status,
                    processed_at     = NOW(),
                    process_error    = :err
                WHERE id = :id
            """),
            {"status": status, "err": (error[:500] if error else None), "id": event_id},
        )
        db.commit()
    except Exception as e:
        logger.warning(f"event_log.mark_projected failed for id={event_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass


def list_pending(db: Session, org_id: Optional[str] = None, limit: int = 100) -> list:
    """Fetch pending events, optionally scoped to one org."""
    params = {"limit": limit}
    if org_id:
        sql = """
            SELECT id, org_id, source, verb, actor, object_type, object_id,
                   payload, observed_at
            FROM event_log
            WHERE processed_status = 'pending' AND org_id = :org_id
            ORDER BY observed_at ASC
            LIMIT :limit
        """
        params["org_id"] = org_id
    else:
        sql = """
            SELECT id, org_id, source, verb, actor, object_type, object_id,
                   payload, observed_at
            FROM event_log
            WHERE processed_status = 'pending'
            ORDER BY observed_at ASC
            LIMIT :limit
        """
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        logger.warning(f"event_log.list_pending failed: {e}")
        return []
    return [
        {
            "id": int(r.id),
            "org_id": str(r.org_id),
            "source": r.source,
            "verb": r.verb,
            "actor": r.actor,
            "object_type": r.object_type,
            "object_id": r.object_id,
            "payload": r.payload,
            "observed_at": r.observed_at.isoformat() if r.observed_at else None,
        }
        for r in rows
    ]


def query_range(
    db: Session,
    org_id: str,
    source: Optional[str] = None,
    verb: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 500,
) -> list:
    """Read-only scan of events in a time window. Used by replay and explainer."""
    where = ["org_id = :org_id"]
    params = {"org_id": org_id, "limit": limit}
    if source:
        where.append("source = :source")
        params["source"] = source
    if verb:
        where.append("verb = :verb")
        params["verb"] = verb
    if since:
        where.append("observed_at >= :since")
        params["since"] = since
    if until:
        where.append("observed_at < :until")
        params["until"] = until

    sql = f"""
        SELECT id, source, verb, actor, object_type, object_id, payload, observed_at
        FROM event_log
        WHERE {' AND '.join(where)}
        ORDER BY observed_at ASC
        LIMIT :limit
    """
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        logger.warning(f"event_log.query_range failed: {e}")
        return []
    return [
        {
            "id": int(r.id),
            "source": r.source,
            "verb": r.verb,
            "actor": r.actor,
            "object_type": r.object_type,
            "object_id": r.object_id,
            "payload": r.payload,
            "observed_at": r.observed_at.isoformat() if r.observed_at else None,
        }
        for r in rows
    ]
