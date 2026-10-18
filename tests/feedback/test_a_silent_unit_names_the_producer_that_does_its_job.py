r"""A unit in the canonical registry that proposes nothing must say which it is.

⛔⛔ WHAT WAS WRONG, AND IT WAS A WRONG CONCLUSION RATHER THAN WRONG CODE. The GeniOS Design Atlas
records Layer 7 gap **#2** as *"Direct personalization evolution is missing. Behavior and Adaptive
cohort builder returns no proposals"*, citing `units.unit_behavior_evolution` and
`unit_adaptive_evolution` — which do return nothing, through a shared `_cohort_candidate` whose
entire body is `return []`.

⛔ **It is not missing.** Both Atlas components are built, 776 and 301 lines, one package down:

    packs/brains/behavior_distill.py::distill          → LearningTarget.BEHAVIOR
    packs/brains/adaptive_lease.py::lease_proposals    → LearningTarget.RUNTIME, 7-day TTL

…and `feedback/brain_pipeline.brain_pipeline_proposals` appends their output to the **same weekly
run**, from the line directly after `run_all_units` in `orchestrator.run_learning`:

    proposals = list(run_all_units(batch, policy, now))
    proposals.extend(brain_pipeline_proposals(conn, org_id=org_id, policy=policy, now=now))

⛔ THE STUB PREDATES THE IMPLEMENTATION BY A MONTH. `365cf7a6` (2026-08-08, *"the ten analysis
units"*) introduced `_cohort_candidate`; `ed1b10c3` (2026-09-07, *"Layer 3 v2 … the four brains"*)
built the real producers in another package. The placeholder was never removed or declared, and
`ALL_ANALYSIS_UNITS` — the one list a reader scans to see which Layer 7 components exist — still
shows a silent unit where a built component belongs.

⛔⛔ TWO READERS HAVE NOW REACHED THE SAME WRONG VERDICT FROM THE SAME EVIDENCE: the Atlas, and this
programme on 2026-10-02, which filed gap #2 as *"the only fully LIVE one"* before reading
`brain_pipeline_proposals`. **A call site that looks wired is not a wired call site — and a call
site that looks DEAD is not a dead feature.**

⛔ THE PLACEHOLDERS ARE DECLARED, NOT DELETED. Deleting them would take the Atlas's component names
out of the canonical registry, and they cost nothing: they return `()`.

⛔ AND THIS FILE CLOSES A BLIND SPOT IN `S1`'s GUARD. `durable_from_a_measurement()` reads
`UNIT_TARGETS`, which is `units.py`'s registry — so "which producer may write which brain" was
guarded for eleven units and **unguarded for the two that actually produce.** `DELEGATED` carries
each producer's target and `broken_delegations()` asserts it from the producer's own AST. *A guard
that stops at a package boundary catches nothing across it.*
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from genios_engine.feedback import target_policy as T

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENGINE = _ROOT / "genios_engine"


def _producer(unit: str) -> tuple[pathlib.Path, str, str]:
    """`(path, function, declared target)` for one delegation."""
    producer, target, _why, _mover = T.DELEGATED[unit]
    rel, _, func = producer.partition("::")
    return _ENGINE / rel, func, target


# =============================================================================================
# 1 · both directions over the declaration
# =============================================================================================

def test_no_silent_unit_is_left_unexplained() -> None:
    """⛔ A unit in `ALL_ANALYSIS_UNITS` that proposes nothing is either a **declared stub**
    (`None` in `UNIT_TARGETS`, with its reason) or a **declared placeholder** (an entry in
    `DELEGATED`, naming the producer that does its job). Anything else is the exact state that
    produced the Atlas's wrong verdict twice: a named component, a silent unit, no record of
    which."""
    assert T.undelegated_silent_units() == (), (
        f"silent units with no declared stub reason and no delegation: "
        f"{T.undelegated_silent_units()}")


def test_no_delegation_names_a_unit_that_is_no_longer_silent() -> None:
    """⛔ The second direction. If `_cohort_candidate` ever gains a body, these units start
    proposing — and then there would be TWO producers for one brain subject, which is the shape
    `reason/situation_reasoner.clamp_confidence` was filed under in L5: *two implementations of a
    one-way law is the shape that lets one of them start raising.*"""
    assert T.stale_delegations() == (), (
        f"delegations naming a unit that now proposes, or is gone: {T.stale_delegations()}")


@pytest.mark.parametrize("unit", sorted(T.DELEGATED))
def test_every_delegation_carries_a_producer_a_reason_and_a_mover(unit: str) -> None:
    producer, target, why, mover = T.DELEGATED[unit]
    assert "::" in producer, producer
    assert target in T.measured_unit_targets().get(unit, ()) or target == "RUNTIME", target
    assert len(why) >= 80, f"{unit}'s reason says nothing usable"
    assert "MOVES WHEN" in mover, f"{unit}'s mover does not say when it moves"


# =============================================================================================
# 2 · ⛔ the five links — asserted together, then one at a time so a failure names WHICH
# =============================================================================================

def test_every_delegation_is_live() -> None:
    """⛔⛔ THE GUARD WITH TEETH. Losing any one of the five links silently returns the layer to
    the state the Atlas recorded: a registry that lists the component and a product that produces
    nothing."""
    assert T.broken_delegations() == (), (
        f"delegations that are no longer live: {T.broken_delegations()}")


@pytest.mark.parametrize("unit", sorted(T.DELEGATED))
def test_link_1_the_producer_exists(unit: str) -> None:
    path, func, _target = _producer(unit)
    assert path.exists(), path
    assert func in T._module_functions(path), f"{path.name} no longer defines {func}"


@pytest.mark.parametrize("unit", sorted(T.DELEGATED))
def test_link_2_the_producer_is_not_itself_empty(unit: str) -> None:
    """⛔ The delegation would otherwise point at a second stub, which is how a chain of
    placeholders reads as a built feature."""
    path, func, _target = _producer(unit)
    node = T._module_functions(path)[func]
    assert not T._returns_only_empty(node), f"{func} now returns nothing"


@pytest.mark.parametrize("unit", sorted(T.DELEGATED))
def test_link_3_the_driver_calls_the_producer(unit: str) -> None:
    path, func, _target = _producer(unit)
    hop_path, hop_fn = T.DRIVER_HOP
    hop = T._module_functions(_ENGINE / hop_path)[hop_fn]
    assert func in T._called_names(hop), f"{hop_fn} no longer calls {func}"


def test_link_4_the_weekly_run_calls_the_driver() -> None:
    """⛔ The single line every delegated producer depends on. Remove it and both components stop
    producing while `ALL_ANALYSIS_UNITS` still lists a unit for each."""
    entry_path, entry_fn = T.DRIVER_ENTRY
    entry = T._module_functions(_ENGINE / entry_path)[entry_fn]
    assert T.DRIVER_HOP[1] in T._called_names(entry)


@pytest.mark.parametrize("unit", sorted(T.DELEGATED))
def test_link_5_the_producer_still_emits_the_declared_target(unit: str) -> None:
    """⛔ The target is the SINK — it decides whether a proposal expires, waits for a human, or
    becomes permanent. `S1` guards that for `units.py`'s eleven; this guards it across the package
    boundary for the two that actually produce."""
    path, _func, target = _producer(unit)
    emitted = T._targets_in(ast.parse(path.read_text(encoding="utf-8")))
    assert emitted == frozenset({target}), f"{path.name} emits {sorted(emitted)}, declared {target}"


def test_the_resolver_reads_the_module_not_the_function() -> None:
    """⛔ Link 5 walks the whole MODULE on purpose. Both producers build their `LearningObject` in
    a private helper that the entry function then calls, so a function-scoped walk finds no target
    at all and reports every delegation as broken. **The same mistake as grepping for a keyword
    argument, one level up.**"""
    for unit in T.DELEGATED:
        path, func, target = _producer(unit)
        in_function = T._targets_in(T._module_functions(path)[func])
        in_module = T._targets_in(ast.parse(path.read_text(encoding="utf-8")))
        assert target not in in_function, (
            f"{func} now names {target} directly — the module-scoped walk is no longer required, "
            "but it is still correct; this test is the record of why it exists")
        assert target in in_module


# =============================================================================================
# 3 · the components are real work, and the Atlas's conclusion is refuted
# =============================================================================================

@pytest.mark.parametrize("unit", sorted(T.DELEGATED))
def test_the_producer_reads_production_data(unit: str) -> None:
    """⛔ Evidence that it is a component and not a signature: each producer issues a real read.
    Asserted on the presence of a `select`, not on a line count, because a line count rots on any
    refactor and this does not."""
    path, _func, _target = _producer(unit)
    src = path.read_text(encoding="utf-8")
    assert re.search(r"select\s+", src, re.I), f"{path.name} issues no read"


def test_the_two_units_the_atlas_called_missing_still_propose_nothing() -> None:
    """⛔ The Atlas's observation was CORRECT; its conclusion was not. Both halves are asserted so
    the next reader gets the whole fact at once."""
    assert T._proposes_something("unit_behavior_evolution") is False
    assert T._proposes_something("unit_adaptive_evolution") is False
    assert set(T.DELEGATED) == {"unit_behavior_evolution", "unit_adaptive_evolution"}


def test_the_shared_stub_is_still_the_shared_stub() -> None:
    """⛔ `_cohort_candidate` is what makes both units look wired at their call site. Pinned, so
    the day somebody implements it the duplicate-producer question is raised deliberately rather
    than discovered."""
    tree = ast.parse((_ENGINE / "feedback" / "units.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "_cohort_candidate")
    assert T._returns_only_empty(node)
    for unit in ("unit_behavior_evolution", "unit_adaptive_evolution"):
        body = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == unit)
        assert "_cohort_candidate" in T._called_names(body)


# =============================================================================================
# 4 · the two sinks, and why only one of them needs a clock
# =============================================================================================

def test_the_adaptive_producer_goes_through_the_expiring_runtime_path() -> None:
    """⛔ This is the one place the Atlas's Adaptive boundary — *'Decays, expires, and rolls
    back'* — is actually met. `lease_proposals` emits `RUNTIME`, which `govern()` routes to
    `TEMPORARY` and `publish_runtime` writes to `temporary_memories`, whose `expires_at` is
    `NOT NULL`."""
    path, _func, target = _producer("unit_adaptive_evolution")
    assert target == "RUNTIME"
    src = path.read_text(encoding="utf-8")
    assert "expires_at=now + timedelta(seconds=lease_ttl_seconds(policy))" in src
    assert "LEASE_TTL_SECONDS = 7 * 24 * 3600" in src


def test_the_behaviour_producer_targets_a_durable_brain_and_says_why_that_is_right() -> None:
    """⛔ `BEHAVIOR` is in `DURABLE_BRAIN_TARGETS`, so this producer writes a permanent row — and
    that is correct: a behaviour pattern is a CLAIM about how a person works, the same category as
    `unit_pattern_learning`'s ORGANIZATION proposals, and the Atlas's boundary for this component
    is *'population and identity scoped'*, not *'decays and expires'*.

    ⛔ Asserted because the reason is the only thing separating it from
    `DURABLE_FROM_A_MEASUREMENT`'s one entry."""
    _path, _func, target = _producer("unit_behavior_evolution")
    assert target in T.DURABLE_BRAIN_TARGETS
    _p, _t, why, _m = T.DELEGATED["unit_behavior_evolution"]
    assert "CLAIM" in why and "not a measurement" in why
    assert "unit_behavior_evolution" not in T.durable_from_a_measurement()


def test_the_durable_measurement_finding_is_unchanged_by_this_unit() -> None:
    """⛔ `S4` widened the guard across a package boundary and must not have moved `S1`'s finding.
    Still exactly one, still the same one."""
    assert T.durable_from_a_measurement() == ("unit_recommendation_learning",)
    assert set(T.durable_from_a_measurement()) == set(T.DURABLE_FROM_A_MEASUREMENT)


# =============================================================================================
# 5 · the chain's root — the heartbeat
# =============================================================================================

def test_the_weekly_run_is_driven_by_the_heartbeat() -> None:
    """⛔ Link 4 only matters if `run_learning` itself runs. `run_learning_sweep` is called from
    the maintenance sweep, and it calls `run_learning` per tenant inside its own transaction."""
    from genios_engine.api import routes
    from genios_engine.feedback.orchestrator import run_learning_sweep

    assert "run_learning_sweep" in inspect.getsource(routes.run_maintenance_sweep)
    assert "run_learning(" in inspect.getsource(run_learning_sweep)
