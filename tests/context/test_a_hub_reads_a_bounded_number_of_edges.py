"""L2 rebuild A4 — one node's neighbour read is bounded, and a capped read says so.

`max_nodes` bounds how many nodes a snapshot keeps, never how many rows one neighbour query returns: a hub returned
every edge it has, each sweep. Now a node's read stops at `MAX_EDGES_PER_NODE`, and a node that reaches it marks the
view truncated (`max_edges`) — a capped neighbourhood never reads as a complete one.
"""
from __future__ import annotations

import pytest

from genios_engine.context import bounded_read as B

pytestmark = pytest.mark.unit


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalar(self):
        return 7


class _Conn:
    """A graph with one hub: `hub` has `n` edges; each query honours `:lim` as Postgres would."""

    def __init__(self, n):
        self.n, self.limits = n, []

    def execute(self, stmt, params=None):
        params = params or {}
        if "graph_versions" in str(stmt):
            return _Rows([])
        self.limits.append(params.get("lim"))
        if params.get("n") != "hub":
            return _Rows([])
        rows = [{"edge_type": "works_with", "from_node_id": "hub", "to_node_id": f"n{i}", "confidence": 1,
                 "valid_from": None} for i in range(self.n)]
        return _Rows(rows[:params["lim"]])


def test_a_hub_reads_at_most_the_cap_and_the_view_says_it_was_capped():
    conn = _Conn(B.MAX_EDGES_PER_NODE + 300)
    view = B.read_bounded(conn, "o", B.ReadRequest(seeds=("hub",), max_hops=2, max_nodes=10_000))
    assert conn.limits and set(conn.limits) == {B.MAX_EDGES_PER_NODE}
    assert len(view.edges) == B.MAX_EDGES_PER_NODE
    assert view.truncated and view.truncated_by == "max_edges"


def test_a_small_node_is_read_whole_and_complete():
    conn = _Conn(12)
    view = B.read_bounded(conn, "o", B.ReadRequest(seeds=("hub",), max_hops=2, max_nodes=10_000))
    assert len(view.edges) == 12 and view.complete and view.truncated_by is None
