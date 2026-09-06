"""W9 defect #8 — the polling scheduler has a PRODUCTION CALLER.

`tests/capture/acquire/test_scheduler.py` proves the three units are correct: gmail and notion
get different cadences, jitter is deterministic, a day-long gap becomes a catch-up. Every one of
those assertions passed while nothing in `genios_engine/` called `plan_poll`, so a Notion page
was still re-listed every six hours and an outage was still silently skipped. Correct units with
no caller do nothing — the same shape of defect as the semantic lane that eleven modules deep had
no call site.

So this file asserts the WIRING, never the arithmetic, and it drives it from the outside:

* `platform/scheduler._tick` — the function the daemon thread actually runs — marks its thread,
  which is what makes the gate bind the sweep and not a person pressing "Sync now";
* `run_sync` — the one function every polling path in the product goes through — consults the
  decision, refuses to touch the connector when the turn has not come, and raises its own page
  budget when the connection is behind.

The connector counts its calls, so "not polled" is proved by the provider never being reached
rather than by a flag the same code set.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
from genios_engine.capture.acquire.scheduler import (
    DEFAULT_PAGE_BUDGET,
    ConnectionSchedule,
    plan_poll,
    tick_grace_seconds,
)
from genios_engine.capture.acquire.sync_runner import (
    in_scheduled_sweep,
    run_sync,
    scheduled_sweep,
    sweep_cadence_policy,
    sweep_tick_seconds,
)
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

WAVE = "W9"
GATE = "G9"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
ORG = "org_poll"
CONN = "con_poll"
OWNER = "founder@genios.ai"


class _CountingMailbox:
    """A connector that records every page it was asked for and reaches no network.

    The count is the whole point: a scheduler that decided "not due" and then fetched anyway
    would satisfy any assertion made against its own return value.
    """

    def __init__(self, source: str = "gmail", *, pages: int = 1, per_page: int = 2) -> None:
        self.source = source
        self.fetches: list[str | None] = []
        self._pages = pages
        self._per_page = per_page

    def validate_connection(self) -> bool:
        return True

    def _batch(self, cursor: str | None) -> SourceBatch:
        self.fetches.append(cursor)
        page = len(self.fetches)
        objects = [
            RawObject(source=self.source, object_type="email_message",
                      source_object_id=f"{self.source}_p{page}_m{i}",
                      occurred_at=NOW - timedelta(minutes=page),
                      actor_email="buyer@acme.com", recipients=(OWNER,),
                      raw={"subject": f"Page {page} message {i}",
                           "body": "We can move forward with the annual contract."})
            for i in range(self._per_page)]
        nxt = f"cur_{page}" if page < self._pages else None
        return SourceBatch(objects=objects, next_cursor=nxt)

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return self._batch(cursor)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return self._batch(cursor)

    def fetch_content(self, object_ref: str) -> dict:
        return {}


def _poll(connector, cursors, *, source="gmail", now=NOW, **kw):
    """One scheduled poll through the real entry point, on a thread marked as the sweep's."""
    with scheduled_sweep():
        return run_sync(connector, org_id=ORG, connection_id=CONN,
                        repo=InMemorySourceEventRepository(), cursor_store=cursors,
                        source=source, mailbox_owner=OWNER, _now=lambda: now, **kw)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# The production caller
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_scheduler_tick_runs_inside_the_marked_scope(monkeypatch):
    """`platform/scheduler._tick` is what the daemon thread executes. If it does not mark its
    thread, every sweep is ungated and the three cadence units are decoration."""
    from genios_engine.api import routes
    from genios_engine.platform import scheduler as S

    seen: list[bool] = []
    monkeypatch.setattr(routes, "run_maintenance_sweep",
                        lambda *a, **kw: seen.append(in_scheduled_sweep()) or {"ok": True})
    assert S._tick() == {"ok": True}
    assert seen == [True], "the scheduler's tick did not mark itself as a scheduled poll"
    assert in_scheduled_sweep() is False, "the mark leaked past the tick"


def test_the_bounded_sweep_still_marks_the_worker_thread(monkeypatch):
    """The tick runs on a watchdog worker, not on the loop thread — a mark set on the wrong one
    would be invisible to `run_sync` and the gate would silently never bind."""
    from genios_engine.api import routes
    from genios_engine.platform import scheduler as S

    seen: list[bool] = []
    monkeypatch.setattr(routes, "run_maintenance_sweep",
                        lambda *a, **kw: seen.append(in_scheduled_sweep()) or {"ok": True})
    assert S._run_sweep_bounded() == {"ok": True}
    assert seen == [True]


