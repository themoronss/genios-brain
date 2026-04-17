"""
Google Calendar push notification receiver.

Split from webhooks.py to keep each route file under the 300-line budget.
Google delivers state via headers (body is empty); we look up the channel,
verify the opaque token (if stored), then trigger an incremental sync.
"""

import json
import logging
import threading

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/webhooks/calendar")
async def calendar_push_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_goog_channel_id: str = Header(None, alias="X-Goog-Channel-ID"),
    x_goog_channel_token: str = Header(None, alias="X-Goog-Channel-Token"),
    x_goog_resource_state: str = Header(None, alias="X-Goog-Resource-State"),
    x_goog_resource_id: str = Header(None, alias="X-Goog-Resource-ID"),
    x_goog_message_number: str = Header(None, alias="X-Goog-Message-Number"),
):
    if not x_goog_channel_id:
        raise HTTPException(status_code=400, detail={"error": "MISSING_CHANNEL_ID"})

    # First delivery after subscription is a no-op "sync" ping — acknowledge.
    if x_goog_resource_state == "sync":
        return {"acknowledged": True, "action": "sync_ack"}

    row = db.execute(
        text("""
            SELECT org_id, calendar_id, channel_token
            FROM calendar_sync_state
            WHERE watch_channel_id = :cid
            LIMIT 1
        """),
        {"cid": x_goog_channel_id},
    ).fetchone()

    if not row:
        logger.info(f"Calendar webhook: unknown channel_id {x_goog_channel_id}")
        return {"acknowledged": True, "action": "channel_not_found"}

    if row.channel_token and row.channel_token != (x_goog_channel_token or ""):
        logger.warning(f"Calendar webhook: token mismatch for channel {x_goog_channel_id}")
        raise HTTPException(status_code=401, detail={"error": "TOKEN_MISMATCH"})

    org_id = str(row.org_id)
    calendar_id = row.calendar_id

    event_id = _log_event(db, org_id, calendar_id, x_goog_channel_id,
                          x_goog_resource_state, x_goog_resource_id, x_goog_message_number)

    # Phase 2: mirror into canonical event_log
    try:
        from app.memory import event_log
        event_log.append(
            db, org_id=org_id, source="calendar", verb="push",
            actor=None, object_type="calendar",
            object_id=calendar_id,
            payload={
                "channel_id": x_goog_channel_id,
                "calendar_id": calendar_id,
                "resource_state": x_goog_resource_state,
                "resource_id": x_goog_resource_id,
                "message_number": x_goog_message_number,
            },
        )
    except Exception as e:
        logger.debug(f"event_log.append (calendar push) failed: {e}")

    threading.Thread(target=_run_sync, args=(org_id, event_id), daemon=True).start()

    return {
        "acknowledged": True,
        "action": "sync_triggered",
        "org_id": org_id,
        "calendar_id": calendar_id,
        "resource_state": x_goog_resource_state,
    }


def _log_event(db, org_id, calendar_id, channel_id, state, resource_id, message_number):
    try:
        ins = db.execute(
            text("""
                INSERT INTO webhook_events (org_id, source, event_type, payload, status, received_at)
                VALUES (:org_id, 'calendar', 'push_notification', CAST(:payload AS jsonb), 'received', NOW())
                RETURNING id
            """),
            {
                "org_id": org_id,
                "payload": json.dumps({
                    "channel_id": channel_id,
                    "calendar_id": calendar_id,
                    "resource_state": state,
                    "resource_id": resource_id,
                    "message_number": message_number,
                }),
            },
        ).fetchone()
        db.commit()
        return str(ins[0]) if ins else None
    except Exception as e:
        logger.warning(f"Calendar webhook event log failed (non-critical): {e}")
        db.rollback()
        return None


def _update_event_status(event_id, status, error=None):
    if not event_id:
        return
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            db.execute(
                text("""
                    UPDATE webhook_events
                    SET status = :status, error = :err, processed_at = NOW()
                    WHERE id = :id
                """),
                {"status": status, "err": (error[:500] if error else None), "id": event_id},
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass


def _run_sync(org_id: str, event_id: str):
    from app.redis_client import redis_client
    lock_key = f"sync_lock:calendar:{org_id}"
    if not redis_client.set(lock_key, "1", nx=True, ex=300):
        logger.info(f"Calendar webhook: sync already running for org {org_id} — skipping duplicate")
        _update_event_status(event_id, "skipped")
        return

    try:
        from app.tasks.calendar_sync import run_calendar_sync
        run_calendar_sync(org_id)
        logger.info(f"Calendar webhook: incremental sync complete for org {org_id}")
        _update_event_status(event_id, "processed")
    except Exception as sync_err:
        logger.error(f"Calendar webhook: sync failed for org {org_id}: {sync_err}")
        _update_event_status(event_id, "failed", str(sync_err))
    finally:
        try:
            redis_client.delete(lock_key)
        except Exception:
            pass
