"""Realtime fan-out — `realtime_events` (migration 0148) → in-memory SSE subscribers (P3 §2.5).

WRITERS call `publish(conn, …)` inside the transaction that commits what they announce (the
transactional outbox of plan §9.6), then `wake()` after commit so this process delivers at once
instead of on the next poll.

ONE POLLER THREAD PER PROCESS, started lazily by the first subscriber and idle (zero queries) while
nobody is subscribed. Each poll is one statement on the process's pooled engine — the connection is
checked out for that statement only, so an SSE client never holds one (G-17: the session pooler is
8+4). Subscribers live in a dict keyed by (org, seat); events are handed to each subscriber's
asyncio queue with `call_soon_threadsafe`.

SEQUENCE GAPS. `seq` is a bigserial: a transaction that took seq 10 can commit after one that took
11. The poller remembers a gap it has jumped over for `GAP_WAIT_S` and re-reads from below it, so a
late commit is still delivered (once — delivered seqs are remembered above the floor). A gap that
never fills (a rolled-back writer) is forgotten after the wait.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.realtime")

KINDS = frozenset({"moment.new", "moment.updated", "slice.delta", "policy.updated",
                   "device.revoked"})
POLL_INTERVAL_S = 1.0
BATCH = 500
GAP_WAIT_S = 10.0
QUEUE_MAX = 1000
RETENTION_DAYS = 7


# ── writing ───────────────────────────────────────────────────────────────────────────────────
def publish(conn, *, org_id: str, seat_id: str | None, kind: str, payload: dict) -> int:
    """Insert one event in the CALLER's transaction; returns its seq. PostgreSQL only (the SQLite
    test schemas have no outbox) — elsewhere a no-op returning 0."""
    if kind not in KINDS:
        raise ValueError(f"unknown realtime event kind: {kind}")
    if conn.dialect.name != "postgresql":
        return 0
    return int(conn.execute(text(
        "insert into realtime_events (org_id, seat_id, kind, payload) "
        "values (:o, :s, :k, cast(:p as jsonb)) returning seq"),
        {"o": org_id, "s": seat_id, "k": kind,
         "p": json.dumps(payload, separators=(",", ":"), default=str)}).scalar())


_BUMP_SLICES = text(
    "with seats as (select distinct seat_id from devices where org_id = :o "
    " and revoked_at is null), "
    "up as (insert into seat_slice_versions (org_id, seat_id, version, updated_at) "
    " select :o, seat_id, cast(extract(epoch from clock_timestamp()) * 1000 as bigint), now() "
    " from seats on conflict (org_id, seat_id) do update set "
    " version = greatest(seat_slice_versions.version + 1, excluded.version), updated_at = now() "
    " returning seat_id, version) "
    "insert into realtime_events (org_id, seat_id, kind, payload) "
    "select :o, seat_id, 'slice.delta', jsonb_build_object('version', version) from up")


def bump_slice_versions(conn, org_id: str) -> int:
    """Bump the slice version of every seat of `org_id` that holds a live device and announce it
    (`slice.delta`), in the CALLER's transaction — called from `GraphStore.bump_version`, the one
    step every graph write already takes (see reason/moments/slice.py for why this hook). One
    statement; a no-op off PostgreSQL. Returns the seats bumped."""
    if conn.dialect.name != "postgresql":
        return 0
    return conn.execute(_BUMP_SLICES, {"o": org_id}).rowcount or 0


def replay(engine, *, org_id: str, seat_id: str, after_seq: int, limit: int = BATCH) -> list[dict]:
    """The seat's events (and the org-wide ones) after `after_seq`, oldest first. One statement."""
    with engine.connect() as c:
        rows = c.execute(text(
            "select seq, org_id, seat_id, kind, payload from realtime_events "
            "where org_id = :o and seq > :after and (seat_id = :s or seat_id is null) "
            "order by seq limit :n"),
            {"o": org_id, "s": seat_id, "after": int(after_seq), "n": limit}).mappings().all()
    return [_event(r) for r in rows]


