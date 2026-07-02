"""
Phase 9: Live activity SSE stream.

Powers the homepage "watch the brain think" feed. Pushes the most recent
brain decisions, lifecycle transitions, and live tool fetches to any
listening client (the website, dashboards) as Server-Sent Events.

Polling implementation: 2s interval, last-id cursor on (source, id) so we
never re-deliver the same event. Public, anonymized — never returns
contact emails or private fact bodies. Org names anonymized to first
letter + number (e.g. "M-orgs" pattern) so a single org's activity
isn't fingerprinted.

Why SSE not Websockets: SSE is one-direction, simpler infra, plays nice
with CDNs and Vercel proxies. The frontend can re-attach automatically
on disconnect.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_POLL_INTERVAL_S = 2.0
_MAX_PER_TICK = 10


def _fetch_activity(db: Session, since_iso: str | None) -> list[dict]:
    """Pull recent brain activity for the public "watch the brain think" feed.

    Neutralized on v2: all three original sources were dropped in migration
    0015 — `recommendations` + `pending_alerts` (dead System-B brain router,
    now removed) and `interactions` (v1 auto-classified email table, replaced by
    graph_nodes/facts). Querying them here would fail on every 2s poll tick, so
    those blocks are removed rather than left to log-spam.

    Kept as a live route (mounted, public, SSE) returning an empty feed until a
    v2 activity source is wired from `proactive_insights` / the graph event log.
    """
    return []


@router.get("/v1/activity/stream")
async def activity_stream(
    db: Session = Depends(get_db),
    initial: int = Query(5, ge=0, le=20, description="initial items pushed"),
):
    """
    SSE endpoint. Long-lived connection. Sends recent brain activity every
    2 seconds. CORS-permissive so the marketing site can embed directly.
    """

    async def event_generator():
        # Initial burst — let the user see SOMETHING immediately
        try:
            initial_items = _fetch_activity(db, since_iso=None)[:initial]
            for item in reversed(initial_items):
                yield {
                    "event": "activity",
                    "data": json.dumps(item, default=str),
                }
        except Exception as e:
            logger.debug(f"initial burst failed: {e}")

        last_seen: set[str] = {i.get("id") for i in initial_items if i.get("id")}

        while True:
            try:
                items = _fetch_activity(db, since_iso=None)
                fresh = [i for i in items if i.get("id") and i["id"] not in last_seen]
                for item in reversed(fresh):
                    yield {
                        "event": "activity",
                        "data": json.dumps(item, default=str),
                    }
                    last_seen.add(item["id"])
                # Trim memory — keep last 200 ids only
                if len(last_seen) > 200:
                    last_seen = set(list(last_seen)[-100:])
            except Exception as e:
                logger.debug(f"activity tick failed: {e}")

            # Heartbeat keeps proxies (Vercel, Cloudflare) from killing the
            # connection. EventSourceResponse adds its own pings too.
            yield {"event": "ping", "data": str(int(datetime.now(
                timezone.utc).timestamp()))}
            await asyncio.sleep(_POLL_INTERVAL_S)

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/v1/activity/recent")
def activity_recent(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
):
    """Non-SSE poll endpoint — lightweight alternative for clients that
    can't open SSE (mobile webviews, some embeds). Same shape as the
    stream events; CORS-open."""
    items = _fetch_activity(db, since_iso=None)[:limit]
    return {
        "items": items,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
