"""U01–U02 · the bounded read, and the truncation it must never hide.

    pytest tests/context/test_the_bounded_read_says_when_it_stopped.py -q

`context/` offered exactly two graph reads and both returned the whole tenant. This is the third.

⛔ THE TEST THAT MATTERS IS THE TRUNCATION ONE. A walk that hit its cap and returned quietly gives a
partial answer that reads as a complete one — the same failure `coverage` exists to prevent one layer
down. Most of section 3 is that single distinction, stated several ways.
"""

from __future__ import annotations

import pytest

from genios_engine.context.bounded_read import (DEFAULT_MAX_HOPS, DEFAULT_MAX_NODES, BoundedView,
                                                ReadRequest, expand)

pytestmark = pytest.mark.unit


def _graph(adj):
    """adj: {node: [(edge_type, other), ...]} -> a Neighbours callable."""
    def walk(node):
        for edge_type, other in adj.get(node, ()):
            yield edge_type, other, {"edge_type": edge_type, "a": node, "b": other}
    return walk


_LINE = _graph({"a": [("mentions", "b")], "b": [("mentions", "c")], "c": [("mentions", "d")],
                "d": [("mentions", "e")]})


# =================================================================================================
# 1 · ⛔ bounded by default
# =================================================================================================
def test_the_defaults_are_bounds_not_infinity():
    """An unbounded default makes every caller's mistake invisible until the tenant is large enough
    for it to hurt — which is when it is hardest to fix."""
    req = ReadRequest(seeds=("a",))
    assert req.max_hops == DEFAULT_MAX_HOPS
    assert req.max_nodes == DEFAULT_MAX_NODES
    assert DEFAULT_MAX_HOPS > 0 and DEFAULT_MAX_NODES > 0


def test_a_read_with_no_seeds_is_refused():
    """Seedless means "the whole tenant", which is the shape this module exists to replace. Refusing
    here is the difference between a bounded API and an unbounded one with extra fields."""
    with pytest.raises(ValueError, match="starts somewhere"):
        ReadRequest(seeds=())


@pytest.mark.parametrize(("field", "value"), [("max_hops", -1), ("max_nodes", 0)])
def test_a_bound_that_cannot_hold_the_seeds_is_refused(field, value):
    with pytest.raises(ValueError):
        ReadRequest(seeds=("a",), **{field: value})


def test_the_request_is_frozen():
    """A caller that could widen its own bounds mid-walk has no bounds."""
    req = ReadRequest(seeds=("a",))
    with pytest.raises(Exception):
        req.max_nodes = 10_000


# =================================================================================================
# 2 · the walk
# =================================================================================================
def test_zero_hops_returns_the_seeds_alone():
    view = expand(ReadRequest(seeds=("a",), max_hops=0), _LINE)
    assert view.node_ids == ("a",)
    assert view.edges == ()


def test_one_hop_reaches_the_neighbours():
    view = expand(ReadRequest(seeds=("a",), max_hops=1), _LINE)
    assert view.node_ids == ("a", "b")


def test_a_walk_that_runs_out_of_graph_is_complete():
    """⛔ The other half of the truncation distinction: finishing early because there is nothing more
    must NOT look like being cut off."""
    view = expand(ReadRequest(seeds=("a",), max_hops=9), _LINE)
    assert view.node_ids == ("a", "b", "c", "d", "e")
    assert view.complete is True
    assert view.truncated_by is None


def test_a_cycle_does_not_loop_forever():
    view = expand(ReadRequest(seeds=("a",), max_hops=9),
                  _graph({"a": [("x", "b")], "b": [("x", "a")]}))
    assert view.node_ids == ("a", "b")
    assert view.complete is True


def test_duplicate_seeds_are_one_node():
    view = expand(ReadRequest(seeds=("a", "a"), max_hops=0), _LINE)
    assert view.node_ids == ("a",)


