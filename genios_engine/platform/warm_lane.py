"""WARM LANE — a new email / upload reaches graph + reasoning + cards within ~2 minutes.

Before this, a pushed email was captured and published by the Composio webhook in real time and
then sat until the 6-hourly sweep ran the chain (provision → L2 `process_pending` → L4 `run_all`
→ `build_cards_for_org`). The lane closes that gap with no broker: the doors `enqueue()` the event
ids they just emitted, a daemon thread wakes (a `threading.Event`, with a ~3 s poll fallback for
rows another instance enqueued), and runs the SAME chain `api/routes._run_l2` runs — one run per
org per burst, however many events the burst held.

THE QUEUE IS A TRIGGER, NOT A DATA QUEUE. The chain pulls what it always pulled; a row in
`l2_work_queue` only says "this org has events newer than the last run's start". That makes
coalescing free — one run drains every queued event of the org — and fixes the rule for when a row
is finished: when a chain run that STARTED after the row was enqueued completes. Whoever ran it —
this worker, the scheduler tick, a user's Sync job — marks it (`run_exclusive`), so no caller can
leave a row behind that another caller already covered, and no row is marked by a run that could
not have seen its events.

SINGLE-FLIGHT for every chain caller (G-25): `run_exclusive` holds an `org_run_leases` row for the
length of the chain, heart-beaten, so two runs for one org never overlap across threads OR
instances. A caller that cannot get the lease waits briefly and then DEFERS: it enqueues an
org-level trigger (event_id '*'), whose `enqueued_at` is after the running holder's start, so the
holder cannot mark it and the lane runs the org again once the holder is done. Nothing is lost.

Postgres only, multi-instance safe: FOR UPDATE SKIP LOCKED claims plus lease rows. No advisory
locks (a session pooler hands them to the wrong session), no LISTEN/NOTIFY (the pooler drops it).
No engine of its own — every statement rides the process's one pooled engine — and the GLOBAL
concurrency is `warm_lane_workers` slot leases, default 1.
"""

from __future__ import annotations

import os
import random
import socket
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.warm_lane")

ORG_TRIGGER = "*"              # event_id of an org-level trigger (a deferred chain caller)
LEASE_SECONDS = 120            # org lease + slot lease + row claim; heart-beaten while running
HEARTBEAT_SECONDS = 30
POLL_SECONDS = float(os.environ.get("GENIOS_WARM_LANE_POLL", "3"))
MAX_ATTEMPTS = 5               # failed chain runs before a row is parked for a human
BACKOFF_BASE_SECONDS = 10.0
BACKOFF_CAP_SECONDS = 600.0
BUSY_RETRY_SECONDS = 5.0       # org lease held elsewhere: look again shortly, costs no attempt
CLAIM_SCAN = 500               # oldest open rows looked at per claim, before grouping
MAX_ROWS_PER_RUN = 5000        # the chain drains at most process_pending's default 5000 anyway
STALE_WARN_SECONDS = 300       # oldest pending row older than this → a warning per minute
RETENTION_DAYS = 7             # finished rows kept this long, then pruned by the worker
CHAIN_WAIT_SECONDS = 30.0      # `_run_l2` callers: wait this long for a busy org, then defer
SYNC_JOB_WAIT_SECONDS = 900.0  # a user's Sync job waits longer — its progress bar is watching

_WORKER_BASE = f"{socket.gethostname()}:{os.getpid()}"
_wake = threading.Event()
_stop = threading.Event()
_threads: list[threading.Thread] = []
_held = threading.local()      # org ids this thread holds the lease for → reentrancy
_housekeeping = {"stale_check": 0.0, "prune": 0.0}


# ── pure policy (hermetic-testable) ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class QueueRow:
    id: int
    org_id: str
    event_id: str
    source: str
    enqueued_at: datetime
    attempts: int = 0