def purge_expired(engine, *, now: datetime | None = None, batch: int = 10000,
                  max_batches: int = 20) -> int:
    """Retention: events older than 7 days, in bounded batches (maintenance heartbeat)."""
    now = now or datetime.now(timezone.utc)
    cut = now - timedelta(days=RETENTION_DAYS)
    deleted = 0
    for _ in range(max_batches):
        with engine.begin() as c:
            n = c.execute(text(
                "delete from realtime_events where seq in (select seq from realtime_events "
                "where created_at < :cut order by seq limit :n)"), {"cut": cut, "n": batch}
            ).rowcount or 0
        deleted += n
        if n < batch:
            break
    return deleted


def _event(r) -> dict:
    payload = r["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {"seq": int(r["seq"]), "org_id": r["org_id"], "seat_id": r["seat_id"],
            "kind": r["kind"], "payload": payload or {}}


def sse_format(event: dict) -> str:
    """Plan §18.3: `id:` = seq, `event:` = kind, one-line JSON `data:`."""
    data = json.dumps(event["payload"], separators=(",", ":"), default=str)
    return f"id: {event['seq']}\nevent: {event['kind']}\ndata: {data}\n\n"


# ── subscribers ───────────────────────────────────────────────────────────────────────────────
@dataclass(eq=False)
class Subscriber:
    org_id: str
    seat_id: str
    device_id: str | None                 # None = a signed-in seat (dashboard), not a device
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(QUEUE_MAX))
    overflowed: bool = False

    def wants(self, event: dict) -> bool:
        if event["org_id"] != self.org_id:
            return False
        if event["seat_id"] is not None and event["seat_id"] != self.seat_id:
            return False
        if event["kind"] == "device.revoked":
            dev = (event.get("payload") or {}).get("device_id")
            return self.device_id is None or dev == self.device_id
        return True

    def offer(self, event: dict | None) -> None:
        """Runs on the subscriber's loop. A full queue ends the stream (None) — the client
        reconnects with Last-Event-ID and replays from the database, so nothing is lost."""
        if self.overflowed:
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.overflowed = True
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(None)


