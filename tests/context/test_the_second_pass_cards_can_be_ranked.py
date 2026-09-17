"""19 of 138 cards carried no importance, and a null does not fail a gate — it disappears.

    pytest tests/context/test_the_second_pass_cards_can_be_ranked.py -q

MEASURED ON THE PILOT, 2026-09-15, on the first full sweep after the second reading pass existed:
138 open situations and 19 unranked — 8 `analytic_movement`, 6 `condition_in_review`, 5
`commitment_overdue`. Every one of them a card the second pass had just made knowable, and every
one of them unrankable into a feed.

THE ORDERING, and why both halves of it are right. `refresh_situation_importance` runs far above
the end of the sweep because all six of BLG-18's modifiers read a `derived.*` fact — trend, cohort
position, anomaly, blocked count — written by the analytic block above it. Composing any earlier
reads LAST sweep's analytic stratum, and on a tenant's first sweep an empty one: every modifier
silent, and the cause nothing to do with the composer.

But the second reading pass runs after the angles, because that is the entire point of it — the
readings that consume residue, angle verdicts and correlator output cannot see them on the first
pass, which is the sweep-ordering cycle it was added to close. So it writes situations AFTER the
composer has already run, and the composer's own docstring names the result exactly: *"a null is
invisible to the gate rather than failing it — the situations nobody ranks would be exactly the
ones nobody notices."*

THE FIX IS A SECOND COMPOSITION, NOT A REORDER. Moving either pass breaks the other: composing
later reads a stale stratum, reading earlier breaks the coverage measurement residue is computed
against. The composer is idempotent and byte-stable by construction — a property that is already
load-bearing, because its record reaches the expertise package's content hash and a per-sweep
value there once put 995 MB on one tenant's database — so re-running it rewrites the already-ranked
situations with identical bytes and mints nothing.
"""
from __future__ import annotations

import ast
import inspect

import pytest

from genios_engine.context import runner

pytestmark = pytest.mark.unit


def _module() -> ast.Module:
    return ast.parse(inspect.getsource(runner))


def _calls_named(tree, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and (getattr(n.func, "id", "") == name
                 or getattr(n.func, "attr", "") == name)]


def _first_call_to(tree, *names: str) -> ast.Call | None:
    found = [c for n in names for c in _calls_named(tree, n)]
    return min(found, key=lambda c: c.lineno) if found else None


def test_the_composer_runs_again_after_the_second_reading_pass() -> None:
    """THE DEFECT ITSELF. Without this, every card the second pass creates is born unranked and
    stays that way until the next sweep — which is a whole cycle of the model-gated and
    correlator-fed cards being invisible to anything that orders a feed."""
    tree = _module()
    reread = _first_call_to(tree, "_reread")
    assert reread is not None, "the second reading pass is gone"

    ranks = [c for c in (_calls_named(tree, "refresh_situation_importance") + _calls_named(tree, "_rank"))]
    assert ranks, "nothing composes importance at all"
    after = [c for c in ranks if c.lineno > reread.lineno]
    assert after, ("importance is composed only BEFORE the second reading pass, so every "
                   "situation that pass creates carries a null importance")


def test_the_first_composition_still_runs_before_it() -> None:
    """The other half, which a careless fix would delete. The modifiers read the analytic stratum,
    so the composer must still run after the analytic block — not only at the very end."""
    tree = _module()
    reread = _first_call_to(tree, "_reread")
    ranks = _calls_named(tree, "refresh_situation_importance") + _calls_named(tree, "_rank")
    before = [c for c in ranks if c.lineno < reread.lineno]
    assert before, ("the composer no longer runs before the second pass; on a sweep where the "
                    "second pass writes nothing, nothing would be ranked at all")


def test_the_second_composition_is_skipped_when_the_pass_wrote_nothing() -> None:
    """The common case is a second pass with nothing to add. Re-composing the whole org anyway
    would spend a full pass every sweep to rank zero new situations."""
    src = inspect.getsource(runner)
    tail = src[src.index("second_pass_rows = _reread"):]
    guard = tail.index("if second_pass_rows")
    rank = tail.index("refresh_situation_importance as _rank")
    assert guard < rank, "the second composition is not guarded by the pass having written rows"


def test_neither_composition_can_take_the_sweep_down() -> None:
    """Both are derived views, recomputed on the next drain. A ranking failure that costs
    ingestion would trade a feed's order for the tenant's data."""
    tree = _module()
    for call in _calls_named(tree, "refresh_situation_importance") + _calls_named(tree, "_rank"):
        holders = [t for t in ast.walk(tree) if isinstance(t, ast.Try)
                   and any(call is c for c in ast.walk(t))]
        assert holders, f"an importance composition at line {call.lineno} is unguarded"


def test_the_composer_is_still_the_kind_of_function_that_may_be_run_twice() -> None:
    """The fix rests on idempotence, so the property is pinned where the fix depends on it rather
    than only asserted in a docstring. A clock read inside the stored record would mint a fresh
    ~238 kB expertise package per situation per sweep — the mechanism that put 995 MB on one
    tenant's database — and running the composer twice would double that rate."""
    from genios_engine.context import situation_bso

    composed = ast.parse(inspect.getsource(situation_bso.refresh_situation_importance))
    banned = {"now", "utcnow", "today", "time", "monotonic"}
    offenders = [getattr(n.func, "attr", "") or getattr(n.func, "id", "")
                 for n in ast.walk(composed) if isinstance(n, ast.Call)
                 and (getattr(n.func, "attr", "") in banned or getattr(n.func, "id", "") in banned)]
    assert offenders == [], f"the composer reads a clock of its own: {offenders}"
