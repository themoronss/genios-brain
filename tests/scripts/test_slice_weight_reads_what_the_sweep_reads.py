"""S17-F1 · `scripts/slice_weight.py` had never run — its first statement named a column that does not exist.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q \
        tests/scripts/test_slice_weight_reads_what_the_sweep_reads.py

`yc2_w27_s17` M40.C1.L-logic.V1.U03, found by planning every statement (STEP-17 §3.2). The script is
L2-3's cost check: *"take ten real candidates and compute the slice size in tokens"*, built *"exactly
the way `domain_shadow` does"*. Its own copy of the sweep's situation read selected `anchor_type`
from `context_situations` — a column of `context_correlations`; the sweep reads the anchor's
`node_type` from `graph_nodes`. Every run raised `UndefinedColumn` on its first statement, since
`aa6ab06e` (24 Sep). It now reads the sweep's own statement, so the two cannot drift again.
"""
from __future__ import annotations

import sys

import pytest
from sqlalchemy import text

from genios_engine.platform import statement_plans as sp
from genios_engine.reason import domain_shadow

ORG = "org_s17_slice_weight"


def test_the_script_reads_the_sweeps_own_statement():
    """One statement, not a copy: the copy is what drifted."""
    from scripts import slice_weight

    assert slice_weight._SITUATIONS is domain_shadow._ACTIVE_SITUATIONS
    own = [s for s in sp.statements() if s.path == "scripts/slice_weight.py"]
    assert not [s for s in own if "context_situations" in s.sql], (
        "the script holds its own situation read again — it drifted once")


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the script needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name) values (:o, 'Slice Weight')"), {"o": ORG})
        c.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, canonical_key, display_name) "
            "values ('n_s17_acme', :o, 'company', 'acme.test', 'Acme')"), {"o": ORG})
        c.execute(text(
            "insert into context_situations (situation_id, org_id, correlation_id, anchor_node_id, "
            "situation_type, domain, status, confidence_overall) values ('sit_s17_acme', :o, "
            "'outreach:n_s17_acme', 'n_s17_acme', 'awaiting_response', 'admin', 'active', 0.8)"),
            {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def test_every_statement_of_the_script_plans(engine):
    from scripts import slice_weight

    with engine.connect() as c:
        assert sp.plan(c, slice_weight._SITUATIONS) is None
        for stmt in [s for s in sp.statements() if s.path == "scripts/slice_weight.py"
                     and not s.holes]:
            assert sp.plan(c, stmt.sql) is None, (stmt.line, stmt.sql)


def test_the_script_runs_and_weighs_the_situation(engine, live_db_url, monkeypatch, capsys):
    from scripts import slice_weight

    monkeypatch.setattr(sys, "argv", ["slice_weight.py", "--org", ORG, "--sample", "5",
                                      "--database-url", live_db_url])
    assert slice_weight.main() == 0
    out = capsys.readouterr().out
    assert "WHAT A CONTEXT SLICE WEIGHS" in out
    assert "sit_s17_acme" in out and "awaiting_response" in out, out
