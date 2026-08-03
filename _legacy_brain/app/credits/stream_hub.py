"""In-process pub/sub for credit-balance changes → SSE push (no client polling).

deduct() / topup() / _activate_plan() (sync code, any thread) call
`hub.publish(org_id)` whenever an org's credit balance changes. The SSE endpoint
(async, main loop) subscribes one queue per browser connection and, on each
signal, re-reads the authoritative DB total and pushes it. Signal-only (carries
no value) so the SSE always sends the fresh, correct number — never a stale or
partial one.

Scope: catches every WEB-process mutation — query deducts, connect-triggered
syncs (FastAPI BackgroundTask), top-ups, plan activation. Cross-process Celery
deducts (the 6h periodic sync) won't fire this hub; the SSE's heartbeat re-read
and the next user action reconcile those.
"""
from __future__ import annotations

import asyncio
import threading
from collections import defaultdict


class CreditStreamHub:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Record the loop the SSE generators run on so sync publishers (which
        run in worker threads) can schedule queue puts onto it thread-safely."""
        self._loop = loop

    def subscribe(self, org_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        with self._lock:
            self._subs[org_id].add(q)
        return q

    def unsubscribe(self, org_id: str, q: asyncio.Queue) -> None:
        with self._lock:
            self._subs.get(org_id, set()).discard(q)
            if org_id in self._subs and not self._subs[org_id]:
                self._subs.pop(org_id, None)

    def publish(self, org_id: str) -> None:
        """Signal that org_id's balance changed. Thread-safe; a no-op when no
        client is listening or the loop hasn't been bound yet."""
        loop = self._loop
        if loop is None or not org_id:
            return
        with self._lock:
            queues = list(self._subs.get(org_id, ()))
        for q in queues:
            try:
                loop.call_soon_threadsafe(_safe_put, q)
            except RuntimeError:
                # Loop not running (shutdown) — drop the signal silently.
                pass


def _safe_put(q: asyncio.Queue) -> None:
    try:
        q.put_nowait(1)
    except asyncio.QueueFull:
        pass


# Module-level singleton — imported by the SSE endpoint and the credit mutators.
hub = CreditStreamHub()
