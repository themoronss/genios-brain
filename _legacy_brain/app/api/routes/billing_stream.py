"""SSE: live credit-balance push for the dashboard (replaces client polling).

GET /v1/billing/stream?token=<jwt>      (EventSource can't send headers, so the
                                         dashboard JWT comes via query param)
        ?org=<org_id>                    (dev only — refused when GENIOS_ENV=production)

One persistent connection per browser tab. On connect we push the current
balance; thereafter the in-process credit hub signals on every balance change
and we push the fresh DB total. Heartbeat every 15s keeps proxies from closing
the idle stream. No client-side polling anywhere.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text
from sse_starlette.sse import EventSourceResponse

from app.credits.stream_hub import hub
from app.database import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter()

_HEARTBEAT_SECONDS = 15
_COMMIT_SETTLE_SECONDS = 0.05  # let a just-fired deduct's commit land before re-read


def _resolve_org(token: str | None, org: str | None) -> str:
    if token:
        from core.api.deps import _org_from_jwt

        org_id = _org_from_jwt(token)
        if org_id:
            return org_id
    if org and os.getenv("GENIOS_ENV", "").lower() != "production":
        return org
    raise HTTPException(status_code=401, detail="missing or invalid token")


def _read_balance(org_id: str) -> dict:
    """Authoritative current balance, read on its own short-lived session so the
    long-running SSE connection never holds a DB connection open between events."""
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT COALESCE(credits, 0) AS plan, COALESCE(topup_credits, 0) AS topup "
                "FROM orgs WHERE id = :o"
            ),
            {"o": org_id},
        ).fetchone()
    finally:
        db.close()
    plan = int(row.plan) if row else 0
    topup = int(row.topup) if row else 0
    return {"balance": plan + topup, "plan": plan, "topup": topup}


@router.get("/v1/billing/stream")
async def billing_stream(
    request: Request,
    token: str | None = Query(None),
    org: str | None = Query(None),
):
    org_id = _resolve_org(token, org)
    hub.bind_loop(asyncio.get_running_loop())
    q = hub.subscribe(org_id)

    async def gen():
        try:
            # Initial state so the meter is correct the instant the page loads.
            yield {"event": "balance", "data": json.dumps(_read_balance(org_id))}
            while True:
                if await request.is_disconnected():
                    return
                try:
                    await asyncio.wait_for(q.get(), timeout=_HEARTBEAT_SECONDS)
                    # Coalesce a burst of deducts (e.g. a sync draining N items)
                    # into a single fresh read.
                    while not q.empty():
                        q.get_nowait()
                    await asyncio.sleep(_COMMIT_SETTLE_SECONDS)
                    yield {"event": "balance", "data": json.dumps(_read_balance(org_id))}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}
        finally:
            hub.unsubscribe(org_id, q)

    return EventSourceResponse(gen())
