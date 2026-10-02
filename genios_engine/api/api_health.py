r"""What `api/` deliberately does not call — the HTTP surface's declared silence.

⛔ TWO FUNCTIONS, AND TOGETHER THEY SAY SOMETHING PRECISE: **the policy enforcement path does not
exist.** One of them is honest about that in the future tense and the other is not.

⛔ AND 25 ROUTE HANDLERS ARE NOT IN THIS TABLE, DELIBERATELY. A `@router.get` function is wired by a
decorator and has no Python caller by design, so `reachability.decorated_functions` drops them before
the scan. Asking `api/` for 25 declarations that all say *"a route handler has no Python caller"*
would be paperwork, and `tests/executive/test_a_call_resolved_by_name_is_not_a_call.py` pins the
exclusion. Auth dependencies are dropped too — `require_session_seat` has **8** `Depends()`
references and is wired, not silent.

The machinery is `platform/reachability.py`, shared rather than copied. ⛔ Three wiring mechanisms
are subtracted before anything reaches this table: a **call**, a **decorator** (a route handler has
no Python caller by design) and a **reference** (`Depends(f)`, a dispatch table, a registry). The
third is the biggest — engine-wide it rescued **46** functions that looked unreached, including
`platform/auth.require_owner` with **35** references.
"""
from __future__ import annotations

from pathlib import Path

from genios_engine.platform.reachability import (engine_sources, missing, now_called,
                                                 package_functions, undeclared)

_PKG = Path(__file__).resolve().parent
_ENGINE = _PKG.parent


#: ⛔ Public functions in `api/` with no production caller — `{name: (why, mover)}`.
#:
#: CLOSED, and checked in BOTH directions by `tests/api/test_the_api_layer_says_what_it_does_not_call.py`: an entry naming a function that
#: is now called is as much a lie as a function that is unreached and undeclared.
UNREACHED: dict[str, tuple[str, str]] = {
    "approval_routes.enqueue": (
        "⛔ ITS DOCSTRING CLAIMS A CALLER IT DOES NOT HAVE: *'Park an action pending human approval. "
        "Returns the approval id. **Called from the policy enforcement path** (a require_approval "
        "decision). Kept importable for that wiring.'* Measured 2026-10-01: zero calls, zero "
        "references, zero tests. **The policy enforcement path does not exist**, so 'called from' "
        "is a sentence about a future. Its sibling `policy_routes.evaluate` says the same thing in "
        "the future tense and is therefore the honest one. "
        "⛔ NOT TO BE CONFUSED WITH L4's `requires_approval`. That is a FIELD on "
        "`contracts/execution.ExecutionAction`, read at `execution.py:233` to gate autonomy, and it "
        "IS live — 410 of 794 actions carry it. This is a policy VERDICT string in a different "
        "ladder. **Two implementations of one word can be two different questions**, and merging "
        "these two findings would have been wrong.",
        "MOVES WHEN the policy enforcement path is built, which is the same mover as "
        "`policy_routes.evaluate` — ⛔ the pair moves together or neither does, because an enqueue "
        "with nothing deciding and a decision with nowhere to park are each half a feature"),

    "policy_routes.evaluate": (
        "*'Strongest decision across enabled rules (allow<warn<require_approval<block). `rules` are "
        "serialized policy rows. **Kept importable for a future enforcement path.**'* ⛔ The honest "
        "half of the pair: it says *future*, and it is. A pure evaluator sitting in a routes module "
        "because that is where the policy rows are served from, not because a route calls it.",
        "MOVES WITH `approval_routes.enqueue` — see that entry. ⛔ Whether a policy ladder should "
        "enforce at all is a product decision nobody has taken"),
}


def _sources() -> dict[str, str]:
    return engine_sources(_ENGINE)


def api_functions() -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in `api/`."""
    return package_functions(_PKG)


def api_undeclared() -> tuple[str, ...]:
    """Unreached public functions in `api/` that this module does not declare."""
    return undeclared(_PKG, _sources(), frozenset(UNREACHED))


def api_missing() -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction."""
    return missing(_PKG, frozenset(UNREACHED))


def api_now_called() -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie."""
    return now_called(_sources(), frozenset(UNREACHED))


__all__ = ["UNREACHED", "api_functions", "api_missing", "api_now_called", "api_undeclared"]
