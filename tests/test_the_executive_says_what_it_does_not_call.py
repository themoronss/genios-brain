"""L4-00 · the executive layer could not say which of its silences were deliberate.

⛔ WHAT THIS LAYER IS, MEASURED FIRST. `executive/` is 27 files and 6,167 lines (25 / 5,731 when
this file was written), and unlike Layer 3's dormant machinery it IS wired: `api/routes.py:1195`
calls `sweep.run_executive` for every org
on every heartbeat tick, before distribution, and that plans commitments from authoritative
decisions then validates, transitions, reminds, escalates and closes them. Five tables, delegation
wiring, fourteen test files, and `record_outcome` feeding Layer 7. **The execution half is done.**

⛔ WHAT WAS MISSING IS THE DECLARATION. `reason/uncited_lanes`, `reason/situation_binding`,
`context/lane_health.DORMANT_LANES` and `patterns/routing.UNROUTED_PATTERN_TYPES` all exist so a
reader can tell a deferred capability from a forgotten one. `executive/` had NOTHING of the kind,
so three public functions with no caller looked exactly like three oversights — and one of them,
`monitor.blocking_action`, was a real product gap while the other two are correct.

⛔ **UPDATED 2026-10-01.** `monitor.blocking_action` is now wired (see the count test below), so
the table is five. And the citation above was `api/routes.py:1150`; it is **1195** — the claim was
true and the address had gone stale, which is finding **F11** in
`speedrun008/YCW27/layer-4-executive/03-FINDINGS.md`. ⛔ `tests/test_spec_deferrals_resolve.py`
cannot catch that: it resolves document paths, not `file.py:line` citations in prose.

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


def test_the_count_is_five_and_they_are_the_measured_five():
    """Pinned so the gap is a number rather than an impression. It may shrink; it may not grow
    without somebody writing down why.

    ⛔ SIX -> FIVE ON 2026-10-01, and it shrank the way the docstring invites.
    `monitor.blocking_action` is now called from `executive/reminder.reminder_facts`, so its
    `next_action` names the step actually outstanding instead of `actions[0]`.

    What it was doing before: `reminder_facts` read `execution.first_action`, which is
    `self.actions[0]` with **no completion filter**, and that value travels to
    `deliver/executive_bridge.py:105` and onto a Slack message. ⛔ So a commitment whose first step
    was already done was reminded about the **finished** step — which `sweep.py`'s own docstring
    calls *"the single most damaging thing a system like this can do"*.

    ⛔ Measured 2026-10-01: **0 of 794 actions had ever been completed**, so the two agreed on every
    commitment in existence and it had never fired. It fires on the first completion, and
    `api/executive_routes.complete_action` is live — which is why it was fixed before the feature
    was used. Tests:
    `tests/executive/test_a_reminder_names_the_step_it_waits_on.py` (11, and six of them are the
    first tests `blocking_action` has ever had).
    """
    assert set(U.UNREACHED) == {"assignment.resolve_approver_seat",
                                "coordination.can_complete",
                                "coordination.coordination_snapshot",
                                "execution.build_from_decision",
                                "lifecycle.is_terminal"}
    # ⛔ AND NONE OF THE FIVE IS NOW UNTESTED. Two were — `blocking_action` (wired in U3) and
    # `lifecycle.is_terminal`, which got its first tests in
    # `tests/executive/test_a_closed_set_with_two_spellings.py`. Measured there: the guard at
    # `execution_guard.py:126` re-inlines `TERMINAL_STATES` and CANNOT import the predicate,
    # because `lifecycle.py:39` imports `execution_guard`. The caller that wants it may not have
    # it, which is why the entry stays rather than closing.
    #
    # ⛔ ONE OF THE FIVE IS A REAL PRODUCT GAP — it was two. `assignment.resolve_approver_seat` is
    # the one left, and it is blocked twice over: `execution_actions` has no approver column (so a
    # contract field and migration `0191`, behind the unapplied `0186`-`0190`) and
    # `authority_rules` holds zero rows, so the answer would be `None` on all 410 gated actions.
    # Receipt #32 counts it rather than leaving it to prose.
    real = [k for k, (why, _m) in U.UNREACHED.items() if "REAL PRODUCT GAP" in why]
    assert sorted(real) == ["assignment.resolve_approver_seat"]


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


def test_no_pull_only_surface_has_quietly_acquired_a_producer():
    """⛔ THE MISSING DIRECTION, AND THE STALENESS IT LET THROUGH FOR WEEKS.

    `UNREACHED` is checked both ways: undeclared silences fail, and declarations for things now
    called fail too. `PULL_ONLY` had only the first half — three tests asking whether the routes
    exist, whether the tables overlap, and one BESPOKE check on `modes.load_preventive`. Nothing
    asked the other four whether they had grown a producer.

    ⛔ So `summary.build_summary` sat here saying the ladder *"is still only composed where a caller
    asks for a summary, **never as a scheduled digest**"* while
    `deliver/outbox._current_digest_payload` composed a `one_minute` summary and `_drain_claimed`
    sent it on the very next line (`outbox.py:1073`, inside `drain`). It had a route AND a
    producer, so it was not pull-only — it was simply shipped. It has been removed.

    > ⛔ **One direction alone is half a guard, and a guard written for one member of a closed
    > table is half of that.**

    This is the preventive check generalised: for every surface, the function it names must not be
    CALLED anywhere under `deliver/`. A route plus a producer is a push, whatever the entry says.
    """
    delivery = {name: src for name, src in _sources().items()
                if name.startswith("genios_engine/deliver/")}
    called = U.called_names(delivery)

    for surface in U.PULL_ONLY:
        function = surface.split(".")[-1]
        assert called.get(function, 0) == 0, (
            f"⛔ `{surface}` is called {called[function]} time(s) under `deliver/`, so it has a "
            "producer and is no longer pull-only. Either it ships — remove the entry and say so "
            "where a reader will look — or the call is not a producer and the entry must say why. "
            "This is exactly how `summary.build_summary` went stale.")


def test_the_preventive_surface_still_records_that_no_card_is_built():
    """⛔ THE ONE CLAIM THAT NEEDS MORE THAN THE GENERAL CHECK. `modes.py` calls preventive mode
    the vision's USP. The general test above proves `load_preventive` has no caller in `deliver/`;
    this proves `deliver/` does not reach preventive mode by ANY other spelling, which is a
    stronger statement and the one the entry actually makes."""
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
