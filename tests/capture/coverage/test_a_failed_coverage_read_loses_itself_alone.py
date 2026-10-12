"""`03` F120 · a coverage read that fails loses that read alone — never the pass that called it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/coverage/test_a_failed_coverage_read_loses_itself_alone.py -q

`yc2_w27_s18` M48.C2.L-data.V0.U07 (L1 Signals, `capture/coverage/window`) and M48.C2.L-data.V1.U08
(L3 Context Graph, `context/situations`).

⛔ WHAT WAS WRONG. `capture/coverage/window.coverage_for_window` and the source list of
`context/situations.window_coverage_gaps` caught a failed statement with a bare `except` and went on.
On Postgres a failed statement aborts the transaction that holds it, and the three situation passes
that call these reads do so inside their own transaction (`outreach_situations`, `situations`,
`support_situations`): every later read and write of the pass then failed the same way, swallowed —
the defect `outreach_situations._optional` and `coverage_for_connection` were written against. Each
read now runs in a SAVEPOINT: it loses its own answer (UNKNOWN, or no sentence) and the transaction
reads on. A failed statement is made here the plainest way — a window bound Postgres cannot read.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.coverage.window import SyncHealth, coverage_for_window

pytestmark = pytest.mark.pg

ORG = "org_s18_failed_coverage_read"
UNTIL = datetime(2026, 10, 12, tzinfo=timezone.utc)


@pytest.fixture
def engine(pg_store):
    return pg_store.engine


def test_a_failed_window_read_is_unknown_and_the_transaction_reads_on(engine):
    with engine.begin() as c:
        cov = coverage_for_window(c, org_id=ORG, source="gmail", since="not a date", until=UNTIL)
        assert cov.health is SyncHealth.UNKNOWN and cov.runs == 0
        assert c.execute(text("select 1")).scalar() == 1, (
            "the failed read aborted the caller's transaction: every later read of the pass fails")


def test_a_window_read_that_succeeds_is_unchanged(engine):
    """The negative half: the savepoint changes nothing for a read that works."""
    since = datetime(2026, 9, 1, tzinfo=timezone.utc)
    with engine.begin() as c:
        cov = coverage_for_window(c, org_id=ORG, source="gmail", since=since, until=UNTIL)
        assert cov.runs == 0 and cov.health is SyncHealth.UNKNOWN
        assert c.execute(text("select 1")).scalar() == 1