@dataclass
class OrgBatch:
    org_id: str
    rows: list[QueueRow] = field(default_factory=list)

    @property
    def ids(self) -> list[int]:
        return [r.id for r in self.rows]

    @property
    def event_ids(self) -> list[str]:
        return sorted({r.event_id for r in self.rows if r.event_id != ORG_TRIGGER})

    @property
    def oldest(self) -> datetime:
        return min(r.enqueued_at for r in self.rows)


def group_by_org(rows: Iterable[QueueRow]) -> list[OrgBatch]:
    """Rows → one batch per org, the org whose oldest row has waited longest first."""
    batches: dict[str, OrgBatch] = {}
    for row in rows:
        batches.setdefault(row.org_id, OrgBatch(row.org_id)).rows.append(row)
    return sorted(batches.values(), key=lambda b: (b.oldest, b.org_id))


def backoff_seconds(attempts: int) -> float:
    """Delay before retrying a row whose chain run failed on its `attempts`-th try."""
    return min(BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * (2 ** max(0, attempts - 1)))


def plan_failure(rows: Iterable[QueueRow]) -> tuple[list[int], dict[float, list[int]]]:
    """A failed run → (row ids to park, {retry delay: row ids}). Attempts were counted at claim."""
    park: list[int] = []
    retry: dict[float, list[int]] = {}
    for row in rows:
        if row.attempts >= MAX_ATTEMPTS:
            park.append(row.id)
        else:
            retry.setdefault(backoff_seconds(row.attempts), []).append(row.id)
    return park, retry


# ── enqueue + wake ──────────────────────────────────────────────────────────────────────────────

def wake() -> None:
    """Start this process's worker now instead of at its next poll."""
    _wake.set()


def enqueue(engine, org_id: str, event_ids: Iterable[str], source: str) -> int:
    """Queue `event_ids` of `org_id` for the lane and wake the worker. Returns rows written.

    Idempotent per open row: an event already pending is left as it is (its events are the same
    events). The ORG trigger is the exception — its `enqueued_at` moves forward, because a second
    deferral means "a run must START after now", which the pending one no longer promises if a
    run began since it was written. Never raises: the doors call this after their own work has
    committed, and a trigger that failed to queue is picked up by the next sweep tick anyway."""
    ids = sorted({str(e) for e in event_ids if e})
    if engine is None or not ids:
        return 0
    try:
        with engine.begin() as c:
            written = c.execute(text(
                "insert into l2_work_queue (org_id, event_id, source) "
                "select :o, e, :s from unnest(cast(:ids as text[])) as e "
                "on conflict (org_id, event_id) where done_at is null and parked_at is null "
                "do update set enqueued_at = now(), source = excluded.source "
                "where l2_work_queue.event_id = :trigger"),
                {"o": org_id, "s": source[:80], "ids": ids, "trigger": ORG_TRIGGER}).rowcount
    except Exception:      # noqa: BLE001 — a door must never fail because its trigger did
        _log.exception("warm lane enqueue failed org=%s source=%s events=%d", org_id, source,
                       len(ids))
        return 0
    wake()
    return int(written or 0)


def wait_until_done(engine, org_id: str, event_ids: Iterable[str], *, timeout_s: float,
                    poll_s: float = 2.0) -> bool:
    """Block until no open (unfinished, unparked) queue row remains for these events. True when
    they are all finished or parked, False on timeout. For a caller that must act on the chain's
    result — the upload door's fact/entity count."""
    ids = sorted({str(e) for e in event_ids if e})
    if not ids:
        return True
    wake()
    deadline = time.monotonic() + timeout_s
    while True:
        with engine.connect() as c:
            open_rows = c.execute(text(
                "select count(*) from l2_work_queue where org_id = :o "
                "and event_id = any(cast(:ids as text[])) and done_at is null and parked_at is null"),
                {"o": org_id, "ids": ids}).scalar()
        if not open_rows:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)


# ── leases ──────────────────────────────────────────────────────────────────────────────────────

