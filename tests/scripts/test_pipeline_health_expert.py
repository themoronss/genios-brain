"""STEP-12 · the health of the expert pass — reviews per day, refusals by reason, spend against the cap.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_expert.py -q

`scripts/pipeline_health.check_the_expert_says_why_and_stays_in_budget` (tree `yc2_w27_s12`
M32.C3.L-interface.V3.U06), read-only on real rows. It reports the last day's reviews by status and the
refusals by what they said (`expert_reviews`), and today's spend against the expert's own cap (`06` D7: $2)
from the ledger its budget is read from — every R-7 consult in `l4_r_site_calls`, a retried one included.
It FAILS while a row that is not valid has no reason — the schema refuses one, so this is the schema
changed under it — or while today's spend is over the cap, which is a gate that let a call through. No
review in the window passes, saying so.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.pg
ORG = "health_expert_org"


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
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'he@example.test')"),
                  {"o": ORG})
    with engine.connect() as c:
        yield c
        c.rollback()
    with engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _row(c, fp, status, *, reason=None, cost=27_000, hours_ago=1.0):
    c.execute(text(
        "insert into expert_reviews (org_id, file_id, fingerprint, model, prompt_version, "
        " dossier_digest, status, reason, review, cost_micro_usd, reviewed_at, inputs, triggers) "
        "values (:o, 'node_f', :fp, 'claude-sonnet-5', 'expert-review.v2', 'sha256:d', :s, :r, "
        " case when :s = 'valid' then cast('{\"mode\": \"wait\"}' as jsonb) end, :cost, "
        " now() - make_interval(secs => :secs), cast('{}' as jsonb), cast('[]' as jsonb))"),
        {"o": ORG, "fp": fp, "s": status, "r": reason, "cost": cost, "secs": hours_ago * 3600})


def _spent(c, cost, *, secs_ago=0.0, site="R-7"):
    """One consult on the R-site ledger, as the gate's receipt writes it."""
    c.execute(text(
        "insert into l4_r_site_calls (org_id, site, outcome, tier, cache_key, cost_micro_usd, created_at) "
        "values (:o, :site, 'ran', 'T2', 'k', :cost, now() - make_interval(secs => :secs))"),
        {"o": ORG, "site": site, "cost": cost, "secs": secs_ago})


def _check(c):
    return _module().check_the_expert_says_why_and_stays_in_budget(c, ORG)


def test_no_review_in_the_window_passes_saying_so(conn):
    check = _check(conn)
    assert check.ok and check.measured == "no expert review in the last 24 hours"


def test_it_reports_reviews_by_status_refusals_by_reason_and_the_days_spend(conn):
    _row(conn, "ffp-1", "valid", hours_ago=0)
    _row(conn, "ffp-2", "valid", hours_ago=0)
    _row(conn, "ffp-3", "refused", reason="number_not_in_dossier: 4317", hours_ago=0)
    _row(conn, "ffp-4", "refused", reason="number_not_in_dossier: 4317", hours_ago=0)
    _row(conn, "ffp-5", "over_budget", reason="daily_budget_exhausted", cost=0, hours_ago=0)
    _row(conn, "ffp-6", "valid", hours_ago=30)                       # outside the window
    for _ in range(4):
        _spent(conn, 27_000)                                         # four consults that cost
    _spent(conn, 999_000, secs_ago=3 * 86400)                        # another day's
    _spent(conn, 900_000, site="R-2")                                # the narration's own day
    check = _check(conn)
    assert check.ok, check
    assert check.measured.startswith("5 reviews in 24 h — over_budget 1, refused 2, valid 2")
    assert "spent today $0.11 of $2.00" in check.measured
    assert check.detail == ["refused × 2: number_not_in_dossier: 4317",
                            "over_budget × 1: daily_budget_exhausted"]


def test_a_refusal_with_no_reason_fails(conn):
    conn.execute(text("alter table expert_reviews drop constraint expert_reviews_reason_check"))
    _row(conn, "ffp-1", "refused", reason="  ")
    check = _check(conn)
    assert not check.ok and "1 not valid with no reason" in check.measured
    assert "expert_reviews_reason_check" in check.fix


def test_spend_over_the_cap_fails(conn):
    for i in range(3):
        _row(conn, f"ffp-{i}", "valid", cost=700_000, hours_ago=0)
        _spent(conn, 700_000)
    check = _check(conn)
    assert not check.ok and "spent today $2.10 of $2.00" in check.measured
    assert "budget" in check.fix


def test_spend_over_the_cap_with_no_review_still_fails(conn):
    """I2a (`yc2_w27_s1718` M40.C3.L-logic.V0.U07, second crosscheck): the spend is read BEFORE
    `expert_reviews`, so a day over its cap is a FAIL even when nothing was reviewed — the probe's
    own shape, a spend row with no review alongside it (`review_file` is the only R-7 caller and
    every spending outcome writes a review row, so this state is a probe's doing, not a live one —
    but the ordering fix means it is never read as NO DATA either way)."""
    for _ in range(3):
        _spent(conn, 700_000)
    check = _check(conn)
    assert not check.ok and not check.no_data
    assert check.measured == "no expert review in the last 24 hours; spent today $2.10 of $2.00"
    assert "budget" in check.fix


def test_it_is_one_of_the_checks_the_script_runs_and_reads_the_gates_own_cap():
    from genios_engine.reason.bundle.sites import SITE_EXPERT
    assert _module().check_the_expert_says_why_and_stays_in_budget in _module().CHECKS
    assert _module().EXPERT_DAILY_CAP_MICRO_USD == 2_000_000 and SITE_EXPERT == "R-7"
