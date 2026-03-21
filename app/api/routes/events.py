from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
import asyncio
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def event_generator(org_id: str):
    """Generate SSE events for real-time updates."""
    last_check = datetime.now(timezone.utc)

    while True:
        try:
            db = SessionLocal()
            try:
                # Check for new activity
                events = db.execute(
                    text("""
                        SELECT event_type, event_data, created_at
                        FROM activity_log
                        WHERE org_id = :org_id AND created_at > :since
                        ORDER BY created_at DESC
                        LIMIT 10
                    """),
                    {"org_id": org_id, "since": last_check}
                ).fetchall()

                # Check sync status
                sync = db.execute(
                    text("""
                        SELECT sync_status, sync_total, sync_processed, sync_error, last_synced_at
                        FROM oauth_tokens
                        WHERE org_id = :org_id
                        LIMIT 1
                    """),
                    {"org_id": org_id}
                ).fetchone()
            finally:
                db.close()

            if events:
                for event in events:
                    data = {
                        "type": "activity",
                        "event_type": event[0],
                        "event_data": event[1] if isinstance(event[1], dict) else {},
                        "created_at": event[2].isoformat() if event[2] else None
                    }
                    yield f"data: {json.dumps(data, default=str)}\n\n"
                last_check = datetime.now(timezone.utc)

            if sync:
                sync_data = {
                    "type": "sync_status",
                    "status": sync[0] or "idle",
                    "total": sync[1] or 0,
                    "processed": sync[2] or 0,
                    "error": sync[3],
                    "last_synced_at": sync[4].isoformat() if sync[4] else None
                }
                yield f"data: {json.dumps(sync_data, default=str)}\n\n"

            # Heartbeat
            yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

        except Exception as e:
            logger.error(f"SSE error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        await asyncio.sleep(3)  # Poll every 3 seconds


@router.get("/events/stream/{org_id}")
async def stream_events(org_id: str):
    """SSE endpoint for real-time sync status + activity updates."""
    return StreamingResponse(
        event_generator(org_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