def _acquire_org(engine, org_id: str, holder: str) -> datetime | None:
    """Take the org lease if it is free, expired, or already ours. Returns the database's instant
    of acquisition — the run's START, against which queued rows are judged — or None if busy."""
    with engine.begin() as c:
        row = c.execute(text(
            "insert into org_run_leases as l (org_id, holder, lease_until, heartbeat_at, acquired_at) "
            "values (:o, :h, now() + make_interval(secs => :ttl), now(), now()) "
            "on conflict (org_id) do update set holder = excluded.holder, "
            "lease_until = excluded.lease_until, heartbeat_at = excluded.heartbeat_at, "
            "acquired_at = excluded.acquired_at "
            "where l.lease_until < now() or l.holder = excluded.holder "
            "returning now() as started_at"),
            {"o": org_id, "h": holder, "ttl": LEASE_SECONDS}).first()
    return row.started_at if row is not None else None


def _beat_org(engine, org_id: str, holder: str) -> bool:
    with engine.begin() as c:
        return bool(c.execute(text(
            "update org_run_leases set lease_until = now() + make_interval(secs => :ttl), "
            "heartbeat_at = now() where org_id = :o and holder = :h"),
            {"o": org_id, "h": holder, "ttl": LEASE_SECONDS}).rowcount)


def _release_org(engine, org_id: str, holder: str) -> None:
    with engine.begin() as c:
        c.execute(text("delete from org_run_leases where org_id = :o and holder = :h"),
                  {"o": org_id, "h": holder})


def _mark_done(engine, org_id: str, started_at: datetime, holder: str) -> int:
    """Finish every open row of the org enqueued no later than the run's start."""
    with engine.begin() as c:
        return int(c.execute(text(
            "update l2_work_queue set done_at = now(), claimed_by = coalesce(claimed_by, :h), "
            "lease_until = null, last_error = null "
            "where org_id = :o and done_at is null and parked_at is null "
            "and enqueued_at <= :started"),
            {"o": org_id, "started": started_at, "h": holder[:120]}).rowcount or 0)


def _acquire_slot(engine, holder: str, slots: int) -> int | None:
    order = list(range(max(1, slots)))
    random.shuffle(order)
    for slot in order:
        with engine.begin() as c:
            row = c.execute(text(
                "insert into warm_lane_slots as s (slot, holder, lease_until, heartbeat_at) "
                "values (:n, :h, now() + make_interval(secs => :ttl), now()) "
                "on conflict (slot) do update set holder = excluded.holder, "
                "lease_until = excluded.lease_until, heartbeat_at = excluded.heartbeat_at "
                "where s.lease_until < now() or s.holder = excluded.holder returning slot"),
                {"n": slot, "h": holder, "ttl": LEASE_SECONDS}).first()
        if row is not None:
            return int(row.slot)
    return None


def _beat_slot(engine, slot: int, holder: str) -> bool:
    with engine.begin() as c:
        return bool(c.execute(text(
            "update warm_lane_slots set lease_until = now() + make_interval(secs => :ttl), "
            "heartbeat_at = now() where slot = :n and holder = :h"),
            {"n": slot, "h": holder, "ttl": LEASE_SECONDS}).rowcount)


def _release_slot(engine, slot: int, holder: str) -> None:
    with engine.begin() as c:
        c.execute(text("delete from warm_lane_slots where slot = :n and holder = :h"),
                  {"n": slot, "h": holder})


class _Heartbeat:
    """Extends a set of leases every HEARTBEAT_SECONDS until stopped. A beat that finds its lease
    gone (it expired and was taken) is logged loudly: the run keeps going — stopping a chain half
    way is worse than finishing it — but the overlap is on the record."""

    def __init__(self, name: str, beats: list[Callable[[], bool]] | None = None) -> None:
        self.beats = list(beats or [])
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name=name)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(HEARTBEAT_SECONDS):
            for beat in list(self.beats):
                try:
                    if beat() is False:
                        _log.error("warm lane lease LOST while running (%s) — it expired and was "
                                   "taken; a second run may overlap this one", self._thread.name)
                except Exception:      # noqa: BLE001 — a missed beat is not fatal
                    _log.warning("warm lane heartbeat failed (%s)", self._thread.name,
                                 exc_info=True)

    def stop(self) -> None:
        self._stop.set()


