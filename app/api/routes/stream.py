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
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Request
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

        # `recommendations` was dropped in migration 0015 with the dead System-B
        # brain router that fed it. No v2 source writes it, so there is nothing
        # to stream — this loop emits heartbeats only (keeping the SSE contract
        # + connection alive) until a v2 stream source is wired from
        # `proactive_insights`. The per-row emit + delivered_at UPDATE were
        # removed with the dropped table.

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

    # `recommendations` was dropped in migration 0015 with the dead System-B
    # brain router that fed it. No v2 source writes it, so this poll returns an
    # empty set (route kept live so existing clients don't 404) until a v2
    # source is wired from `proactive_insights`.
    items: list[dict] = []
    return {"recommendations": items, "count": len(items), "ack": ack}
