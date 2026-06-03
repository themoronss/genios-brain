"""SSE stream endpoint (Phase 5.7).

GET /v1/stream/recommendations?min_priority=0.6

Clients hold an open HTTP/1.1 `text/event-stream` connection; the server emits a
JSON event per new recommendation that passes the priority filter. Heartbeat
comment every 15s keeps the connection alive through proxies.

Delivery source: polls the `recommendations` table for rows with
`delivered_at IS NULL AND org_id = <caller>` and marks them delivered on send.
(Same table the webhook dispatcher reads; a client using SSE replaces their
webhook use case.)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db, verify_api_key

logger = logging.getLogger(__name__)

router = APIRouter()

_POLL_SECONDS = 3
_HEARTBEAT_SECONDS = 15


async def _event_gen(
    request: Request,
    db: Session,
    org_id: str,
    min_priority: float,
) -> AsyncIterator[dict]:
    """Yield SSE events for new recommendations. Caller handles timeouts."""
    last_heartbeat = asyncio.get_event_loop().time()

    while True:
        if await request.is_disconnected():
            return

        try:
            rows = db.execute(
                text("""
                    SELECT id, insight_type, category, priority, confidence,
                           title, reason, action, subject_entity_id, created_at,
                           evidence, precedent_links, suggested_action,
                           confidence_level, rationale
                    FROM recommendations
                    WHERE org_id = :oid
                      AND delivered_at IS NULL
                      AND priority >= :pri
                    ORDER BY created_at ASC
                    LIMIT 50
                """),
                {"oid": org_id, "pri": min_priority},
            ).fetchall()
        except Exception as e:
            logger.warning(f"sse poll failed: {e}")
            rows = []

        for r in rows:
            # Payload v2 — new fields always emitted; consumers built against
            # v1 can ignore them (additive contract).
            payload = {
                "payload_version": 2,
                "recommendation_id": str(r[0]),
                "insight_type": r[1],
                "category": r[2],
                "priority": float(r[3] or 0),
                "confidence": float(r[4] or 0),
                "confidence_level": r[13],
                "title": r[5],
                "rationale": r[14] or r[6],
                "reason": r[6],  # v1 compat
                "action": r[7],  # v1 compat
                "suggested_action": r[12],
                "evidence": r[10] or [],
                "precedent_links": r[11] or [],
                "subject_entity_id": str(r[8]) if r[8] else None,
                "created_at": r[9].isoformat() if r[9] else None,
            }
            yield {"event": "recommendation", "data": json.dumps(payload, default=str)}

            try:
                db.execute(
                    text("UPDATE recommendations SET delivered_at = NOW() WHERE id = :id"),
                    {"id": str(r[0])},
                )
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"sse delivered_at update failed: {e}")

        now = asyncio.get_event_loop().time()
        if now - last_heartbeat >= _HEARTBEAT_SECONDS:
            yield {"event": "ping", "data": "{}"}
            last_heartbeat = now

        await asyncio.sleep(_POLL_SECONDS)


@router.get("/v1/stream/recommendations")
async def stream_recommendations(
    request: Request,
    min_priority: float = 0.6,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    min_priority = max(0.0, min(1.0, float(min_priority)))
    return EventSourceResponse(_event_gen(request, db, org_id, min_priority))


# ── REST poll — for batch / scheduled agents that don't want a live stream ──
# Returns up to `limit` undelivered recommendations ordered by priority then
# created_at. Marks them delivered (so the next call moves on) unless
# ?ack=false is passed (read-only peek). Mirrors the SSE payload v2 schema.
@router.get("/v1/recommendations/pending")
def list_pending_recommendations(
    min_priority: float = 0.6,
    limit: int = 20,
    ack: bool = True,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    min_priority = max(0.0, min(1.0, float(min_priority)))
    limit = max(1, min(100, int(limit)))

    rows = db.execute(
        text("""
            SELECT id, insight_type, category, priority, confidence,
                   title, reason, action, subject_entity_id, created_at,
                   evidence, precedent_links, suggested_action,
                   confidence_level, rationale
            FROM recommendations
            WHERE org_id = :oid
              AND delivered_at IS NULL
              AND priority >= :pri
            ORDER BY priority DESC, created_at ASC
            LIMIT :lim
        """),
        {"oid": org_id, "pri": min_priority, "lim": limit},
    ).fetchall()

    items = []
    for r in rows:
        items.append({
            "payload_version": 2,
            "recommendation_id": str(r[0]),
            "insight_type": r[1],
            "category": r[2],
            "priority": float(r[3] or 0),
            "confidence": float(r[4] or 0),
            "confidence_level": r[13],
            "title": r[5],
            "rationale": r[14] or r[6],
            "reason": r[6],
            "action": r[7],
            "suggested_action": r[12],
            "evidence": r[10] or [],
            "precedent_links": r[11] or [],
            "subject_entity_id": str(r[8]) if r[8] else None,
            "created_at": r[9].isoformat() if r[9] else None,
        })

    if ack and items:
        ids = [i["recommendation_id"] for i in items]
        try:
            db.execute(
                text("UPDATE recommendations SET delivered_at = NOW() "
                     "WHERE id = ANY(CAST(:ids AS uuid[]))"),
                {"ids": ids},
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"pending poll ack failed: {e}")

    return {"recommendations": items, "count": len(items), "ack": ack}