# ── single-flight run ───────────────────────────────────────────────────────────────────────────

@dataclass
class RunOutcome:
    status: str                       # ok | failed | busy
    started_at: datetime | None = None
    run_ms: int = 0
    marked_done: int = 0
    locked: bool = True               # False: the lease table was unreachable, ran unguarded

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def _held_orgs() -> set[str]:
    held = getattr(_held, "orgs", None)
    if held is None:
        held = _held.orgs = set()
    return held


def run_exclusive(engine, org_id: str, fn: Callable[[], Any], *, caller: str,
                  wait_s: float = 0.0, defer: bool = True,
                  on_wait: Callable[[], Any] | None = None) -> RunOutcome:
    """Run `fn` (one chain run for `org_id`) while holding the org's lease.

    `fn` returning False means the chain failed (it logged why); anything else is success. An
    exception propagates after the lease is released — a caller that re-raises today still does.
    On success every queued row of the org enqueued before the run started is marked done.

    Busy: poll for up to `wait_s` (calling `on_wait` every ~15 s so a watched job stays alive),
    then, if `defer`, queue an org trigger so the lane runs the org after the holder is done.

    Reentrant per thread. Fails OPEN if the lease table cannot be read at all (no database, a
    stub engine in a unit test): the chain runs unguarded, exactly as it did before this lane,
    and says so — the same "never let the guard block a sync" rule `_sync_active` follows."""
    if org_id in _held_orgs():
        t0 = time.perf_counter()
        result = fn()
        return RunOutcome("failed" if result is False else "ok",
                          run_ms=round((time.perf_counter() - t0) * 1000))
    holder = f"{_WORKER_BASE}:{caller}:{uuid.uuid4().hex[:8]}"[:120]
    deadline = time.monotonic() + max(0.0, wait_s)
    last_wait_beat = time.monotonic()
    while True:
        try:
            started_at = _acquire_org(engine, org_id, holder)
        except Exception as exc:      # noqa: BLE001 — see "fails OPEN" above
            _log.warning("org run lease unavailable (%s: %s) — running %s for org=%s unguarded",
                         type(exc).__name__, str(exc)[:160], caller, org_id)
            t0 = time.perf_counter()
            result = fn()
            return RunOutcome("failed" if result is False else "ok", locked=False,
                              run_ms=round((time.perf_counter() - t0) * 1000))
        if started_at is not None:
            break
        if time.monotonic() >= deadline:
            if defer:
                enqueue(engine, org_id, [ORG_TRIGGER], source=f"deferred:{caller}")
            _log.info("chain for org=%s is running elsewhere; %s %s", org_id, caller,
                      "deferred to the warm lane" if defer else "backed off")
            return RunOutcome("busy")
        if on_wait is not None and time.monotonic() - last_wait_beat >= 15:
            last_wait_beat = time.monotonic()
            try:
                on_wait()
            except Exception:      # noqa: BLE001
                pass
        time.sleep(min(1.0 + random.random() * 0.5, max(0.05, deadline - time.monotonic())))

    _held_orgs().add(org_id)
    beat = _Heartbeat(f"org-lease-{org_id}"[:60], [lambda: _beat_org(engine, org_id, holder)])
    t0 = time.perf_counter()
    outcome = RunOutcome("failed", started_at=started_at)
    try:
        result = fn()
        outcome.status = "failed" if result is False else "ok"
    finally:
        outcome.run_ms = round((time.perf_counter() - t0) * 1000)
        beat.stop()
        _held_orgs().discard(org_id)
        if outcome.ok:
            try:
                outcome.marked_done = _mark_done(engine, org_id, started_at, holder)
            except Exception:      # noqa: BLE001 — unmarked rows only cost one redundant run
                _log.exception("warm lane could not mark rows done org=%s", org_id)
        try:
            _release_org(engine, org_id, holder)
        except Exception:      # noqa: BLE001 — an unreleased lease expires on its own
            _log.warning("org run lease release failed org=%s (expires in %ss)", org_id,
                         LEASE_SECONDS, exc_info=True)
    return outcome


