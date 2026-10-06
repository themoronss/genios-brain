"""The twelve golden replays, executed — and replays 01–07 driven through the real chain.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/replays/test_golden_replays.py -q

Each mutation in each replay becomes one parameterised assertion.

**Replays 01–07** — the founder's own cases (`STEP-01` §1) — are now judged on the ENGINE. Where a
founder case IS a mutation's input (`atlas_expression.EXPRESSED`), the mutation's pass condition
is checked on that case's run through `engine_runner.run_case`: the production sync door, the
real chain, recorded model answers. A blocked mutation is a strict xfail — and since the check now
runs the engine instead of an unconditional `pytest.fail`, the day its capability lands the check
passes, the xfail fails, and the spec must be moved to `possible_today`. Every other mutation is
NOT EXPRESSIBLE, says why, and is counted apart from *blocked* — the board never folds the two.

**Replays 08–12** keep the shape they had: the specification is held well-formed, and a blocked
mutation names what blocks it. They are the next replays to drive.

What each replay checks first is still the *prohibition* — the specifications are unusually precise
about what must NOT happen (do not target the connector, do not turn silence into urgency, do not
recap a meeting nobody confirmed), and prohibitions are checkable long before the positive
behaviour exists.
"""
from __future__ import annotations

import os

import pytest

from tests.replays import atlas_expression as ax
from tests.replays import cassettes
from tests.replays.founder_case import load_cases
from tests.replays.harness import ReplaySpec, blocked_marker, load_specs

SPECS = load_specs()
CASES = {c.case_id: c for c in load_cases()}
#: The replays the founder set drives. 08–12 follow when their cases exist.
DRIVEN = {f"{n:02d}" for n in range(1, 8)}
_PREDICATES = {"case", "card_about", "min", "max", "mentions", "level_in", "memory", "no_phrase",
               "why"}


def _scratch_db() -> None:
    if os.environ.get("GENIOS_TEST_DATABASE_URL"):
        return
    if os.environ.get("GENIOS_GOLDEN_REQUIRED") == "1":
        pytest.fail("GENIOS_GOLDEN_REQUIRED=1 and no GENIOS_TEST_DATABASE_URL — the golden set "
                    "never skips in its own job")
    pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")


def _id(spec: ReplaySpec, index: int) -> str:
    return f"{spec.replay_id}-{spec.slug}-m{index:02d}"


# =================================================================================================
# replays 08–12 — the specification, held well-formed
# =================================================================================================
def _undriven():
    for spec in SPECS:
        if spec.replay_id in DRIVEN:
            continue
        for index, mutation in enumerate(spec.mutations):
            marks = [blocked_marker(mutation)] if mutation.is_blocked else []
            yield pytest.param(spec, mutation, id=_id(spec, index), marks=marks)


@pytest.mark.parametrize(("spec", "mutation"), list(_undriven()))
def test_replay_mutation(spec: ReplaySpec, mutation) -> None:
    """A runnable case asserts the specification can BE an oracle; a blocked case fails here
    deliberately, naming its missing capability, so the day it works the xfail fails loudly."""
    if mutation.is_blocked:
        pytest.fail(
            f"replay {spec.replay_id} ({spec.title}) — mutation not satisfiable today.\n"
            f"  mutation:  {mutation.mutation}\n"
            f"  required:  {mutation.expected_decision}\n"
            f"  forbidden: {mutation.prohibited}\n"
            f"  blocked on: {mutation.blocked_on}")
    assert mutation.pass_condition.strip(), (
        f"replay {spec.replay_id} mutation {mutation.mutation!r} is marked runnable but states "
        "no pass condition — it cannot decide anything")
    assert mutation.prohibited.strip(), (
        f"replay {spec.replay_id} mutation {mutation.mutation!r} states no prohibited behaviour")


