"""STEP-03 · the run ledger and the cross-org sweep say what a sync archived.

    pytest tests/test_the_run_ledger_counts_archived.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_the_run_ledger_counts_archived.py -q

`api/routes.py` (tree `yc2_w27_s03/M21.C4.L-interface.V4.U02`). `l1_sync_runs` gained `archived`
(migration 0192) and a column no writer names is null — or, here, zero — in every row: `started_at`
is this table's cautionary tale. So `_run_ledger` names it, and `/ingest/all`, the cross-org cron,
carries it in its totals and per connection. A sweep that archived Boardy's nudges and reported
`dropped: 0` and nothing else would read as a mailbox with no noise at all.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import text

from genios_engine.capture.acquire.sync_runner import SyncSummary

ORG = "org_ledger_archived"
CONN = "con_ledger_archived"


def test_the_cross_org_sweep_carries_archived_in_its_totals_and_per_connection(monkeypatch):
    from genios_engine.api import routes

    conns = [SimpleNamespace(org_id="o1", connection_id="c1", source_type="gmail", seat_id=None),
             SimpleNamespace(org_id="o2", connection_id="c2", source_type="gmail", seat_id=None)]
    summaries = {"c1": SyncSummary(scanned=5, emitted=2, archived=3),
                 "c2": SyncSummary(scanned=4, emitted=1, archived=2, parked=1)}
    monkeypatch.setattr(routes._connections, "list_active", lambda: conns)
    monkeypatch.setattr(routes, "run_sync", lambda connector, **kw: summaries[kw["connection_id"]])
    for name in ("make_relevance_classifier", "make_connector_for", "_bind_gate_costs",
                 "_semantic_activated_orgs", "_mailbox_owner_for_connection",
                 "_sender_resolver_for", "_coverage_fn_for", "_esqe_stage_for",
                 "_semantic_lane_for", "_structured_lane_for"):
        monkeypatch.setattr(routes, name, lambda *a, **kw: None)

    out = routes.ingest_all(BackgroundTasks(), auto_l2=False, _internal=None)

    assert out["totals"]["archived"] == 5
    assert (out["totals"]["emitted"], out["totals"]["dropped"]) == (3, 0)
    assert [p["archived"] for p in out["per_connection"]] == [3, 2]


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the ledger write needs real Postgres")
    return live_db_url


@pytest.mark.pg
def test_the_ledger_row_says_what_the_run_archived(pg_url, monkeypatch):
    from genios_engine.api import routes
    from genios_engine.platform.db import get_engine

    engine = get_engine(pg_url)
    monkeypatch.setattr(routes, "_l1_stores", lambda: routes.L1Stores())
    with engine.begin() as conn:
        conn.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
        conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
        conn.execute(text("insert into orgs (id, name, email) values (:o, :o, 'la@example.test')"),
                     {"o": ORG})
    try:
        routes._run_ledger(org_id=ORG, connection_id=CONN, source="gmail", mode="incremental",
                           summary=SyncSummary(scanned=9, emitted=4, archived=5))
        with engine.connect() as conn:
            row = conn.execute(text("select scanned, emitted, dropped, archived from l1_sync_runs "
                                    "where org_id = :o"), {"o": ORG}).one()
        assert tuple(row) == (9, 4, 0, 5)
    finally:
        with engine.begin() as conn:
            conn.execute(text("delete from l1_sync_runs where org_id = :o"), {"o": ORG})
            conn.execute(text("delete from orgs where id = :o"), {"o": ORG})
