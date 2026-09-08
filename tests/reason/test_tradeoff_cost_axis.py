"""U4 — `core.tradeoff`'s third axis, which has never once spoken.

`CostVersusBenefitPlugin` read `effort_bp` from `core.effort`. There is no `core.effort`: no file,
no class, no registration, nothing that publishes anything. `_prior_bp` reads an absent prior as
"the unit did not complete" and the plugin then correctly stays silent — so a unit that declares
three axes has been shipping two, and the silence looked exactly like the deliberate one it uses
when a capability has not deployed both sides of a comparison.

`effort_bp` is published by `core.cost`, and always has been.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.reasoning import ResultStatus
from genios_engine.reason.reasoners import CORE_UNITS, SUPPLEMENTARY_UNITS
from genios_engine.reason.reasoners.tradeoff_unit import AXIS_SOURCES, TradeoffUnit

from .conftest import completed, run

REGISTERED_IDS = frozenset(unit().spec.reasoner_id
                           for unit in CORE_UNITS + SUPPLEMENTARY_UNITS)


def _both_sides() -> dict:
    """One prior per axis side, all three axes measurable, none of them tied."""
    return {
        "core.impact": completed("core.impact", impact_bp=8_000),
        "core.cost": completed("core.cost", effort_bp=3_000),
        "core.opportunity": completed("core.opportunity", opportunity_bp=7_000),
        "core.risk": completed("core.risk", risk_bp=4_000),
        "core.temporal": completed("core.temporal", urgency_bp=6_500),
        "core.confidence": completed("core.confidence", confidence_bp=5_000),
    }


@pytest.mark.parametrize("config_key, default_unit, metric", AXIS_SOURCES)
def test_every_axis_default_names_a_registered_unit(config_key, default_unit, metric):
    """The table exists to be checked. `cost_source` pointed at `core.effort` for the whole life
    of this unit and nothing anywhere could say so."""
    assert default_unit in REGISTERED_IDS, f"{config_key} defaults to a unit that does not exist"


def test_the_cost_source_default_is_the_unit_that_publishes_effort():
    """Named explicitly, not just 'registered': `core.cost` is where `effort_bp` comes from, and
    a default that pointed at some other real unit would be just as dead and less obvious."""
    publishers = {unit().unit_id for unit in CORE_UNITS
                  if "effort_bp" in getattr(unit(), "publishes", ())}

    assert dict((key, unit) for key, unit, _ in AXIS_SOURCES)["cost_source"] in publishers


def test_the_cost_versus_benefit_axis_produces_an_observation():
    """The acceptance row: an axis that has never spoken, speaking."""
    result = run(TradeoffUnit(), prior=_both_sides())

    assert result.status is ResultStatus.COMPLETED
    axes = {finding.finding_id for finding in result.findings}
    assert "tradeoff.cost_vs_benefit" in axes
    assert result.metrics["axis_count"] == 3


def test_the_axis_names_what_is_being_given_up():
    """A tradeoff that does not name the loser is a recommendation nobody can audit."""
    result = run(TradeoffUnit(), prior=_both_sides())
    finding = next(item for item in result.findings
                   if item.finding_id == "tradeoff.cost_vs_benefit")

    assert "favours.benefit" in finding.reason_codes
    assert "concedes.restraint" in finding.reason_codes
    assert finding.metrics["leading_bp"] == 8_000
    assert finding.metrics["trailing_bp"] == 3_000


def test_a_capability_can_still_appoint_its_own_cost_authority():
    """The default moved; the seam did not. A capability running its own effort model under
    another id must still be able to point the axis at it."""
    prior = _both_sides()
    prior["sales.effort_model"] = completed("sales.effort_model", effort_bp=9_000)

    result = run(TradeoffUnit(), config={"cost_source": "sales.effort_model"}, prior=prior)
    finding = next(item for item in result.findings
                   if item.finding_id == "tradeoff.cost_vs_benefit")

    assert finding.metrics["leading_bp"] == 9_000        # restraint now leads, benefit concedes
    assert "favours.restraint" in finding.reason_codes


def test_the_axis_is_still_silent_when_a_side_genuinely_did_not_run():
    """The fix must not turn a real blind spot into a fabricated zero: an undeployed cost unit is
    still a missing side, and inventing free effort is exactly what this plugin refuses to do."""
    prior = _both_sides()
    del prior["core.cost"]

    result = run(TradeoffUnit(), prior=prior)

    assert result.metrics["axis_count"] == 2
    assert "tradeoff.cost_vs_benefit" not in {item.finding_id for item in result.findings}


def test_a_zero_effort_reading_is_not_the_same_as_no_effort_unit():
    """The sentinel's whole job. A cost unit that ran and measured no effort is a landslide in
    favour of acting; a cost unit that never ran is an unknown, and the two must not agree."""
    prior = _both_sides()
    prior["core.cost"] = completed("core.cost", effort_bp=0)

    measured = run(TradeoffUnit(), prior=prior)

    assert measured.metrics["axis_count"] == 3
    finding = next(item for item in measured.findings
                   if item.finding_id == "tradeoff.cost_vs_benefit")
    assert finding.metrics["tension_bp"] == 0            # nothing is being given up
    assert "favours.benefit" in finding.reason_codes