# ═════════════════════════════════════════════════════════════════════════════════════════════
# A source that is not due is NOT POLLED
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_source_polled_a_moment_ago_is_not_polled_again():
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(minutes=1))
    cursors.save(ORG, CONN, "gmail", cursor=None, watermark=NOW - timedelta(minutes=1))
    connector = _CountingMailbox()

    second = _poll(connector, cursors)

    assert connector.fetches == [], "the provider was called for a connection that was not due"
    assert second.scanned == 0 and second.emitted == 0
    assert second.skipped_not_due is True
    assert second.poll is not None and second.poll.cadence.interval_seconds == 900


def test_the_first_poll_of_a_new_connection_is_never_deferred():
    """A connection with no cursor has never been polled; jittering its first run would hold a
    new tenant's data hostage for no benefit."""
    connector = _CountingMailbox()
    summary = _poll(connector, InMemoryCursorStore())

    assert connector.fetches == [None]
    assert summary.emitted == 2
    assert summary.poll is not None and summary.poll.due is True
    assert summary.poll.catch_up.reason == "first_run"


@pytest.mark.parametrize("source,minutes_ago,expect_polled", [
    ("gmail", 5, False),        # 5 minutes into a 15-minute cadence
    ("gmail", 30, True),        # past it
    ("notion", 30, False),      # 30 minutes into a 12-hour cadence
    ("notion", 60 * 13, True),  # past it, jitter and grace included
])
def test_the_gate_follows_the_source_cadence(source, minutes_ago, expect_polled):
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(minutes=minutes_ago))
    cursors.save(ORG, CONN, source, cursor=None, watermark=NOW - timedelta(minutes=minutes_ago))
    connector = _CountingMailbox(source)

    summary = _poll(connector, cursors, source=source)

    assert bool(connector.fetches) is expect_polled
    assert summary.poll is not None and summary.poll.due is expect_polled


def test_a_manual_run_is_never_gated():
    """Pressing "Sync now" two minutes after a sweep must still reach the provider. The gate
    binds a rhythm; it must not bind an instruction."""
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(minutes=1))
    cursors.save(ORG, CONN, "gmail", cursor=None, watermark=NOW - timedelta(minutes=1))
    connector = _CountingMailbox()

    summary = run_sync(connector, org_id=ORG, connection_id=CONN,
                       repo=InMemorySourceEventRepository(), cursor_store=cursors,
                       source="gmail", mailbox_owner=OWNER, _now=lambda: NOW)

    assert connector.fetches == [None], "a manual sync was silently swallowed by the cadence gate"
    assert summary.poll is None and summary.skipped_not_due is False


def test_an_external_cron_can_opt_into_the_cadence_without_the_thread_mark():
    """/ingest/all is a sweep driven from outside the process; it gets the same rhythm by
    saying so, which is why the switch is a parameter and not only a thread."""
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(minutes=1))
    cursors.save(ORG, CONN, "gmail", cursor=None, watermark=NOW - timedelta(minutes=1))
    connector = _CountingMailbox()

    summary = run_sync(connector, org_id=ORG, connection_id=CONN,
                       repo=InMemorySourceEventRepository(), cursor_store=cursors,
                       source="gmail", mailbox_owner=OWNER, _now=lambda: NOW,
                       respect_cadence=True)

    assert connector.fetches == []
    assert summary.skipped_not_due is True


