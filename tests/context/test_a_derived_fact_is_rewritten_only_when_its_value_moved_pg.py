"""L3 rebuild 2b — a derived fact is rewritten only when its value moved (real Postgres).

Prod 19 Oct: `graph_facts` took 120 k updates on 2.2 k derived rows — every recompute rewrote its row with the
SWEEP's clock as `occurred_at` / `valid_from`, so a fact that had held for a week read as true since this morning
(the bitemporal "when it became true" lost) and every sweep left dead tuples behind. Now an unchanged recompute
leaves the row exactly as it was; a new value rewrites it (and dates it); a retired fact the writer computes again
comes back — the reversal `derived._UPSERT_FACT` exists for.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_derived_fact_is_rewritten_only_when_its_value_moved_pg.py -q
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.derived import _write_fact

pytestmark = pytest.mark.pg

ORG = "org_l3_fact_diff"
NODE = "node_l3_fact_diff"
T0 = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'F', 'facts@example.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from graph_facts where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _write(engine, value, at):
    with engine.begin() as c:
        _write_fact(c, ORG, NODE, "derived.momentum", value, "string", at)


def _row(engine):
    with engine.connect() as c:
        return c.execute(text("select xmin::text as x, value, valid_from, status from graph_facts "
                              "where org_id = :o and field = 'derived.momentum'"), {"o": ORG}).one()


def test_an_unchanged_recompute_leaves_the_fact_as_it_was(engine):
    _write(engine, '"rising"', T0)
    before = _row(engine)
    _write(engine, '"rising"', T0 + timedelta(hours=6))
    after = _row(engine)
    assert after.x == before.x, "no new tuple for an unchanged value"
    assert after.valid_from == T0, "the value has held since it was first computed, not since this sweep"


def test_a_new_value_is_written_and_dated_now(engine):
    _write(engine, '"rising"', T0)
    _write(engine, '"falling"', T0 + timedelta(days=2))
    row = _row(engine)
    assert row.value == "falling" and row.valid_from == T0 + timedelta(days=2)


def test_a_retired_fact_computed_again_comes_back(engine):
    _write(engine, '"rising"', T0)
    with engine.begin() as c:
        c.execute(text("update graph_facts set status = 'superseded', valid_to = :t where org_id = :o"),
                  {"o": ORG, "t": T0 + timedelta(days=1)})
    _write(engine, '"rising"', T0 + timedelta(days=3))
    row = _row(engine)
    assert row.status == "active", "the same value written again revives a retired fact"
