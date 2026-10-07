"""STEP-06 · a situation's end after admission: one row per admitted candidate, saying what came of it.

    pytest tests/test_migration_0194_situation_outcomes.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_migration_0194_situation_outcomes.py -q

`migrations/0194_situation_outcomes.sql` (tree `yc2_w27_s06/M24.C2.L-contract.V0.U01`). The admission
gate records admit / hold / reject (0122) and the change gate every decided subject (0191); what ended
in between was a counter in a log line (`speedrun008/YC-II W27/` STEP-06 §8). The vocabulary is closed
in the schema — a typo in an outcome is a refused write, never a new value nobody reads — and a row
hangs off its admission decision, so the ledger it explains cannot be deleted from under it.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

ORG = "so0194_org"
AT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'so0194@example.test')"),
                  {"o": ORG})
        for decision in ("dec_1", "dec_2"):
            c.execute(text(
                "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
                "candidate_hash, outcome, candidate, schema_version, decided_at) values "
                "(:d, :o, 'sit_1', :h, 'admit', cast('{}' as jsonb), 'v1', :at)"),
                {"d": decision, "o": ORG, "h": f"hash_{decision}", "at": AT})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from situation_admission_decisions where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _insert(c, **over):
    row = {"o": ORG, "d": "dec_1", "s": "sit_1", "outcome": "no_route",
           "reason": "predicate_rejected", "at": AT}
    row.update(over)
    c.execute(text(
        "insert into situation_outcomes (org_id, decision_id, situation_id, outcome, reason, "
        "recorded_at, last_seen_at) values (:o, :d, :s, :outcome, :reason, :at, :at)"), row)


@pytest.mark.pg
def test_the_table_has_the_columns_the_readers_need(engine):
    with engine.connect() as c:
        cols = {r.column_name: (r.data_type, r.is_nullable) for r in c.execute(text(
            "select column_name, data_type, is_nullable from information_schema.columns "
            "where table_name = 'situation_outcomes'"))}
    assert cols == {
        "org_id": ("text", "NO"), "decision_id": ("text", "NO"), "situation_id": ("text", "NO"),
        "outcome": ("text", "NO"), "reason": ("text", "YES"),
        "recorded_at": ("timestamp with time zone", "NO"),
        "last_seen_at": ("timestamp with time zone", "NO"), "sweeps": ("integer", "NO"),
    }


@pytest.mark.pg
def test_one_row_per_admitted_candidate(engine):
    with engine.begin() as c:
        _insert(c)
        _insert(c, d="dec_2", outcome="decided", reason=None)
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, outcome="error")


@pytest.mark.pg
@pytest.mark.parametrize("outcome", ["decided", "no_route", "incomplete", "conflict",
                                     "required_missing", "unsupported", "no_tenant_pack",
                                     "budget_exhausted", "error"])
def test_every_named_outcome_is_accepted(engine, outcome):
    with engine.begin() as c:
        _insert(c, outcome=outcome)


@pytest.mark.pg
def test_an_unknown_outcome_is_refused(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, outcome="vanished")


@pytest.mark.pg
def test_a_row_needs_the_admission_it_explains(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _insert(c, d="dec_nobody_admitted")


@pytest.mark.pg
def test_deleting_the_admission_deletes_its_outcome(engine):
    with engine.begin() as c:
        _insert(c)
        c.execute(text("delete from situation_admission_decisions where decision_id = 'dec_1'"))
        left = c.execute(text("select count(*) from situation_outcomes where org_id = :o"),
                         {"o": ORG}).scalar()
    assert left == 0


@pytest.mark.pg
def test_deleting_the_tenant_cascades(engine):
    with engine.begin() as c:
        _insert(c)
        c.execute(text("delete from situation_admission_decisions where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        left = c.execute(text("select count(*) from situation_outcomes where org_id = :o"),
                         {"o": ORG}).scalar()
    assert left == 0
