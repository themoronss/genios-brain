"""STEP-02 · the change gate's store: one row per subject, saying what it was decided on.

    pytest tests/test_migration_0191_reasoning_fingerprints.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_migration_0191_reasoning_fingerprints.py -q

`migrations/0191_reasoning_fingerprints.sql` (tree `yc2_w27_s02/M20.C2.L-contract.V0.U01`). The gate
skips a subject only when what its decision depends on is unchanged, so it has to remember, per
subject, the fingerprint the last decision was made on, the run that made it and what came of it.

The vocabularies are closed in the schema, the way `pipeline_counters` closes its stages: a typo in
a lane or an outcome must be a refused write, never a new value nobody reads. The table is the
tenant's runtime state, so `/reset` wipes it and deleting the account cascades it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from genios_engine.api import account_routes

ORG = "fp0191_org"
AT = datetime(2026, 10, 6, 12, 0, tzinfo=timezone.utc)


def test_reset_wipes_the_fingerprints():
    assert "reasoning_fingerprints" in account_routes._ORG_SCOPED_TABLES


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'fp0191@example.test') "
                       "on conflict do nothing"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _insert(c, **over):
    row = {"o": ORG, "k": "sit_1|expertise.account_admin", "lane": "compiled",
           "fp": "fp_" + "0" * 24, "outcome": "emitted", "run": "run_1", "at": AT}
    row.update(over)
    c.execute(text(
        "insert into reasoning_fingerprints (org_id, subject_key, lane, fingerprint, outcome, "
        "run_id, decided_at, last_checked_at) values "
        "(:o, :k, :lane, :fp, :outcome, :run, :at, :at)"), row)


@pytest.mark.pg
def test_the_table_has_the_columns_the_gate_reads(engine):
    with engine.connect() as c:
        cols = {r.column_name: (r.data_type, r.is_nullable) for r in c.execute(text(
            "select column_name, data_type, is_nullable from information_schema.columns "
            "where table_name = 'reasoning_fingerprints'"))}
    assert cols == {
        "org_id": ("text", "NO"), "subject_key": ("text", "NO"), "lane": ("text", "NO"),
        "fingerprint": ("text", "NO"), "outcome": ("text", "NO"), "run_id": ("text", "YES"),
        "decided_at": ("timestamp with time zone", "NO"),
        "last_checked_at": ("timestamp with time zone", "NO"), "skips": ("integer", "NO"),
    }


@pytest.mark.pg
def test_one_row_per_subject(engine):
    with engine.begin() as c:
        _insert(c)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, fp="fp_" + "1" * 24)


@pytest.mark.pg
@pytest.mark.parametrize("column, value", [("lane", "compiled_v2"), ("outcome", "skipped")])
def test_a_lane_or_outcome_outside_the_vocabulary_is_refused(engine, column, value):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, **{column: value})


@pytest.mark.pg
@pytest.mark.parametrize("lane", ["compiled", "legacy", "native"])
@pytest.mark.parametrize("outcome", ["emitted", "standing", "deferred", "indeterminate",
                                     "suppressed", "shadow"])
def test_every_lane_and_outcome_in_the_vocabulary_is_accepted(engine, lane, outcome):
    with engine.begin() as c:
        _insert(c, k=f"{lane}|{outcome}", lane=lane, outcome=outcome)
        assert c.execute(text("select skips from reasoning_fingerprints where org_id = :o and "
                              "subject_key = :k"), {"o": ORG, "k": f"{lane}|{outcome}"}).scalar() == 0


@pytest.mark.pg
def test_a_negative_skip_count_is_refused(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c)
            c.execute(text("update reasoning_fingerprints set skips = -1 where org_id = :o"),
                      {"o": ORG})


@pytest.mark.pg
def test_deleting_the_account_takes_the_fingerprints(engine):
    with engine.begin() as c:
        _insert(c)
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        assert c.execute(text("select count(*) from reasoning_fingerprints where org_id = :o"),
                         {"o": ORG}).scalar() == 0
