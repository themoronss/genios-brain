"""
Webhook ingest endpoints — Phase 10.
  POST /v1/webhooks/gmail   — Gmail push notification receiver (Startup only)
  GET  /v1/webhooks/events  — Last 50 webhook events for the authenticated org
"""

import base64
import json
import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.plan_enforcer import get_org_plan

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/webhooks/gmail")
async def gmail_push_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive Gmail push notifications (Pub/Sub HTTP push delivery).
    Startup plan only — triggers incremental Gmail sync on receipt.

    Google sends:
      { "message": { "data": "<base64>", "messageId": "...", "publishTime": "..." }, "subscription": "..." }

    The base64 `data` decodes to: { "emailAddress": "...", "historyId": "123456" }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "INVALID_BODY", "message": "Expected JSON body"})

    message = body.get("message", {})
    raw_data = message.get("data", "")

    if not raw_data:
        # Google sends an empty keep-alive — acknowledge silently
        return {"acknowledged": True, "action": "keepalive"}

    try:
        decoded = base64.b64decode(raw_data + "==").decode("utf-8")
        notification = json.loads(decoded)
    except Exception:
        logger.warning("Gmail webhook: could not decode notification data")
        return {"acknowledged": True, "action": "decode_failed"}

    email_address = notification.get("emailAddress", "")
    history_id = notification.get("historyId")

    if not email_address:
        return {"acknowledged": True, "action": "no_email"}

    # Look up the org that owns this Gmail account
    row = db.execute(
        text("""
            SELECT org_id FROM oauth_tokens
            WHERE account_email = :email
              AND provider = 'google'
            LIMIT 1
        """),
        {"email": email_address},
    ).fetchone()

    if not row:
        logger.info(f"Gmail webhook: no org found for {email_address}")
        return {"acknowledged": True, "action": "org_not_found"}

    org_id = str(row.org_id)

    # Only process for Startup plan (real-time sync tier)
    plan_info = get_org_plan(db, org_id)
    if plan_info["tier"] != "startup":
        logger.debug(f"Gmail webhook: org {org_id} is on {plan_info['tier']} plan — skipping real-time sync")
        return {"acknowledged": True, "action": "plan_not_eligible"}

    # Log the webhook event
    event_id = None
    try:
        row = db.execute(
            text("""
                INSERT INTO webhook_events (org_id, source, event_type, payload, status, received_at)
                VALUES (:org_id, 'gmail', 'push_notification', :payload::jsonb, 'received', NOW())
                RETURNING id
            """),
            {
                "org_id": org_id,
                "payload": json.dumps({"email": email_address, "historyId": history_id}),
            },
        ).fetchone()
        event_id = str(row[0]) if row else None
        db.commit()
    except Exception as e:
        logger.warning(f"Gmail webhook event log failed (non-critical): {e}")
        db.rollback()

    # Trigger incremental Gmail sync in background — Redis lock prevents pile-up
    def _run_sync():
        from app.redis_client import redis_client as _redis
        lock_key = f"sync_lock:gmail:{org_id}"

        # Try to acquire lock (TTL = 5 min max sync time)
        acquired = _redis.set(lock_key, "1", nx=True, ex=300)
        if not acquired:
            logger.info(f"Gmail webhook: sync already running for org {org_id} — skipping duplicate")
            # Mark this event as skipped
            if event_id:
                try:
                    from app.database import SessionLocal
                    _db = SessionLocal()
                    _db.execute(
                        text("UPDATE webhook_events SET status='skipped', processed_at=NOW() WHERE id=:id"),
                        {"id": event_id},
                    )
                    _db.commit()
                    _db.close()
                except Exception:
                    pass
            return

        try:
            from app.tasks.gmail_sync import run_gmail_sync
            run_gmail_sync(org_id)
            logger.info(f"Gmail webhook: incremental sync complete for org {org_id}")
            if event_id:
                _db = None
                try:
                    from app.database import SessionLocal
                    _db = SessionLocal()
                    _db.execute(
                        text("UPDATE webhook_events SET status='processed', processed_at=NOW() WHERE id=:id"),
                        {"id": event_id},
                    )
                    _db.commit()
                except Exception:
                    pass
                finally:
                    if _db:
                        _db.close()
        except Exception as sync_err:
            logger.error(f"Gmail webhook: sync failed for org {org_id}: {sync_err}")
            if event_id:
                _db = None
                try:
                    from app.database import SessionLocal
                    _db = SessionLocal()
                    _db.execute(
                        text("UPDATE webhook_events SET status='failed', error=:err, processed_at=NOW() WHERE id=:id"),
                        {"id": event_id, "err": str(sync_err)},
                    )
                    _db.commit()
                except Exception:
                    pass
                finally:
                    if _db:
                        _db.close()
        finally:
            _redis.delete(lock_key)

    t = threading.Thread(target=_run_sync, daemon=True)
    t.start()

    return {
        "acknowledged": True,
        "action": "sync_triggered",
        "org_id": org_id,
        "history_id": history_id,
    }


# ── GET /v1/webhooks/events ────────────────────────────────────────────────────

@router.get("/v1/webhooks/events")
def list_webhook_events(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    Return the last 50 webhook events for the authenticated org.
    Startup plan only (real-time sync tier).
    """
    plan_info = get_org_plan(db, org_id)
    if plan_info["tier"] != "startup":
        raise HTTPException(
            status_code=403,
            detail={"error": "PLAN_LIMIT", "message": "Webhook event log is available on Startup plan only.", "upgrade_required": True},
        )

    rows = db.execute(
        text("""
            SELECT id, source, event_type, payload, status, error, received_at, processed_at
            FROM webhook_events
            WHERE org_id = :org_id
            ORDER BY received_at DESC
            LIMIT 50
        """),
        {"org_id": org_id},
    ).fetchall()

    events = [
        {
            "id": str(r.id),
            "source": r.source,
            "event_type": r.event_type,
            "payload": r.payload,
            "status": r.status,
            "error": r.error,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in rows
    ]

    return {"events": events, "count": len(events)}
