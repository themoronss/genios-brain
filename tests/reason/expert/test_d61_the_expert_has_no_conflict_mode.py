"""STEP-13 · D61 held in a test: the expert has no conflict mode — declared, not built, and visible.

    .venv/bin/python -m pytest -q tests/reason/expert/test_d61_the_expert_has_no_conflict_mode.py

Tree `yc2_w27_s13` M36.C1.L-logic.V1.U08 (crosscheck X31). `06` D61 decided "not now": no golden case and no
measured need for a *conflict* mode of the expert — two sources disagreeing, a ruling asked for. So a covered
file never reaches the CONFLICT lane: `reason/expert/decide` routes its lane with no `conflict_open`, and the
compiled lane stands a covered file's situations down before it compiles. The router's CONFLICT lane stays
reachable from the deciders that pass it (`reason/decision_maker`, `reason/llm_decision_maker`). This file makes
the declaration a fact a build can see: the day the expert routes a conflict, it fails — the signal to revisit
D61 and write its test, never to delete this one quietly.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from genios_engine.contracts.reasoning import DecisionOutcome, OutputLane
from genios_engine.reason.output_lane import route

pytestmark = pytest.mark.unit

REASON = Path(__file__).resolve().parents[3] / "genios_engine" / "reason"


def _route_calls(path: Path) -> list[ast.Call]:
    """Every call of `reason/output_lane.route` in `path`, under whatever name the module imported it as."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
             and (n.module or "").endswith("output_lane") for a in n.names if a.name == "route"}
    assert names, f"{path.name} does not import the router"
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) in names]


def test_the_expert_routes_with_no_conflict():
    calls = _route_calls(REASON / "expert" / "decide.py")
    assert calls, "the expert's decision routes its lane"
    assert all("conflict_open" not in {k.arg for k in c.keywords} for c in calls), (
        "the expert now routes a conflict: D61 is being revisited — write its test and restate this one")


@pytest.mark.parametrize("module", ["decision_maker.py", "llm_decision_maker.py"])
def test_the_conflict_lane_stays_reachable_from_the_deciders_that_pass_it(module):
    calls = _route_calls(REASON / module)
    assert any("conflict_open" in {k.arg for k in c.keywords} for c in calls), module


def test_the_router_still_has_a_conflict_lane():
    assert route(outcome=DecisionOutcome.DECISION, confidence_bp=9_000, conflict_open=True).lane == \
        OutputLane.CONFLICT
