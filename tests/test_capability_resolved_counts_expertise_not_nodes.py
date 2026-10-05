"""The funnel's third number must count EXPERTISE RESOLVED, never SUBJECTS EXAMINED.

    pytest tests/test_capability_resolved_counts_expertise_not_nodes.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest … -q -m pg      # + the behavioural half

⛔ WHY THIS FILE EXISTS. `_run_l2_chain` relayed `run_all()["nodes"]` as `capability_resolved`.
`nodes` is `len(graph_nodes read)` (`reason/runner.py`, the `select node_id, node_type,
canonical_key from graph_nodes` read) — the subjects the sweep EXAMINED, counted before a single
capability is resolved. So the one funnel stage whose job is to expose the Atlas's gate 3 — *"no
authored expertise, so an empty package"* — reported the population it loses FROM, and on a tenant
whose subjects mostly resolve nothing it read HIGHER than `situations_formed`: a funnel that grows
in the middle.

The loss itself was worse than mis-labelled, it was absent. The per-node loop skipped a subject
with no rule and no native capability on a bare `continue` — no counter, no receipt — so the
single largest unexplained drop in the product was literally uncounted.

⛔ ASSERTED ON THE AST, NOT ON TEXT NEAR A THING. This repo's blunt-grep family has bitten seven
times, every time matching the author's own prose — and this file's own docstring contains both
`nodes` and `capability_resolved`, so a substring scan here would match itself. Every structural
check below walks the tree.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from genios_engine.platform import funnel as _funnel
from genios_engine.platform.funnel import CAPABILITY_RESOLVED, NO_CAPABILITY, STAGES

_ENGINE = Path(__file__).resolve().parents[1] / "genios_engine"


def _tree(rel: str) -> ast.Module:
    return ast.parse((_ENGINE / rel).read_text(encoding="utf-8"), filename=rel)


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found — the test's premise moved, not the product's")


def _count_calls(fn: ast.AST) -> list[ast.Call]:
    """Every `_count(...)` call inside a function body."""
    return [n for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_count"]


def _stage_of(call: ast.Call) -> str | None:
    """The funnel stage a `_count(_funnel.X, …)` call writes.

    The AST carries the CONSTANT'S NAME (`CAPABILITY_RESOLVED`); the stage is its VALUE
    (`capability_resolved`). Resolved through the module rather than lower-cased, so a constant
    whose value stops matching its name is a failure here instead of a silent miss.
    """
    if not call.args:
        return None
    first = call.args[0]
    if not isinstance(first, ast.Attribute):
        return None
    return getattr(_funnel, first.attr, None)


# =================================================================================================
# 1 · the relay reads the resolution, and cannot read the node count
# =================================================================================================
def test_the_chain_relays_capability_resolved_from_the_outcomes_counter():
    """The value handed to `_count` for this stage must come out of the pass's `outcomes` dict."""
    chain = _func(_tree("api/routes.py"), "_run_l2_chain")
    calls = [c for c in _count_calls(chain) if _stage_of(c) == CAPABILITY_RESOLVED]
    assert len(calls) == 1, "exactly one writer per number — see platform/funnel.py"
    value = calls[0].args[1]
    reads = {n.func.value.id for n in ast.walk(value)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "get" and isinstance(n.func.value, ast.Name)}
    assert "_outcomes" in reads, (
        "capability_resolved must be read from the reasoning pass's outcomes counter; "
        f"it reads {reads or 'nothing recognisable'}")


def test_the_node_count_can_never_again_be_this_stages_value():
    """⛔ THE MUTATION THIS FILE EXISTS TO REJECT. Relaying `nodes` here is the original defect; it
    must fail as a structure, not merely look wrong."""
    chain = _func(_tree("api/routes.py"), "_run_l2_chain")
    calls = [c for c in _count_calls(chain) if _stage_of(c) == CAPABILITY_RESOLVED]
    literals = {n.value for n in ast.walk(calls[0].args[1])
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "nodes" not in literals, (
        "`nodes` is len(graph_nodes read) — the subjects examined, not the expertise resolved")


def test_the_stage_vocabulary_did_not_grow_a_sixth_name():
    """`NO_CAPABILITY` is a loss REASON, not a stage: migration 0188 carries the five-name list as a
    check constraint, so a sixth value would be a silent schema break."""
    assert len(STAGES) == 5
    assert NO_CAPABILITY not in STAGES


# =================================================================================================
# 2 · the loop counts both sides of the gate
# =================================================================================================
def _per_node_gate(run_fn: ast.FunctionDef) -> ast.If:
    """The `if not rules and not node_capabilities:` branch — found by its TEST, not by its text."""
    for node in ast.walk(run_fn):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.BoolOp):
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if {"rules", "node_capabilities"} <= names and isinstance(node.test.op, ast.And):
            if all(isinstance(v, ast.UnaryOp) and isinstance(v.op, ast.Not)
                   for v in node.test.values):
                return node
    raise AssertionError("the no-expertise gate is gone from the per-node loop")


