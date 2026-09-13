"""Realtime — `GET /v1/stream` (SSE; device or seat token) — SCREEN_INTEL_P3_BUILD.md §2.5.

Events: moment.new · moment.updated · slice.delta {"version": N} · policy.updated · device.revoked.
Format per plan §18.3 (`id:` = realtime_events.seq). `Last-Event-ID` (header, or `last_event_id`
query for clients that cannot set it) replays from `realtime_events` (7 days). A heartbeat comment
every 20 s. The stream ends — and the client reconnects with Last-Event-ID — when its access token
expires, after an hour, when its subscriber queue overflows, or right after telling a device that
it was revoked.

No database connection is held per client: auth is one statement, replay a few, and everything
live comes from the process's one poller (`platform/realtime.py`).
"""
from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool

from genios_engine.api.moment_routes import Principal, principal
from genios_engine.platform import devices as D
from genios_engine.platform import realtime

router = APIRouter(tags=["realtime"])

HEARTBEAT_S = 20.0
MAX_STREAM_S = 3600.0
REPLAY_PAGES = 10


def _ends(event: dict, p: Principal) -> bool:
    return (event["kind"] == "device.revoked" and p.device_id is not None
            and (event.get("payload") or {}).get("device_id") == p.device_id)


async def event_stream(p: Principal, *, engine, last_event_id: int | None, hub=None,
                       heartbeat_s: float = HEARTBEAT_S, max_s: float = MAX_STREAM_S,
                       is_disconnected=None):
    """The SSE body for one client. Subscribes BEFORE replaying so nothing committed in between
    is missed; live events at or below what replay already sent are skipped by seq."""
    hub = hub or realtime.hub()
    sub = hub.subscribe(org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id)
    deadline = time.monotonic() + max_s
    if p.expires_at:
        deadline = min(deadline, time.monotonic() + max(0.0, p.expires_at - time.time()))
    try:
        yield "retry: 3000\n\n"
        if last_event_id is None:
            # Live from "now": the poller's cursor, primed if this is the process's first client.
            sent = await run_in_threadpool(hub.prime)
        else:
            sent = int(last_event_id)
            for _ in range(REPLAY_PAGES):
                rows = await run_in_threadpool(realtime.replay, engine, org_id=p.org_id,
                                               seat_id=p.seat_id, after_seq=sent)
                for ev in rows:
                    if sub.wants(ev):
                        yield realtime.sse_format(ev)
                        if _ends(ev, p):
                            return
                if rows:
                    sent = rows[-1]["seq"]
                if len(rows) < realtime.BATCH:
                    break
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            if is_disconnected is not None and await is_disconnected():
                return
            try:
                ev = await asyncio.wait_for(sub.queue.get(), timeout=min(heartbeat_s, remaining))
            except asyncio.TimeoutError:
                yield ": hb\n\n"
                continue
            if ev is None:                      # overflow or shutdown: reconnect and replay
                return
            if ev["seq"] <= sent:
                continue
            sent = ev["seq"]
            yield realtime.sse_format(ev)
            if _ends(ev, p):
                return
    finally:
        hub.unsubscribe(sub)


@router.get("/v1/stream")
async def stream(request: Request):
    dstore, cstore = D.stores()
    p = await run_in_threadpool(principal, request, dstore)
    if isinstance(p, JSONResponse):
        return p
    raw = (request.headers.get("last-event-id")
           or request.query_params.get("last_event_id") or "").strip()
    last = int(raw) if raw.isdigit() else None
    return StreamingResponse(
        event_stream(p, engine=cstore.engine, last_event_id=last,
                     is_disconnected=request.is_disconnected),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"})


__all__ = ["event_stream", "router"]
