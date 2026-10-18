r"""A call resolved by name alone is a call to any function with that name.

⛔ WHAT WAS WRONG. `executive/unreached.called_names` resolves aliases correctly and then counts by
NAME ALONE, so every function sharing a name shares one count. Measured 2026-10-01:

    genios_engine/capture/parked/refetch.py:267     queue.claim_due()

is `InMemoryRefetchQueue.claim_due` — a different function, in a different package, with a
different signature. On the strength of it `deliver/spine.claim_due` read as REACHED, and the whole
claiming tier of the v2 delivery path was invisible to the declaration guard.

⛔ IT WAS NOT A SMALL BLIND SPOT. Switching `executive/`'s own guard to the precise resolver grew
its declared inventory from FIVE to TEN:

    readiness.read              11 apparent callers -> 0   ⛔ and the WHOLE module is unreached
    execution_guard.is_live      3                  -> 0   ⛔ third spelling of one closed set
    lifecycle.is_open            2                  -> 0   ⛔ second spelling of the same set
    execution_store.supersede    2                  -> 0   a race-free replacement path, uncalled
    delegation.propose           1                  -> 0   superseded by two better-named siblings

The names most affected are the shortest and most natural: `read`, `stop`, `resolve`, `extend`,
`is_live`. ⛔ **The failure direction is "reached", which is the direction that reports fewer
problems.**

⛔ AND THE FIRST FIX WAS WORSE THAN THE BUG. Version one credited every imported module with every
call name in the file — 443,610 pairs — and reported `lane_display.describe` and `runner.run_all` as
unreached, because both are called through an alias (`describe_lane`, `run_l3`). A resolver that is
merely stricter is not more correct. This module pins BOTH directions.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.executive import unreached as U

_ENGINE = Path(U.__file__).resolve().parents[1]


def _sources() -> dict[str, str]:
    return {str(p): p.read_text(encoding="utf-8") for p in _ENGINE.rglob("*.py")}


# ---------------------------------------------------------------------------------------------
# the collision, and the five it hid
# ---------------------------------------------------------------------------------------------

def test_a_same_named_method_elsewhere_is_not_a_call() -> None:
    """⛔ The defect, pinned on the case that found it."""
    s = _sources()
    assert U.called_names(s).get("claim_due", 0) > 0, (
        "the collision this module exists for has gone -- if nothing in capture/ calls a method of "
        "this name any more, re-derive spine.claim_due before deleting this test")
    assert U.qualified_call_sites("spine.claim_due", s) == 0, (
        "a file that imports nothing from spine voted on whether spine.claim_due is called")


def test_each_of_the_five_executive_entries_was_hidden_by_the_collision() -> None:
    """⛔ Every one of the five looked reached and none of them is. If a future commit makes one
    genuinely reached, its declaration goes stale and `missing()` is where that surfaces -- this
    test records WHY they are declared at all."""
    s = _sources()
    loose, counts = U.called_names(s), U.qualified_call_counts(s)
    for qualified in ("readiness.read", "execution_guard.is_live", "lifecycle.is_open",
                      "execution_store.supersede", "delegation.propose"):
        module, _, name = qualified.partition(".")
        assert loose.get(name, 0) > 0, (
            f"{qualified} no longer collides with anything -- the loose resolver would now find it "
            "too, so this entry stopped being evidence for the precise one")
        assert counts.get((module, name), 0) == 0, f"{qualified} is now called"


def test_the_whole_readiness_module_is_unreached_not_merely_its_entry_point() -> None:
    """⛔ The sharpest of the five. `read` -> `assess` -> `_verdict` is the entire public chain, and
    `assess`'s only caller is `read` itself. So `assess` having a caller proves nothing about the
    module being used -- which is exactly how a chain stays invisible."""
    counts = U.qualified_call_counts(_sources())
    assert counts.get(("readiness", "read"), 0) == 0
    assert counts.get(("readiness", "assess"), 0) == 1, (
        "assess should have exactly one caller -- read(), inside the same unreached module")


# ---------------------------------------------------------------------------------------------
# ⛔ the other direction: a stricter resolver that is wrong is not an improvement
# ---------------------------------------------------------------------------------------------

def test_an_aliased_import_resolves_to_its_original_name() -> None:
    """⛔ THE MISTAKE VERSION ONE MADE. `card_builder.py` does
    `from .lane_display import describe as describe_lane` and calls the alias; `api/routes.py` does
    `from genios_engine.reason.runner import run_all as run_l3`, five times. A resolver that counts
    the name as written reports both as dead."""
    counts = U.qualified_call_counts(_sources())
    assert counts.get(("lane_display", "describe"), 0) > 0, (
        "describe is called through the alias describe_lane -- reporting it unreached would have "
        "put a live function into a declared-silence table")
    assert counts.get(("runner", "run_all"), 0) >= 5, (
        "run_all is called five times through the alias run_l3")


def test_a_module_alias_resolves_to_the_module() -> None:
    """`from genios_engine.executive import delegation as DLG`, then `DLG.propose_action()`."""
    counts = U.qualified_call_counts(_sources())
    assert counts.get(("delegation", "propose_action"), 0) >= 2
    assert counts.get(("delegation", "create_proposal"), 0) >= 1
    assert counts.get(("delegation", "propose"), 0) == 0, (
        "three entry points to one idea, and the plainest name is the unused one")


def test_a_bare_call_credits_its_own_module() -> None:
    """⛔ NO FILE IMPORTS ITSELF. Requiring an import reported `outbox.shadow_resolve_v2` -- called
    at `outbox.py:1441`, inside its own file -- as unreached, which would have declared L5's one
    production measurement of the v2 path dead."""
    counts = U.qualified_call_counts(_sources())
    assert counts.get(("outbox", "shadow_resolve_v2"), 0) > 0


def test_the_resolver_is_not_merely_returning_zero() -> None:
    """⛔ A resolver that answers 0 for everything passes every assertion above that looks for a
    zero. This is the counterweight: it must find the calls that exist."""
    counts = U.qualified_call_counts(_sources())
    nonzero = sum(1 for v in counts.values() if v > 0)
    assert nonzero > 5000, f"only {nonzero} qualified calls found across the engine -- implausible"
    assert counts.get(("spine", "log_delivery_event"), 0) >= 2, (
        "tracker.py and outbox.py both import and call it")


def test_the_two_resolvers_are_keyed_differently_and_that_is_the_point() -> None:
    """`called_names` -> `{name: count}`. `qualified_call_counts` -> `{(module, name): count}`.
    ⛔ The second is not a refinement of the first; it answers a question the first cannot express,
    which is why both stay."""
    s = _sources()
    loose, precise = U.called_names(s), U.qualified_call_counts(s)
    assert all(isinstance(k, str) for k in loose)
    assert all(isinstance(k, tuple) and len(k) == 2 for k in precise)


# ---------------------------------------------------------------------------------------------
# ⛔ the limitation this guard must never be pointed at without knowing
# ---------------------------------------------------------------------------------------------

def test_a_decorator_registered_function_has_no_python_caller_by_design() -> None:
    """⛔ 25 public functions in the engine are registered by a decorator -- FastAPI route handlers
    -- and the framework calls them, not Python code. Both resolvers correctly find zero qualified
    callers, so pointing this guard at `api/` would report a working HTTP surface as dead.

    `executive/` and `deliver/` have no routes, which is why neither declaration module has ever
    had to care. ⛔ Recorded here because the engine-wide form of this measurement (`STEP-17`) must
    exclude them, and discovering that after writing 25 declarations is the expensive order.
    """
    import ast
    counts = U.qualified_call_counts(_sources())
    decorated_and_unqualified = 0
    for path in (_ENGINE / "api").glob("*.py"):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                                   # pragma: no cover
            continue
        for node in tree.body:
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.decorator_list and not node.name.startswith("_")
                    and counts.get((path.stem, node.name), 0) == 0):
                decorated_and_unqualified += 1
    assert decorated_and_unqualified >= 20, (
        "the api/ route handlers should read as unqualified-unreached -- if they do not, something "
        "now calls them from Python and this limitation needs re-measuring")
