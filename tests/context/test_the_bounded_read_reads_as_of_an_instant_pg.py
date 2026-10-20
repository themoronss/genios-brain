"""L3 rebuild 4a — the bounded read L2 uses can read the graph as it stood at an instant (real Postgres).

Atlas v2 (the read API L2 uses; P2·13): "what did we know on 29 Sep?" returns the same answer forever. The whole-graph
`GraphStore.read_graph(as_of=)` could; the bounded walk could not. Now `ReadRequest(as_of=)` reads an edge only if we
had learned it by then (`recorded_at`) and it had not closed — the one predicate `graph_store._WINDOW_AT`. With no
instant the read is exactly what it was.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_the_bounded_read_reads_as_of_an_instant_pg.py -q
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.context.bounded_read import ReadRequest, read_bounded

pytestmark = pytest.mark.pg

ORG = "org_l3_as_of"
T0 = datetime(2026, 9, 1, 9, tzinfo=timezone.utc)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.platform.db import get_engine
    eng = get_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, 'A', 'asof@example.test')"), {"o": ORG})
        for ev, to, recorded, closed in (("e_open", "n_open", T0, None),
                                          ("e_closed", "n_closed", T0, T0 + timedelta(days=5)),
                                          ("e_late", "n_late", T0 + timedelta(days=10), None)):
            c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, "
                           " to_node_id, valid_from, recorded_at, valid_to) values (:ev, :ev, :o, 'works_with', "
                           " 'hub', :to, :rec, :rec, :closed)"),
                      {"ev": ev, "o": ORG, "to": to, "rec": recorded, "closed": closed})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from graph_edges where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _nodes(engine, as_of):
    with engine.connect() as c:
        view = read_bounded(c, ORG, ReadRequest(seeds=("hub",), max_hops=2, max_nodes=100, as_of=as_of))
    return set(view.node_ids) - {"hub"}


def test_now_reads_the_open_graph_as_before(engine):
    assert _nodes(engine, None) == {"n_open", "n_late"}


def test_an_instant_reads_what_was_known_and_still_true_then(engine):
    assert _nodes(engine, T0 + timedelta(days=2)) == {"n_open", "n_closed"}, \
        "the closed edge still held; the late one was not yet known"
    assert _nodes(engine, T0 + timedelta(days=7)) == {"n_open"}
    assert _nodes(engine, T0 - timedelta(days=1)) == set(), "before anything was known: nothing"


def test_the_as_of_read_is_the_shared_point_in_time_predicate_word_for_word():
    from genios_engine.context import bounded_read as B
    from genios_engine.context.graph_store import _WINDOW_AT
    assert B._NEIGHBOUR_SQL_AT == B._NEIGHBOUR_SQL.replace("valid_to is null", _WINDOW_AT, 1)
