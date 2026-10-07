"""STEP-07 · the health check: the company brief exists and is current.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_pipeline_health_company_brief.py -q

`scripts/pipeline_health.check_the_company_brief_exists_and_is_current` (tree `yc2_w27_s07 ·
M25.C6.L-interface.V2.U01`). Until the founder accepts a line, no prompt carries the brief — so the check
fails, and names what waits: the proposals, and the way to draft one. Once a line is accepted it passes,
naming the version, the lines the budget left out, the proposals still waiting and when the weekly review
last ran. It reads through the audit's read-only connection, as every check does.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

ORG = "org_s07_health_brief"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def _health():
    import importlib
    return importlib.import_module("scripts.pipeline_health")


def test_the_check_runs_in_every_audit():
    assert _health().check_the_company_brief_exists_and_is_current in _health().CHECKS


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the check needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, company, email) "
                       "values (:o, 'Arjun Rao', 'Nimbus Labs', 'arjun@health.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _check(engine):
    from scripts._gate import read_only_connection
    conn = read_only_connection(engine)
    try:
        return _health().check_the_company_brief_exists_and_is_current(conn, ORG)
    finally:
        conn.close()


def test_it_fails_with_no_accepted_line_and_names_what_waits(engine):
    from genios_engine.platform import company_brief_store as store
    with engine.begin() as c:
        store.propose(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                      proposed_by="drafter", at=AT)
    check = _check(engine)
    assert not check.ok
    assert check.measured == ("no accepted line — no prompt carries a brief; 1 proposal(s) waiting; "
                              "no weekly review yet")
    assert [d for d in check.detail if d.startswith("waiting: ")] == [
        next(d for d in check.detail if "raise the pre-seed round" in d)]
    assert "scripts/draft_company_brief.py" in check.fix and "scripts/company_brief.py" in check.fix


def test_it_passes_once_a_line_is_accepted_and_names_the_version_and_the_review(engine):
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.company_brief import brief_for
    with engine.begin() as c:
        store.add(c, org_id=ORG, section="watchlist", words="Hub71 — the program",
                  domain="hub71.com", decided_by="founder", at=AT)
        c.execute(text("insert into company_brief_reviews (org_id, week_key, started_at, finished_at, "
                       " outcome, proposed) values (:o, '2026-W41', :t, :t, 'proposed', 2)"),
                  {"o": ORG, "t": AT})
        version = brief_for(c, ORG).version
    check = _check(engine)
    assert check.ok, check.measured
    assert check.measured == (f"version {version}, 1 accepted line(s), 0 left out by the budget; "
                              "0 proposal(s) waiting; last weekly review 2026-W41 (proposed, 2 "
                              "proposed)")
