"""`l1_sync_runs` records when a sync BEGAN, not only when it stopped.

    pytest tests/capture/test_sync_run_ledger.py -q      (the pg test needs GENIOS_TEST_DATABASE_URL)

The column has existed since the table did; the insert never named it. Production therefore holds
443 run rows, every one of them with `started_at` NULL — so the first question anybody asks about
a slow tenant ("how long did that sync take?") had no answer in the ledger built to answer it, and
a run that hung looked identical to one that finished instantly.

Two halves, because they break independently: `run_sync` must PRODUCE the instant, and
`_run_ledger` must WRITE it. A test of either alone leaves the other free to regress.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.capture.acquire.sync_runner import SyncSummary, run_sync
from genios_engine.capture.connectors.base import SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.platform.db import get_engine

ORG = "org_sync_ledger"
CONN = "con_sync_ledger"
START = datetime(2026, 5, 4, 8, 30, tzinfo=timezone.utc)


class _EmptyConnector:
    """A provider with nothing new. The point is the RUN, not what it carried."""

    source = "gmail"

    def incremental_changes(self, cursor=None, limit=50, since=None):
        return SourceBatch(objects=[], next_cursor=None)

    def initial_snapshot(self, cursor=None, limit=50):
        return self.incremental_changes(cursor, limit)

    def validate_connection(self) -> bool:
        return True


def test_run_sync_stamps_the_instant_it_began():
    """From the injected `_now` seam, never a bare clock — so this asserts a value rather than a
    range, and a frozen replay stamps the same instant twice."""
    summary = run_sync(_EmptyConnector(), org_id=ORG, connection_id=CONN,
                       repo=InMemorySourceEventRepository(), source="gmail",
                       _now=lambda: START)
    assert summary.started_at == START


def test_a_summary_that_never_ran_still_reports_no_start():
    """The failure path: a caller reporting a TOTAL sync failure has no summary at all, and NULL
    is the honest answer for a run that never began. A default of `now()` in the DDL would have
    made every failed run look like it started the moment somebody noticed it."""
    assert SyncSummary().started_at is None


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the ledger write needs real Postgres")
    return live_db_url


def test_the_ledger_row_carries_the_start(pg_url, monkeypatch):
    """Through `api/routes._run_ledger` — the hook every HTTP sync caller shares — and read back
    out of the table, because what was broken was the INSERT and not the dataclass."""
    from genios_engine.api import routes

    engine = get_engine(pg_url)
    # The four L1 seams are exercised by their own files; this one is about the ledger row, so the
    # stores are stood down and `finalize_l1` runs over an empty summary.
    monkeypatch.setattr(routes, "_l1_stores", lambda: routes.L1Stores())
    with engine.begin() as conn:
        conn.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
        # `l1_sync_runs` cascades from `orgs`, so the tenant has to exist before its run does.
        # Required columns are read off the live schema rather than listed, so a table that gains
        # one breaks the product and not this fixture.
        names = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'"))]
        cols = ["id"] + names
        conn.execute(text(f"insert into orgs ({', '.join(cols)}) values "
                          f"({', '.join(':' + c for c in cols)})"),
                     {"id": ORG, **{n: "scratch" for n in names}})

    finished = START + timedelta(minutes=4)
    routes._run_ledger(org_id=ORG, connection_id=CONN, source="gmail", mode="incremental",
                       summary=SyncSummary(scanned=7, emitted=2, started_at=START))

    with engine.connect() as conn:
        row = conn.execute(text("select started_at, finished_at, scanned, emitted "
                                "from l1_sync_runs where org_id = :o"), {"o": ORG}).one()
        conn_started = row.started_at
    assert conn_started == START, "the ledger wrote a run with no start — the column is unfilled"
    assert row.finished_at is not None and row.finished_at >= conn_started
    assert row.finished_at <= finished + timedelta(days=3650)   # sanity: a real instant, not 1970
    assert (row.scanned, row.emitted) == (7, 2)

    with engine.begin() as conn:
        conn.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