# ── the worker ──────────────────────────────────────────────────────────────────────────────────

_OPEN = "done_at is null and parked_at is null"
_CLAIMABLE = f"{_OPEN} and (lease_until is null or lease_until < now())"


def _row(r) -> QueueRow:
    return QueueRow(id=int(r.id), org_id=r.org_id, event_id=r.event_id, source=r.source,
                    enqueued_at=r.enqueued_at, attempts=int(r.attempts or 0))


def has_claimable(engine) -> bool:
    with engine.connect() as c:
        return c.execute(text(f"select 1 from l2_work_queue where {_CLAIMABLE} limit 1")).first() \
            is not None


def claim_batch(engine, worker_id: str) -> tuple[OrgBatch, datetime] | None:
    """Claim every claimable row of the org that has waited longest, in one transaction.

    SKIP LOCKED on both reads, so two workers never claim one row; each claimed row gets a
    lease (`lease_until`), which is also how a crashed worker's rows come back — the lease runs
    out and the row is claimable again. Attempts are counted HERE, so a run that kills its
    process still counts towards the park."""
    with engine.begin() as c:
        scan = [_row(r) for r in c.execute(text(
            "select id, org_id, event_id, source, enqueued_at, attempts from l2_work_queue "
            f"where {_CLAIMABLE} order by enqueued_at, id limit :n for update skip locked"),
            {"n": CLAIM_SCAN})]
        batches = group_by_org(scan)
        if not batches:
            return None
        first = batches[0]
        more = c.execute(text(
            "select id from l2_work_queue where org_id = :o and " + _CLAIMABLE +
            " and not (id = any(cast(:ids as bigint[]))) order by enqueued_at, id "
            "limit :n for update skip locked"),
            {"o": first.org_id, "ids": first.ids,
             "n": max(0, MAX_ROWS_PER_RUN - len(first.ids))}).scalars().all()
        rows = c.execute(text(
            "update l2_work_queue set claimed_by = :w, attempts = attempts + 1, "
            "lease_until = now() + make_interval(secs => :ttl) "
            "where id = any(cast(:ids as bigint[])) "
            "returning id, org_id, event_id, source, enqueued_at, attempts, now() as claimed_at"),
            {"w": worker_id[:120], "ttl": LEASE_SECONDS,
             "ids": first.ids + [int(i) for i in more]}).fetchall()
    if not rows:
        return None
    return OrgBatch(first.org_id, sorted((_row(r) for r in rows), key=lambda r: r.id)), \
        rows[0].claimed_at


def _beat_rows(engine, worker_id: str, ids: list[int]) -> bool:
    with engine.begin() as c:
        c.execute(text(
            "update l2_work_queue set lease_until = now() + make_interval(secs => :ttl) "
            "where id = any(cast(:ids as bigint[])) and claimed_by = :w and " + _OPEN),
            {"ids": ids, "w": worker_id[:120], "ttl": LEASE_SECONDS})
    return True


