"""STEP-06 · the store of what came of each admitted situation — one row per candidate, its current end.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_situation_outcome_store.py -q

Tree `yc2_w27_s06 · M24.C2.L-data.V1.U01`. One row per admitted candidate (its admission
`decision_id`): the same end again moves the clock and the count, a different end replaces it and
starts the count again — never a row per sweep.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

ORG = "so_store_org"
AT = datetime(2026, 10, 7, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'so@example.test')"),
                  {"o": ORG})
        c.execute(text(
            "insert into situation_admission_decisions (decision_id, org_id, situation_id, "
            "candidate_hash, outcome, candidate, schema_version, decided_at) values "
            "('dec_1', :o, 'sit_1', 'h1', 'admit', cast('{}' as jsonb), 'v1', :at)"),
            {"o": ORG, "at": AT})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _rows(eng):
    with eng.connect() as c:
        return c.execute(text("select count(*) from situation_outcomes where org_id = :o"),
                         {"o": ORG}).scalar()


def _row(c, decision_id="dec_1"):
    return c.execute(text(
        "select outcome, reason, recorded_at, last_seen_at, sweeps from situation_outcomes "
        "where org_id = :o and decision_id = :d"), {"o": ORG, "d": decision_id}).first()


def test_the_same_end_again_moves_the_clock_and_the_count_not_the_rows(engine):
    from genios_engine.reason import situation_outcome_store as so
    for i in range(3):
        with engine.begin() as c:
            so.record(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                      outcome=so.NO_ROUTE, reason="predicate_rejected",
                      at=AT + timedelta(minutes=30 * i))
    with engine.connect() as c:
        row = _row(c)
    assert _rows(engine) == 1
    assert (row.outcome, row.reason, row.sweeps) == ("no_route", "predicate_rejected", 3)
    assert row.recorded_at == AT and row.last_seen_at == AT + timedelta(minutes=60)


def test_a_different_end_replaces_the_outcome_and_starts_again(engine):
    from genios_engine.reason import situation_outcome_store as so
    with engine.begin() as c:
        so.record(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                  outcome=so.BUDGET_EXHAUSTED, reason=None, at=AT)
        so.record(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                  outcome=so.BUDGET_EXHAUSTED, reason=None, at=AT + timedelta(hours=1))
        so.record(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                  outcome=so.DECIDED, reason=None, at=AT + timedelta(days=1))
        row = _row(c)
    assert (row.outcome, row.sweeps, row.recorded_at) == ("decided", 1, AT + timedelta(days=1))
    assert _rows(engine) == 1


def test_an_unknown_outcome_is_refused_before_the_database_sees_it(engine):
    from genios_engine.reason import situation_outcome_store as so
    with engine.begin() as c:
        with pytest.raises(ValueError):
            so.record(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                      outcome="vanished", reason=None, at=AT)


def test_the_store_and_the_schema_name_the_same_outcomes(engine):
    from genios_engine.reason import situation_outcome_store as so
    with engine.connect() as c:
        definition = c.execute(text(
            "select pg_get_constraintdef(oid) from pg_constraint "
            "where conname = 'situation_outcomes_outcome_check'")).scalar()
    assert {o for o in so.OUTCOMES if f"'{o}'" in definition} == set(so.OUTCOMES)
    assert so.STOPS == so.OUTCOMES - {so.DECIDED}


def test_an_unchanged_pass_keeps_the_end_and_moves_only_its_clock(engine):
    from genios_engine.reason import situation_outcome_store as so
    with engine.begin() as c:
        so.record(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                  outcome=so.DECIDED, reason="emitted", at=AT)
        so.record_seen(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                       at=AT + timedelta(minutes=30))
        so.record_seen(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1",
                       at=AT + timedelta(minutes=60))
        row = _row(c)
    assert (row.outcome, row.reason, row.sweeps) == ("decided", "emitted", 3)
    assert row.recorded_at == AT and row.last_seen_at == AT + timedelta(minutes=60)


def test_a_candidate_decided_before_the_table_existed_is_written_as_unchanged(engine):
    from genios_engine.reason import situation_outcome_store as so
    with engine.begin() as c:
        so.record_seen(c, org_id=ORG, decision_id="dec_1", situation_id="sit_1", at=AT)
        row = _row(c)
    assert (row.outcome, row.reason, row.sweeps) == ("decided", "unchanged", 1)

