"""Executable contract for the Tradeoff Unit (`core.tradeoff`).

The unit exists to hold two honest units against each other and report the argument between them.
These tests pin the properties that make that argument trustworthy:

* **Two sides or nothing.** A missing counterweight is a blind spot, never a landslide.
* **The loser is named.** Every lean carries what it conceded, so an explanation can be argued with.
* **It compares, it never chooses.** No adjustment, no check, no candidate ever leaves this unit.
* **Total ordering.** The headline tension is a property of the evidence, not of plugin order.
* **Metric authority is respected.** It reads confidence; it must never publish it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.tradeoff_unit import (
    CostVersusBenefitPlugin,
    RiskVersusRewardPlugin,
    SpeedVersusCertaintyPlugin,
    TradeoffUnit,
)
from genios_engine.reason.unit import UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------------------------
# Fixtures: a real capability, a real snapshot, real prior results
# ---------------------------------------------------------------------------------------------

def _request(*, config=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.tradeoff", "1.0.0", config=config or {}),),
        plays=(PlayDefinition(play_id="restore_momentum", version="1",
                              label="Restore Momentum", steps=("Draft a grounded reply",)),),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts={"deal.status": "open"},
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _completed(reasoner_id: str, **metrics) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1",
                          status=ResultStatus.COMPLETED, matched=True, metrics=metrics)


def _view(prior=None, *, config=None) -> UnitView:
    request = _request(config=config)
    return UnitView(request=request, spec=request.capability.reasoners[0],
                    prior={item.reasoner_id: item for item in (prior or ())})


def _codes(observation) -> set[str]:
    return set(observation.reason_codes)


# ---------------------------------------------------------------------------------------------
# Silence: a tradeoff needs two sides, and a missing side is not a zero
# ---------------------------------------------------------------------------------------------

def test_no_axis_is_reported_when_nothing_ran_before_it():
    """Scheduled first by mistake, the unit must say nothing rather than invent a dilemma."""
    view = _view()

    assert SpeedVersusCertaintyPlugin().contribute(view) == ()
    assert RiskVersusRewardPlugin().contribute(view) == ()
    assert CostVersusBenefitPlugin().contribute(view) == ()


def test_one_published_side_is_a_blind_spot_not_a_landslide():
    """Risk without opportunity would read as 'all downside' — the exact fabrication L4 forbids."""
    view = _view([_completed("core.risk", risk_bp=8_000)])

    assert RiskVersusRewardPlugin().contribute(view) == ()


def test_a_unit_that_failed_is_treated_as_absent_not_as_zero():
    """A crashed opportunity unit has no opinion; reading it as 'no upside' inverts the call."""
    view = _view([
        _completed("core.risk", risk_bp=8_000),
        ReasonerResult("core.opportunity", "1", ResultStatus.FAILED,
                       reason_codes=("reasoner_failure",)),
    ])

    assert RiskVersusRewardPlugin().contribute(view) == ()


def test_a_measured_zero_still_produces_an_axis():
    """Zero risk is a finding; the absence of a tradeoff is itself worth reporting."""
    view = _view([_completed("core.opportunity", opportunity_bp=9_000),
                  _completed("core.risk", risk_bp=0)])

    observation, = RiskVersusRewardPlugin().contribute(view)

    assert observation.metrics["tension_bp"] == 0        # a free move, not an agonising one
    assert "favours.reward" in _codes(observation)


# ---------------------------------------------------------------------------------------------
# The tension formula: what "contested" means
# ---------------------------------------------------------------------------------------------

def test_two_strong_and_close_pressures_are_the_hardest_call():
    """8000 upside against 7900 exposure is the situation a human is actually needed for."""
    view = _view([_completed("core.opportunity", opportunity_bp=8_000),
                  _completed("core.risk", risk_bp=7_900)])

    observation, = RiskVersusRewardPlugin().contribute(view)

    # weaker side 7900, margin 100 → 7900 * 9900 / 10000
    assert observation.metrics["tension_bp"] == 7_821
    assert observation.metrics["margin_bp"] == 100


def test_a_wide_gap_is_a_settled_question_however_large_the_numbers():
    view = _view([_completed("core.opportunity", opportunity_bp=9_500),
                  _completed("core.risk", risk_bp=1_000)])

    observation, = RiskVersusRewardPlugin().contribute(view)

    assert observation.metrics["tension_bp"] == 150      # 1000 * 1500 / 10000, rounded half up
    assert "favours.reward" in _codes(observation)


def test_an_immaterial_lean_names_no_winner():
    """One basis point must not decide which objective 'won' — explanations would flip on noise."""
    view = _view([_completed("core.opportunity", opportunity_bp=6_100),
                  _completed("core.risk", risk_bp=6_000)])

    observation, = RiskVersusRewardPlugin().contribute(view)

    assert "balanced.risk_vs_reward" in _codes(observation)
    assert not any(code.startswith("favours.") for code in observation.reason_codes)
    assert not any(code.startswith("concedes.") for code in observation.reason_codes)


def test_a_capability_can_demand_a_wider_margin_before_a_side_is_named():
    """A regulated capability may want a decisive gap before claiming one objective beat another."""
    prior = [_completed("core.opportunity", opportunity_bp=6_600),
             _completed("core.risk", risk_bp=6_000)]

    default, = RiskVersusRewardPlugin().contribute(_view(prior))
    strict, = RiskVersusRewardPlugin().contribute(
        _view(prior, config={"decisive_margin_bp": 2_000}))

    assert "favours.reward" in _codes(default)
    assert "balanced.risk_vs_reward" in _codes(strict)


def test_a_malformed_margin_setting_is_a_manifest_fault():
    with pytest.raises(ValueError, match="basis points"):
        RiskVersusRewardPlugin().contribute(_view(
            [_completed("core.opportunity", opportunity_bp=5_000),
             _completed("core.risk", risk_bp=4_000)],
            config={"decisive_margin_bp": 25_000}))


# ---------------------------------------------------------------------------------------------
# Speed versus certainty: doubt is the case for waiting
# ---------------------------------------------------------------------------------------------

def test_high_confidence_removes_the_case_for_waiting():
    """Well-evidenced and time-pressured is not a dilemma; it is a reason to move."""
    view = _view([_completed("core.temporal", urgency_bp=8_000),
                  _completed("core.confidence", confidence_bp=9_000)])

    observation, = SpeedVersusCertaintyPlugin().contribute(view)

    assert observation.metrics["trailing_bp"] == 1_000   # 10000 - confidence
    assert "favours.speed" in _codes(observation)
    assert "concedes.certainty" in _codes(observation)


def test_thin_evidence_pulls_against_a_deadline():
    """Urgent and barely evidenced is the classic contested call, and must read as one."""
    view = _view([_completed("core.temporal", urgency_bp=6_000),
                  _completed("core.confidence", confidence_bp=2_500)])

    observation, = SpeedVersusCertaintyPlugin().contribute(view)

    # doubt = 7500 against urgency 6000 → the case for waiting leads by 1500
    assert observation.metrics["leading_bp"] == 7_500
    assert observation.metrics["tension_bp"] == 5_100    # 6000 * 8500 / 10000
    assert "favours.certainty" in _codes(observation)
    assert "concedes.speed" in _codes(observation)


def test_a_capability_may_appoint_different_units_for_an_axis():
    """Substituting an authority is configuration, not a code change."""
    view = _view([_completed("sales.deadline", urgency_bp=7_000),
                  _completed("core.confidence", confidence_bp=5_000)],
                 config={"speed_source": "sales.deadline"})

    observation, = SpeedVersusCertaintyPlugin().contribute(view)

    assert observation.metrics["leading_bp"] == 7_000


# ---------------------------------------------------------------------------------------------
# Cost versus benefit
# ---------------------------------------------------------------------------------------------

def test_unmeasured_effort_is_never_treated_as_free():
    """Without a cost authority deployed the axis stays silent instead of assuming zero work."""
    view = _view([_completed("core.impact", impact_bp=7_000)])

    assert CostVersusBenefitPlugin().contribute(view) == ()


def test_heavy_effort_against_modest_benefit_concedes_the_benefit():
    view = _view([_completed("core.impact", impact_bp=3_000),
                  _completed("core.effort", effort_bp=8_000)])

    observation, = CostVersusBenefitPlugin().contribute(view)

    assert "favours.restraint" in _codes(observation)
    assert "concedes.benefit" in _codes(observation)


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_the_unit_satisfies_the_reasoner_protocol():
    assert isinstance(TradeoffUnit(), Reasoner)


def test_a_run_with_no_prior_units_publishes_an_empty_tension_not_a_guess():
    result = TradeoffUnit().evaluate(_request(), {})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is False
    assert dict(result.metrics) == {"tension_bp": 0, "margin_bp": 0,
                                    "axis_count": 0, "contested_count": 0}
    assert result.findings == ()


def test_the_quiet_enterprise_renewal_leans_to_the_upside_and_says_what_it_gave_up():
    """A real scenario, end to end.

    A £400k renewal has gone quiet with three weeks left. `core.temporal` reports 9000bp of time
    pressure. `core.confidence` is only 5200bp — the buyer's silence is genuinely ambiguous.
    `core.opportunity` sees 8500bp of headroom; `core.risk` sees 5000bp of exposure. Effort to act
    is 3000bp against 7000bp of impact.

    The hardest argument in that situation is upside against exposure, and the evidence leans to
    the upside. The unit must report that lean, its margin, and — critically — that caution is what
    was conceded, so the delivered card can say so out loud.
    """
    prior = {item.reasoner_id: item for item in (
        _completed("core.temporal", urgency_bp=9_000),
        _completed("core.confidence", confidence_bp=5_200),
        _completed("core.opportunity", opportunity_bp=8_500),
        _completed("core.risk", risk_bp=5_000),
        _completed("core.impact", impact_bp=7_000),
        _completed("core.effort", effort_bp=3_000),
    )}

    result = TradeoffUnit().evaluate(_request(), prior)

    # risk_vs_reward: weaker 5000, margin 3500 → 5000 * 6500 / 10000 = 3250, the sharpest of three
    assert result.metrics["tension_bp"] == 3_250
    assert result.metrics["margin_bp"] == 3_500
    assert result.metrics["axis_count"] == 3
    assert result.metrics["contested_count"] == 1
    assert result.matched is True
    assert "headline.favours.reward" in result.reason_codes
    assert "headline.concedes.caution" in result.reason_codes
    assert "tradeoff_contested" in result.reason_codes
    # The quieter axes are still on the record: speed won its own argument against certainty.
    assert "favours.speed" in result.reason_codes
    assert "concedes.certainty" in result.reason_codes
    assert {finding.finding_id for finding in result.findings} == {
        "tradeoff.cost_vs_benefit", "tradeoff.risk_vs_reward", "tradeoff.speed_vs_certainty"}


def test_every_axis_becomes_a_finding_even_when_the_call_was_easy():
    """What was given up belongs in the explanation whether or not the decision was hard."""
    result = TradeoffUnit().evaluate(_request(), {item.reasoner_id: item for item in (
        _completed("core.opportunity", opportunity_bp=9_000),
        _completed("core.risk", risk_bp=500),
    )})

    assert result.matched is False
    assert "tradeoff_settled" in result.reason_codes
    finding, = result.findings
    assert finding.matched is False
    assert "concedes.caution" in finding.reason_codes


def test_the_headline_is_the_sharpest_axis_not_the_first_plugin():
    """Registration order must never decide which tension a human is shown."""
    result = TradeoffUnit().evaluate(_request(), {item.reasoner_id: item for item in (
        # cost_vs_benefit sorts first alphabetically but is the easiest call here
        _completed("core.impact", impact_bp=9_000),
        _completed("core.effort", effort_bp=200),
        _completed("core.opportunity", opportunity_bp=6_000),
        _completed("core.risk", risk_bp=5_900),
    )})

    assert result.metrics["tension_bp"] == 5_841        # 5900 * 9900 / 10000
    assert "headline.balanced.risk_vs_reward" in result.reason_codes


def test_a_perfect_tie_between_axes_is_broken_by_name_not_by_order():
    """Identical tension and margin on two axes still yields one stable, replayable headline."""
    prior = {item.reasoner_id: item for item in (
        _completed("core.opportunity", opportunity_bp=6_000),
        _completed("core.risk", risk_bp=4_000),
        _completed("core.impact", impact_bp=6_000),
        _completed("core.effort", effort_bp=4_000),
    )}

    result = TradeoffUnit().evaluate(_request(), prior)

    # Both axes score identically; cost_vs_benefit wins the tie on plugin id alone.
    assert "headline.favours.benefit" in result.reason_codes
    assert "headline.favours.reward" not in result.reason_codes


def test_the_same_situation_reasons_identically_twice():
    """Replayability is the whole promise: no clock, no randomness, no iteration order."""
    prior = {item.reasoner_id: item for item in (
        _completed("core.temporal", urgency_bp=7_400),
        _completed("core.confidence", confidence_bp=4_100),
        _completed("core.opportunity", opportunity_bp=6_600),
        _completed("core.risk", risk_bp=6_200),
    )}
    unit = TradeoffUnit()

    first = unit.evaluate(_request(), prior)
    second = unit.evaluate(_request(), prior)

    assert dict(first.metrics) == dict(second.metrics)
    assert first.reason_codes == second.reason_codes
    assert first.semantic_hash == second.semantic_hash


# ---------------------------------------------------------------------------------------------
# Boundaries: this unit analyses, it never decides
# ---------------------------------------------------------------------------------------------

def test_the_unit_never_touches_a_candidate():
    """Emitting an adjustment or check would make it a second decision authority."""
    result = TradeoffUnit().evaluate(_request(), {item.reasoner_id: item for item in (
        _completed("core.opportunity", opportunity_bp=8_000),
        _completed("core.risk", risk_bp=7_500),
    )})

    assert result.adjustments == ()
    assert result.checks == ()


def test_the_unit_never_republishes_a_reserved_shared_metric():
    """It reads confidence and urgency; publishing either would silently re-score the system."""
    published = set(TradeoffUnit().publishes)

    assert published.isdisjoint({"confidence_bp", "urgency_bp", "priority_override_bp"})

    result = TradeoffUnit().evaluate(_request(), {item.reasoner_id: item for item in (
        _completed("core.temporal", urgency_bp=9_000),
        _completed("core.confidence", confidence_bp=2_000),
    )})

    assert set(result.metrics) <= published


def test_a_contested_reading_is_not_a_recommendation():
    """`matched` says a dilemma exists — it must never be read as 'take the leading side'."""
    result = TradeoffUnit().evaluate(_request(), {item.reasoner_id: item for item in (
        _completed("core.opportunity", opportunity_bp=7_000),
        _completed("core.risk", risk_bp=6_900),
    )})

    assert result.matched is True
    assert result.adjustments == ()
    assert all(not code.startswith("recommend") for code in result.reason_codes)
