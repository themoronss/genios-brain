"""STEP-04 · the compiled lane reads who we are once per sweep, not once per situation.

    pytest tests/reason/test_the_shadow_reads_who_we_are_once.py -q

Tree `yc2_w27_s04 · M22.C2.L-logic.V2.U23`, found by U14's report. `situation_bso.gather_members`
leaves us out of a situation's members (U14) and reads `platform/self_identity.identity_for` itself
when it is not handed the answer. `reason/domain_shadow.shadow_compile` called it once per situation
without one — one more statement for every situation of every sweep. Checked by the AST: the sweep
reads the identity outside its loop and hands it to every `gather_members`.
"""
from __future__ import annotations

import ast
import inspect

from genios_engine.reason import domain_shadow


def _tree() -> ast.AST:
    return ast.parse(inspect.getsource(domain_shadow.shadow_compile))


def _named(node: ast.AST, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)
            and (getattr(n.func, "id", None) == name or getattr(n.func, "attr", None) == name)]


def test_every_member_gathering_is_handed_the_identity():
    calls = _named(_tree(), "gather_members")
    assert calls, "the sweep no longer gathers members — re-read this test"
    assert all("us" in {k.arg for k in c.keywords} for c in calls), (
        "gather_members reads who we are again, once per situation")


def test_the_identity_is_read_once_outside_the_loop():
    tree = _tree()
    assert len(_named(tree, "identity_for")) == 1
    inside = [c for loop in ast.walk(tree) if isinstance(loop, (ast.For, ast.While))
              for c in _named(loop, "identity_for")]
    assert not inside, "who we are is read inside the per-situation loop"
