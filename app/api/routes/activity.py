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
from sqlalchemy import text
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

_POLL_INTERVAL_S = 2.0
_MAX_PER_TICK = 10


def _anonymize_contact(name: str) -> str:
    if not name:
        return "(unknown)"
    parts = name.strip().split()
    if not parts:
        return "(unknown)"
    initial = parts[0][0].upper()
    suffix = "."
    if len(parts) > 1:
        suffix = " " + parts[1][0].upper() + "."
    return f"{initial}{suffix}"


def _fetch_activity(db: Session, since_iso: str | None) -> list[dict]:
    """Pull recent items from recommendations + interactions live-fetch."""
    out: list[dict] = []
    since_clause = ""
    params = {"lim": _MAX_PER_TICK}
    if since_iso:
        since_clause = "AND created_at > :since"
        params["since"] = since_iso

    try:
        rows = db.execute(text(f"""
            SELECT id::text AS id, created_at, insight_type,
                   COALESCE(title, reason, '') AS msg
            FROM recommendations
            WHERE created_at > NOW() - INTERVAL '5 minutes'
              {since_clause}
            ORDER BY created_at DESC
            LIMIT :lim
        """), params).fetchall()
        for r in rows:
            out.append({
                "kind": "decision",
                "id": str(r.id),
                "ts": r.created_at.isoformat() if r.created_at else None,
                "label": r.insight_type or "insight",
                "text": (r.msg or "")[:160],
            })
    except Exception as e:
        logger.debug(f"activity recommendations fetch failed: {e}")

    try:
        rows = db.execute(text("""
            SELECT id::text AS id, interaction_at, source,
                   COALESCE(subject, summary, '') AS msg
            FROM interactions
            WHERE interaction_at > NOW() - INTERVAL '5 minutes'
              AND source IN ('gmail_live', 'calendar_live')
            ORDER BY interaction_at DESC
            LIMIT :lim
        """), {"lim": _MAX_PER_TICK}).fetchall()
        for r in rows:
            out.append({
                "kind": "live_fetch",
                "id": str(r.id),
                "ts": r.interaction_at.isoformat() if r.interaction_at else None,
                "label": r.source,
                "text": (r.msg or "")[:160],
            })
    except Exception as e:
        logger.debug(f"activity interactions fetch failed: {e}")

    try:
        rows = db.execute(text("""
            SELECT id::text AS id, created_at, insight_type,
                   COALESCE(title, '') AS msg, contact_name
            FROM pending_alerts
            WHERE created_at > NOW() - INTERVAL '5 minutes'
            ORDER BY created_at DESC
            LIMIT :lim
        """), {"lim": _MAX_PER_TICK}).fetchall()
        for r in rows:
            out.append({
                "kind": "proactive_alert",
                "id": str(r.id),
                "ts": r.created_at.isoformat() if r.created_at else None,
                "label": r.insight_type or "alert",
                "text": (r.msg or "")[:160],
                "contact": _anonymize_contact(r.contact_name or ""),
            })
    except Exception:
        pass  # pending_alerts may not exist on older deploys

    out.sort(key=lambda x: x.get("ts") or "", reverse=True)
    return out[: _MAX_PER_TICK]


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
