"""L4-00 · the executive layer could not say which of its silences were deliberate.

⛔ WHAT THIS LAYER IS, MEASURED FIRST. `executive/` is 25 files and 5,731 lines, and unlike Layer
3's dormant machinery it IS wired: `api/routes.py:1150` calls `sweep.run_executive` for every org
on every heartbeat tick, before distribution, and that plans commitments from authoritative
decisions then validates, transitions, reminds, escalates and closes them. Five tables, delegation
wiring, fourteen test files, and `record_outcome` feeding Layer 7. **The execution half is done.**

⛔ WHAT WAS MISSING IS THE DECLARATION. `reason/uncited_lanes`, `reason/situation_binding`,
`context/lane_health.DORMANT_LANES` and `patterns/routing.UNROUTED_PATTERN_TYPES` all exist so a
reader can tell a deferred capability from a forgotten one. `executive/` had NOTHING of the kind,
so three public functions with no caller looked exactly like three oversights — and one of them,
`monitor.blocking_action`, is a real product gap while the other two are correct.

This file makes that distinction enforceable in both directions.
"""
from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.executive import unreached as U

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "genios_engine"
EXECUTIVE = ENGINE / "executive"


def _sources() -> dict[str, str]:
    out = {}
    for path in ENGINE.rglob("*.py"):
        try:
            out[str(path.relative_to(ROOT))] = path.read_text(encoding="utf-8")
        except OSError:                                       # pragma: no cover
            continue
    return out


def _unreached() -> frozenset[str]:
    """`{module.function}` for every public executive function nothing calls."""
    called = U.called_names(_sources())          # ONE pass over the engine, not one per function
    found = set()
    for path in sorted(EXECUTIVE.glob("*.py")):
        # ⛔ `unreached.py` IS THE GUARD, and its callers are this file by design. Scanning it
        # would demand a declared silence for each of its own helpers — noise that says nothing
        # about the layer. `__init__.py` re-exports and defines nothing.
        if path.name in {"__init__.py", "unreached.py"}:
            continue
        for name in U.public_functions(path):
            if called.get(name, 0) == 0:
                found.add(f"{path.stem}.{name}")
    return frozenset(found)


# =================================================================================================
# 1 · ⛔ THE TOTALITY GUARD — both directions
# =================================================================================================

def test_every_unreached_executive_function_is_declared():
    """⛔ THE DIRECTION THAT MATTERS. A unit built, tested, green and called by nothing looks
    exactly like one that works. Layer 2 counted that nine times and Layer 3 twelve; this is the
    first guard that makes it impossible to add a tenth here in silence."""
    extra = U.undeclared(_unreached())
    assert extra == (), (
        f"{len(extra)} public executive function(s) are called by nothing and have no entry in "
        f"UNREACHED: {extra}. Add one saying why it is not called and what would change that — or "
        "wire it.")


def test_every_declared_entry_is_still_unreached():
    """The other direction, and the one L3-01 lost: a declaration for something now wired reads as
    a live gap forever, and sends the next reader looking for work that is done."""
    gone = U.missing(_unreached())
    assert gone == (), (
        f"UNREACHED still names {gone}, which are now called (or deleted). Remove the entries — a "
        "stale silence is worse than none, because somebody will act on it.")


def test_the_count_is_six_and_they_are_the_measured_six():
    """Pinned so the gap is a number rather than an impression. It may shrink; it may not grow
    without somebody writing down why."""
    assert set(U.UNREACHED) == {"assignment.resolve_approver_seat",
                                "coordination.can_complete",
                                "coordination.coordination_snapshot",
                                "execution.build_from_decision",
                                "lifecycle.is_terminal",
                                "monitor.blocking_action"}
    # ⛔ TWO OF THE SIX ARE REAL PRODUCT GAPS, and they are marked so a reader scanning this table
    # does not weigh a one-line predicate the same as a missing approver.
    real = [k for k, (why, _m) in U.UNREACHED.items() if "REAL PRODUCT GAP" in why]
    assert sorted(real) == ["assignment.resolve_approver_seat", "monitor.blocking_action"]


def test_every_declaration_carries_a_reason_and_a_mover():
    """A silence without a mover is one nobody will ever end; one without a reason gets 'fixed' by
    the next reader who notices it. Every declared-silence table in this codebase carries both."""
    for name, (why, mover) in U.UNREACHED.items():
        assert len(why) > 150, f"{name} has no real reason recorded"
        assert "MOVES WHEN" in mover, f"{name} declares no mover"