@pytest.mark.parametrize("mode", ["backfill", "recovery"])
def test_backfill_and_recovery_are_never_on_a_cadence(mode):
    """Both are explicit acts with their own bounds — a drain of full history and a safety
    re-scan of a fixed window. Neither has ever answered to a poll interval."""
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(minutes=1))
    cursors.save(ORG, CONN, "gmail", cursor=None, watermark=NOW - timedelta(minutes=1))
    connector = _CountingMailbox()

    summary = _poll(connector, cursors, mode=mode)

    assert connector.fetches == [None]
    assert summary.poll is None


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Catch-up: an outage is paid for in PAGES, once
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_connection_behind_by_a_day_gets_the_extended_page_budget():
    """The default `max_pages=1` of a plain caller would drain one page after a 24-hour outage
    and then advance the watermark past everything it did not read."""
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(hours=24))
    cursors.save(ORG, CONN, "gmail", cursor=None, watermark=NOW - timedelta(hours=24))
    connector = _CountingMailbox(pages=6, per_page=1)

    summary = _poll(connector, cursors)

    assert summary.poll is not None and summary.poll.is_catch_up is True
    assert summary.poll.max_pages > DEFAULT_PAGE_BUDGET
    assert len(connector.fetches) == 6, (
        "the catch-up budget did not reach the page loop — one page after an outage is the "
        "silent loss this unit exists to prevent")
    assert summary.scanned == 6


def test_a_healthy_connection_keeps_the_callers_page_budget():
    """Catch-up must extend a run, never define it: a caller that asked for 2 pages on a
    connection that is up to date still gets 2."""
    # 40 minutes into a 15-minute cadence: two intervals late, which is a slow tick and not an
    # outage — `CATCH_UP_INTERVAL_MULTIPLE` is three for exactly this reason.
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(minutes=40))
    cursors.save(ORG, CONN, "gmail", cursor=None, watermark=NOW - timedelta(minutes=40))
    connector = _CountingMailbox(pages=9, per_page=1)

    summary = _poll(connector, cursors, max_pages=2)

    assert summary.poll is not None and summary.poll.is_catch_up is False
    assert len(connector.fetches) == 2


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Configuration reaches the gate
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_a_per_connection_override_reaches_the_running_sweep():
    """A tenant who sets a tighter cadence on ONE connection gets it; the source policy would
    have said no."""
    cursors = InMemoryCursorStore(clock=lambda: NOW - timedelta(hours=2))
    cursors.save(ORG, CONN, "notion", cursor=None, watermark=NOW - timedelta(hours=2))
    connector = _CountingMailbox("notion")

    summary = _poll(connector, cursors, source="notion", cadence_override_seconds=3600)

    assert connector.fetches == [None]
    assert summary.poll is not None and summary.poll.cadence.origin == "override"


def test_the_shipped_policy_is_what_the_sweep_uses_and_the_old_setting_is_its_fallback():
    """`sync_interval_hours` is not deleted, it is demoted: it stops being how often EVERYTHING
    polls and becomes the cadence of a source nobody has tuned."""
    from genios_engine.platform.config import get_settings

    policy = sweep_cadence_policy()
    assert policy.interval_for("gmail") == 900
    assert policy.interval_for("notion") == 12 * 3600
    assert policy.default_seconds == int(get_settings().sync_interval_hours * 3600)
    assert sweep_tick_seconds() == int(get_settings().sync_interval_hours * 3600)


def test_an_operator_cadence_string_overlays_the_shipped_table(monkeypatch):
    from genios_engine.platform import config as C

    sweep_cadence_policy.cache_clear()
    C.get_settings.cache_clear()
    monkeypatch.setenv("GENIOS_SYNC_CADENCES", "gmail=5m,default=2h")
    try:
        policy = sweep_cadence_policy()
        assert policy.interval_for("gmail") == 300
        assert policy.interval_for("notion") == 12 * 3600, "an untouched source kept its default"
        assert policy.default_seconds == 7200
    finally:
        monkeypatch.delenv("GENIOS_SYNC_CADENCES", raising=False)
        sweep_cadence_policy.cache_clear()
        C.get_settings.cache_clear()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Jitter must spread a herd, never halve a poll rate
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_jitter_never_makes_a_source_poll_less_often_than_its_cadence():
    """A sweep whose tick EQUALS the cadence is where a positive offset silently halves the poll
    rate: the turn lands past the tick, the tick says "not due", and the source is polled every
    other tick forever. The grace is the offset's own width, so the connection is pulled into
    the current tick and never into an earlier cadence."""
    tick = 6 * 3600
    late = [cid for cid in (f"con_{i}" for i in range(60))
            if plan_poll(ConnectionSchedule(ORG, cid, "gdrive",
                                            last_success_at=NOW - timedelta(seconds=tick)),
                         now=NOW).due is False]
    assert late, "no connection of this sample is delayed by jitter — the test proves nothing"

    for cid in late:
        graced = plan_poll(ConnectionSchedule(ORG, cid, "gdrive",
                                              last_success_at=NOW - timedelta(seconds=tick)),
                           now=NOW, sweep_tick_seconds=tick)
        assert graced.due is True, f"{cid} still polls at half its cadence"


