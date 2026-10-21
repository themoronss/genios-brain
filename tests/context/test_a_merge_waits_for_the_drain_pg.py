"""A merge takes the org's graph version first, as every graph writer does — so it never interleaves with a drain.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_merge_waits_for_the_drain_pg.py -q

L3 audit, 21 Oct 2026. Every graph writer runs `bump_version` first, which locks the org's `graph_versions` row
until it commits — that is what makes the drain's parallel workers commit one at a time. `merge.apply_merge` and
`reverse_merge` skipped it: a drain writing to the merged node between the merge's snapshot and its close
committed facts onto a closed node no reader sees (`health.orphan_fact`), and every read keyed on the version
(the L2 snapshot's `graph@<revision>`, the device slices) never saw the merge. Proved by `lock_timeout`: while a
drain's transaction holds the version, the merge cannot start.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import exc as sa
from sqlalchemy import text

from genios_engine.context.merge import apply_merge, reverse_merge

pytestmark = pytest.mark.pg
ORG = f"org_merge_waits_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def org(pg_store):
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                  {"o": ORG, "e": f"{ORG}@example.test"})
        a = pg_store.find_or_create_node(c, org_id=ORG, node_type="company", canonical_key="company:acme",
                                         display_name="Acme", event_id=None)
        b = pg_store.find_or_create_node(c, org_id=ORG, node_type="company", canonical_key="company:acme-inc",
                                         display_name="Acme Inc", event_id=None)
    yield pg_store, a, b
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id=:o"), {"o": ORG})


def _version(engine) -> int:
    with engine.connect() as c:
        return int(c.execute(text("select coalesce(max(graph_version), 0) from graph_versions where org_id=:o"),
                             {"o": ORG}).scalar())


def test_a_merge_moves_the_graph_version_and_so_does_its_reversal(org):
    store, a, b = org
    before = _version(store.engine)
    with store.engine.begin() as c:
        merge_id = apply_merge(c, org_id=ORG, survivor_node_id=a, merged_node_id=b, reason="same company")["merge_id"]
    assert _version(store.engine) > before, "a merge changed the graph and the version said nothing"
    after_merge = _version(store.engine)
    with store.engine.begin() as c:
        reverse_merge(c, org_id=ORG, merge_id=merge_id)
    assert _version(store.engine) > after_merge


def test_a_merge_cannot_start_while_a_drain_holds_the_org(org):
    store, a, b = org
    drain = store.engine.connect()
    tx = drain.begin()
    try:
        store.bump_version(drain, ORG)                  # a drain's event, mid-transaction
        with store.engine.connect() as c:
            with c.begin():
                c.execute(text("set local lock_timeout = '300ms'"))
                with pytest.raises(sa.OperationalError, match="lock timeout"):
                    apply_merge(c, org_id=ORG, survivor_node_id=a, merged_node_id=b, reason="same company")
    finally:
        tx.rollback()
        drain.close()
    with store.engine.begin() as c:                     # the drain gone, the merge goes through
        assert apply_merge(c, org_id=ORG, survivor_node_id=a, merged_node_id=b, reason="same company")