# =================================================================================================
# replays 01–07 — on the engine
# =================================================================================================
def _driven(expressed: bool):
    for spec in SPECS:
        if spec.replay_id not in DRIVEN:
            continue
        for index, mutation in enumerate(spec.mutations):
            expression = ax.expression(spec.replay_id, index)
            if (expression is not None) != expressed:
                continue
            marks = []
            if expressed:
                marks = [pytest.mark.pg, pytest.mark.golden]
                if mutation.is_blocked:
                    marks.append(pytest.mark.xfail(
                        strict=True, raises=AssertionError,
                        reason=f"blocked: {mutation.blocked_on or 'capability not implemented'}"))
            yield pytest.param(spec, index, mutation, expression, id=_id(spec, index),
                               marks=marks)


@pytest.mark.parametrize(("spec", "index", "mutation", "expression"), list(_driven(True)))
def test_a_driven_mutation_holds_on_the_engine(spec, index, mutation, expression) -> None:
    """The mutation's pass condition, checked on the run of the founder case that is its input."""
    _scratch_db()
    run = cassettes.replayed(CASES[expression["case"]])
    problems = ax.check(expression, run)
    assert not problems, (
        f"replay {spec.replay_id} m{index:02d} on {expression['case']} ({expression['why']}):\n"
        f"  required:  {mutation.expected_decision}\n"
        f"  pass:      {mutation.pass_condition}\n"
        f"  measured:  " + "\n             ".join(problems))


@pytest.mark.parametrize(("spec", "index", "mutation", "expression"), list(_driven(False)))
def test_an_undriven_mutation_says_why_it_cannot_be_expressed(spec, index, mutation,
                                                             expression) -> None:
    """Counted apart from blocked — not a pass, not a fail, and never silent."""
    reason = ax.NOT_EXPRESSIBLE.get(spec.replay_id, "")
    assert len(reason.strip()) >= 40, (
        f"replay {spec.replay_id} m{index:02d} is neither driven nor explained")


def test_the_expression_map_names_real_mutations_cases_and_predicates() -> None:
    by_id = {s.replay_id: s for s in SPECS}
    for (replay_id, index), expression in ax.EXPRESSED.items():
        assert replay_id in DRIVEN and replay_id in by_id, replay_id
        assert 0 <= index < len(by_id[replay_id].mutations), (replay_id, index)
        assert expression["case"] in CASES, expression["case"]
        assert set(expression) <= _PREDICATES, set(expression) - _PREDICATES
        assert expression.get("why"), (replay_id, index)
        # A check that only counts silence must carry a witness, or it passes on nothing.
        if expression.get("max") == 0:
            assert expression.get("memory"), f"{replay_id} m{index:02d} counts silence unwitnessed"
    assert set(ax.NOT_EXPRESSIBLE) == DRIVEN


def test_the_driven_split_is_visible() -> None:
    """Publish the split rather than letting a mostly-unexpressed set read as passing."""
    total = sum(len(s.mutations) for s in SPECS if s.replay_id in DRIVEN)
    driven = len(ax.EXPRESSED)
    print(f"\natlas replays 01–07: {total} mutations · driven through the engine {driven} · "
          f"not expressible yet {total - driven}")
    assert total == 80 and 0 < driven < total


# =================================================================================================
# every replay — what the specification itself must say
# =================================================================================================
@pytest.mark.parametrize("spec", SPECS, ids=lambda s: f"{s.replay_id}-{s.slug}")
def test_replay_declares_its_layer_obligations(spec: ReplaySpec) -> None:
    """Every replay must say which layer owes what: the failures these replays describe are
    handoff failures, and a replay that attributes nothing cannot say where to fix anything."""
    layers = {o.get("layer") for o in spec.layer_obligations}
    assert layers, f"replay {spec.replay_id} attributes no obligations to any layer"
    assert layers <= {"L1", "L2", "L3", "L4", "L5", "L6", "L7"}, f"unknown layer in {layers}"


@pytest.mark.parametrize("spec", SPECS, ids=lambda s: f"{s.replay_id}-{s.slug}")
def test_replay_states_what_is_prohibited(spec: ReplaySpec) -> None:
    """The prohibitions are the part that is checkable first, so they must be present."""
    assert spec.prohibited_behaviors or any(m.prohibited for m in spec.mutations), (
        f"replay {spec.replay_id} names nothing that is forbidden — it cannot fail anything")
