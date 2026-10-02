r"""`capture/` states what it does not call — and the machinery is shared, not copied.

⛔ WHAT WAS WRONG. Four packages declared their own silences; the other seven had never been asked.
Measured 2026-10-01 with the corrected resolver: **123 top-level public functions across the engine
are unreached by production and declared nowhere.** `capture/` holds **7**.

⛔ AND THE MACHINERY COULD NOT HAVE BEEN REUSED WHERE IT WAS. `executive/unreached.py` wrote the AST
walk, and `deliver/delivery_health.py` imported it from there — legal, because `deliver/` is PRODUCT
layer 6 and `executive/` is 5, so that import is DOWNWARD. **`capture/` is layer 1**, and
`capture/ -> executive/` is an UPWARD import `tests/test_layer_topology.py` fails the build over. So
`STEP-17` began by moving it to `platform/reachability.py` (CROSS_CUTTING), which every layer may
import and which imports nothing from the engine at all.

⛔ ONE TABLE, NOT THREE, AND THE SHAPE IS A FINDING. `deliver/` needed three — an un-cut-over
architecture, deliberate silences, and defects — because it carries a second delivery control plane.
`capture/`'s seven are all one kind: tooling and reports whose reader is a person or a test. **A
package gets the tables its triage needs**, and adding an empty `KNOWN_UNWIRED` here to match
`deliver/` would be a table asserting nothing.
"""
from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

from genios_engine.capture import capture_health as C
from genios_engine.platform import reachability as R

_PKG = Path(C.__file__).resolve().parent
_ENGINE = _PKG.parent


# ---------------------------------------------------------------------------------------------
# 1 · the inventory, both directions
# ---------------------------------------------------------------------------------------------

def test_every_unreached_public_function_is_declared() -> None:
    """The whole point: a function nothing calls either has a reason here, or it is an oversight."""
    assert C.capture_undeclared() == (), (
        "these public functions in capture/ are called by nothing in the engine and declared "
        f"nowhere: {C.capture_undeclared()}")


def test_no_declared_entry_names_a_function_that_does_not_exist() -> None:
    """⛔ Declared and written are two directions; one alone is half a guard. An entry for a deleted
    function reads as a considered decision about live code."""
    assert C.capture_missing() == (), f"entries naming absent functions: {C.capture_missing()}"


def test_no_declared_entry_has_quietly_acquired_a_caller() -> None:
    """⛔ L4's actual bug: `summary.build_summary` sat in `PULL_ONLY` after `outbox._drain_claimed`
    started sending it on a tick, because that table had only the first direction."""
    assert C.capture_now_called() == (), (
        "these entries declare a function uncalled and the engine now calls it -- the entry is the "
        f"lie, not the call: {C.capture_now_called()}")


def test_every_entry_carries_a_reason_and_a_mover() -> None:
    """`reason/unit_health.DeclaredSilence` refuses construction without a mover, for this reason: a
    silent lane with no named mover is an undeclared silence with paperwork."""
    thin = [name for name, (why, mover) in C.UNREACHED.items()
            if len(why) < 80 or len(mover) < 20]
    assert not thin, f"entries whose reason or mover says nothing usable: {thin}"


# ---------------------------------------------------------------------------------------------
# 2 · ⛔ the shared machinery — one implementation, eleven users
# ---------------------------------------------------------------------------------------------

def test_the_declaration_uses_the_shared_machinery_and_does_not_copy_it() -> None:
    """⛔ A second AST walk is a second answer waiting to disagree with the first. Read from the
    AST, so a comment mentioning the module does not satisfy it."""
    tree = ast.parse(Path(C.__file__).read_text(encoding="utf-8"))
    imported_from = {n.module for n in ast.walk(tree)
                     if isinstance(n, ast.ImportFrom) and n.module}
    assert any(m.endswith("platform.reachability") for m in imported_from), (
        "capture_health does not import the shared machinery -- a copied walk will disagree")
    assert not any(m and "executive" in m for m in imported_from), (
        "capture/ imports executive/ -- that is layer 1 importing layer 5, which "
        "tests/test_layer_topology.py fails the build over, and it is why the machinery moved")


def test_the_shared_machinery_reproduces_this_table_exactly() -> None:
    """⛔ THE PROOF THE EXTRACTION IS FAITHFUL, and it is asserted rather than assumed.

    The shared walk, run over `capture/`, must return exactly the set this module declares — set for
    set, not count for count. The same assertion holds for `executive/` and `deliver/`, which is
    what made moving the machinery safe.
    """
    found = R.unreached_in(_PKG, R.engine_sources(_ENGINE))
    assert found == frozenset(C.UNREACHED), (
        f"the shared walk and this table disagree: {sorted(found ^ frozenset(C.UNREACHED))}")


def test_the_self_exclusion_is_derived_and_not_a_list() -> None:
    """⛔ IT WAS A LIST FOR ABOUT A MINUTE. `SELF_DECLARING` named the declaration modules, and the
    first thing that happened after writing it was adding `capture_health.py` and forgetting to add
    its name — so the scan reported this module's own four helpers as undeclared.

    **A list you must remember to extend is a list that will be wrong.** A declaration module is now
    detected by the fact that makes it one: it imports `platform.reachability`.
    """
    assert R._is_declaration_module(Path(C.__file__)), (
        "capture_health is no longer detected as a declaration module, so its own helpers will be "
        "demanded as declared silences")
    assert not any(q.startswith("capture_health.") for q in C.capture_functions()), (
        "the declaration module is being scanned as ordinary code")