def test_the_walk_is_breadth_first_so_a_cap_keeps_the_nearest():
    """⛔ Depth-first under the same cap returns one long thread and calls it a neighbourhood. What
    survives a cap should be what is NEAREST the thing asked about."""
    view = expand(ReadRequest(seeds=("root",), max_hops=9, max_nodes=3),
                  _graph({"root": [("x", "near1"), ("x", "near2")],
                          "near1": [("x", "far")]}))
    assert view.node_ids == ("root", "near1", "near2")
    assert "far" not in view.node_ids


# =================================================================================================
# 3 · ⛔ truncation is REPORTED, never silent
# =================================================================================================
def test_the_hop_limit_reports_itself():
    view = expand(ReadRequest(seeds=("a",), max_hops=2), _LINE)
    assert view.node_ids == ("a", "b", "c")
    assert view.truncated is True
    assert view.truncated_by == "max_hops"
    assert view.hops_walked == 2


def test_the_node_cap_reports_itself():
    view = expand(ReadRequest(seeds=("a",), max_hops=9, max_nodes=2), _LINE)
    assert view.truncated is True
    assert view.truncated_by == "max_nodes"
    assert len(view.node_ids) == 2


def test_more_seeds_than_the_cap_is_truncation_before_a_single_hop():
    """Not an error — a report. Silently dropping seeds would answer a question nobody asked."""
    view = expand(ReadRequest(seeds=("a", "b", "c"), max_nodes=2), _LINE)
    assert view.node_ids == ("a", "b")
    assert view.truncated_by == "max_nodes"


def test_complete_and_truncated_are_never_both_true():
    for req in (ReadRequest(seeds=("a",), max_hops=1),
                ReadRequest(seeds=("a",), max_hops=9),
                ReadRequest(seeds=("a",), max_hops=9, max_nodes=2)):
        view = expand(req, _LINE)
        assert view.complete is not view.truncated


def test_a_capped_walk_never_returns_an_edge_to_a_node_it_withheld():
    """⛔ A view whose edges point at things it does not contain is worse than a smaller view: the
    caller joins on the edge, finds nothing, and reads the absence as a fact."""
    view = expand(ReadRequest(seeds=("a",), max_hops=9, max_nodes=3),
                  _graph({"a": [("x", "b"), ("x", "c"), ("x", "d")],
                          "b": [("x", "e")]}))
    returned = set(view.node_ids)
    for edge in view.edges:
        assert edge["a"] in returned
        assert edge["b"] in returned


def test_the_truncation_flag_survives_a_walk_that_is_exactly_the_cap():
    """Exactly-at-the-cap with nothing beyond it is COMPLETE. A cap that reports truncation whenever
    it is touched would make every caller widen bounds it never actually hit."""
    view = expand(ReadRequest(seeds=("a",), max_hops=9, max_nodes=5), _LINE)
    assert len(view.node_ids) == 5
    assert view.complete is True


# =================================================================================================
# 4 · edge types narrow the walk
# =================================================================================================
def test_an_edge_type_filter_keeps_the_walk_on_the_question():
    view = expand(ReadRequest(seeds=("a",), edge_types=("owns",), max_hops=9),
                  _graph({"a": [("owns", "b"), ("mentions", "junk")]}))
    assert view.node_ids == ("a", "b")


def test_no_edge_type_filter_means_any_edge():
    assert ReadRequest(seeds=("a",)).allows("anything") is True


def test_a_filtered_out_edge_is_not_returned_either():
    """Returning the edge while withholding its node would re-create the dangling-edge problem."""
    view = expand(ReadRequest(seeds=("a",), edge_types=("owns",), max_hops=9),
                  _graph({"a": [("owns", "b"), ("mentions", "junk")]}))
    assert all(e["edge_type"] == "owns" for e in view.edges)


# =================================================================================================
# 5 · the revision comes back with the view
# =================================================================================================
def test_the_view_carries_a_revision_slot():
    """⛔ A read that did not say which revision it saw cannot be the basis of a compare-and-set, and
    every read here is a candidate basis for one."""
    assert "revision" in BoundedView.__dataclass_fields__


def test_an_unknown_revision_is_none_not_zero():
    """Zero is a revision. `None` is "the store could not say" — conflating them would let a
    compare-and-set guard against a version that never existed."""
    assert expand(ReadRequest(seeds=("a",)), _LINE).revision is None
