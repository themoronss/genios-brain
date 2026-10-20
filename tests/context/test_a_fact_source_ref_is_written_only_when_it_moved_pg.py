"""L3 rebuild 2a — a derived fact's receipts are written only when they moved (real Postgres).

Measured on prod 19 Oct: `graph_source_refs` took 1.23 M inserts and 1.23 M deletes for 17 k live rows — every
sweep deleted every derived receipt and inserted it again. Now a repeated write of the same receipts leaves every
row exactly as it was (the same tuple — `xmin` does not move, so no dead row, no vacuum debt); a changed receipt
rewrites that row alone; a member that left is deleted alone; another writer's refs are never touched.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_fact_source_ref_is_written_only_when_it_moved_pg.py -q
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from genios_engine.context.derived_provenance import EventReceipt, write_fact_source_refs

pytestmark = pytest.mark.pg

ORG = "org_l3_refs_diff"
FACT = "fv_l3_refs_diff"


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'R', 'refs@example.test')"), {"o": ORG})
        c.execute(text("insert into graph_source_refs (source_ref_id, org_id, fact_version_id, event_id, evidence, "
                       " extractor_version) values ('ref_other_writer', :o, :f, 'evt_x', '{}'::jsonb, 'other.v1')"),
                  {"o": ORG, "f": FACT})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from graph_source_refs where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _r(event, group="gmail", quote="q"):
    return EventReceipt(event_id=event, source="gmail", independence_group=group, occurred_at=None,
                        source_object_id=f"m_{event}", evidence={"quote": quote})


def _write(engine, receipts):
    with engine.begin() as c:
        write_fact_source_refs(c, org_id=ORG, fact_version_id=FACT, receipts=tuple(receipts))


def _rows(engine):
    with engine.connect() as c:
        return {r.event_id: (str(r.xmin), r.extractor_version) for r in c.execute(text(
            "select event_id, xmin, extractor_version from graph_source_refs where org_id = :o"), {"o": ORG})}


def test_the_same_receipts_again_write_nothing(engine):
    _write(engine, [_r("evt_a"), _r("evt_b")])
    before = _rows(engine)
    _write(engine, [_r("evt_a"), _r("evt_b")])
    assert _rows(engine) == before, "an unchanged receipt is not rewritten — same tuple, no dead row"


def test_only_what_moved_is_written(engine):
    _write(engine, [_r("evt_a"), _r("evt_b"), _r("evt_c")])
    before = _rows(engine)
    _write(engine, [_r("evt_a"), _r("evt_b", quote="changed")])          # b changed, c left, a the same
    after = _rows(engine)
    assert after["evt_a"] == before["evt_a"], "an unchanged receipt keeps its tuple"
    assert after["evt_b"][0] != before["evt_b"][0], "a changed receipt is rewritten"
    assert "evt_c" not in after, "a member that left is deleted"
    assert after["evt_x"] == before["evt_x"], "another writer's refs are never touched"


def test_no_receipts_left_deletes_this_writers_refs_only(engine):
    _write(engine, [_r("evt_a")])
    _write(engine, [])
    assert set(_rows(engine)) == {"evt_x"}
