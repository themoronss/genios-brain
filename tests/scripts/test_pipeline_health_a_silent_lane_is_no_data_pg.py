"""03 F24 · an LLM lane that made no call in the window is NO DATA for that lane — never a pass.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q \
        tests/scripts/test_pipeline_health_a_silent_lane_is_no_data_pg.py

`yc2_w27_s17` M40.C3.L-logic.V0.U02. ⛔ F24, re-measured 5 Oct: every narrator failure of 4 Oct
stopped at exactly 1,400 tokens, the last before the fix that raised the cap was committed — and the
narrator made no call after it. The 24-hour ceiling check went on passing, because the lane it guards
was simply absent from the window. So a lane that called in the last week and not in the window is
named, and the check says NO DATA: it cannot vouch for a lane it did not see. A failing lane is still
a FAIL whatever is silent beside it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from scripts import pipeline_health as ph

ORG = "org_s17_silent_lane"


@pytest.fixture
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the checks read llm_costs")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    try:
        c.execute(text("insert into orgs (id, name) values (:o, 'Silent Lane') "
                       "on conflict (id) do nothing"), {"o": ORG})
        yield c
    finally:
        tx.rollback()
        c.close()


def _calls(c, purpose: str, *, n: int, hours_ago: float, failed: int = 0, out: int = 300):
    at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    for i in range(n):
        c.execute(text(
            "insert into llm_costs (org_id, model, purpose, input_tokens, output_tokens, success, "
            "created_at) values (:o, 'claude-sonnet-5', :p, 1000, :out, :ok, :at)"),
            {"o": ORG, "p": purpose, "out": out + i, "ok": i >= failed,
             "at": at - timedelta(minutes=i)})


def _both(c):
    return (ph.check_llm_failure_rate(c, ORG, hours=24, ceiling_bp=2000),
            ph.check_no_silent_truncation(c, ORG, hours=24))


def test_the_narrator_silent_since_three_days_is_no_data_and_named(conn):
    _calls(conn, "l1_extract", n=6, hours_ago=1)
    _calls(conn, "l4_bundle", n=8, hours_ago=72)          # F24: the narrator, then nothing
    for check in _both(conn):
        assert check.verdict == ph.NO_DATA, (check.name, check.measured)
        assert "l4_bundle" in check.measured, check.measured
        assert "l1_extract" not in check.measured.split("no call")[-1], check.measured
        assert any(line.startswith("l4_bundle: no call in 24h") for line in check.detail)


def test_when_every_lane_that_called_this_week_called_today_the_lanes_pass(conn):
    _calls(conn, "l1_extract", n=6, hours_ago=1)
    _calls(conn, "l4_bundle", n=6, hours_ago=2)
    for check in _both(conn):
        assert check.verdict == ph.PASS, (check.name, check.measured)


def test_a_failing_lane_fails_whatever_is_silent_beside_it(conn):
    _calls(conn, "l1_extract", n=6, hours_ago=1, failed=4)
    _calls(conn, "l4_bundle", n=8, hours_ago=72)
    rate, _ = _both(conn)
    assert rate.verdict == ph.FAIL and "l1_extract: 4/6" in rate.measured


def test_failures_pinned_to_one_ceiling_fail_whatever_is_silent_beside_it(conn):
    for i in range(3):
        conn.execute(text(
            "insert into llm_costs (org_id, model, purpose, output_tokens, success, created_at) "
            "values (:o, 'claude-sonnet-5', 'l4_bundle', 1400, false, now() - make_interval("
            "mins => :m))"), {"o": ORG, "m": i})
    _calls(conn, "l1_relevance", n=5, hours_ago=96)
    _, truncation = _both(conn)
    assert truncation.verdict == ph.FAIL and "l4_bundle: 3 failures all at 1400" in \
        truncation.measured


def test_a_lane_silent_for_longer_than_the_lookback_is_not_named(conn):
    """A lane retired a month ago is not a lane this check should vouch for."""
    _calls(conn, "l1_extract", n=6, hours_ago=1)
    _calls(conn, "old_lane", n=6, hours_ago=24 * (ph.SILENT_LANE_LOOKBACK_DAYS + 2))
    for check in _both(conn):
        assert check.verdict == ph.PASS and "old_lane" not in check.measured
