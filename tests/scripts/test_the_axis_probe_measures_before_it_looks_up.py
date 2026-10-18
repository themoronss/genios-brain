r"""`R.U05` · the lost-axis probe's verdict rule — and the one bug it actually had.

    pytest tests/scripts/test_the_axis_probe_measures_before_it_looks_up.py -q

The script talks to production; what is tested here is the pure part — given what fired and what
each side publishes, which axes are lost and whose fault that is.

⛔ WHY THIS FILE EXISTS. The first version of the rule asked, for each side of a non-firing axis,
*"is this side's unit declared silent?"* and reported **`core.cost` as an undeclared cause** of
`cost_vs_benefit`. `core.cost` publishes `effort_bp` on **1,973 of 1,973** completed runs. It is
healthy, and it is absent from the declarations *because* it is healthy.

> **A declaration list answers "is this absence declared". It never answers "is there an absence."**

That was the third artefact my own measurements produced in one session, all the same shape:
inferring absence from a list of declared absences instead of from the data. These tests are each a
wrong verdict the probe really produced.

⛔ AND THE PROBE'S OTHER EARLY MISREADING, pinned below: it read `AXIS_SOURCES[*][0]` as the axis
name. It is the SOURCE KEY (`benefit_source`), so the probe announced *"a 6-axis comparator that
has never compared 6"* and *"every axis has NEVER fired"* — both false, and both looked exactly
like findings. Axis names live in `tradeoff_unit.AXES`; keys reach units through `AXIS_SOURCES`.
"""
from __future__ import annotations

import pytest

from genios_engine.reason.reasoners.tradeoff_unit import AXES, AXIS_SIDES, AXIS_SOURCES
from scripts.l2_tradeoff_axes import DECLARED_AXES, UNIT_FOR_KEY, classify_lost_axes

pytestmark = pytest.mark.unit

IMPACT = ("core.impact", "impact_bp")
COST = ("core.cost", "effort_bp")
ALL_PUBLISHING = {(u, m): 1 for _, u, m in AXIS_SOURCES}


# --------------------------------------------------------------------------------------------
# the bug
# --------------------------------------------------------------------------------------------

def test_a_side_that_publishes_is_healthy_and_is_never_called_a_cause() -> None:
    """⛔ The exact wrong verdict: `core.cost` reported as an undeclared cause while publishing
    `effort_bp` on every single run."""
    publishes = dict(ALL_PUBLISHING)
    publishes[IMPACT] = 0                       # the one side that really is absent
    declared, undeclared, healthy = classify_lost_axes({"speed_vs_certainty": 1,
                                                        "risk_vs_reward": 1}, publishes)
    assert undeclared == {}, f"a publishing unit must never be a cause: {undeclared}"
    assert healthy == {"cost_vs_benefit": ["core.cost.effort_bp"]}
    assert list(declared) == ["cost_vs_benefit"]
    assert declared["cost_vs_benefit"][0][:2] == IMPACT


def test_a_side_that_publishes_nothing_and_is_declared_names_its_mover() -> None:
    publishes = dict(ALL_PUBLISHING)
    publishes[IMPACT] = 0
    declared, _, _ = classify_lost_axes({"speed_vs_certainty": 1, "risk_vs_reward": 1}, publishes)
    _, _, mover = declared["cost_vs_benefit"][0]
    assert "Harsh" in mover, "a declared absence with no named mover cannot be cleared"


def test_a_side_that_publishes_nothing_and_is_undeclared_is_the_state_to_act_on() -> None:
    publishes = dict(ALL_PUBLISHING)
    publishes[COST] = 0                          # pretend core.cost went quiet, undeclared
    _, undeclared, _ = classify_lost_axes({"speed_vs_certainty": 1, "risk_vs_reward": 1},
                                          publishes)
    assert undeclared == {"cost_vs_benefit": [COST]}


def test_an_axis_that_fired_is_not_examined_at_all() -> None:
    """A firing axis needs no diagnosis, and diagnosing it would report its quiet side as a fault."""
    publishes = {(u, m): 0 for _, u, m in AXIS_SOURCES}
    declared, undeclared, healthy = classify_lost_axes({a: 1 for a, _, _ in AXES}, publishes)
    assert (declared, undeclared, healthy) == ({}, {}, {})


def test_both_sides_of_a_lost_axis_are_reported_never_just_one() -> None:
    """An axis needs both; naming one would send a reader to fix half of it."""
    publishes = {(u, m): 0 for _, u, m in AXIS_SOURCES}
    declared, undeclared, _ = classify_lost_axes({}, publishes)
    for axis in DECLARED_AXES:
        found = len(declared.get(axis, [])) + len(undeclared.get(axis, []))
        assert found == 2, f"{axis} compares two sides; the verdict named {found}"


# --------------------------------------------------------------------------------------------
# the earlier misreading — axis names are not source keys
# --------------------------------------------------------------------------------------------

def test_the_axis_names_are_the_axes_and_not_the_source_keys() -> None:
    assert DECLARED_AXES == ("speed_vs_certainty", "risk_vs_reward", "cost_vs_benefit")
    keys = {key for _, pair in AXIS_SIDES.items() for key in pair}
    assert keys.isdisjoint(set(DECLARED_AXES)), (
        "source keys and axis names must stay distinguishable, or a reader conflates them again")
    assert len(DECLARED_AXES) == 3 and len(AXIS_SOURCES) == 6


def test_every_axis_side_resolves_to_a_unit_and_a_metric() -> None:
    """Derived from the unit, so a new axis cannot be added without its sources resolving."""
    for axis in DECLARED_AXES:
        for key in AXIS_SIDES[axis]:
            assert key in UNIT_FOR_KEY, f"{axis} names {key}, which maps to no unit"
            unit_id, metric = UNIT_FOR_KEY[key]
            assert unit_id.startswith(("core.", "legacy.")) and metric.endswith("_bp")


def test_the_probe_reads_the_unit_rather_than_restating_it() -> None:
    """Two lists that must agree with nothing making them agree is the shape this avoids."""
    assert DECLARED_AXES == tuple(axis for axis, _, _ in AXES)
    assert dict(AXIS_SIDES) == {a: (f, s) for a, f, s in AXES}
