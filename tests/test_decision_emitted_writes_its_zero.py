"""STEP-18 B17 · the funnel's fourth number writes its zero, and counts every lane.

    pytest tests/test_decision_emitted_writes_its_zero.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest … -q        # + the behavioural half

⛔ WHAT WAS WRONG. `reason/runner.run` counts into a `Counter`, and `dict(out)` carries only the keys
something incremented. The sweep relayed `_outcomes.get("emitted")`, so a pass that emitted nothing
handed `None` to `_count`, which writes NO ROW — the row migration 0188 reserves for "the stage did
not run". On production, 2026-10-05: 64 sweeps since 3 Oct, `capability_resolved` written in 59 of
them, `decision_emitted` in 3, its values 1–4 and never 0.

⛔ AND IT COUNTED ONE LANE OF THREE. `emitted` is the rule lane's key; `native_emitted` and
`composite` never reached the stage. In the three sweeps that built cards it read 4, 2 and 1 beside
15, 3 and 3 cards — a funnel that grew in the middle.

Structural checks walk the AST, never the text: this docstring names every key it checks.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

from genios_engine.platform.funnel import CAPABILITY_RESOLVED, DECISION_EMITTED

_ENGINE = Path(__file__).resolve().parents[1] / "genios_engine"


def _func(rel: str, name: str) -> ast.FunctionDef:
    tree = ast.parse((_ENGINE / rel).read_text(encoding="utf-8"), filename=rel)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {rel} — the test's premise moved")


def _increments(fn: ast.FunctionDef, constant: str) -> list[ast.AugAssign]:
    """Every `out[<constant>] += …` in a function, the constant referenced by NAME."""
    return [n for n in ast.walk(fn)
            if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Subscript)
            and isinstance(n.target.slice, ast.Name) and n.target.slice.id == constant]


# =================================================================================================
# 1 · the relay reads the pass's own count
# =================================================================================================
def test_the_sweep_relays_the_passs_own_decision_count():
    chain = _func("api/routes.py", "_run_l2_chain")
    calls = [n for n in ast.walk(chain)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "_count"
             and n.args and isinstance(n.args[0], ast.Attribute)
             and n.args[0].attr == "DECISION_EMITTED"]
    assert len(calls) == 1, "exactly one writer per number — see platform/funnel.py"
    gets = [n for n in ast.walk(calls[0].args[1])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "get"]
    assert gets, "the stage is not read from the pass's outcomes"
    key = gets[0].args[0]
    assert isinstance(key, ast.Attribute) and key.attr == "DECISION_EMITTED", (
        "the relay reads a lane's key (`emitted`) instead of the pass's own decision count")


# =================================================================================================
# 2 · the runner counts every lane, and writes its zeros only when the pass completed
# =================================================================================================
def test_every_lane_that_emits_counts_into_the_stage():
    run_fn = _func("reason/runner.py", "run")
    counted = [n for n in _increments(run_fn, "DECISION_EMITTED")
               if not (isinstance(n.value, ast.Constant) and n.value.value == 0)]
    assert len(counted) >= 3, (
        f"{len(counted)} emission sites count into decision_emitted; the rule lane, native "
        "capabilities and composites each emit decisions")


def test_a_completed_pass_writes_both_zeros_and_a_retry_writes_none():
    run_fn = _func("reason/runner.py", "run")
    returns = [n for n in ast.walk(run_fn) if isinstance(n, ast.Return)
               and isinstance(n.value, ast.Dict)
               and any(isinstance(k, ast.Constant) and k.value == "outcomes" for k in n.value.keys)]
    final = max(returns, key=lambda r: r.lineno)
    retries = [r for r in returns if r is not final]
    assert retries, "the early-return retry paths are gone — the zero rule needs re-reading"
    for constant in ("CAPABILITY_RESOLVED", "DECISION_EMITTED"):
        zeros = [n for n in _increments(run_fn, constant)
                 if isinstance(n.value, ast.Constant) and n.value.value == 0]
        assert zeros, f"a completed pass does not write {constant}'s zero"
        for z in zeros:
            assert max(r.lineno for r in retries) < z.lineno < final.lineno, (
                f"{constant}'s zero is written where a retrying pass would report it: a pass that "
                "stopped early would claim it looked and found nothing")


def test_the_multi_pack_merge_sums_decisions():
    """Unlike `capability_resolved` (every pack walks the same subjects, so a max), decisions are
    per pack — two packs that each emit one decision emitted two."""
    merge = _func("reason/runner.py", "run_all")
    special = [n for n in ast.walk(merge) if isinstance(n, ast.If)
               and any(isinstance(c, ast.Name) and c.id == "DECISION_EMITTED"
                       for c in ast.walk(n.test))]
    assert not special, "decision_emitted is merged by a special case; it must be summed"


# =================================================================================================
# 3 · behavioural — a pass that decides nothing reports 0, not nothing
# =================================================================================================
@pytest.mark.pg
@pytest.mark.skipif(not os.environ.get("GENIOS_TEST_DATABASE_URL"),
                    reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
def test_a_pass_that_decides_nothing_reports_zero(pg_store):
    from datetime import datetime, timezone

    from sqlalchemy import text

    from genios_engine.packs.wiring import make_registry
    from genios_engine.platform.intelligence_onboarding import provision_intelligence
    from genios_engine.reason.runner import run_all
    from tests.test_e2e_all_layers import _fresh_tenant, _seed_org

    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    org = "funnel_zero_decision"
    _seed_org(pg_store, org)
    _fresh_tenant(pg_store, org)
    provision_intelligence(pg_store.engine, org)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into graph_nodes (org_id, node_id, node_type, canonical_key) "
                       "values (:o, :n, :t, :k) on conflict do nothing"),
                  {"o": org, "n": "nd_nothing_to_decide", "t": "zzz_no_such_subject",
                   "k": "zzz:nothing-to-decide"})

    out = run_all(org_id=org, store=pg_store, eval_time=datetime(2026, 10, 2, tzinfo=timezone.utc),
                  registry=make_registry(url))
    assert out["packs"], "the tenant has no pack, so no pass ran — the premise of this test failed"
    outcomes = out["outcomes"]
    assert outcomes.get(DECISION_EMITTED) == 0, (
        f"a pass that emitted nothing must report 0, not omit the key: {outcomes}")
    assert CAPABILITY_RESOLVED in outcomes, f"capability_resolved's zero is missing: {outcomes}"