# =================================================================================================
# 2 · ⛔ THE SCANNER IS STRUCTURAL — a mention is not a call
# =================================================================================================

def test_a_definition_is_not_a_call():
    """The hand-written grep this replaces counted `def f` as a use and reported two live
    functions as dead. Counting `ast.Call` nodes cannot make that mistake."""
    assert U.call_sites("f", {"m": "def f():\n    return 1\n"}) == 0


def test_an_all_entry_and_a_docstring_are_not_calls():
    """⛔ THE BLUNT-GREP GUARD, and it caught a real false positive during this build: `__all__`
    exports `cards_from_situations` as a NAME, and a first-draft check in L3-19 read that as the
    feature literal. Same family, tenth occurrence on this branch."""
    assert U.call_sites("f", {"m": '"""calls f sometimes."""\n__all__ = ["f"]\n'}) == 0


def test_both_call_shapes_count():
    """`f()` and `mod.f()` are the same use. Counting only the bare form would declare every
    function reached through a module alias as dead — which is most of `deliver/`'s imports."""
    assert U.call_sites("f", {"a": "f()\n"}) == 1
    assert U.call_sites("f", {"a": "mod.f()\n"}) == 1
    assert U.call_sites("f", {"a": "f()\nmod.f()\nother()\n"}) == 2


def test_public_functions_reads_module_scope_only():
    """A nested helper is not a public surface, and a method belongs to its class."""
    src = ("def top():\n"
           "    def inner():\n        pass\n"
           "    return inner\n"
           "def _private():\n    pass\n"
           "class C:\n    def method(self):\n        pass\n")
    path = ROOT / "_scan_probe.py"
    path.write_text(src, encoding="utf-8")
    try:
        assert U.public_functions(path) == ("top",)
    finally:
        path.unlink()


# =================================================================================================
# 3 · ⛔ PULL-ONLY IS A DIFFERENT CLAIM FROM UNREACHED
# =================================================================================================

def test_the_pull_only_surfaces_really_have_routes():
    """These are NOT unreached — each has a live HTTP route. What they lack is a producer. If one
    lost its route it would become unreached and belong in the other table."""
    routes = (ENGINE / "api" / "executive_routes.py").read_text(encoding="utf-8")
    for surface, (route, _why) in U.PULL_ONLY.items():
        path = route.split(" ", 1)[1]
        assert f'@router.get("{path}")' in routes, f"{surface} claims {route}, which does not exist"


def test_no_surface_is_in_both_tables():
    """A function cannot be both uncalled and reachable by a route. Overlap would mean one of the
    two tables is describing something it did not measure."""
    pull = {name.split(".")[-1] for name in U.PULL_ONLY}
    unreached = {name.split(".")[-1] for name in U.UNREACHED}
    assert pull & unreached == set()


def test_the_preventive_surface_records_that_no_card_is_built():
    """⛔ THE CLAIM WORTH PROTECTING. `modes.py` calls preventive mode the vision's USP, and
    measured, `deliver/` contains no reference to it — so no preventive finding has ever become a
    card. The day one does, this entry is stale and must be rewritten rather than left saying the
    opposite of what ships."""
    delivered = any("preventive" in src for name, src in _sources().items()
                    if name.startswith("genios_engine/deliver/"))
    assert not delivered, (
        "deliver/ now references preventive — the PULL_ONLY entry for modes.load_preventive is "
        "out of date. Update it to say what is pushed and under what threshold.")
    assert "USP" in U.PULL_ONLY["modes.load_preventive"][1]


# =================================================================================================
# 4 · ⛔ THE DECLARED UNKNOWN
# =================================================================================================

def test_the_unit_numbering_question_is_recorded_as_open_not_as_a_gap():
    """⛔ Units 6 and 8 have no file, and three files carry no number — which does not divide. The
    L5 spec that assigned them is not in this repo, and L3-17 is the standing lesson about
    declaring a capability missing because a search found no name: `prior_decision 0` was a grep,
    and the thing it declared absent had run on every sweep for months."""
    assert "Cannot be resolved without the L5 spec" in U.UNIT_NUMBERING_UNRESOLVED
    assert "MOVES WHEN" in U.UNIT_NUMBERING_UNRESOLVED
