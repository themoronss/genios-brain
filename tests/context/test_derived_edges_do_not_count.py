"""A derived edge re-asserted on every sweep is not an interaction.

The support and outreach readings re-write their `concerns` edge on every L2 pass. `write_edge`
bumped `interaction_count` on every re-write, so the count grew with the number of sweeps, not
with contact (measured: the settle call after a sync drain added one to every such edge)."""
from genios_engine.context.graph_store import GraphStore


class _HeldEdgeConn:
    """A connection on which the edge already exists; records what the update was sent."""

    def __init__(self):
        self.updates: list[dict] = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if sql.lstrip().lower().startswith("update graph_edges"):
            self.updates.append(dict(params or {}))

        class _Result:
            def first(self_inner):
                return type("Row", (), {"edge_version_id": "edgev_held"})()
        return _Result()


def _rewrite(**kw) -> dict:
    conn = _HeldEdgeConn()
    store = GraphStore.__new__(GraphStore)          # the held-edge path touches no store state
    out = store.write_edge(conn, org_id="o", edge_type="concerns", from_node_id="a",
                           to_node_id="b", confidence=0.9, occurred_at=None, event_id="desk:o",
                           evidence={}, source="engine", **kw)
    assert out is None and len(conn.updates) == 1
    return conn.updates[0]


def test_a_derived_edge_re_asserted_does_not_bump_the_interaction_count():
    assert _rewrite(count_interaction=False)["bump"] == 0


def test_a_real_repeat_interaction_still_bumps_it():
    assert _rewrite()["bump"] == 1


def test_both_readings_that_write_concerns_edges_mark_them_derived():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "genios_engine" / "context"
    for name in ("support_situations.py", "outreach_situations.py"):
        calls = [n for n in ast.walk(ast.parse((root / name).read_text()))
                 if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "write_edge"]
        assert calls, name
        for call in calls:
            kw = {k.arg: k.value for k in call.keywords}
            assert isinstance(kw.get("count_interaction"), ast.Constant) \
                and kw["count_interaction"].value is False, name
