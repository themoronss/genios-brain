"""STEP-10 · one mailbox's coverage read that fails loses that read alone — and says so.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/coverage/test_a_mailbox_read_that_fails_says_so.py -q

`capture/coverage/window.coverage_for_connection` (tree `yc2_w27_s10 · M29.C5.L-logic.V1.U06`). Found by
STEP-10's crosscheck (X3): each of its two reads caught every exception and answered "no mailbox" or "no
run" — the safe direction, since a file can then never say "no reply" — but silently, and on Postgres a
failed statement aborts the transaction that holds it, so every later read on the same connection (the
receipt's next mailbox, the file's numbers) failed too and was swallowed the same way. Now each read runs
in a savepoint, logs a warning naming the tenant and the mailbox, and the reads after it go on.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.coverage.window import SyncHealth, coverage_for_connection
from tests.context.workstream_world import reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_window_fails"
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
LOGGER = "genios.capture.coverage"

#: What makes each read fail on a live connection, inside the test's own transaction only.
NO_CONNECTIONS = "set local search_path to pg_catalog"
NO_RUNS = "create temp table l1_sync_runs (run_id text) on commit drop"


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        c.execute(text(
            "insert into connections (connection_id, org_id, source_type, capture_scope, status) "
            "values ('con_x', :o, 'gmail', cast('{\"backfill_days\": 60}' as jsonb), 'connected')"),
            {"o": ORG})
        c.execute(text(
            "insert into l1_sync_runs (run_id, org_id, connection_id, source, mode, scanned, "
            " claimed_total, cursor_exhausted, error, started_at, finished_at) values "
            " ('run_x', :o, 'con_x', 'gmail', 'incremental', 1, 1, true, null, :at, :at)"),
            {"o": ORG, "at": NOW - timedelta(days=1)})
    yield pg_store
    reset(pg_store, ORG)


def _read(store, breaks: str | None = None):
    """The mailbox's window read inside one transaction — after `breaks`, when given — and whether
    that transaction can still read afterwards."""
    with store.engine.connect() as c, c.begin():
        if breaks:
            c.execute(text(breaks))
        window = coverage_for_connection(c, org_id=ORG, connection_id="con_x", now=NOW)
        return window, c.execute(text("select 1")).scalar()


def test_a_readable_mailbox_reads_its_runs(store):
    window, alive = _read(store)
    assert (window.runs, window.health, alive) == (1, SyncHealth.HEALTHY, 1)


def test_an_unreadable_connection_is_no_mailbox_and_the_reads_after_it_go_on(store, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        window, alive = _read(store, NO_CONNECTIONS)
    assert (window, alive) == (None, 1)
    [said] = [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert ORG in said and "con_x" in said


def test_unreadable_runs_are_no_run_and_the_reads_after_them_go_on(store, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        window, alive = _read(store, NO_RUNS)
    assert (window.connection_id, window.runs, window.health, alive) == (
        "con_x", 0, SyncHealth.UNKNOWN, 1)
    [said] = [r.getMessage() for r in caplog.records if r.name == LOGGER]
    assert ORG in said and "con_x" in said


def test_a_read_that_works_says_nothing(store, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        _read(store)
    assert not [r for r in caplog.records if r.name == LOGGER]
