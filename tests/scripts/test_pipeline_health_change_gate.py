"""STEP-02 · the health check that the change gate is running and saving — on real rows.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_change_gate.py -q

`scripts/pipeline_health.check_the_change_gate_skips_what_did_not_change` (tree
`yc2_w27_s02/M20.C6.L-interface.V4.U02`). The gate's two failure modes, each its own FAIL:

  * it is not running — sweeps ran and it recorded nothing;
  * it saves nothing — four or more sweeps ran and not one subject was skipped, which is what a
    fingerprint carrying an input that moves every sweep looks like (STEP-02 §7, risk 2).

No sweep in the window is nothing to judge, and passes saying so.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "health_gate_org"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pipeline_health.py"


def _module():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


@pytest.fixture
def conn():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    engine = create_engine(url)
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'hg@example.test')"),
                  {"o": ORG})
    with engine.connect() as c:
        yield c
        c.rollback()
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _sweeps(c, n: int) -> None:
    now = datetime.now(timezone.utc)
    for i in range(n):
        c.execute(text("insert into pipeline_counters (org_id, sweep_id, stage, n, sweep_at) "
                       "values (:o, :s, 'signals_detected', 0, :t)"),
                  {"o": ORG, "s": f"sweep_{i}", "t": now - timedelta(minutes=15 * i)})


def _subject(c, key: str, skips: int) -> None:
    now = datetime.now(timezone.utc)
    c.execute(text(
        "insert into reasoning_fingerprints (org_id, subject_key, lane, fingerprint, outcome, "
        "decided_at, last_checked_at, skips) values (:o, :k, 'compiled', 'fp_x', 'standing', "
        ":d, :t, :s)"), {"o": ORG, "k": key, "d": now - timedelta(hours=1), "t": now, "s": skips})


def test_no_sweep_in_the_window_is_nothing_to_judge(conn):
    check = _module().check_the_change_gate_skips_what_did_not_change(conn, ORG)
    assert check.ok and "no sweep" in check.measured


def test_sweeps_with_nothing_recorded_fail_the_gate_is_not_running(conn):
    _sweeps(conn, 2)
    check = _module().check_the_change_gate_skips_what_did_not_change(conn, ORG)
    assert not check.ok and "recorded nothing" in check.measured


def test_four_sweeps_and_not_one_skip_fail_the_gate_saves_nothing(conn):
    _sweeps(conn, 4)
    for i in range(3):
        _subject(conn, f"sit_{i}|cap", skips=0)
    check = _module().check_the_change_gate_skips_what_did_not_change(conn, ORG)
    assert not check.ok and "0 of 3" in check.measured


def test_a_gate_that_skips_passes_and_says_how_much(conn):
    _sweeps(conn, 4)
    _subject(conn, "sit_1|cap", skips=5)
    _subject(conn, "sit_2|cap", skips=0)
    check = _module().check_the_change_gate_skips_what_did_not_change(conn, ORG)
    assert check.ok and "1 of 2" in check.measured


def test_the_check_runs_in_the_script(conn):
    module = _module()
    assert module.check_the_change_gate_skips_what_did_not_change in module.CHECKS
