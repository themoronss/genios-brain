"""L3-09 · the graph's relations were a free string, so nothing could be violated.

`graph_edges.edge_type` is `text not null` with no check constraint, and there was no list of legal
values anywhere in the engine. Six are written. Anything else was accepted silently — INCLUDING A
TYPO OF ONE OF THE SIX, which writes a relation no reader queries and an edge that is invisible for
ever with nothing failing.

⛔ THE SPECS NAME THE SAME HAZARD: "`related_to` must not silently become `blocks`" (§2), and
"co-occurrence cannot produce `causes` or `blocks`" (CC-35, DP-06). Neither could be prevented,
because there was no vocabulary to violate.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from genios_engine.context.graph_store import EDGE_TYPES, FORBIDDEN_EDGE_TYPES, GraphStore

_ROOT = Path(__file__).resolve().parents[2] / "genios_engine"


def _write(edge_type: str):
    return GraphStore.write_edge(
        None, None, org_id="o", edge_type=edge_type, from_node_id="a", to_node_id="b",
        confidence=1.0, occurred_at=None, event_id="e", evidence={}, source=None)


# =================================================================================================
# 1 · ⛔ THE SET IS CLOSED, AND AN UNKNOWN TYPE RAISES
# =================================================================================================

def test_a_typo_of_a_real_edge_type_raises_rather_than_writing_an_invisible_edge():
    """⛔ THE FAILURE THIS EXISTS FOR. `work_at` is one character from `works_at`, and before this
    it wrote a relation that every reader walks straight past — a fact in the graph that can never
    be found, with no error anywhere."""
    with pytest.raises(ValueError, match="unknown edge_type"):
        _write("work_at")


def test_an_invented_relation_raises():
    with pytest.raises(ValueError, match="unknown edge_type"):
        _write("mentioned_in_passing")


def test_the_raise_names_the_legal_set_so_the_caller_can_choose():
    """An error that says "invalid" sends the reader to the source. One that lists the alternatives
    lets them pick the relation they actually meant."""
    with pytest.raises(ValueError) as e:
        _write("nope")
    for known in EDGE_TYPES:
        assert known in str(e.value)


def test_it_raises_rather_than_skipping():
    """⛔ A skip would let it ship. An edge type is written by a PROGRAMMER, not supplied by data,
    so an unknown one is a bug in the caller — the same argument `corroborate` makes at its own
    seam, where "a warn would let it ship"."""
    src = (_ROOT / "context/graph_store.py").read_text()
    body = src[src.index("def write_edge("):]
    body = body[:body.index("def _write_ref(")]
    assert "raise ValueError" in body
    guard = body[:body.index("if not from_node_id")]
    assert "return None" not in guard, "the vocabulary check must raise, not skip silently"


# =================================================================================================
# 2 · ⛔ THE THREE FORBIDDEN RELATIONS
# =================================================================================================

@pytest.mark.parametrize("bad", ["causes", "blocks", "related_to"])
def test_a_conclusion_cannot_be_stored_as_an_observation(bad):
    """⛔ These are not typos. They are conclusions wearing an edge's clothes: cheap to write, and
    afterwards impossible to tell from something a source said."""
    with pytest.raises(ValueError, match="may not assert"):
        _write(bad)


def test_each_refusal_carries_its_own_reason():
    """"Not allowed" teaches nobody. The reason is what stops the next person adding it back with
    a better argument, because the argument is already written down."""
    for name, reason in FORBIDDEN_EDGE_TYPES.items():
        assert len(reason) > 60, f"{name} is forbidden without a reason"
    assert "co-occurrence" in FORBIDDEN_EDGE_TYPES["causes"]
    assert "requires" in FORBIDDEN_EDGE_TYPES["blocks"], (
        "the refusal must name what the caller should use instead")


def test_the_two_sets_never_overlap():
    """A type in both would be legal or forbidden depending on which check ran first."""
    assert not (set(EDGE_TYPES) & set(FORBIDDEN_EDGE_TYPES))


# =================================================================================================
# 3 · ⛔ TOTALITY, BOTH DIRECTIONS
# =================================================================================================

def test_every_declared_type_is_actually_written_somewhere():
    """A declared relation nobody writes is a promise the graph does not keep — a reader can query
    it for ever and get nothing, with no way to tell that from "there are none"."""
    written = set()
    for py in _ROOT.rglob("*.py"):
        written |= set(re.findall(r'edge_type=["\']([a-z_]+)["\']', py.read_text()))
    unwritten = set(EDGE_TYPES) - written
    assert not unwritten, (
        f"declared but never written: {sorted(unwritten)}. Either something stopped writing it — "
        "and every reader of it is now silently empty — or it should not be in the vocabulary.")


def test_every_written_type_is_declared():
    """The other half, and the one the raise enforces at runtime. Here it is enforced at build
    time, so a new writer is caught before a tenant hits it."""
    for py in _ROOT.rglob("*.py"):
        for found in re.findall(r'edge_type=["\']([a-z_]+)["\']', py.read_text()):
            assert found in EDGE_TYPES, (
                f"{py.relative_to(_ROOT)} writes edge_type={found!r}, which is not declared")


def test_every_type_says_what_it_means_and_what_it_does_not():
    """⛔ `attended` means presence, not engagement; `corresponded_with` means mail was exchanged,
    not that a relationship is strong. Those distinctions are exactly how an edge becomes a
    conclusion, so each entry states them."""
    for name, meaning in EDGE_TYPES.items():
        assert "->" in meaning, f"{name} does not state its direction"
        assert len(meaning) > 40, f"{name} is declared without a meaning"


def test_the_column_is_still_free_text_and_that_is_why_the_guard_is_here():
    """If a check constraint ever lands, this guard becomes belt-and-braces rather than the only
    thing standing between a typo and an invisible edge — worth knowing which it is."""
    sql = (_ROOT.parent / "migrations" / "0004_l2_context_graph.sql").read_text()
    assert "edge_type       text not null" in sql
    assert "check (edge_type" not in sql
