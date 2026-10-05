"""STEP-01 · the sweep chain takes one instant, so a replay can run it at a pinned time.

    pytest tests/test_the_sweep_chain_has_one_clock.py -q

⛔ WHY. `_run_l2_chain` read `now()` for the funnel's sweep and handed nothing to the stages, each
of which then read its own clock. A golden case replayed against the real chain at a fixed instant
could not be: the chain judged it at the wall clock — the same defect that made four tests expire
this week (a fixed seed date beside a wall-clock evaluation). Production passes nothing and behaves
exactly as before.

Read from the AST, never the text.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROUTES = Path(__file__).resolve().parents[1] / "genios_engine" / "api" / "routes.py"


def _chain() -> ast.FunctionDef:
    tree = ast.parse(ROUTES.read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_run_l2_chain")


def _call(fn: ast.FunctionDef, name: str) -> ast.Call:
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and (getattr(n.func, "id", None) == name or getattr(n.func, "attr", None) == name)]
    assert len(calls) == 1, f"expected one call to {name}, found {len(calls)}"
    return calls[0]


def _passes_the_instant(call: ast.Call, keyword: str) -> bool:
    value = next((k.value for k in call.keywords if k.arg == keyword), None)
    return value is not None and any(isinstance(n, ast.Name) and n.id == "eval_time"
                                     for n in ast.walk(value))


def test_the_chain_takes_an_optional_instant():
    chain = _chain()
    kwonly = {a.arg: d for a, d in zip(chain.args.kwonlyargs, chain.args.kw_defaults)}
    assert "eval_time" in kwonly, "_run_l2_chain has no instant to replay at"
    assert isinstance(kwonly["eval_time"], ast.Constant) and kwonly["eval_time"].value is None, (
        "production passes nothing: the default must stay None (= now)")


def test_every_stage_is_handed_the_same_instant():
    chain = _chain()
    for name, keyword in (("process_pending", "eval_time"), ("run_l3", "eval_time"),
                          ("build_cards_for_org", "eval_time"), ("run_post_passes", "now")):
        assert _passes_the_instant(_call(chain, name), keyword), (
            f"{name} is not handed the chain's instant: it reads its own clock")


def test_the_funnels_sweep_is_stamped_with_that_instant():
    chain = _chain()
    stamped = [n for n in ast.walk(chain) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "_sweep_at" for t in n.targets)]
    assert stamped and any(isinstance(n, ast.Name) and n.id == "eval_time"
                           for n in ast.walk(stamped[0].value)), (
        "the funnel's sweep_at ignores the chain's instant")