def settle(engine, batch: OrgBatch, outcome: RunOutcome, worker_id: str,
           claimed_at: datetime, error: str | None = None) -> None:
    """Put the claimed rows where the run's outcome says they belong."""
    ids = batch.ids
    with engine.begin() as c:
        if outcome.status == "ok":
            # `run_exclusive` already finished every row enqueued before the run started. What is
            # left of the claim is either a row an unguarded run could not mark (finish it: it was
            # enqueued before the claim, so before the run), or an org trigger re-armed during
            # the run (release it, without charging an attempt, for the next run).
            c.execute(text(
                "update l2_work_queue set done_at = now(), lease_until = null, last_error = null "
                "where id = any(cast(:ids as bigint[])) and " + _OPEN +
                " and enqueued_at <= :cut"),
                {"ids": ids, "cut": outcome.started_at or claimed_at})
            c.execute(text(
                "update l2_work_queue set claimed_by = null, lease_until = null, "
                "attempts = greatest(attempts - 1, 0) "
                "where id = any(cast(:ids as bigint[])) and " + _OPEN), {"ids": ids})
            return
        if outcome.status == "busy":
            c.execute(text(
                "update l2_work_queue set claimed_by = null, attempts = greatest(attempts - 1, 0), "
                "lease_until = now() + make_interval(secs => :d) "
                "where id = any(cast(:ids as bigint[])) and " + _OPEN),
                {"ids": ids, "d": BUSY_RETRY_SECONDS})
            return
        park, retry = plan_failure(batch.rows)
        err = (error or "chain run failed")[:500]
        for delay, group in retry.items():
            c.execute(text(
                "update l2_work_queue set claimed_by = null, last_error = :e, "
                "lease_until = now() + make_interval(secs => :d) "
                "where id = any(cast(:ids as bigint[])) and " + _OPEN),
                {"ids": group, "d": delay, "e": err})
        if park:
            c.execute(text(
                "update l2_work_queue set claimed_by = null, lease_until = null, "
                "parked_at = now(), last_error = :e "
                "where id = any(cast(:ids as bigint[])) and " + _OPEN),
                {"ids": park, "e": err})
    if park:
        _log.error("warm lane PARKED %d row(s) for org=%s after %d failed runs: %s",
                   len(park), batch.org_id, MAX_ATTEMPTS, err)
        from genios_engine.platform import ops_alert
        ops_alert.notify("warm_lane_parked", org_id=batch.org_id, rows=len(park), error=err)


def _default_run_chain(org_id: str) -> RunOutcome:
    # lazy import — routes.py wires the stores at import time; importing here avoids a cycle.
    # Looked up per call (not bound once) so the chain is always the one `_run_l2` runs today.
    from genios_engine.api import routes
    out = routes._run_l2(org_id, lease_wait_s=0.0, defer=False)
    return out if isinstance(out, RunOutcome) else RunOutcome("failed")


def run_once(engine, worker_id: str, *, run_chain: Callable[[str], RunOutcome] | None = None,
             slots: int | None = None) -> bool:
    """One claim → one coalesced chain run → settle. True if a run was attempted (the loop then
    looks again at once), False when there was nothing this worker could take."""
    if not has_claimable(engine):
        return False
    run_chain = run_chain or _default_run_chain
    slots = int(slots if slots is not None else max(1, get_settings().warm_lane_workers))
    slot = _acquire_slot(engine, worker_id, slots)
    if slot is None:
        return False                                   # the lane's global concurrency is in use
    beat = _Heartbeat(f"warm-slot-{slot}", [lambda: _beat_slot(engine, slot, worker_id)])
    try:
        claimed = claim_batch(engine, worker_id)
        if claimed is None:
            return False
        batch, claimed_at = claimed
        beat.beats.append(lambda: _beat_rows(engine, worker_id, batch.ids))
        wait_ms = max(0, round((claimed_at - batch.oldest).total_seconds() * 1000))
        from genios_engine.platform.stage_timer import stage
        error = None
        with stage("warm.run", batch.org_id, events=len(batch.event_ids),
                   rows=len(batch.ids), wait_ms=wait_ms) as st:
            try:
                outcome = run_chain(batch.org_id)
            except Exception as exc:      # noqa: BLE001 — a crashed run is a failed run
                _log.exception("warm lane chain crashed org=%s", batch.org_id)
                outcome, error = RunOutcome("failed"), f"{type(exc).__name__}: {exc}"
            st["status"] = outcome.status
        settle(engine, batch, outcome, worker_id, claimed_at, error=error)
        _log.info("warm lane run org=%s status=%s events_coalesced=%d rows=%d queue_wait_ms=%d "
                  "run_ms=%d marked_done=%d", batch.org_id, outcome.status, len(batch.event_ids),
                  len(batch.ids), wait_ms, st["ms"], outcome.marked_done)
        return outcome.status != "busy"
    finally:
        beat.stop()
        try:
            _release_slot(engine, slot, worker_id)
        except Exception:      # noqa: BLE001 — expires on its own
            _log.warning("warm lane slot release failed (expires in %ss)", LEASE_SECONDS)