# ---------------------------------------------------------------------------------------------
# 3 · ⛔ the triage, pinned where it is load-bearing
# ---------------------------------------------------------------------------------------------

def test_one_table_is_the_right_number_for_this_package() -> None:
    """⛔ THE SHAPE IS A FINDING. `deliver/` needed three tables because it carries a second
    delivery architecture; `capture/`'s seven are all one kind. An empty `KNOWN_UNWIRED` here would
    assert nothing, and a table that asserts nothing teaches a reader to skip the ones that do."""
    tables = [n for n in ("UNREACHED", "PULL_ONLY", "KNOWN_UNWIRED", "UNCUT_OVER")
              if hasattr(C, n)]
    assert tables == ["UNREACHED"], (
        f"capture_health now has {tables} -- if a second kind of silence genuinely appeared here, "
        "this test is where that is recorded; if not, the extra table asserts nothing")


def test_the_benchmark_harness_is_exercised_by_tests_and_not_by_the_pipeline() -> None:
    """⛔ The distinction that makes three of the seven benign. A harness scores the layer; it is
    not a step in it. Wiring `score_benchmark` would score every object on every sweep to answer a
    question nobody asked that tick."""
    tests = {str(p): p.read_text(encoding="utf-8") for p in (_ENGINE.parent / "tests").rglob("*.py")}
    by_test = R.qualified_call_counts(tests)
    for name in ("score_benchmark", "calibrate", "behavioural_score_is_quotable"):
        assert f"benchmark.{name}" in C.UNREACHED
        assert by_test.get(("benchmark", name), 0) > 0, (
            f"benchmark.{name} is now exercised by nothing at all -- it has stopped being a "
            "harness and become dead code, which is a different entry")


def test_the_undocumented_one_is_declared_as_undocumented() -> None:
    """⛔ `source_registry.is_buildable` is the only one of the seven with NO docstring, NO test and
    NO caller. Declaring it deliberate would invent a reason; declaring it a defect would invent a
    severity. **An honest "nobody wrote down what this is for" is a declaration; a guessed reason is
    decoration.**"""
    why, mover = C.UNREACHED["source_registry.is_buildable"]
    assert "NO DOCSTRING" in why.upper() or "no docstring" in why
    assert "recorded nowhere" in why

    from genios_engine.capture import source_registry
    assert inspect.getdoc(source_registry.is_buildable) is None, (
        "somebody documented it -- then the entry should say what it is for, or it should be wired")

    tests = {str(p): p.read_text(encoding="utf-8") for p in (_ENGINE.parent / "tests").rglob("*.py")}
    assert R.qualified_call_counts(tests).get(("source_registry", "is_buildable"), 0) == 0, (
        "it now has a test, which is evidence of intent and changes this entry")


def test_the_report_with_no_renderer_names_its_missing_reader() -> None:
    """⛔ `intent_rate.degraded_sources`'s own docstring names the person who would read it — *"the
    useful question a person asks of this report is which connector do I look at"* — and nothing
    calls it. **A function that names its reader and has no caller is a surface that was never
    built**, not a helper somebody forgot."""
    for name in ("unknown_rate_bp", "degraded_sources"):
        why, mover = C.UNREACHED[f"intent_rate.{name}"]
        assert "renderer" in why.lower() or "reader" in why.lower()
        assert "surface" in mover.lower(), (
            f"intent_rate.{name}'s mover no longer names the surface that would call it")


# ---------------------------------------------------------------------------------------------
# 4 · ⛔ the policy decisions, visible rather than buried
# ---------------------------------------------------------------------------------------------

def test_the_script_policy_is_one_named_constant() -> None:
    """⛔ `SCRIPTS_ARE_CALLERS` decides whether an ops CLI counts as a caller, and it applies to all
    eleven packages. It was taken while the question was open, so it is one constant to flip and
    nothing reads `scripts/` around it."""
    assert isinstance(R.SCRIPTS_ARE_CALLERS, bool)
    with_scripts = len(R.engine_sources(_ENGINE, include_scripts=True))
    without = len(R.engine_sources(_ENGINE, include_scripts=False))
    assert with_scripts > without, "the scripts directory is no longer being read at all"
    assert len(R.engine_sources(_ENGINE)) == (with_scripts if R.SCRIPTS_ARE_CALLERS else without), (
        "the default no longer follows SCRIPTS_ARE_CALLERS, so flipping the constant would do "
        "nothing")


def test_a_decorator_registered_function_is_not_demanded_as_a_declaration() -> None:
    """⛔ 25 public functions in `api/` are registered by a FastAPI decorator and have no Python
    caller by design. `capture/` has no routes, which is why this exclusion costs it nothing — and
    it is asserted here because the engine-wide scan must not demand 25 declarations that all say
    the same thing."""
    api = _ENGINE / "api"
    if not api.is_dir():                                      # pragma: no cover
        return
    decorated = {n for p in api.glob("*.py") for n in R.decorated_functions(p)}
    assert len(decorated) >= 20, (
        "the route handlers stopped being decorator-registered -- re-measure before running the "
        "engine-wide scan over api/")
    assert not any(q.split(".", 1)[1] in decorated for q in C.capture_functions()), (
        "a capture/ function shares a name with a route handler and is being excluded by accident")
