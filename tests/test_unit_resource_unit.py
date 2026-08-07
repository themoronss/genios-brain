"""Executable contract for Layer 4 · Part 2 — the Resource Unit (`core.resource`).

The unit answers "do we actually have what this would take?". These tests pin the properties that
make that answer safe to build on:

* **Silence is not zero.** An owner nobody measured is not an owner with no capacity. Every plugin
  must contribute nothing when its facts are absent, and the unit must omit the metric rather than
  publish a fabricated shortfall that would make every play look infeasible.
* **A shortfall cautions, it never eliminates.** Capacity is a WARN at the `precondition` stage.
  Turning it into an elimination would let a busy calendar silently overrule a human's judgement.
* **The binding constraint wins.** Scarce budget and an available owner do not average out.
* **Determinism.** Same frozen situation twice, same numbers and the same result hash — which is
  what makes a decision replayable months later.
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
    ReasonerSpec,
    ReasoningRequest,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.common import active_spec
from genios_engine.reason.reasoners.resource_unit import (
    HeadroomPlugin,
    OwnerAvailabilityPlugin,
    ResourceUnit,
    WorkloadSaturationPlugin,
)
from genios_engine.reason.unit import UnitCategory, UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)
UNIT_ID = "core.resource"


def _play(play_id: str = "send_followup") -> PlayDefinition:
    return PlayDefinition(play_id=play_id, version="1", label=play_id.replace("_", " ").title(),
                          steps=("Draft a grounded follow-up",))


def _request(facts=None, *, config=None, plays=None, evidence=()) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec(UNIT_ID, "1.0.0", config=config or {}),),
        plays=tuple(plays or (_play(),)),
        policies=(),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
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
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _view(request: ReasoningRequest) -> UnitView:
    return UnitView(request=request, spec=active_spec(request, UNIT_ID), prior={})


def _evaluate(facts=None, *, config=None, plays=None, evidence=()):
    return ResourceUnit().evaluate(
        _request(facts, config=config, plays=plays, evidence=evidence), {})


# ---------------------------------------------------------------------------------------------
# Owner availability — capacity is a person before it is a budget line
# ---------------------------------------------------------------------------------------------

def test_a_measured_availability_outranks_a_status_label():
    """A number someone measured beats a coarse CRM label; otherwise tuning is impossible."""
    view = _view(_request({"deal.owner": "dana_whitfield", "owner.status": "available",
                           "owner.availability_bp": 2_500}))

    observation, = OwnerAvailabilityPlugin().contribute(view)

    assert observation.metrics["capacity_bp"] == 2_500


def test_an_owner_on_leave_has_no_capacity_at_all():
    """Assigning work to someone who is out is the failure this whole unit exists to surface."""
    view = _view(_request({"deal.owner": "dana_whitfield", "owner.status": "out_of_office"}))

    observation, = OwnerAvailabilityPlugin().contribute(view)

    assert observation.metrics["capacity_bp"] == 0
    assert observation.reason_codes == ("owner_availability_declared",)


def test_a_busy_owner_is_reduced_not_erased_and_the_reduction_is_tunable():
    """A busy account manager and a busy surgeon are not equally busy — Layer 3 decides which."""
    facts = {"deal.owner": "dana_whitfield", "owner.status": "busy"}

    default, = OwnerAvailabilityPlugin().contribute(_view(_request(facts)))
    tuned, = OwnerAvailabilityPlugin().contribute(
        _view(_request(facts, config={"owner_reduced_availability_bp": 1_500})))

    assert default.metrics["capacity_bp"] == 4_000
    assert tuned.metrics["capacity_bp"] == 1_500


def test_an_empty_owner_field_that_was_captured_is_evidence_of_no_executor():
    """Someone looked and found nobody assigned — that is an observation, not an absence."""
    view = _view(_request({"deal.owner": ""}))

    observation, = OwnerAvailabilityPlugin().contribute(view)

    assert observation.kind == "resource.owner_unassigned"
    assert observation.metrics["capacity_bp"] == 0
    assert observation.reason_codes == ("no_owner_to_execute",)


def test_an_unmeasured_owner_produces_no_availability_claim():
    """The core silence rule: no facts, no observation — never a fabricated zero."""
    view = _view(_request({"deal.owner": "dana_whitfield"}))

    assert OwnerAvailabilityPlugin().contribute(view) == ()


def test_an_unrecognised_status_word_is_treated_as_unknown_not_available():
    """Guessing availability upward is how work lands on someone who is on parental leave."""
    view = _view(_request({"deal.owner": "dana_whitfield", "owner.status": "sabbatical_q3"}))

    assert OwnerAvailabilityPlugin().contribute(view) == ()


def test_a_malformed_availability_figure_is_unknown_rather_than_full():
    """Corrupt input must never read as maximum capacity — that is the dangerous direction."""
    view = _view(_request({"deal.owner": "dana_whitfield", "owner.availability_bp": "plenty"}))

    assert OwnerAvailabilityPlugin().contribute(view) == ()


# ---------------------------------------------------------------------------------------------
# Workload saturation — availability and load are separate questions
# ---------------------------------------------------------------------------------------------

def test_open_commitments_are_measured_against_declared_serving_capacity():
    """Load is only meaningful relative to what the capability says a person can carry."""
    view = _view(_request({"owner.open_items": 4}, config={"workload_capacity_items": 8}))

    observation, = WorkloadSaturationPlugin().contribute(view)

    assert observation.metrics == {"load_bp": 5_000, "open_items": 4, "capacity_items": 8}


def test_load_saturates_instead_of_pretending_to_rank_degrees_of_overload():
    """Twice over capacity and five times over are both simply 'cannot take more'."""
    view = _view(_request({"owner.open_items": 50}, config={"workload_capacity_items": 10}))

    observation, = WorkloadSaturationPlugin().contribute(view)

    assert observation.metrics["load_bp"] == 10_000


def test_a_declared_load_is_used_directly_without_recounting_items():
    """A system that already computed load knows more than a raw item count does."""
    view = _view(_request({"owner.load_bp": 6_500, "owner.open_items": 99}))

    observation, = WorkloadSaturationPlugin().contribute(view)

    assert observation.metrics == {"load_bp": 6_500}


def test_owner_and_team_load_are_reported_separately():
    """A team at the wall is a real constraint even when this one person is free."""
    view = _view(_request({"owner.load_bp": 1_000, "team.load_bp": 9_500}))

    observations = WorkloadSaturationPlugin().contribute(view)

    assert [item.kind for item in observations] == ["resource.owner_workload",
                                                    "resource.team_workload"]
    assert [item.metrics["load_bp"] for item in observations] == [1_000, 9_500]


def test_no_workload_facts_means_no_workload_claim():
    """An uncounted queue is not an empty queue."""
    assert WorkloadSaturationPlugin().contribute(_view(_request({"deal.status": "open"}))) == ()


# ---------------------------------------------------------------------------------------------
# Budget and time headroom — the two resources that run out on their own
# ---------------------------------------------------------------------------------------------

def test_budget_headroom_is_the_unspent_fraction_of_the_declared_allowance():
    view = _view(_request({"budget.total_minor": 50_000, "budget.remaining_minor": 12_500}))

    observation, = HeadroomPlugin().contribute(view)

    assert observation.kind == "resource.budget_headroom"
    assert observation.metrics["headroom_bp"] == 2_500


def test_budget_headroom_needs_both_sides_of_the_ratio():
    """A remaining figure with no allowance to compare it against says nothing about headroom."""
    assert HeadroomPlugin().contribute(_view(_request({"budget.remaining_minor": 12_500}))) == ()
    assert HeadroomPlugin().contribute(
        _view(_request({"budget.total_minor": 0, "budget.remaining_minor": 0}))) == ()


def test_time_headroom_is_measured_against_the_frozen_evaluation_time():
    """Never a clock: this is what lets the same deadline reading reproduce in a replay."""
    view = _view(_request({"commitment.due_at": "2026-08-13T12:00:00+00:00"}))

    observation, = HeadroomPlugin().contribute(view)

    assert observation.metrics == {"headroom_bp": 10_000, "hours_remaining": 168}


def test_a_deadline_already_past_leaves_no_headroom_but_still_reports_how_far_past():
    """Missed by an hour and missed by a week read very differently to a human."""
    view = _view(_request({"commitment.due_at": "2026-08-06T09:00:00+00:00"}))

    observation, = HeadroomPlugin().contribute(view)

    assert observation.metrics == {"headroom_bp": 0, "hours_remaining": -3}
    assert observation.reason_codes == ("deadline_passed",)


def test_the_deadline_field_is_capability_configurable():
    """Different domains name their clock differently; the reasoning is the same."""
    view = _view(_request({"meeting.start_at": "2026-08-09T12:00:00+00:00"},
                          config={"deadline_field": "meeting.start_at"}))

    observation, = HeadroomPlugin().contribute(view)

    assert observation.metrics["hours_remaining"] == 72


def test_an_unparseable_deadline_is_not_a_deadline():
    assert HeadroomPlugin().contribute(_view(_request({"commitment.due_at": "soon"}))) == ()


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_unknown_capacity_warns_rather_than_inventing_a_shortfall():
    """The blind spot must reach the human; a zero would look like a measured impossibility."""
    result = _evaluate({"deal.status": "open"})

    assert result.matched is None
    assert "capacity_bp" not in result.metrics
    assert result.metrics["resource_signal_count"] == 0
    check, = result.checks
    assert (check.stage, check.outcome, check.reason_code) == (
        "precondition", CheckOutcome.WARN, "resource_capacity_unknown")


def test_an_observed_saturation_is_still_warned_when_capacity_itself_is_unmeasured():
    """A load reading without an availability reading is a partial answer, not no answer."""
    result = _evaluate({"owner.open_items": 40})

    assert result.matched is True
    assert result.metrics["load_bp"] == 10_000
    assert [check.reason_code for check in result.checks] == [
        "workload_saturated", "resource_capacity_unknown"]


def test_the_binding_constraint_wins_on_every_axis():
    """Scarce budget and an available owner do not average out into 'half feasible'."""
    result = _evaluate({
        "owner.status": "available",                      # capacity 10000
        "deal.owner": "dana_whitfield",
        "owner.load_bp": 1_000, "team.load_bp": 9_000,    # heaviest load binds
        "budget.total_minor": 50_000, "budget.remaining_minor": 40_000,   # 8000
        "commitment.due_at": "2026-08-06T13:00:00+00:00",                 # one hour of 168
    })

    assert result.metrics["capacity_bp"] == 10_000
    assert result.metrics["load_bp"] == 9_000
    assert result.metrics["headroom_bp"] == 60        # the clock, not the money, is the constraint


def test_a_comfortably_resourced_situation_records_a_pass_rather_than_going_quiet():
    """The audit trail must show capacity was checked, not that the unit skipped it."""
    result = _evaluate({
        "deal.owner": "dana_whitfield", "owner.status": "available", "owner.open_items": 2,
        "budget.total_minor": 50_000, "budget.remaining_minor": 45_000,
        "commitment.due_at": "2026-08-11T12:00:00+00:00",
    })

    assert result.matched is False
    assert result.findings == ()
    check, = result.checks
    assert (check.outcome, check.reason_code) == (
        CheckOutcome.PASS, "resource_capacity_available")


def test_a_shortfall_never_eliminates_a_play():
    """Running short of capacity is a caution; only policy may remove a play from the contest."""
    result = _evaluate({
        "deal.owner": "", "owner.open_items": 90,
        "budget.total_minor": 50_000, "budget.remaining_minor": 0,
        "commitment.due_at": "2026-08-01T12:00:00+00:00",
    })

    assert result.checks
    assert all(check.stage == "precondition" for check in result.checks)
    assert all(check.outcome == CheckOutcome.WARN for check in result.checks)
    assert not any(check.outcome == CheckOutcome.ELIMINATE for check in result.checks)


def test_checks_are_ordered_by_play_id_not_by_authoring_order():
    """No ordering in this system may depend on the order a manifest happened to be written in."""
    result = _evaluate({"deal.status": "open"},
                       plays=(_play("zeta_play"), _play("alpha_play")))

    assert [check.play_id for check in result.checks] == ["alpha_play", "zeta_play"]


def test_the_capacity_floor_is_capability_tunable():
    """What counts as 'too thin to attempt' is a business judgement, authored in Layer 3."""
    facts = {"deal.owner": "dana_whitfield", "owner.availability_bp": 5_000}

    assert _evaluate(facts).matched is False
    strained = _evaluate(facts, config={"capacity_floor_bp": 6_000})
    assert strained.matched is True
    assert [check.reason_code for check in strained.checks] == ["owner_capacity_below_floor"]


def test_a_malformed_threshold_is_a_deployment_fault_not_a_silent_default():
    with pytest.raises(ValueError, match="integer basis points"):
        _evaluate({"deal.status": "open"}, config={"capacity_floor_bp": 20_000})


def test_a_zero_workload_capacity_is_rejected_where_it_is_authored():
    with pytest.raises(ValueError, match="positive integer"):
        _evaluate({"owner.open_items": 3}, config={"workload_capacity_items": 0})


def test_the_unit_cites_the_evidence_its_observations_stood_on():
    """A shortfall that cannot be traced to a captured fact is not auditable."""
    facts = {"deal.owner": "dana_whitfield", "owner.availability_bp": 1_000}
    evidence = (EvidenceRef("ev_owner", "deal.owner", "dana_whitfield"),
                EvidenceRef("ev_avail", "owner.availability_bp", 1_000))

    result = _evaluate(facts, evidence=evidence)

    assert result.evidence_ids == ("ev_avail", "ev_owner")


def test_the_unit_never_publishes_a_metric_another_unit_is_the_authority_for():
    """Publishing confidence_bp or urgency_bp here would silently re-score the whole system."""
    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}

    assert set(ResourceUnit.publishes).isdisjoint(reserved)


def test_the_unit_reports_and_does_not_decide():
    """No adjustment, no ranking, no winner — synthesis belongs to the Decision Maker."""
    result = _evaluate({"deal.owner": "", "owner.open_items": 90})

    assert result.adjustments == ()


def test_the_same_situation_twice_yields_the_same_numbers_and_the_same_hash():
    """Replayability is the whole promise; two identical runs must be indistinguishable."""
    facts = {"deal.owner": "dana_whitfield", "owner.status": "busy", "owner.open_items": 7,
             "budget.total_minor": 50_000, "budget.remaining_minor": 6_000,
             "commitment.due_at": "2026-08-08T12:00:00+00:00"}

    first, second = _evaluate(facts), _evaluate(facts)

    assert dict(first.metrics) == dict(second.metrics)
    assert first.semantic_hash == second.semantic_hash


def test_it_satisfies_the_reasoner_protocol_and_declares_its_place_in_the_roster():
    unit = ResourceUnit()

    assert isinstance(unit, Reasoner)
    assert unit.spec.reasoner_id == UNIT_ID
    assert unit.category == UnitCategory.OPTIMIZATION


# ---------------------------------------------------------------------------------------------
# One real situation, end to end
# ---------------------------------------------------------------------------------------------

def test_the_northwind_renewal_nobody_can_actually_staff():
    """Dana owns the Northwind renewal, is out of office, is carrying 14 open items against a
    capacity of 10, has $20 of a $500 budget left, and the customer's deadline is six hours away.

    Every axis is short at once. The unit must say so on all three, name each shortfall, and still
    leave the play standing — a human may well decide that one email from someone else is exactly
    the right answer, and this unit is not entitled to take that option away.
    """
    result = _evaluate({
        "deal.owner": "dana_whitfield",
        "owner.status": "out_of_office",
        "owner.open_items": 14,
        "budget.total_minor": 50_000,
        "budget.remaining_minor": 2_000,
        "commitment.due_at": "2026-08-06T18:00:00+00:00",
    }, plays=(_play("send_renewal_followup"),))

    assert result.matched is True
    assert result.metrics["capacity_bp"] == 0          # on leave
    assert result.metrics["load_bp"] == 10_000         # 14 items against a capacity of 10
    assert result.metrics["headroom_bp"] == 357        # six hours of a 168-hour window
    assert result.metrics["resource_signal_count"] == 4

    assert [check.reason_code for check in result.checks] == [
        "owner_capacity_below_floor", "resource_headroom_exhausted", "workload_saturated"]
    assert all(check.play_id == "send_renewal_followup" and check.outcome == CheckOutcome.WARN
               for check in result.checks)

    # Each shortfall survives as its own finding, so a card can explain which resource is missing.
    assert sorted(finding.finding_id for finding in result.findings) == [
        "resource.budget_headroom", "resource.deadline_headroom", "resource.owner_availability",
        "resource.owner_workload"]
