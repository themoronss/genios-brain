"""STEP-03 · every mail carries an attention tier, and a sync counts what it archived.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/test_migration_0192_attention_and_archive.py -q

`migrations/0192_attention_and_archive.sql` (tree `yc2_w27_s03/M21.C1.L-contract.V0.U01`). The gate stops
deleting mail: what it would have dropped it ARCHIVES — kept, read by no model — and every kept mail
says which tier it is in and why. The tier vocabulary is closed in the schema, the way
`pipeline_counters` closes its stages: a typo is a refused write, never a fourth tier nobody reads.
`skim` is declared for STEP-07 (the brief assigns it); nothing writes it yet.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.pg
ORG = "m0192_org"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'm0192@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _columns(c, table: str) -> dict:
    return {r.column_name: (r.data_type, r.is_nullable, r.column_default) for r in c.execute(text(
        "select column_name, data_type, is_nullable, column_default from information_schema.columns "
        "where table_name = :t"), {"t": table})}


def _event(c, *, key: str, attention, reason=None, outcome="archived"):
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
        "dedup_key, actor, occurred_at, captured_at, sync_mode, schema_version, outcome, "
        "attention, attention_reason) values (:e, :o, 'conn_m0192', 'gmail', 'message', :k, :d, "
        "cast('{}' as jsonb), :t, :t, 'backfill', 3, :outcome, :a, :r)"),
        {"e": f"evt_{key}", "o": ORG, "k": key, "d": f"gmail:message:{key}", "a": attention,
         "r": reason, "outcome": outcome, "t": datetime(2026, 10, 6, tzinfo=timezone.utc)})


def test_source_events_carry_a_tier_and_its_reason(engine):
    with engine.connect() as c:
        cols = _columns(c, "source_events")
    assert cols["attention"][:2] == ("text", "YES")
    assert cols["attention_reason"][:2] == ("text", "YES")


def test_a_sync_run_counts_what_it_archived(engine):
    with engine.connect() as c:
        archived = _columns(c, "l1_sync_runs")["archived"]
    assert archived[0] == "integer" and archived[1] == "NO" and "0" in str(archived[2])


@pytest.mark.parametrize("tier", ["deep", "skim", "archive"])
def test_every_tier_in_the_vocabulary_is_accepted(engine, tier):
    with engine.begin() as c:
        _event(c, key=f"ok_{tier}", attention=tier, reason="N-02")


def test_no_tier_is_a_value_too(engine):
    """A dropped non-mail object (S0 `out_of_scope`, a structured refusal) carries no tier."""
    with engine.begin() as c:
        _event(c, key="none", attention=None, outcome="dropped")


def test_a_tier_outside_the_vocabulary_is_refused(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as c:
            _event(c, key="bad", attention="later")
