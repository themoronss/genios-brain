"""STEP-10 · a coverage receipt that cannot be read loses that read alone — and says so.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_receipt_that_cannot_be_read_says_so.py -q

`context/coverage_receipt.receipt_for` (tree `yc2_w27_s10 · M29.C5.L-logic.V2.U05`). Found by STEP-10's
crosscheck (X3): `receipt_for` and `_last_sync` caught every exception and answered "no mailbox" or "never
synced" — the safe direction, since "no reply" can then never be said — but silently, and on Postgres a
failed statement aborts the transaction that holds it, so every read after it on the same connection failed
too: the next mailbox's, and whatever the file's reader asked next. Now each read runs in a savepoint and
logs a warning naming the tenant (and the mailbox), and the reads after it go on.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.coverage_receipt import receipt_for

from .workstream_world import T0, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s10_receipt_fails"
NOW = T0 + timedelta(days=10)
LOGGER = "genios.context.coverage_receipt"

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
    """The tenant's receipt inside one transaction — after `breaks`, when given — and whether that
    transaction can still read afterwards."""
    with store.engine.connect() as c, c.begin():
        if breaks:
            c.execute(text(breaks))
        receipt = receipt_for(c, ORG, now=NOW)
        return receipt, c.execute(text("select 1")).scalar()


def _said(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == LOGGER]


def test_a_readable_receipt_names_its_mailbox_and_its_last_sync(store, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        [receipt], alive = _read(store)
    assert (receipt.connection_id, receipt.last_finished_at, receipt.last_completed, alive) == (
        "con_x", NOW - timedelta(days=1), True, 1)
    assert _said(caplog) == [], "a read that works says nothing"


def test_unreadable_connections_are_an_empty_receipt_and_the_reads_after_it_go_on(store, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        receipt, alive = _read(store, NO_CONNECTIONS)
    assert (receipt, alive) == ([], 1)
    [said] = _said(caplog)
    assert ORG in said


def test_an_unreadable_last_sync_has_not_completed_and_the_reads_after_it_go_on(store, caplog):
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        [receipt], alive = _read(store, NO_RUNS)
    assert (receipt.connection_id, receipt.last_finished_at, receipt.last_completed, alive) == (
        "con_x", None, False, 1)
    [said] = _said(caplog)
    assert ORG in said and "con_x" in said
