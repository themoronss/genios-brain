"""Executable contract for the Impact Unit (`core.impact`).

Impact is the number that decides whether a human ever looks at something. These tests pin the
properties that make it trustworthy:

* **Silence is never zero.** Every missing input must leave the corresponding metric *absent*, not
  reported as nothing-at-stake. A fabricated zero is indistinguishable downstream from a measured
  one, and it would quietly demote exactly the deals that matter most.
* **The blend renormalises.** Partial data must not shrink a known-large stake.
* **The unit analyses, never decides.** It may tilt a play the capability author already named, by
  an amount the author already authorised, and nothing else.
* **Determinism.** The same frozen situation produces byte-identical metrics, twice.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    EvidenceRef,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.impact_unit import (
    IMPACT_ADJUSTMENT_REASON,
    AccountImportancePlugin,
    ImpactUnit,
    RevenueExposurePlugin,
    StrategicLinkagePlugin,
)

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
GOAL_ID = "grow_enterprise_arr"


def _request(*, facts=None, config=None, evidence=(), plays=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.renewal_at_risk",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal(GOAL_ID, "Grow enterprise ARR"),
        reasoners=(ReasonerSpec("core.impact", "1.0.0", config=config or {}),),
        plays=tuple(plays or (PlayDefinition(
            play_id="executive_escalation", version="1", label="Executive escalation",
            steps=("Brief the exec sponsor",), impact_bp=5_000),)),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=9,
        root_entity_id="deal_northwind",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=facts or {},
        evidence=tuple(evidence),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="crm.deal_updated",
    )


def _view(request: ReasoningRequest, prior=None):
    unit = ImpactUnit()
    spec = request.capability.reasoners[0]
    return unit.retrieve(request, spec, prior or {})


def _relationship(coverage_bp: int, status=ResultStatus.COMPLETED) -> dict:
    return {"core.relationship": ReasonerResult(
        reasoner_id="core.relationship", reasoner_version="1", status=status,
        metrics={"coverage_bp": coverage_bp} if status == ResultStatus.COMPLETED else {})}


# ---------------------------------------------------------------------------------------------
# Revenue exposure — money is only large relative to a declared reference
# ---------------------------------------------------------------------------------------------

def test_deal_value_is_scored_against_the_capabilitys_own_definition_of_large():
    """150k against a 200k reference is three quarters of a full stake, not an absolute verdict."""
    view = _view(_request(facts={"deal.value": 150_000},
                          config={"reference_value": 200_000}))

    (observation,) = RevenueExposurePlugin().contribute(view)

    assert observation.metrics["strength_bp"] == 7_500
    assert observation.metrics["exposure_value"] == 150_000
    assert observation.reason_codes == ("revenue_at_stake",)


def test_a_deal_far_above_the_reference_saturates_rather_than_running_away():
    """A ten-times-reference deal deserves the top of the scale, not ten times the priority."""
    view = _view(_request(facts={"deal.value": 2_000_000},
                          config={"reference_value": 200_000}))

    (observation,) = RevenueExposurePlugin().contribute(view)

    assert observation.metrics["strength_bp"] == 10_000


def test_an_unrecorded_deal_value_produces_no_observation():
    """An unsynced amount is unknown. Scoring it as 0 would bury a live deal under a data gap."""
    assert RevenueExposurePlugin().contribute(_view(_request(facts={"deal.status": "open"}))) == ()


def test_a_malformed_deal_value_is_silence_rather_than_a_fabricated_zero():
    """CRM text in a money column is a data fault; it must not read as 'this deal is worthless'."""
    view = _view(_request(facts={"deal.value": "not-a-number"}))

    assert RevenueExposurePlugin().contribute(view) == ()


def test_a_zero_amount_carries_no_information_about_the_stake():
    """CRMs write 0 for 'not filled in yet', so 0 is an absence of evidence, not evidence."""
    assert RevenueExposurePlugin().contribute(_view(_request(facts={"deal.value": 0}))) == ()


# ---------------------------------------------------------------------------------------------
# Account importance — an explicit business classification outranks an inferred proxy
# ---------------------------------------------------------------------------------------------

def test_a_named_account_tier_outranks_inferred_relationship_breadth():
    """If the business has designated the account strategic, thread count does not get a vote."""
    view = _view(
        _request(facts={"account.tier": "Strategic"},
                 config={"account_tier_field": "account.tier",
                         "account_tier_bp": {"strategic": 9_000, "smb": 2_000}}),
        prior=_relationship(1_000))

    (observation,) = AccountImportancePlugin().contribute(view)

    assert observation.metrics["strength_bp"] == 9_000
    assert observation.reason_codes == ("named_account_tier",)


def test_relationship_breadth_stands_in_when_no_tier_was_declared():
    """Accumulated relationship capital is a weaker but real proxy for what is at stake."""
    view = _view(_request(facts={"deal.status": "open"}), prior=_relationship(6_000))

    (observation,) = AccountImportancePlugin().contribute(view)

    assert observation.metrics["strength_bp"] == 6_000
    assert observation.reason_codes == ("relationship_footprint",)


def test_a_relationship_reasoner_that_never_ran_contributes_nothing():
    """'Dependency absent' and 'coverage is genuinely zero' are different facts."""
    assert AccountImportancePlugin().contribute(_view(_request())) == ()


def test_a_failed_relationship_reasoner_is_not_read_as_zero_coverage():
    view = _view(_request(), prior=_relationship(0, status=ResultStatus.FAILED))

    assert AccountImportancePlugin().contribute(view) == ()


def test_an_unmapped_tier_falls_back_instead_of_inventing_a_weight():
    """A tier the author never priced is unknown; the proxy is a better answer than a guess."""
    view = _view(
        _request(facts={"account.tier": "partner"},
                 config={"account_tier_field": "account.tier",
                         "account_tier_bp": {"strategic": 9_000}}),
        prior=_relationship(4_000))

    (observation,) = AccountImportancePlugin().contribute(view)

    assert observation.reason_codes == ("relationship_footprint",)
    assert observation.metrics["strength_bp"] == 4_000


# ---------------------------------------------------------------------------------------------
# Strategic linkage — intent lives in the capability, never in the entity alone
# ---------------------------------------------------------------------------------------------

def test_strategic_linkage_stays_silent_until_the_capability_names_the_field():
    """Untagged work is unclassified, not unimportant, so an unconfigured unit says nothing."""
    view = _view(_request(facts={"deal.initiatives": ("expand_enterprise",)}))

    assert StrategicLinkagePlugin().contribute(view) == ()


def test_the_strongest_linkage_sets_the_level_rather_than_the_sum():
    """Five minor initiatives do not outweigh one company priority."""
    view = _view(_request(
        facts={"deal.initiatives": ("logo_refresh", "expand_enterprise", "unpriced_pilot")},
        config={"strategic_link_field": "deal.initiatives",
                "strategic_goal_bp": {"expand_enterprise": 8_000, "logo_refresh": 1_000}}))

    (observation,) = StrategicLinkagePlugin().contribute(view)

    assert observation.metrics["strength_bp"] == 8_000
    assert observation.metrics["linked_goal_count"] == 2       # the unpriced one is not counted
    assert observation.reason_codes == ("linked_to_strategic_initiative",)


def test_linkage_to_the_capabilitys_own_goal_counts_without_being_listed():
    """The capability exists to move that goal, so work attached to it is strategic already."""
    view = _view(_request(
        facts={"deal.initiatives": (GOAL_ID,)},
        config={"strategic_link_field": "deal.initiatives", "goal_alignment_bp": 7_000}))

    (observation,) = StrategicLinkagePlugin().contribute(view)

    assert observation.metrics["strength_bp"] == 7_000
    assert observation.reason_codes == ("linked_to_capability_goal",)


def test_a_single_string_link_is_read_the_same_as_a_one_item_list():
    """Layer 2 emits scalars and lists for the same field; the reading must not depend on shape."""
    config = {"strategic_link_field": "deal.initiatives",
              "strategic_goal_bp": {"expand_enterprise": 8_000}}
    scalar = _view(_request(facts={"deal.initiatives": "expand_enterprise"}, config=config))
    listed = _view(_request(facts={"deal.initiatives": ("expand_enterprise",)}, config=config))

    assert StrategicLinkagePlugin().contribute(scalar)[0].metrics \
        == StrategicLinkagePlugin().contribute(listed)[0].metrics


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_a_dimension_that_did_not_report_is_absent_from_the_metrics():
    """The gap must stay visible: an omitted metric lets the reader default; a 0 lies to them."""
    result = ImpactUnit().evaluate(
        _request(facts={"deal.value": 180_000}, config={"reference_value": 200_000}), {})

    assert result.metrics["revenue_exposure_bp"] == 9_000
    assert "relationship_exposure_bp" not in result.metrics
    assert "strategic_bp" not in result.metrics
    # Renormalised over what was seen — a known-large deal is not diluted by unmeasured dimensions.
    assert result.metrics["impact_bp"] == 9_000
    assert result.metrics["impact_signal_count"] == 1


def test_a_situation_with_no_measurable_stake_publishes_no_impact_at_all():
    """No opinion is a legitimate result. matched=None says so; matched=False would be a claim."""
    result = ImpactUnit().evaluate(_request(facts={"deal.status": "open"}), {})

    assert result.matched is None
    assert "impact_bp" not in result.metrics
    assert result.metrics["impact_signal_count"] == 0
    assert result.adjustments == ()


def test_the_unit_never_publishes_a_metric_another_unit_owns():
    """confidence_bp and urgency_bp have named authorities; emitting them here rescores all."""
    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}

    assert reserved.isdisjoint(ImpactUnit().publishes)


def test_the_same_frozen_situation_scores_identically_twice():
    """Replay is the whole point: an audit months later must reproduce the number exactly."""
    request = _request(
        facts={"deal.value": 150_000, "account.tier": "strategic",
               "deal.initiatives": ("expand_enterprise",)},
        config={"reference_value": 200_000, "account_tier_field": "account.tier",
                "account_tier_bp": {"strategic": 9_000},
                "strategic_link_field": "deal.initiatives",
                "strategic_goal_bp": {"expand_enterprise": 8_000}})

    first = ImpactUnit().evaluate(request, {})
    second = ImpactUnit().evaluate(request, {})

    assert dict(first.metrics) == dict(second.metrics)
    assert first.semantic_hash == second.semantic_hash


def test_the_unit_satisfies_the_reasoner_protocol():
    assert isinstance(ImpactUnit(), Reasoner)


# ---------------------------------------------------------------------------------------------
# Tilting plays — authored in Layer 3, scaled here, chosen by nobody in Part 2
# ---------------------------------------------------------------------------------------------

def test_a_material_stake_tilts_only_the_plays_the_capability_authored():
    """The unit supplies magnitude; the author supplies which play the magnitude favours."""
    result = ImpactUnit().evaluate(
        _request(facts={"deal.value": 200_000},
                 config={"reference_value": 200_000,
                         "play_impact_bp": {"executive_escalation": 2_000}}), {})

    assert [(item.play_id, item.component, item.delta_bp) for item in result.adjustments] \
        == [("executive_escalation", "impact", 2_000)]
    assert result.adjustments[0].reason_code == IMPACT_ADJUSTMENT_REASON


def test_the_authored_delta_is_a_ceiling_scaled_by_the_measured_stake():
    """A barely-material deal must not get the same push as a company-defining one."""
    result = ImpactUnit().evaluate(
        _request(facts={"deal.value": 120_000},
                 config={"reference_value": 200_000,
                         "play_impact_bp": {"executive_escalation": 2_000}}), {})

    assert result.metrics["impact_bp"] == 6_000
    assert result.adjustments[0].delta_bp == 1_200          # 2,000bp ceiling × 6,000bp of stake


def test_an_immaterial_stake_tilts_nothing():
    """Below the declared threshold the unit reports the size and stays out of the contest."""
    result = ImpactUnit().evaluate(
        _request(facts={"deal.value": 20_000},
                 config={"reference_value": 200_000,
                         "play_impact_bp": {"executive_escalation": 2_000}}), {})

    assert result.matched is False
    assert result.metrics["impact_bp"] == 1_000
    assert result.adjustments == ()
    assert result.checks == ()
    assert "immaterial_impact" in result.reason_codes


def test_every_tilt_is_mirrored_by_an_auditable_check():
    """A component delta with no trace row is an unexplained score change months later."""
    result = ImpactUnit().evaluate(
        _request(facts={"deal.value": 200_000},
                 config={"reference_value": 200_000,
                         "play_impact_bp": {"executive_escalation": 2_000}}), {})

    (check,) = result.checks
    assert (check.play_id, check.stage, check.outcome) \
        == ("executive_escalation", "cost_benefit", CheckOutcome.ADJUST)
    assert check.evaluator_id == "core.impact"
    assert check.detail["delta_bp"] == 2_000


def test_a_malformed_authored_delta_is_a_loud_capability_fault():
    """Silently coercing bad tuning would let a broken manifest reprice plays undetected."""
    request = _request(facts={"deal.value": 200_000},
                       config={"reference_value": 200_000,
                               "play_impact_bp": {"executive_escalation": 40_000}})

    with pytest.raises(ValueError, match="play_impact_bp"):
        ImpactUnit().evaluate(request, {})


# ---------------------------------------------------------------------------------------------
# One real scenario, end to end
# ---------------------------------------------------------------------------------------------

def test_the_northwind_renewal_reports_a_high_stake_across_all_three_dimensions():
    """Northwind: a 150k renewal, on a strategic-tier account, tagged to the enterprise push.

    This is the case the unit exists for. Revenue alone reads 7,500bp — meaningful but not alarming.
    The account tier and the strategic tag are what lift it to 8,050bp and put it in front of a
    human. Any refactor that loses a dimension will show up here as a materially lower number.
    """
    request = _request(
        facts={"deal.value": 150_000, "account.tier": "strategic",
               "deal.initiatives": ("expand_enterprise",), "deal.status": "open"},
        evidence=(
            EvidenceRef("ev_value", "deal.value", 150_000, source_ref_id="crm_deal_9"),
            EvidenceRef("ev_tier", "account.tier", "strategic", source_ref_id="crm_account_3"),
            EvidenceRef("ev_init", "deal.initiatives", "expand_enterprise",
                        source_ref_id="planning_doc_1"),
        ),
        config={"reference_value": 200_000,
                "account_tier_field": "account.tier",
                "account_tier_bp": {"strategic": 9_000, "smb": 2_000},
                "strategic_link_field": "deal.initiatives",
                "strategic_goal_bp": {"expand_enterprise": 8_000},
                "play_impact_bp": {"executive_escalation": 2_000}})

    result = ImpactUnit().evaluate(request, {})

    assert result.status == ResultStatus.COMPLETED
    assert result.matched is True
    assert result.metrics["revenue_exposure_bp"] == 7_500
    assert result.metrics["relationship_exposure_bp"] == 9_000
    assert result.metrics["strategic_bp"] == 8_000
    # 7,500×5,000 + 9,000×3,000 + 8,000×2,000 over a 10,000 weight total.
    assert result.metrics["impact_bp"] == 8_050
    assert result.metrics["impact_signal_count"] == 3
    assert result.adjustments[0].delta_bp == 1_610          # 2,000bp ceiling × 8,050bp of stake
    # Every dimension cites what it stood on, and the citations survive into the result.
    assert result.evidence_ids == ("ev_init", "ev_tier", "ev_value")
    assert {finding.finding_id for finding in result.findings} == {
        "impact.revenue_exposure", "impact.account_importance", "impact.strategic_linkage"}
    assert "material_impact" in result.reason_codes