@pytest.mark.parametrize("interval,tick,expected", [
    (900, 6 * 3600, 90),            # capped by the offset's own width (10% of 15 minutes)
    (6 * 3600, 6 * 3600, 2160),     # 10% of six hours
    (6 * 3600, 300, 300),           # a fine-grained sweep needs no more grace than its tick
    (900, 0, 0),                    # an on-demand caller has no tick and gets no grace
])
def test_the_grace_is_bounded_by_both_the_spread_and_the_tick(interval, tick, expected):
    assert tick_grace_seconds(interval, sweep_tick_seconds=tick) == expected


def test_the_grace_never_pulls_a_poll_into_an_earlier_cadence():
    """A 12-hour source polled by a 6-hour sweep must not become a 6-hour source."""
    decision = plan_poll(
        ConnectionSchedule(ORG, CONN, "notion", last_success_at=NOW - timedelta(hours=6)),
        now=NOW, sweep_tick_seconds=6 * 3600)
    assert decision.due is False


# ═════════════════════════════════════════════════════════════════════════════════════════════
# REAL POSTGRESQL — the gate reads `sync_cursors.updated_at`, not an in-memory dict
# ═════════════════════════════════════════════════════════════════════════════════════════════

@pytest.mark.pg
def test_the_gate_defers_a_freshly_polled_connection_through_a_real_cursor_row(live_db_url):
    """An in-memory store agreeing with itself proves nothing about the column the decision
    actually rests on."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres poll-gate test skipped")
    from sqlalchemy import text

    from genios_engine.capture.acquire.cursor_store import PostgresCursorStore
    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)
    with engine.connect() as c:
        org = c.execute(text("select id from orgs limit 1")).scalar()
    assert org, "scratch org missing — conftest seeds one"
    conn_id = "con_pollgate_pg"
    store = PostgresCursorStore(live_db_url)
    try:
        store.save(org, conn_id, "gmail", cursor=None, watermark=None)   # updated_at = now()
        fresh = _CountingMailbox()
        with scheduled_sweep():
            deferred = run_sync(fresh, org_id=org, connection_id=conn_id,
                                repo=InMemorySourceEventRepository(), cursor_store=store,
                                source="gmail", mailbox_owner=OWNER)
        assert fresh.fetches == [], "a connection polled seconds ago was polled again"
        assert deferred.skipped_not_due is True

        with engine.begin() as c:
            c.execute(text("update sync_cursors set updated_at = now() - interval '24 hours' "
                           "where org_id=:o and connection_id=:c and source='gmail'"),
                      {"o": org, "c": conn_id})
        stale = _CountingMailbox(pages=3, per_page=1)
        with scheduled_sweep():
            caught = run_sync(stale, org_id=org, connection_id=conn_id,
                              repo=InMemorySourceEventRepository(), cursor_store=store,
                              source="gmail", mailbox_owner=OWNER)
        assert stale.fetches, "a connection a day behind was not polled"
        assert caught.poll is not None and caught.poll.is_catch_up is True
    finally:
        with engine.begin() as c:
            c.execute(text("delete from sync_cursors where org_id=:o and connection_id=:c"),
                      {"o": org, "c": conn_id})


@pytest.mark.pg
def test_a_tenant_set_cadence_override_is_read_from_the_real_connections_row(live_db_url,
                                                                            monkeypatch):
    """The override is TENANT configuration and the sweep never carries the `Connection` row, so
    `run_sync` looks it up. A lookup against the wrong column would fail exactly the way a
    connection with no override does — the tuning knob would silently do nothing forever, which
    is the same class of defect as a unit with no caller.
    """
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres override test skipped")
    from sqlalchemy import text

    from genios_engine.capture.acquire.cursor_store import PostgresCursorStore
    from genios_engine.capture.connections.store import PostgresConnectionStore
    from genios_engine.contracts.connection import Connection
    from genios_engine.platform import config as C
    from genios_engine.platform.db import get_engine

    C.get_settings.cache_clear()
    monkeypatch.setenv("GENIOS_DATABASE_URL", live_db_url)
    engine = get_engine(live_db_url)
    with engine.connect() as c:
        org = c.execute(text("select id from orgs limit 1")).scalar()
    assert org, "scratch org missing — conftest seeds one"
    conn_id = "con_override_pg"
    connections = PostgresConnectionStore(live_db_url)
    cursors = PostgresCursorStore(live_db_url)
    try:
        connections.add(Connection(org_id=org, connection_id=conn_id, source_type="notion",
                                   composio_user_id=org, config={"cadence_minutes": 1}))
        cursors.save(org, conn_id, "notion", cursor=None, watermark=None)
        with engine.begin() as c:
            c.execute(text("update sync_cursors set updated_at = now() - interval '30 minutes' "
                           "where org_id=:o and connection_id=:c and source='notion'"),
                      {"o": org, "c": conn_id})

        connector = _CountingMailbox("notion")
        with scheduled_sweep():
            summary = run_sync(connector, org_id=org, connection_id=conn_id,
                               repo=InMemorySourceEventRepository(), cursor_store=cursors,
                               source="notion", mailbox_owner=OWNER)

        assert summary.poll is not None
        assert summary.poll.cadence.origin == "override", (
            "the tenant's `cadence_minutes` never reached the gate — notion's 12-hour policy "
            "cadence was used instead")
        assert summary.poll.cadence.interval_seconds == 60
        assert connector.fetches == [None], "the overridden cadence did not make it due"
    finally:
        with engine.begin() as c:
            c.execute(text("delete from sync_cursors where org_id=:o and connection_id=:c"),
                      {"o": org, "c": conn_id})
            c.execute(text("delete from connections where connection_id=:c"), {"c": conn_id})
        C.get_settings.cache_clear()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE REAL SWEEP — `api/routes.run_sync_sweep`, the loop the scheduler actually drives
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_the_real_cross_org_sweep_skips_a_connection_that_is_not_due(monkeypatch):
    """The end of the chain, driven for real: `_tick` marks the thread, `run_maintenance_sweep`
    calls `run_sync_sweep`, and `run_sync_sweep` loops every active connection into `run_sync`.

    Two ticks back to back. The first is the connection's first poll ever, so it runs; the
    second is one second later, which for a 15-minute cadence is not its turn. Before this
    wiring both ticks hit the provider, which is what "one global 6-hour interval, no per-source
    rate" meant in practice.
    """
    from genios_engine.api import routes
    from genios_engine.contracts.connection import Connection

    connector = _CountingMailbox()
    conn = Connection(org_id=ORG, connection_id=CONN, source_type="gmail",
                      composio_user_id=ORG)
    monkeypatch.setattr(routes, "_connections", _OneConnection(conn))
    monkeypatch.setattr(routes, "_cursors", InMemoryCursorStore())
    monkeypatch.setattr(routes, "_repo", InMemorySourceEventRepository())
    # Every optional store off: this test is about WHICH connections the loop polls, and a
    # Postgres-backed park/trace store would only assert that the scratch database has an org.
    for store in ("_parked", "_trace_repo", "_payload_store", "_prepared_store", "_documents",
                  "_graph"):
        monkeypatch.setattr(routes, store, None)
    monkeypatch.setattr(routes, "make_connector_for", lambda *a, **kw: connector)
    monkeypatch.setattr(routes, "make_relevance_classifier", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_semantic_lane_for", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_coverage_fn_for", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_sender_resolver_for", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_semantic_activated_orgs", lambda *a, **kw: frozenset())
    monkeypatch.setattr(routes, "_run_l2", lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_run_ledger", lambda *a, **kw: None)

    with scheduled_sweep():
        first = routes.run_sync_sweep()
        second = routes.run_sync_sweep()

    assert (first["l1_ok"], first["l1_err"]) == (1, 0)
    assert (second["l1_ok"], second["l1_err"]) == (1, 0), "a deferred poll is not an error"
    assert len(connector.fetches) == 1, (
        f"the provider was called {len(connector.fetches)} times across two ticks one second "
        "apart — the sweep is not consulting the cadence")


class _OneConnection:
    """The narrowest `ConnectionStore` the sweep needs: one active connection, no database."""

    def __init__(self, connection) -> None:
        self._connection = connection

    def list_active(self, source_type: str | None = None):
        return [self._connection]

    def get(self, connection_id: str):
        return self._connection if connection_id == self._connection.connection_id else None
