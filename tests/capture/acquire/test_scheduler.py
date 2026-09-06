"""G9 · L1.2.6 Polling Scheduler — the plan's acceptance gate, plus the composition around it.

    pytest tests/capture/acquire/test_scheduler.py -q
    # gmail cadence != notion cadence
    # jitter is deterministic for a given connection_id
    # a 24h gap triggers a catch-up run with catch_up=true

Those three lines are the gate; the rest of this file covers the seams the sweep actually touches
— that a never-polled connection is due immediately rather than waiting out a jittered interval,
that two connections of the same org do not fire on the same second, that a cursor read which
throws leaves the connection scheduled instead of silently dropping it from every future sweep,
and that the last-success timestamp the catch-up decision rests on survives a real Postgres round
trip (an in-memory dict agreeing with itself proves nothing about `sync_cursors.updated_at`).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.cursor_store import Cursor, InMemoryCursorStore
from genios_engine.capture.acquire.scheduler import (
    DEFAULT_PAGE_BUDGET,
    ConnectionSchedule,
    plan_poll,
    schedule_for,
    schedules_for,
    select_due,
)
from genios_engine.contracts.connection import Connection

WAVE = "W9"
GATE = "G9"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
ORG = "org_sched"


def _sched(source="gmail", *, connection_id="con_1", ago_seconds=None, override=None,
           watermark=None) -> ConnectionSchedule:
    return ConnectionSchedule(
        org_id=ORG, connection_id=connection_id, source=source, override_seconds=override,
        last_success_at=None if ago_seconds is None else NOW - timedelta(seconds=ago_seconds),
        watermark=watermark)


@pytest.mark.gate
def test_gate_cadence_differs_by_source_jitter_is_deterministic_and_a_day_gap_catches_up():
    """The three assertions the L1.2.6 acceptance block names, in one place."""
    # 1 — gmail cadence != notion cadence
    gmail = plan_poll(_sched("gmail", ago_seconds=10), now=NOW)
    notion = plan_poll(_sched("notion", ago_seconds=10), now=NOW)
    assert gmail.cadence.interval_seconds != notion.cadence.interval_seconds
    assert (gmail.cadence.interval_seconds, notion.cadence.interval_seconds) == (900, 43200)

    # 2 — jitter is deterministic for a given connection_id: the same schedule replays to the
    #     same instant, and a fresh equal-valued schedule agrees with it.
    again = plan_poll(_sched("gmail", ago_seconds=10), now=NOW + timedelta(minutes=3))
    assert again.next_run_at == gmail.next_run_at
    assert again.jitter == gmail.jitter

    # 3 — a 24h gap triggers a catch-up run with catch_up=true
    stale = plan_poll(_sched("gmail", ago_seconds=24 * 3600,
                             watermark=NOW - timedelta(hours=24)), now=NOW)
    assert stale.is_catch_up is True
    assert stale.due is True
    assert stale.max_pages > DEFAULT_PAGE_BUDGET
    assert stale.catch_up.since == NOW - timedelta(hours=24)      # resume, do not re-ingest


@pytest.mark.parametrize("source,ago_seconds,expected_due", [
    ("gmail", 60, False),            # 1 minute into a 15-minute cadence
    ("gmail", 15 * 60 + 200, True),  # past the interval + the widest possible jitter
    ("notion", 6 * 3600, False),     # 6h into a 12h cadence — not yet
    # 12h cadence + the widest jitter is 13.2h, so 13h is genuinely NOT due yet — the margin in
    # a due-test has to clear the spread, or the row is asserting on the jitter by accident.
    ("notion", 13 * 3600, False),
    ("notion", 14 * 3600, True),
])
def test_due_follows_the_source_cadence(source, ago_seconds, expected_due):
    assert plan_poll(_sched(source, ago_seconds=ago_seconds), now=NOW).due is expected_due


def test_a_never_polled_connection_is_due_immediately_and_unjittered():
    """Jittering the first poll would delay a new tenant's very first data for no benefit — the
    herd this guards against is the recurring boundary, not the connect moment."""
    decision = plan_poll(_sched("gmail"), now=NOW)
    assert (decision.due, decision.next_run_at) == (True, NOW)
    assert decision.catch_up.reason == "first_run"
    assert decision.max_pages == DEFAULT_PAGE_BUDGET


def test_next_run_is_the_interval_plus_that_connections_jitter():
    decision = plan_poll(_sched("gmail", ago_seconds=0), now=NOW)
    assert decision.next_run_at == NOW + timedelta(
        seconds=900 + decision.jitter.offset_seconds)
    assert decision.jitter.offset_seconds != 0        # this key does get spread


def test_connections_of_one_org_do_not_all_fire_on_the_same_second():
    instants = {plan_poll(_sched("gmail", connection_id=f"con_{i}", ago_seconds=0),
                          now=NOW).next_run_at for i in range(50)}
    assert len(instants) > 25, "the org's connections still land on a handful of instants"


def test_per_connection_override_changes_the_schedule():
    decision = plan_poll(_sched("notion", ago_seconds=2 * 3600, override=3600), now=NOW)
    assert decision.cadence.origin == "override"
    assert decision.due is True                       # 12h policy would have said no


def test_select_due_filters_and_orders_oldest_first():
    schedules = [
        _sched("gmail", connection_id="con_fresh", ago_seconds=30),
        _sched("gmail", connection_id="con_late", ago_seconds=6 * 3600),
        _sched("gmail", connection_id="con_latest", ago_seconds=48 * 3600),
        _sched("notion", connection_id="con_notion", ago_seconds=3600),
    ]
    due = select_due(schedules, now=NOW)
    assert [d.connection_id for d in due] == ["con_latest", "con_late"]
    assert due[0].is_catch_up and due[1].is_catch_up


def test_select_due_returns_nothing_when_every_connection_is_fresh():
    assert select_due([_sched("gmail", connection_id=f"con_{i}", ago_seconds=5)
                       for i in range(5)], now=NOW) == ()


def test_schedule_for_reads_the_cursor_and_the_connection_config():
    cursor = Cursor(cursor="tok", watermark=NOW - timedelta(hours=30),
                    synced_at=NOW - timedelta(hours=30))
    conn = Connection(org_id=ORG, connection_id="con_1", source_type="gmail",
                      config={"cadence_minutes": 5})
    schedule = schedule_for(conn, cursor)
    assert schedule == ConnectionSchedule(ORG, "con_1", "gmail", 300,
                                          cursor.synced_at, cursor.watermark)
    assert plan_poll(schedule, now=NOW).is_catch_up is True


def test_schedules_for_survives_a_cursor_store_that_throws():
    """A cursor read failure must cost an extra poll — which dedup absorbs — never a connection
    that quietly stops being scheduled."""
    class _Broken:
        def get(self, *_a, **_kw):
            raise RuntimeError("pooler blip")

    conns = [Connection(org_id=ORG, connection_id="con_1", source_type="gmail")]
    schedules = schedules_for(conns, _Broken())
    assert schedules[0].last_success_at is None
    assert plan_poll(schedules[0], now=NOW).due is True


def test_in_memory_cursor_store_records_when_the_poll_completed():
    """`synced_at` is what tells a late tick from an outage; a store that never sets it makes
    every connection look freshly polled forever."""
    store = InMemoryCursorStore(clock=lambda: NOW - timedelta(hours=24))
    store.save(ORG, "con_1", "gmail", cursor="tok", watermark=NOW - timedelta(hours=24))
    saved = store.get(ORG, "con_1", "gmail")
    assert saved.synced_at == NOW - timedelta(hours=24)
    assert plan_poll(schedule_for(
        Connection(org_id=ORG, connection_id="con_1", source_type="gmail"), saved),
        now=NOW).is_catch_up is True


# ═════════════════════════════════════════════════════════════════════════════════════════════
# REAL POSTGRESQL — the last-success timestamp comes out of `sync_cursors.updated_at`
# ═════════════════════════════════════════════════════════════════════════════════════════════

@pytest.mark.pg
def test_postgres_cursor_round_trips_the_last_success_timestamp(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres scheduler test skipped")
    from sqlalchemy import text

    from genios_engine.capture.acquire.cursor_store import PostgresCursorStore
    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)
    with engine.connect() as c:
        org = c.execute(text("select id from orgs limit 1")).scalar()
    assert org, "scratch org missing — conftest seeds one"
    conn_id = "con_sched_pg"
    store = PostgresCursorStore(live_db_url)
    try:
        store.save(org, conn_id, "gmail", cursor="tok", watermark=NOW - timedelta(hours=24))
        # a poll that completed a day ago: back-date the row the same way an outage would
        with engine.begin() as c:
            c.execute(text("update sync_cursors set updated_at = now() - interval '24 hours' "
                           "where org_id=:o and connection_id=:c and source='gmail'"),
                      {"o": org, "c": conn_id})
        saved = store.get(org, conn_id, "gmail")
        assert saved is not None and saved.synced_at is not None
        now = datetime.now(timezone.utc)
        gap_hours = (now - saved.synced_at).total_seconds() / 3600
        assert 23.9 < gap_hours < 24.1

        decision = plan_poll(schedule_for(
            Connection(org_id=org, connection_id=conn_id, source_type="gmail"), saved), now=now)
        assert decision.due is True and decision.is_catch_up is True
        assert decision.catch_up.since == saved.watermark
    finally:
        with engine.begin() as c:
            c.execute(text("delete from sync_cursors where org_id=:o and connection_id=:c"),
                      {"o": org, "c": conn_id})