class Hub:
    """The process's subscriber map + its one poller thread."""

    def __init__(self, engine_factory=None) -> None:
        self._engine_factory = engine_factory
        self._lock = threading.Lock()
        self._subs: dict[tuple[str, str], set[Subscriber]] = {}
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last: int | None = None
        self._gaps: dict[int, float] = {}      # missing seq → first seen missing (monotonic s)
        self._seen: set[int] = set()           # delivered seqs above the floor
        self._poll_lock = threading.Lock()     # the cursor: poller thread vs prime()

    # subscription ---------------------------------------------------------------------------
    def subscribe(self, *, org_id: str, seat_id: str, device_id: str | None,
                  loop: asyncio.AbstractEventLoop | None = None) -> Subscriber:
        sub = Subscriber(org_id=org_id, seat_id=seat_id, device_id=device_id,
                         loop=loop or asyncio.get_running_loop())
        with self._lock:
            self._subs.setdefault((org_id, seat_id), set()).add(sub)
        self._ensure_thread()
        self._wake.set()
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            group = self._subs.get((sub.org_id, sub.seat_id))
            if group is not None:
                group.discard(sub)
                if not group:
                    del self._subs[(sub.org_id, sub.seat_id)]

    def subscriber_count(self) -> int:
        with self._lock:
            return sum(len(g) for g in self._subs.values())

    # delivery -------------------------------------------------------------------------------
    def dispatch(self, event: dict) -> int:
        with self._lock:
            if event["seat_id"] is None:
                targets = [s for (org, _), g in self._subs.items() if org == event["org_id"]
                           for s in g]
            else:
                targets = list(self._subs.get((event["org_id"], event["seat_id"]), ()))
        n = 0
        for sub in targets:
            if sub.wants(event):
                try:
                    sub.loop.call_soon_threadsafe(sub.offer, event)
                    n += 1
                except RuntimeError:            # the subscriber's loop is gone
                    self.unsubscribe(sub)
        return n

    def ingest(self, rows: list[dict], *, now_s: float | None = None) -> list[dict]:
        """Advance the cursor over one poll's rows (seq-ordered); return the ones to deliver.
        Pure bookkeeping — separated from the SQL so gap handling is unit-testable."""
        now_s = time.monotonic() if now_s is None else now_s
        out: list[dict] = []
        last = self._last or 0
        for ev in rows:
            seq = ev["seq"]
            self._gaps.pop(seq, None)
            if seq in self._seen:
                continue
            if seq > last + 1:
                for missing in range(last + 1, seq):
                    if missing not in self._seen:
                        self._gaps.setdefault(missing, now_s)
            self._seen.add(seq)
            last = max(last, seq)
            out.append(ev)
        self._last = last
        for missing, first in list(self._gaps.items()):
            if now_s - first > GAP_WAIT_S or len(self._gaps) > 10 * BATCH:
                del self._gaps[missing]
        floor = self.floor()
        self._seen = {s for s in self._seen if s > floor}
        return out

    def floor(self) -> int:
        """Read `seq > floor`: below the oldest unfilled gap, else the cursor."""
        last = self._last or 0
        return min(min(self._gaps) - 1, last) if self._gaps else last

    # the poller -----------------------------------------------------------------------------
    def _engine(self):
        if self._engine_factory is not None:
            return self._engine_factory()
        from genios_engine.platform.config import get_settings
        from genios_engine.platform.db import get_engine
        url = get_settings().database_url
        return get_engine(url) if url else None

    def _ensure_thread(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="genios-realtime-poller",
                                            daemon=True)
            self._thread.start()

    def _head(self, c) -> int:
        return int(c.execute(text("select coalesce(max(seq), 0) from realtime_events")
                             ).scalar() or 0)

    def prime(self) -> int:
        """The live cursor, initialised now if the poller has none — a new client without
        Last-Event-ID treats everything after this seq as live (none of it is skipped)."""
        with self._poll_lock:
            if self._last is None:
                engine = self._engine()
                if engine is None:
                    return 0
                with engine.connect() as c:
                    self._last = self._head(c)
            return self._last

    def poll_once(self) -> int:
        engine = self._engine()
        if engine is None:
            return 0
        with self._poll_lock:
            with engine.connect() as c:
                if self._last is None:
                    self._last = self._head(c)
                    return 0
                rows = c.execute(text(
                    "select seq, org_id, seat_id, kind, payload from realtime_events "
                    "where seq > :floor order by seq limit :n"),
                    {"floor": self.floor(), "n": BATCH}).mappings().all()
            events = self.ingest([_event(r) for r in rows])
        delivered = 0
        for ev in events:
            delivered += self.dispatch(ev)
        return delivered

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(POLL_INTERVAL_S)
            self._wake.clear()
            if self._stop.is_set():
                break
            if self.subscriber_count() == 0:
                # Nobody listening: no queries. A later subscriber replays what it missed from
                # the database (Last-Event-ID); the live cursor restarts at the head.
                self._last, self._gaps, self._seen = None, {}, set()
                continue
            try:
                self.poll_once()
            except Exception:                   # noqa: BLE001 — the poller must never die
                _log.exception("realtime poll failed")
                self._stop.wait(POLL_INTERVAL_S)

    def wake(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        t = self._thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=5)
        self._thread = None
        with self._lock:
            subs = [s for g in self._subs.values() for s in g]
        for sub in subs:
            try:
                sub.loop.call_soon_threadsafe(sub.offer, None)
            except RuntimeError:
                pass


_hub = Hub()


def hub() -> Hub:
    return _hub


def wake() -> None:
    """After committing a `publish`, deliver on this process now rather than at the next poll."""
    _hub.wake()


def stop_realtime() -> None:
    _hub.stop()


__all__ = ["BATCH", "Hub", "KINDS", "RETENTION_DAYS", "Subscriber", "hub", "publish",
           "purge_expired", "replay", "sse_format", "stop_realtime", "wake"]
