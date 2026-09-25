"""L3-12 · the graph's node types were a free string too, and two sets of them existed.

`graph_nodes.node_type` is `text not null` with no check constraint, and migration 0004's comment
ends `-- person | company | deal | meeting | ...`. ⛔ THE `| ...` IS THE TELL: an open-ended list in
prose with nothing enforcing it. Ten types are written across the engine; a typo of any of them
mints a node no reader ever asks for — the same failure L3-09 closed for edges.

⛔ AND THERE WERE TWO SETS. `pipeline._NODE_TYPES` is a MENTION WHITELIST — "this whitelist governs
ONLY the L2 mention loop below; the structured lane is NOT gated here" — a narrower rule about
which LLM entity mentions may become nodes at all. Correctly scoped and correctly documented, and
one rename away from being read as the graph's vocabulary.
"""
from __future__ import annotations

import re
from pathlib import Path

from genios_engine.context.graph_store import EDGE_TYPES, NODE_TYPES
from genios_engine.context.pipeline import _NODE_TYPES as MENTION_WHITELIST
from genios_engine.context.read_models import DEFAULT_READ_MODEL, READ_MODELS

_ROOT = Path(__file__).resolve().parents[2] / "genios_engine"


def _written_node_types() -> set[str]:
    """Every node type the engine actually mints — in BOTH shapes it is written in.

    ⛔ THE FIRST DRAFT READ ONLY `node_type="..."` AND MISSED TWO OF TWELVE. `document` and
    `product_usage_event` are minted through named constants (`DOCUMENT_NODE_TYPE`,
    `PRODUCT_USAGE_NODE_TYPE`), so a literal-only scan saw ten types and called the set total —
    and it was the MENTION WHITELIST, which does list `document`, that exposed the miss.

    A totality guard that only recognises one spelling of the thing it counts is not total. It now
    reads both: the keyword literal, and any module-level `*_NODE_TYPE = "..."` constant.
    """
    found: set[str] = set()
    for py in _ROOT.rglob("*.py"):
        text = py.read_text()
        found |= set(re.findall(r'node_type=["\']([a-z_]+)["\']', text))
        found |= set(re.findall(r'^[A-Z_]*NODE_TYPE\s*[:=]\s*["\']([a-z_]+)["\']', text, re.M))
    return found


# =================================================================================================
# 1 · ⛔ TOTALITY, BOTH DIRECTIONS
# =================================================================================================

def test_every_written_node_type_is_declared():
    """A type nobody declared is a node nothing describes, and a typo is indistinguishable from a
    new kind of entity."""
    for found in sorted(_written_node_types()):
        assert found in NODE_TYPES, (
            f"node_type={found!r} is written but not declared in NODE_TYPES")


def test_every_declared_node_type_is_actually_written():
    unwritten = set(NODE_TYPES) - _written_node_types()
    assert not unwritten, (
        f"declared but never minted: {sorted(unwritten)}. A reader can query for it for ever and "
        "get nothing, with no way to tell that from 'there are none'.")


def test_each_type_says_what_anchors_it():
    """⛔ THE ANCHOR IS THE WHOLE THING. It decides whether two sightings are one node — and getting
    it wrong is how a company is fragmented across three nodes or two people are merged into one."""
    for name, meaning in NODE_TYPES.items():
        assert "anchor" in meaning.lower() or "one per org" in meaning, (
            f"{name} is declared without saying what anchors it")


# =================================================================================================
# 2 · ⛔ THE MENTION WHITELIST IS NOT THE GRAPH VOCABULARY
# =================================================================================================

def test_the_mention_whitelist_is_a_strict_part_of_the_graph_vocabulary():
    """⛔ Two sets of node-type names doing different jobs is how a drift starts. The whitelist may
    be narrower — that is its purpose — but it may never name a type the graph does not know."""
    unknown = set(MENTION_WHITELIST) - set(NODE_TYPES) - {"agent"}
    assert not unknown, (
        f"the mention whitelist admits node types the graph does not declare: {sorted(unknown)}")


def test_the_whitelist_still_says_what_it_governs():
    """Its scope is the only thing stopping it being read as the graph's vocabulary, and it is a
    comment. If the comment goes, the confusion is one grep away."""
    src = " ".join((_ROOT / "context/pipeline.py").read_text().split())
    assert "governs ONLY the L2 mention loop" in src
    assert "structured lane" in src and "is NOT gated here" in src


def test_only_a_person_may_be_minted_from_a_mention():
    """`person` is the one type an LLM mention may create, and only with a deterministic address.
    Everything else becomes an observation on the sender — "the SAP/OpenClaw dead-dots go away"."""
    assert "anchored by email address" in NODE_TYPES["person"]
    src = " ".join((_ROOT / "context/pipeline.py").read_text().split())
    assert "a person WITH an email (a deterministic anchor)" in src


# =================================================================================================
# 3 · ⛔ THE READ MODELS ARE A NAMED MAP, NOT A DICT LITERAL IN A FUNCTION
# =================================================================================================

def test_the_read_model_map_is_reachable_without_reading_a_function_body():
    """It was an inline dict inside `build_entity_360`, so "which entities have a tailored view"
    was a question you could only answer by reading a function body."""
    assert READ_MODELS and DEFAULT_READ_MODEL == "entity_360"
    src = (_ROOT / "context/read_models.py").read_text()
    assert "READ_MODELS.get(node.node_type, DEFAULT_READ_MODEL)" in src


def test_every_read_model_is_for_a_real_node_type():
    for node_type in READ_MODELS:
        assert node_type in NODE_TYPES, (
            f"a tailored view exists for {node_type!r}, which the graph never mints")


def test_a_type_without_a_tailored_view_still_gets_a_real_one():
    """⛔ The default is a real answer, not a fallback for an error: `entity_360` carries the node's
    facts, observations and edges. What was missing is that ADDING A NODE TYPE ASKED NOBODY whether
    it needed a view — it silently became generic."""
    generic = set(NODE_TYPES) - set(READ_MODELS)
    assert generic, "every type now has a tailored view — the default is dead and should be removed"
    assert DEFAULT_READ_MODEL not in READ_MODELS.values()


# =================================================================================================
# 4 · ⛔ THE TWO GRAPH VOCABULARIES ARE SIBLINGS AND MUST STAY SEPARATE
# =================================================================================================

def test_a_node_type_and_an_edge_type_never_share_a_name():
    """One name meaning both a thing and a relationship between things is a query nobody can read."""
    assert not (set(NODE_TYPES) & set(EDGE_TYPES))


def test_the_column_is_still_free_text_and_that_is_why_this_guard_exists():
    sql = (_ROOT.parent / "migrations" / "0004_l2_context_graph.sql").read_text()
    assert "node_type              text not null" in sql
    assert "check (node_type" not in sql
