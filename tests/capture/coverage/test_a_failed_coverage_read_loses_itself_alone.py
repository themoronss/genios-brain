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

`yc2_w27_s18` M48.C2.L-data.V2.U18 (S18-X08): a third site of the same shape, unlisted —
`context/situations.unmet_source_families`, which the support and outreach passes call inside their
transaction right before `window_coverage_gaps`. Its failed statement here: an org id Postgres
cannot compare with a text column.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.coverage.window import SyncHealth, coverage_for_window
from genios_engine.context.situations import unmet_source_families, window_coverage_gaps

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


def test_a_failed_source_list_says_nothing_and_the_situation_pass_reads_on(engine):
    """`context/situations.window_coverage_gaps`, which the three situation passes call inside their
    own transaction: its source list loses itself alone."""
    with engine.begin() as c:
        assert window_coverage_gaps(c, ORG, since="not a date", until=UNTIL) == ()
        assert c.execute(text("select 1")).scalar() == 1, (
            "the failed source list aborted the situation pass's transaction")


def test_a_source_list_that_succeeds_still_names_what_cannot_be_ruled_out(engine):
    """The negative half: a source with a sync that never finished still gets its sentence."""
    since = datetime(2026, 9, 1, tzinfo=timezone.utc)
    with engine.begin() as c:
        c.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
        c.execute(text(
            "insert into l1_sync_runs (run_id, org_id, connection_id, source, mode, started_at, "
            "finished_at, scanned, cursor_exhausted) values ('run_s18', :o, 'conn_s18', 'gmail', "
            "'incremental', :at, :at, 5, false)"), {"o": ORG, "at": datetime(2026, 9, 2, tzinfo=timezone.utc)})
        gaps = window_coverage_gaps(c, ORG, since=since, until=UNTIL)
        c.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    assert gaps == ("the gmail sweep did not finish, so a tail of this window was never read",)


def test_a_failed_source_family_read_says_nothing_and_the_pass_reads_on(engine):
    """S18-X08: `unmet_source_families` — the support and outreach passes call it inside their own
    transaction, just before `window_coverage_gaps`."""
    with engine.begin() as c:
        assert unmet_source_families(c, 7, "admin") == ()
        assert c.execute(text("select 1")).scalar() == 1, (
            "the failed source-family read aborted the situation pass's transaction")


def test_a_source_family_read_that_succeeds_still_names_what_is_missing(engine):
    """The negative half: the savepoint changes nothing for a read that works."""
    with engine.begin() as c:
        c.execute(text("delete from source_coverage where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": ORG})
        c.execute(text(
            "insert into source_coverage (org_id, domain, required, connected) values "
            "(:o, 'admin', array['finance', 'email'], array['email'])"),
            {"o": ORG})
        missing = unmet_source_families(c, ORG, "admin")
        c.execute(text("delete from source_coverage where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    assert missing == ("finance",)
