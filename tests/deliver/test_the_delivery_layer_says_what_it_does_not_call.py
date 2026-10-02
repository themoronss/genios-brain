r"""`deliver/` states what it does not call, and every statement is checked in both directions.

⛔ WHAT WAS WRONG. `deliver/` is the largest of the four big packages — 123 top-level public
functions — and it was the only one with no declared-silence module. `reason/` has
`unit_health.py`, `context/` has `lane_health.DORMANT_LANES`, `executive/` has `unreached.py`.
Measured on 2026-10-01 with L4's own tooling and L4's own source convention: **24 of the 123 are
called by nothing in the engine, 0 were declared, and 19 of them had never been read by anybody.**

⛔ THE COUNT WAS FIRST REPORTED AS 4, AND THE ERROR IS WHY `engine_sources` LIVES IN CODE. The first
measurement passed `tests/` into the source set alongside `genios_engine/`, so every function with a
unit test looked reached, and used `rglob` so `channels/` inflated the denominator. Both deviations
erred toward reporting fewer problems. **A reachability number is meaningless without its source
set**, and a convention written only into a document is a convention nothing checks.

⛔ AND THE RESOLVER ITSELF HID A WHOLE TIER. `executive/unreached.called_names` matches an
`ast.Attribute` call by `attr`, which is what correctly resolves aliased imports — and is also what
made `queue.claim_due()` in `capture/parked/refetch.py:267` count as a call to `deliver/spine.
claim_due`, a different function with a different signature in a different package. `spine.claim_due`
was reported reached and is not. **A call resolved by name alone is a call to any function with that
name**, so the "has a declared entry acquired a caller" direction uses `qualified_call_sites`, which
requires the calling file to import it.

⛔ NO BLUNT GREPS. This programme has been bitten fifteen times by a substring check matching the
author's own prose, including once by `ast.get_docstring()` returning CLEANED text while the node
held RAW. Every structural assertion here walks the AST; nothing greps a docstring for a word.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

from genios_engine.deliver import delivery_health as H
from genios_engine.executive.unreached import called_names

_ENGINE = Path(H.__file__).resolve().parents[1]


# ---------------------------------------------------------------------------------------------
# the inventory, both directions
# ---------------------------------------------------------------------------------------------

def test_every_unreached_public_function_is_declared() -> None:
    """The whole point: a function nothing calls either has a reason here, or it is an oversight."""
    assert H.undeclared() == (), (
        "these public functions in deliver/ are called by nothing in the engine and declared "
        f"nowhere: {H.undeclared()}")


def test_no_declared_entry_names_a_function_that_does_not_exist() -> None:
    """⛔ Declared and written are two directions; one alone is half a guard.

    An entry for a deleted function reads as a considered decision about live code.
    """
    assert H.missing() == (), (
        f"declared entries naming functions that do not exist: {H.missing()}")


def test_no_declared_entry_has_quietly_acquired_a_caller() -> None:
    """⛔ L4's actual bug: `summary.build_summary` sat in `PULL_ONLY` after `outbox._drain_claimed`
    started sending it on a tick, because that table had only the first direction."""
    assert H.now_called() == (), (
        "these entries declare a function as uncalled and the engine now calls it -- the entry is "
        f"the lie, not the call: {H.now_called()}")


def test_the_three_tables_do_not_overlap() -> None:
    """A function in two tables has two reasons, and the build cannot say which is current."""
    pairs = [("UNCUT_OVER", "UNREACHED"), ("UNCUT_OVER", "KNOWN_UNWIRED"),
             ("UNREACHED", "KNOWN_UNWIRED")]
    for a, b in pairs:
        overlap = set(getattr(H, a)) & set(getattr(H, b))
        assert not overlap, f"{a} and {b} both claim {sorted(overlap)}"


def test_the_declared_total_is_the_union_of_the_three_tables() -> None:
    """⛔ `DECLARED` is what `undeclared()` subtracts, so a table left out of it would let every
    function in that table satisfy nothing while appearing to be declared."""
    assert H.DECLARED == set(H.UNCUT_OVER) | set(H.UNREACHED) | set(H.KNOWN_UNWIRED)
    assert not (H.DECLARED & set(H.PULL_ONLY)), (
        "PULL_ONLY surfaces are REACHED, so a PULL_ONLY entry must never satisfy the unreached "
        "guard -- a function could then go quiet with nobody noticing")


# ---------------------------------------------------------------------------------------------
# an entry that explains nothing is paperwork
# ---------------------------------------------------------------------------------------------

def test_every_entry_carries_a_reason_and_a_mover() -> None:
    """`reason/unit_health.DeclaredSilence` refuses construction without a mover, for this reason:
    a silent lane with no named mover is an undeclared silence with paperwork."""
    thin = []
    for name, (why, mover) in H.UNREACHED.items():
        if len(why) < 80 or len(mover) < 20:
            thin.append(("UNREACHED", name))
    for name, (_tier, why, _measured_by, mover) in H.UNCUT_OVER.items():
        if len(why) < 80 or len(mover) < 20:
            thin.append(("UNCUT_OVER", name))
    assert not thin, f"entries whose reason or mover says nothing usable: {thin}"


def test_every_known_unwired_entry_names_a_step() -> None:
    """⛔ `KNOWN_UNWIRED` IS NOT A PARKING LOT. A declared defect with no owner is an undeclared
    defect with better manners, and the cheap way to silence this module would be to move a defect
    into it and leave it there."""
    import re
    bad = [n for n, (_what, step) in H.KNOWN_UNWIRED.items()
           if not re.fullmatch(r"STEP-\d{2}", step)]
    assert not bad, f"KNOWN_UNWIRED entries with no closing step: {bad}"


def test_every_uncut_over_entry_names_a_tier_in_the_closed_set() -> None:
    """Four tiers, and an unknown tier is a bookkeeping fault rather than a silent pass -- the rule
    `reason/guards.CANDIDATE_COMPONENTS` applies to score components."""
    bad = [(n, t) for n, (t, _w, _m, _v) in H.UNCUT_OVER.items() if t not in (1, 2, 3, 4)]
    assert not bad, f"UNCUT_OVER entries outside the four tiers: {bad}"


def test_the_only_measured_tier_is_the_one_that_sends_nothing() -> None:
    """⛔ THE FINDING, ASSERTED. The cutover is a gradient: tier 1 (resolution) is shadow-measured
    by `outbox.shadow_resolve_v2`, and tiers 2-4 -- persistence, claiming, policy, every one of
    which touches the network -- have no production evidence at all. If a later commit wires tier 2
    or 3 into the live path, this test is where that shows up.

    ⛔ THIS TEST WAS FIRST WRITTEN AS `"shadow_resolve_v2" in <the prose field>` AND FAILED ON
    CORRECT DATA. The string is present both when a tier NAMES its measurement and when a tier
    explains that the shadow does NOT measure it -- *"`shadow_resolve_v2` stops at resolution and
    never persists"*. Sixteenth time a substring check in this programme matched the author's own
    words. The repair was not a cleverer pattern: `measured_by` became a structured field that is
    `None` or a qualified name, because **a claim worth asserting is worth storing as data.**
    """
    measured = {tier for tier, _why, measured_by, _mover in H.UNCUT_OVER.values()
                if measured_by is not None}
    assert measured == {1}, (
        "exactly tier 1 should carry a measurement; tiers 2-4 touch the network and have no "
        f"production evidence. Tiers carrying one: {sorted(measured)}")

    names = {m for _t, _w, m, _v in H.UNCUT_OVER.values() if m is not None}
    assert names == {"outbox.shadow_resolve_v2"}, (
        f"the only measurement of the v2 path should be the shadow; found {sorted(names)}")


def test_the_declared_measurement_is_itself_reached() -> None:
    """⛔ A tier that names its measurement is making a claim about production, and an unreached
    measurement measures nothing. `presence.absent` is declared exercised BECAUSE
    `shadow_resolve_v2` runs -- so if the shadow stops being called, that declaration becomes false
    and this is where it shows. **Presence is not effect**, applied to the evidence rather than the
    code."""
    sources = H.engine_sources()
    assert H.qualified_call_sites("outbox.shadow_resolve_v2", sources) > 0, (
        "tier 1 is declared shadow-measured and nothing calls the shadow -- the declaration is "
        "then a statement about code that does not run")


# ---------------------------------------------------------------------------------------------
# ⛔ the convention, and the resolver that the convention exposed
# ---------------------------------------------------------------------------------------------

def test_the_source_set_is_the_engine_and_not_the_tests() -> None:
    """⛔ The error that reported 24 as 4. Asserted structurally: `engine_sources` must read under
    `genios_engine/` and nothing else, and it must not reach `tests/`."""
    paths = set(H.engine_sources())
    assert paths, "engine_sources returned nothing"
    assert all("/genios_engine/" in p for p in paths), (
        "engine_sources reached outside the engine")
    assert not any("/tests/" in p for p in paths), (
        "a test is not a caller -- including tests/ makes every unit-tested function look reached, "
        "which is how this layer's unreached count was first reported as 4 instead of 24")
    assert str(_ENGINE / "deliver" / "spine.py") in paths


def test_the_package_scope_is_top_level_files_only() -> None:
    """`glob`, not `rglob` -- matching `executive/unreached.py`. The four functions in `channels/`
    sit behind the `get_channel` registry seam, so a by-name walk reports them dead and they are
    not."""
    assert not any(q.startswith("agent.") or q.startswith("slack.")
                   for q in H.package_functions()), (
        "channels/ adapters are reached through a registry, never by name")
    assert "spine.claim_due" in H.package_functions()


def test_a_same_named_method_elsewhere_cannot_mask_a_function() -> None:
    """⛔ THE RESOLVER DEFECT, PINNED. `capture/parked/refetch.py:267` calls `queue.claim_due()` on
    an `InMemoryRefetchQueue`. `called_names` counts it as a call to `spine.claim_due`;
    `qualified_call_sites` does not, because that file imports nothing from `spine`.

    This is the one assertion in this module that would have caught the error before it was made,
    and it is also the evidence for STEP-13: L4's `UNREACHED` uses the imprecise resolver, so an
    `executive/` function sharing a name with any method in the engine is silently dropped from
    that declaration.
    """
    sources = H.engine_sources()
    assert called_names(sources).get("claim_due", 0) > 0, (
        "the collision this test exists for has gone -- if refetch.py no longer calls a method of "
        "this name, re-derive whether spine.claim_due is genuinely reached before deleting this")
    assert H.qualified_call_sites("spine.claim_due", sources) == 0, (
        "a file that does not import spine voted on whether spine.claim_due is called")


def test_qualified_call_sites_still_sees_a_real_call() -> None:
    """⛔ A precise resolver that returns 0 for everything would pass every test above. `log_delivery
    _event` IS called -- `tracker.py:16` imports it and `outbox.py:1111` imports it in a function
    body -- so the resolver must count it."""
    assert H.qualified_call_sites("spine.log_delivery_event", H.engine_sources()) > 0, (
        "the resolver found no call to a function that two files import and call -- it is not "
        "resolving, it is returning zero")


# ---------------------------------------------------------------------------------------------
# ⛔ the mutation shape that survived 15 tests in L4
# ---------------------------------------------------------------------------------------------

def test_the_walk_actually_READS_the_tables() -> None:
    """⛔ In L4, removing an era bound turned a production number from 3,582 to 0 while 15 tests
    passed, because one test proved the boundary was IMPORTED and nothing proved it was USED.

    So: `undeclared` must reference `DECLARED`, and `now_called` must reference
    `qualified_call_sites` -- read from the AST of each function, excluding its docstring BY
    IDENTITY (the first statement), never by value. `ast.get_docstring()` returns cleaned text
    while the node holds raw, so excluding by value lets prose through.
    """
    for func, expected in ((H.undeclared, "qualified_call_counts"),
                           (H.now_called, "qualified_call_counts"),
                           (H.undeclared, "DECLARED"),
                           (H.now_called, "DECLARED"),
                           (H.missing, "DECLARED")):
        tree = ast.parse(inspect.getsource(func).lstrip())
        body = tree.body[0].body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]                        # the docstring, excluded by IDENTITY
        names = {n.id for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Name)}
        names |= {n.attr for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Attribute)}
        assert expected in names, (
            f"{func.__name__} never reads {expected} -- it is imported and unused, which is the "
            "mutation that survived fifteen tests in L4")


def test_the_defects_are_not_filed_as_decisions() -> None:
    """⛔ The reason there are three tables: filing a broken product promise beside a shim that
    raises on purpose would let the first read as a considered decision.

    ⛔ THIS TEST HARD-CODED THE DEFECT LIST AND SO FAILED TWICE ON CORRECT CODE — once when
    `STEP-14` wired `lane_recall.recall_verdict` and deleted its entry, and again when `STEP-08`
    did the same for `card_builder.resolved_person_name`. Both deletions were right: L4 removed
    `monitor.blocking_action` from `UNREACHED` on exactly that trigger.

    ⛔ THE FIRST REPAIR DIAGNOSED IT AND DID NOT FIX IT. The docstring was corrected to say *"the
    list of defects is not a constant"* and the hard-coded names were left in place, so the same
    failure arrived one step later. **A membership list shrinks every time the work succeeds; an
    invariant does not.** So this now asserts the invariant and nothing else:

      * a defect and a decision never share a table — one function, one current reason
      * every `KNOWN_UNWIRED` entry names the step that closes it (enforced separately too)
      * ⛔ the fail-closed shim is a DECISION, permanently — `push.push_action_to_agents` raises on
        purpose, and wiring it is the incident the delegation protocol exists to refuse
    """
    assert not (set(H.KNOWN_UNWIRED) & set(H.UNREACHED)), (
        "a function filed as both a defect and a decision has two reasons and the build cannot "
        "say which is current")
    assert not (set(H.KNOWN_UNWIRED) & set(H.UNCUT_OVER)), (
        "a defect filed as an un-cut-over tier reads as a decision about a path nobody runs")
    assert "push.push_action_to_agents" in H.UNREACHED, (
        "a shim that raises on purpose is a decision, and must never be filed as a defect -- "
        "wiring it is the incident it exists to refuse")
    assert "push.push_action_to_agents" not in H.KNOWN_UNWIRED
    # ⛔ and the table may only ever SHRINK by a function becoming reached, never by an entry being
    # quietly dropped: anything removed from here must now have a caller, which `undeclared()`
    # checks from the other side.
    assert H.undeclared() == (), (
        f"a function left KNOWN_UNWIRED without acquiring a caller: {H.undeclared()}")
