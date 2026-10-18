"""STEP-06 · the tenant reset and account erasure wipe what came of each admitted situation.

    pytest tests/test_reset_wipes_situation_outcomes.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_reset_wipes_situation_outcomes.py -q

Tree `yc2_w27_s06 · M24.C2.L-data.V1.U02`. `situation_outcomes` (0194) is tenant runtime state, like
`reasoning_fingerprints` (0191): `/reset` erases it, before the admission ledger it hangs off.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.api import account_routes

ORG = "reset_so_org"
AT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


def test_reset_names_the_table_before_the_ledger_it_hangs_off():
    tables = account_routes._ORG_SCOPED_TABLES
    assert "situation_outcomes" in tables
    assert tables.index("situation_outcomes") < tables.index("situation_admission_decisions")


@pytest.mark.pg
def test_the_wipe_leaves_no_outcome_of_the_tenant():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'r@so.test')"),
                  {"o": ORG})
        c.execute(text(
            "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
            "candidate_hash, outcome, candidate, schema_version, decided_at) values "
            "('dec_r', :o, 'sit_r', 'h', 'admit', cast('{}' as jsonb), 'v1', :at)"),
            {"o": ORG, "at": AT})
        c.execute(text(
            "insert into situation_outcomes (org_id, decision_id, situation_id, outcome, "
            "recorded_at, last_seen_at) values (:o, 'dec_r', 'sit_r', 'no_route', :at, :at)"),
            {"o": ORG, "at": AT})
    try:
        with eng.begin() as c:
            wiped = account_routes._wipe(c, ORG)
            left = c.execute(text("select count(*) from situation_outcomes where org_id = :o"),
                             {"o": ORG}).scalar()
        assert wiped["situation_outcomes"] == 1 and left == 0
    finally:
        with eng.begin() as c:
            c.execute(text("delete from orgs where id = :o"), {"o": ORG})
