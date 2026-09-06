"""L1.2.6 · Polling scheduler — the composition of U1 cadence, U2 jitter and U3 catch-up.

The three units answer three separate questions and are useless apart: HOW OFTEN this source
should be polled, WHEN inside that interval this particular connection's turn falls, and WHETHER
this run has time to make up for. `plan_poll` puts them together into one decision a sweep can
act on, and `select_due` turns a list of connections into the subset whose turn it is.

Deliberately NOT a periodic Celery task. The broker is a quota-limited Upstash Redis, and adding
one beat per source cadence would multiply the request count by the number of sources; a poll
decision is a pure function of `now` and the stored cursor, so the existing in-process sweep can
simply ask, on each tick, which connections are due. That also makes the whole scheduler testable
without a broker, a thread, or a clock.

`now` is a parameter everywhere. Nothing in this module calls a clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Sequence

from genios_engine.capture.acquire.cadence import (
    DEFAULT_CADENCE_POLICY,
    Cadence,
    CadencePolicy,
    CadenceRequest,
    connection_override_seconds,
    resolve_cadence,
)
from genios_engine.capture.acquire.catchup import CatchUpPlan, CatchUpRequest, plan_catch_up
from genios_engine.capture.acquire.cursor_store import Cursor, CursorStore
from genios_engine.capture.acquire.jitter import (BP_FULL, DEFAULT_SPREAD_BP, JitterKey,
                                                  JitterOffset, jitter_offset)
from genios_engine.contracts.connection import Connection

#: Pages a healthy incremental run may drain. Matches the sweep's current `max_pages=20`, so a
#: connection that is up to date behaves exactly as it does today and only a catch-up asks for more.
DEFAULT_PAGE_BUDGET = 20


@dataclass(frozen=True)
class ConnectionSchedule:
    """Everything the scheduler needs about one connection, already typed.

    Built by `schedule_for` so that `Connection.config` — untyped tenant JSON — is opened in
    exactly one place and never travels as a dict into the decision units.
    """
    org_id: str
    connection_id: str
    source: str
    override_seconds: int | None = None
    last_success_at: datetime | None = None
    watermark: datetime | None = None


@dataclass(frozen=True)
class PollDecision:
    """Whether to poll this connection now, when its next turn is, and how the answer was reached.

    The whole derivation travels with the answer — cadence origin, jitter offset, catch-up plan —
    because "why did this connection not sync for nine hours" is the question this subsystem is
    always asked, and re-deriving it from logs after the fact is how the last watermark bug went
    unnoticed for nine runs.
    """
    org_id: str
    connection_id: str
    source: str
    due: bool
    next_run_at: datetime
    cadence: Cadence
    jitter: JitterOffset
    catch_up: CatchUpPlan

    @property
    def max_pages(self) -> int:
        """The page budget this run should be given — extended while catching up."""
        return self.catch_up.max_pages

    @property
    def is_catch_up(self) -> bool:
        """Mark the resulting sync run with this, so a recovery is visible as one."""
        return self.catch_up.catch_up


def schedule_for(connection: Connection, cursor: Cursor | None = None) -> ConnectionSchedule:
    """Turn a stored connection plus its cursor into a typed schedule input."""
    return ConnectionSchedule(
        org_id=connection.org_id,
        connection_id=connection.connection_id,
        source=connection.source_type,
        override_seconds=connection_override_seconds(connection),
        last_success_at=cursor.synced_at if cursor is not None else None,
        watermark=cursor.watermark if cursor is not None else None,
    )


def schedules_for(connections: Sequence[Connection],
                  cursor_store: CursorStore | None = None) -> tuple[ConnectionSchedule, ...]:
    """`schedule_for` over a sweep's whole connection list, reading each cursor once.

    A missing or unreadable cursor degrades to "never polled" (poll now) rather than aborting the
    sweep: the failure mode of a cursor read must be an extra poll, which dedup absorbs, and never
    a connection that stops being scheduled.
    """
    out: list[ConnectionSchedule] = []
    for conn in connections:
        cursor = None
        if cursor_store is not None:
            try:
                cursor = cursor_store.get(conn.org_id, conn.connection_id, conn.source_type)
            except Exception:            # noqa: BLE001 — a cursor read must never drop a connection
                cursor = None
        out.append(schedule_for(conn, cursor))
    return tuple(out)


def tick_grace_seconds(interval_seconds: int, *, sweep_tick_seconds: int,
                       spread_bp: int = DEFAULT_SPREAD_BP) -> int:
    """How far BEFORE its jittered turn a connection may be polled by a sweep that ticks every
    `sweep_tick_seconds` — U2's counterweight, and the reason jitter cannot halve a poll rate.

    Jitter spreads a herd INSIDE an interval; it must never make a source poll LESS often than
    its cadence. A sweep whose tick equals the cadence is exactly where it would: the 6-hourly
    heartbeat polls a 6-hour source, the next turn lands at 6h + a positive offset, the tick at
    6h finds it "not due", and the source is polled every TWELVE hours. Half the connections —
    the ones whose digest happened to come out positive — silently poll at half their configured
    rate, and the only symptom is data that is one interval staler than the number in the config.

    The grace is the offset's own width, never more: at most `spread_bp` of the interval, so a
    connection can be pulled forward into the current tick but never into an earlier cadence.
    Capped by the tick, because a sweep that ticks far more often than the cadence has no
    granularity problem to solve and moving its polls early would only spend the provider's
    quota sooner. `sweep_tick_seconds=0` is an on-demand caller with no tick at all — no grace,
    which is the behaviour every existing call site already has.
    """
    if interval_seconds <= 0:
        raise ValueError(f"interval_seconds must be positive, got {interval_seconds}")
    if sweep_tick_seconds < 0:
        raise ValueError(f"sweep_tick_seconds must not be negative, got {sweep_tick_seconds}")
    return min(sweep_tick_seconds, interval_seconds * spread_bp // BP_FULL)


def plan_poll(schedule: ConnectionSchedule, *, now: datetime,
              policy: CadencePolicy = DEFAULT_CADENCE_POLICY,
              base_page_budget: int = DEFAULT_PAGE_BUDGET,
              spread_bp: int = DEFAULT_SPREAD_BP,
              sweep_tick_seconds: int = 0) -> PollDecision:
    """The scheduler's public unit: one connection, one instant, one decision.

    `sweep_tick_seconds` is the cadence of the SWEEP that is asking, and it is a parameter
    because the answer genuinely depends on it: see `tick_grace_seconds`. Zero — the default —
    is an on-demand caller and reproduces the un-graced schedule exactly.
    """
    cadence = resolve_cadence(
        CadenceRequest(schedule.source, schedule.override_seconds), policy=policy)
    jitter = jitter_offset(
        JitterKey(schedule.org_id, schedule.connection_id, schedule.source),
        interval_seconds=cadence.interval_seconds, spread_bp=spread_bp)
    catch_up = plan_catch_up(CatchUpRequest(
        now=now, last_success_at=schedule.last_success_at, watermark=schedule.watermark,
        interval_seconds=cadence.interval_seconds, base_page_budget=base_page_budget))

    if schedule.last_success_at is None:
        # A connection that has never polled is due immediately — jittering the FIRST poll would
        # delay a tenant's very first data by up to 10% of a cadence for no benefit, and the herd
        # this unit guards against is the recurring one, not the connect moment.
        return PollDecision(schedule.org_id, schedule.connection_id, schedule.source,
                            True, now, cadence, jitter, catch_up)

    grace = tick_grace_seconds(cadence.interval_seconds,
                               sweep_tick_seconds=sweep_tick_seconds, spread_bp=spread_bp)
    next_run_at = (schedule.last_success_at
                   + timedelta(seconds=cadence.interval_seconds + jitter.offset_seconds - grace))
    return PollDecision(schedule.org_id, schedule.connection_id, schedule.source,
                        now >= next_run_at, next_run_at, cadence, jitter, catch_up)


def select_due(schedules: Sequence[ConnectionSchedule], *, now: datetime,
               policy: CadencePolicy = DEFAULT_CADENCE_POLICY,
               base_page_budget: int = DEFAULT_PAGE_BUDGET,
               spread_bp: int = DEFAULT_SPREAD_BP,
               sweep_tick_seconds: int = 0) -> tuple[PollDecision, ...]:
    """The connections whose turn it is, oldest-due first.

    Ordering is fairness, not cosmetics: a sweep with a wall-clock budget that runs its list in
    store order starves whatever sorts last, and the connection that has been waiting longest is
    the one closest to needing a catch-up.
    """
    due = [d for d in (plan_poll(s, now=now, policy=policy, base_page_budget=base_page_budget,
                                 spread_bp=spread_bp,
                                 sweep_tick_seconds=sweep_tick_seconds) for s in schedules)
           if d.due]
    return tuple(sorted(due, key=lambda d: (d.next_run_at, d.connection_id)))