def housekeep(engine, *, now: float | None = None) -> None:
    """Once a minute: warn when the backlog's oldest row is older than 5 minutes. Once an hour:
    prune finished rows past retention and long-dead leases. Cheap, in-process, no scheduler."""
    now = time.monotonic() if now is None else now
    if now - _housekeeping["stale_check"] >= 60:
        _housekeeping["stale_check"] = now
        with engine.connect() as c:
            row = c.execute(text(
                "select count(*) as n, extract(epoch from now() - min(enqueued_at)) as age "
                f"from l2_work_queue where {_OPEN}")).first()
        if row is not None and row.age is not None and float(row.age) > STALE_WARN_SECONDS:
            _log.warning("warm lane backlog: oldest pending row is %ds old (%d open row(s)) — "
                         "the lane is behind or stuck", int(row.age), int(row.n))
    if now - _housekeeping["prune"] >= 3600:
        _housekeeping["prune"] = now
        with engine.begin() as c:
            c.execute(text(
                "delete from l2_work_queue where id in (select id from l2_work_queue "
                "where done_at < now() - make_interval(days => :d) limit 5000)"),
                {"d": RETENTION_DAYS})
            c.execute(text("delete from org_run_leases where lease_until < now() - interval '1 hour'"))
            c.execute(text("delete from warm_lane_slots where lease_until < now() - interval '1 hour'"))


def _resolve_engine():
    from genios_engine.api import routes      # lazy: see `_default_run_chain`
    return routes._graph.engine if routes._graph is not None else None


def _loop(worker_id: str, initial_delay: float) -> None:
    if _stop.wait(initial_delay):
        return
    while not _stop.is_set():
        ran = False
        try:
            engine = _resolve_engine()
            if engine is None:
                _log.info("warm lane: no graph store — worker exiting")
                return
            _wake.clear()                  # BEFORE the claim: a wake set after it is not lost
            ran = run_once(engine, worker_id)
            housekeep(engine)
        except Exception:                  # noqa: BLE001 — a crash must never kill the loop
            _log.exception("warm lane tick crashed")
        if not ran:
            _wake.wait(POLL_SECONDS)


def worker_alive() -> bool:
    return any(t.is_alive() for t in _threads)


def start_warm_lane(initial_delay: float | None = None) -> bool:
    """Start the worker thread(s). Idempotent. main.py gates the call on use_real_db."""
    s = get_settings()
    if not s.warm_lane_enabled:
        _log.info("warm lane disabled (GENIOS_WARM_LANE_ENABLED=false) — new events wait for the "
                  "sweep tick")
        return False
    if worker_alive():
        return True
    _stop.clear()
    _threads.clear()
    delay = 5.0 if initial_delay is None else float(initial_delay)
    for n in range(max(1, int(s.warm_lane_workers))):
        worker_id = f"{_WORKER_BASE}:warm{n}"
        thread = threading.Thread(target=_loop, args=(worker_id, delay), daemon=True,
                                  name=f"genios-warm-lane-{n}")
        thread.start()
        _threads.append(thread)
    _log.info("warm lane started (workers=%d, poll=%ss, lease=%ss)", len(_threads), POLL_SECONDS,
              LEASE_SECONDS)
    return True


def stop_warm_lane(timeout: float = 5.0) -> None:
    _stop.set()
    _wake.set()                            # release a sleeping poll at once
    for thread in list(_threads):
        thread.join(timeout)
    _threads.clear()