def _augmented_keys(body: list[ast.stmt]) -> set[str]:
    """Which `out[...] += …` keys a block increments, resolved through the module constants."""
    keys: set[str] = set()
    for stmt in body:
        if not isinstance(stmt, ast.AugAssign) or not isinstance(stmt.target, ast.Subscript):
            continue
        idx = stmt.target.slice
        if isinstance(idx, ast.Constant) and isinstance(idx.value, str):
            keys.add(idx.value)
        elif isinstance(idx, ast.Name):                 # a module constant, e.g. NO_CAPABILITY
            keys.add({"NO_CAPABILITY": NO_CAPABILITY,
                      "CAPABILITY_RESOLVED": CAPABILITY_RESOLVED}.get(idx.id, idx.id))
    return keys


def test_a_subject_with_no_expertise_is_counted_and_not_skipped_silently():
    gate = _per_node_gate(_func(_tree("reason/runner.py"), "run"))
    assert NO_CAPABILITY in _augmented_keys(gate.body), (
        "the bare `continue` is back: a subject with no rule and no capability is being dropped "
        "with no counter, which is the uncounted gate-3 loss")


def test_a_subject_whose_expertise_resolved_is_counted_after_that_gate():
    run_fn = _func(_tree("reason/runner.py"), "run")
    gate = _per_node_gate(run_fn)
    #: The statements of the loop body that follow the gate — the resolved path.
    loop = next(n for n in ast.walk(run_fn)
                if isinstance(n, ast.For) and any(s is gate for s in ast.walk(n)))
    after = loop.body[loop.body.index(gate) + 1:]
    assert CAPABILITY_RESOLVED in _augmented_keys(after), (
        "nothing counts the resolved side, so the stage has no writer of its own")


def test_the_two_sides_of_the_gate_are_different_counters():
    """One key for both halves would make "resolved" and "no expertise" the same number."""
    assert CAPABILITY_RESOLVED != NO_CAPABILITY


# =================================================================================================
# 3 · two packs must not double-count one subject
# =================================================================================================
def test_the_multi_pack_merge_does_not_sum_this_counter():
    """Every pack walks the SAME node set — `nodes` is already a `max` for that reason. Summing
    `capability_resolved` across packs would report more subjects than the tenant has."""
    merge = _func(_tree("reason/runner.py"), "run_all")
    guarded = [n for n in ast.walk(merge)
               if isinstance(n, ast.If)
               and any(isinstance(c, ast.Name) and c.id == "CAPABILITY_RESOLVED"
                       for c in ast.walk(n.test))]
    assert guarded, "the merge treats capability_resolved like every other summed reason counter"
    assert any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "max"
               for c in ast.walk(guarded[0])), "the special case does not take a max"


# =================================================================================================
# 4 · behavioural — the identity only a real run can prove
# =================================================================================================
@pytest.mark.pg
@pytest.mark.skipif(not __import__("os").environ.get("GENIOS_TEST_DATABASE_URL"),
                    reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
def test_resolved_never_exceeds_the_subjects_examined(pg_store):
    """⛔ THE INEQUALITY THE OLD NUMBER COULD NOT VIOLATE BECAUSE IT *WAS* THE NODE COUNT.

    `capability_resolved <= nodes` is the whole claim: expertise can be resolved for at most every
    subject the sweep looked at. With the defect in place the two were equal by construction, so
    this could never fail — and never pass for the right reason either.
    """
    from datetime import datetime, timezone

    from sqlalchemy import text

    from genios_engine.packs.wiring import make_registry
    from genios_engine.reason.runner import run_all
    from tests.test_e2e_all_layers import _fresh_tenant, _seed_org

    url = __import__("os").environ["GENIOS_TEST_DATABASE_URL"]
    org = "funnel_gate3"
    _seed_org(pg_store, org)
    _fresh_tenant(pg_store, org)

    # A subject NO pack rule and NO native capability can speak for. `node_type` is a free string,
    # so this is a subject the resolver must refuse rather than one it happens to miss.
    with pg_store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (org_id, node_id, node_type, canonical_key) "
                       "values (:o, :n, :t, :k) on conflict do nothing"),
                  {"o": org, "n": "nd_no_expertise", "t": "zzz_no_such_subject",
                   "k": "zzz:no-expertise"})

    out = run_all(org_id=org, store=pg_store, eval_time=datetime(2026, 10, 2, tzinfo=timezone.utc),
                  registry=make_registry(url))
    outcomes = out["outcomes"]
    resolved = outcomes.get(CAPABILITY_RESOLVED, 0)

    assert resolved <= out["nodes"], (
        f"more subjects resolved ({resolved}) than were examined ({out['nodes']}) — the stage is "
        "counting something other than resolution")
    assert outcomes.get(NO_CAPABILITY, 0) >= 1, (
        "the unmatched subject was walked past without being counted as a gate-3 loss; "
        f"outcomes={outcomes}")
