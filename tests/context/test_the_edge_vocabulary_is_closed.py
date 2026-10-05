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

import ast
from pathlib import Path

import pytest

from genios_engine.context.graph_store import EDGE_TYPES, FORBIDDEN_EDGE_TYPES, GraphStore

_ROOT = Path(__file__).resolve().parents[2] / "genios_engine"

#: ⛔ THE ONE WRITE SITE WHOSE EDGE TYPE IS DATA, NOT CODE. The structured committer writes
#: `rel["edge_type"]` for every relation a structured mapping declares, so its types are the
#: `RelationMap(...)` literals the collector reads separately — and a config-driven mapping
#: (`registry.mapping_from_dict`, `RelationMap(**r)`) brings its own, which is data and is checked
#: when it is written. Any OTHER site the collector cannot resolve fails the build.
_RESOLVED_THROUGH_RELATION_MAPS = frozenset({"context/structured.py"})


def _module_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `NAME = "string"` assignments — how `documents.py` names `EDGE_EDITED`."""
    out: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value.value
    return out


def _string_at(element: ast.AST, position: int, consts: dict[str, str]) -> set[str] | None:
    """The string at `position` of one literal tuple, or None when it is not a literal."""
    if isinstance(element, ast.Tuple) and len(element.elts) > position:
        value = element.elts[position]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return {value.value}
        if isinstance(value, ast.Name) and value.id in consts:
            return {consts[value.id]}
    return None


def _strings_in(iterable: ast.AST, position: int, consts: dict[str, str]) -> set[str] | None:
    """Every string a `for a, b, verb in <iterable>` binds to position `position`, if the iterable
    is literal: a tuple or list of tuples, a concatenation of those, or a comprehension."""
    if isinstance(iterable, (ast.Tuple, ast.List)):
        found: set[str] = set()
        for element in iterable.elts:
            strings = _string_at(element, position, consts)
            if strings is None:
                return None
            found |= strings
        return found
    if isinstance(iterable, ast.BinOp) and isinstance(iterable.op, ast.Add):
        left = _strings_in(iterable.left, position, consts)
        right = _strings_in(iterable.right, position, consts)
        return None if left is None or right is None else left | right
    if isinstance(iterable, (ast.ListComp, ast.GeneratorExp)):
        return _string_at(iterable.elt, position, consts)
    return None


def _collect(tree: ast.Module, where: str) -> tuple[set[str], list[str]]:
    """(edge types written, write sites that could not be resolved) for one module.

    ⛔ READ FROM THE AST, NOT THE TEXT. The first version of this guard was a regex for
    `edge_type="…"`, and four writers passed straight under it — a loop over literal tuples
    (`context/pipeline.py`, `context/backfill.py`), a module constant (`context/documents.py`) and
    a structured relation (`capture/structured/`). The vocabulary then raised on all four at runtime,
    and the guard that existed to prevent exactly that stayed green.
    """
    consts = _module_constants(tree)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    written: set[str] = set()
    unresolved: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if name == "RelationMap":
            value = node.args[2] if len(node.args) > 2 else next(
                (k.value for k in node.keywords if k.arg == "edge_type"), None)
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                written.add(value.value)
            elif not any(k.arg is None for k in node.keywords):     # `RelationMap(**r)` is data
                unresolved.append(f"{where}:{node.lineno} RelationMap")
            continue
        if name != "write_edge":
            continue
        value = next((k.value for k in node.keywords if k.arg == "edge_type"), None)
        site = f"{where}:{node.lineno}"
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            written.add(value.value)
        elif isinstance(value, ast.Name) and value.id in consts:
            written.add(consts[value.id])
        elif isinstance(value, ast.Name):
            strings, scope = None, node
            while scope in parents:
                scope = parents[scope]
                if isinstance(scope, ast.For) and isinstance(scope.target, ast.Tuple):
                    names = [t.id if isinstance(t, ast.Name) else None for t in scope.target.elts]
                    if value.id in names:
                        strings = _strings_in(scope.iter, names.index(value.id), consts)
                        break
            if strings is None:
                unresolved.append(f"{site} edge_type={value.id}")
            else:
                written |= strings
        else:
            unresolved.append(f"{site} edge_type=<{type(value).__name__}>")
    return written, unresolved


def _engine_edge_writes() -> tuple[set[str], list[str]]:
    written: set[str] = set()
    unresolved: list[str] = []
    for py in sorted(_ROOT.rglob("*.py")):
        rel = py.relative_to(_ROOT).as_posix()
        found, missing = _collect(ast.parse(py.read_text(encoding="utf-8")), rel)
        written |= found
        unresolved += missing
    return written, unresolved


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

def test_the_collector_sees_every_write_path():
    """⛔ THE GUARD'S OWN TEST. Each shape a writer has actually used, and one it cannot read — which
    must come back UNRESOLVED, never silently skipped. Then the engine: the only site it cannot
    resolve is the structured committer, whose types are the `RelationMap` literals."""
    sample = ast.parse(
        "EDGE_X = 'from_a_constant'\n"
        "def f(store, a, b, s):\n"
        "    store.write_edge(c, edge_type='a_literal')\n"
        "    store.write_edge(c, edge_type=EDGE_X)\n"
        "    for frm, to, verb in ((a, b, 'loop_one'), (b, a, 'loop_two')):\n"
        "        store.write_edge(c, edge_type=verb)\n"
        "    for frm, to, verb in [(a, b, 'listed')] + [(b, x, 'comprehended') for x in s]:\n"
        "        store.write_edge(c, edge_type=verb)\n"
        "    for person, kind in ((a, EDGE_X), (b, 'paired')):\n"
        "        store.write_edge(c, edge_type=kind)\n"
        "    store.write_edge(c, edge_type=pick())\n"
        "RelationMap('f', 'person', 'positional', 'in', 'email')\n"
        "RelationMap('f', 'person', edge_type='keyword')\n")
    written, unresolved = _collect(sample, "sample.py")
    assert written == {"a_literal", "from_a_constant", "loop_one", "loop_two", "listed",
                       "comprehended", "paired", "positional", "keyword"}
    assert unresolved == ["sample.py:11 edge_type=<Call>"], unresolved

    _, engine_unresolved = _engine_edge_writes()
    assert {site.split(":")[0] for site in engine_unresolved} == _RESOLVED_THROUGH_RELATION_MAPS, (
        f"write sites the collector cannot resolve: {engine_unresolved}. Resolve the new one (a "
        "literal, a constant, a loop over literal tuples) or declare why it is data.")
    assert len(engine_unresolved) == 1


def test_every_declared_type_is_actually_written_somewhere():
    """A declared relation nobody writes is a promise the graph does not keep — a reader can query
    it for ever and get nothing, with no way to tell that from "there are none"."""
    written, _ = _engine_edge_writes()
    unwritten = set(EDGE_TYPES) - written
    assert not unwritten, (
        f"declared but never written: {sorted(unwritten)}. Either something stopped writing it — "
        "and every reader of it is now silently empty — or it should not be in the vocabulary.")


def test_every_written_type_is_declared():
    """The other half, and the one the raise enforces at runtime. Here it is enforced at build
    time, so a new writer is caught before a tenant hits it."""
    written, _ = _engine_edge_writes()
    undeclared = written - set(EDGE_TYPES)
    assert not undeclared, (
        f"written but not declared: {sorted(undeclared)} — `write_edge` will raise on each of them "
        "at runtime and roll the whole event back. Declare it with what it means, or use the one "
        "that fits.")


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
