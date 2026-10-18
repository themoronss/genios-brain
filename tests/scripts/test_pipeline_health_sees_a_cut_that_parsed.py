"""pipeline_health sees a call cut at its ceiling whether or not it parsed, and an expert day mostly cut.

    GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest -q tests/scripts/test_pipeline_health_sees_a_cut_that_parsed.py

⛔ `yc2_w27_s18` M50.C4.L-interface.V1.U11 (the 13 Oct audit's T5-8, s5t-F6). Two blind spots:

  * the ceiling check read only failures (`not success`). A cut that `parse_json_lenient` closed was a
    success with no error — on every R-site, in the drafter, in `l5_render` — so a lane whose every call
    was cut but parsed was invisible. Since M50.C1.L-contract.V0.U01 such a call names the truncation in
    `error` (`truncated: …`) and since M50.C2.L-logic.V3.U04 the gate records it failed; the check now
    counts every call whose error says `truncated:`, whatever `success` says;
  * the expert's check passed a day on which every review was `truncated` (the Sonnet live pass of 12 Oct:
    203 of 203 cut at 4,000). More than half of a day's reviews cut is now a FAIL: the ceiling is too
    small for what the model writes — thinking included.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from scripts import pipeline_health as ph

ORG = "org_t5_cut_parsed"
CUT = "truncated: the model hit max_tokens and the JSON was cut mid-structure (max_tokens=2400)"


@pytest.fixture
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the checks read llm_costs and expert_reviews")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    try:
        c.execute(text("insert into orgs (id, name) values (:o, 'Cut Parsed') "
                       "on conflict (id) do nothing"), {"o": ORG})
        yield c
    finally:
        tx.rollback()
        c.close()


def _call(c, purpose, *, out, ok, error=None, minutes_ago=5):
    c.execute(text(
        "insert into llm_costs (org_id, model, purpose, input_tokens, output_tokens, success, error, "
        "created_at) values (:o, 'claude-sonnet-5', :p, 1000, :out, :ok, :e, :at)"),
        {"o": ORG, "p": purpose, "out": out, "ok": ok, "e": error,
         "at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)})


def _truncation(c):
    return ph.check_no_silent_truncation(c, ORG, hours=24)


def test_a_lane_whose_cuts_all_parsed_fails(conn):
    for i in range(3):
        _call(conn, "l4_bundle", out=2400, ok=True, error=CUT, minutes_ago=i)
    for i in range(3):
        _call(conn, "l1_extract", out=500 + i, ok=True, minutes_ago=i)
    check = _truncation(conn)
    assert check.verdict == ph.FAIL, check.measured
    assert "l4_bundle: 3" in check.measured and "2400" in check.measured


def test_parsed_and_unparsed_cuts_count_together(conn):
    _call(conn, "l4_bundle", out=2400, ok=False, error=CUT)
    _call(conn, "l4_bundle", out=2400, ok=False, error=CUT, minutes_ago=6)
    _call(conn, "l4_bundle", out=2400, ok=True, error=CUT, minutes_ago=7)
    assert _truncation(conn).verdict == ph.FAIL


def test_successes_with_no_error_are_not_cuts(conn):
    for i in range(4):
        _call(conn, "l4_bundle", out=2400, ok=True, minutes_ago=i)
    assert _truncation(conn).verdict == ph.PASS


def _review(c, n, status, reason=None):
    c.execute(text(
        "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, "
        " dossier_digest, status, reason, review, cost_micro_usd, reviewed_at, inputs, triggers) "
        "values (:o, 'node_f', :fp, 'claude-sonnet-5', 'expert-review.v2', 'sha256:d', :s, :r, "
        " case when :s = 'valid' then cast('{\"mode\": \"wait\"}' as jsonb) end, 27000, "
        " now() - interval '1 hour', cast('{}' as jsonb), cast('[]' as jsonb))"),
        {"o": ORG, "fp": f"fp-{status}-{n}", "s": status, "r": reason})


def _expert(c):
    return ph.check_the_expert_says_why_and_stays_in_budget(c, ORG)


def test_an_expert_day_mostly_cut_fails(conn):
    for i in range(3):
        _review(conn, i, "truncated", "truncated_at_the_token_ceiling")
    _review(conn, 9, "valid")
    check = _expert(conn)
    assert not check.ok and "3 of 4 truncated" in check.measured, check.measured
    assert "ceiling" in check.fix and "sites.py" in check.fix


def test_an_expert_day_cut_by_half_or_less_passes(conn):
    for i in range(2):
        _review(conn, i, "truncated", "truncated_at_the_token_ceiling")
    for i in range(2):
        _review(conn, 10 + i, "valid")
    assert _expert(conn).ok
