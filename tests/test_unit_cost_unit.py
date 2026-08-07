"""Executable contract for the Cost Unit (Layer 4 · Part 2, Optimization).

The Cost Unit is the only unit that argues *against* motion, which makes two of its properties
load-bearing for the whole system:

* It must stay silent about costs it cannot see. A fabricated zero on the cost of waiting tells the
  Decision Maker that delay is free — the most expensive mistake this unit could make.
* It must never eliminate. Price is an input to a decision; a unit that could kill a play on cost
  alone would have quietly become the decision authority.

Everything else here pins the arithmetic that a reviewer should be able to reproduce by hand from
the manifest: effort is the roster's cheapest route, exposure is its worst case.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.cost_unit import (
    COST_BENEFIT_STAGE,
    CostUnit,
    DelayCostPlugin,
    ReversibilityPlugin,
    StepEffortPlugin,
)
from genios_engine.reason.unit import UnitCategory, UnitView

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _play(play_id: str, *, steps=("Draft the reply",), effort=1_200, impact=6_000,
          success=6_000, risk=1_000, read_only=True, external=None) -> PlayDefinition:
    metadata = {} if external is None else {"external_recipient_required": external}
    return PlayDefinition(
        play_id=play_id,
        version="1",
        label=play_id.replace("_", " ").title(),
        steps=tuple(steps),
        effort_bp=effort,
        impact_bp=impact,
        success_probability_bp=success,
        risk_bp=risk,
        read_only=read_only,
        metadata=metadata,
    )


def _request(*, plays=None, config=None, facts=None, policies=()) -> ReasoningRequest:
    specs = [ReasonerSpec("core.cost", "1.0.0", config=config or {})]
    if policies:
        # A capability that declares policies must carry a required core.constraint.
        specs.append(ReasonerSpec("core.constraint", "1.0.0"))
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=tuple(specs),
        plays=tuple(plays or (_play("send_nudge"),)),
        policies=tuple(policies),
    )
    context = ContextSnapshot(
        org_id="org_1",
        graph_version=17,
        root_entity_id="deal_1",
        root_entity_type="deal",
        evaluation_time=NOW,
        selector_version="selector.v1",
        facts=dict(facts or {}),
    )
    return ReasoningRequest(
        org_id="org_1",
        capability=capability,
        context=context,
        evaluation_time=NOW,
        trigger_kind="email.received",
        config_snapshot_id="cfg_1",
    )


def _view(request: ReasoningRequest, prior=None) -> UnitView:
    spec = next(item for item in request.capability.reasoners
                if item.reasoner_id == "core.cost")
    return UnitView(request=request, spec=spec, prior=dict(prior or {}))


def _prior(reasoner_id: str, **metrics) -> ReasonerResult:
    return ReasonerResult(reasoner_id=reasoner_id, reasoner_version="1.0.0",
                          status=ResultStatus.COMPLETED, matched=True, metrics=metrics)


def _days_ago(days: int) -> str:
    return (NOW - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------------------------
# StepEffortPlugin — effort is what the play actually asks for, not what it claims
# ---------------------------------------------------------------------------------------------

def test_effort_is_the_cheapest_route_the_roster_offers():
    """Acting means running one play, so the least anyone could pay is the honest floor.

    Averaging would price a route nobody has to take, and the max would price effort that a cheaper
    alternative makes optional.
    """
    request = _request(plays=(
        _play("log_note", steps=("Log a note",)),
        _play("full_review", steps=("Pull the history", "Draft a brief", "Book a call")),
    ))

    observation = StepEffortPlugin().contribute(_view(request))[0]

    assert observation.metrics["effort_bp"] == 1_200          # one step at the default rate
    assert observation.metrics["effort_ceiling_bp"] == 3_600  # three steps
    assert observation.metrics["play_count"] == 2


def test_effort_rate_is_tunable_per_capability():
    """A capability whose steps are heavier says so in Layer 3 config, not in this unit's code."""
    request = _request(plays=(_play("draft_reply", steps=("Draft", "Send")),),
                       config={"step_effort_bp": 2_000})

    observation = StepEffortPlugin().contribute(_view(request))[0]

    assert observation.metrics["effort_bp"] == 4_000


def test_a_non_integer_effort_rate_is_a_deployment_fault():
    """Bad tuning must fail loudly here rather than become a plausible-looking cost downstream."""
    request = _request(config={"step_effort_bp": "cheap"})

    with pytest.raises(ValueError, match="step_effort_bp"):
        StepEffortPlugin().contribute(_view(request))


# ---------------------------------------------------------------------------------------------
# DelayCostPlugin — the silence that must never be priced at zero
# ---------------------------------------------------------------------------------------------

def test_delay_cost_says_nothing_when_nothing_dates_the_silence():
    """No timestamp and no momentum reading means the cost of waiting is unknown, not zero.

    This is the protection that stops "we have no evidence delay hurts" from being delivered as
    "delay does not hurt".
    """
    assert DelayCostPlugin().contribute(_view(_request())) == ()


def test_delay_cost_ignores_an_unparseable_timestamp_rather_than_guessing():
    """A corrupt fact is missing evidence, not evidence of a fresh conversation."""
    request = _request(facts={"deal.last_inbound": "last tuesday"})

    assert DelayCostPlugin().contribute(_view(request)) == ()


def test_delay_cost_prices_whole_days_of_waiting():
    """Ten days of silence at the default 400bp/day is a 4,000bp cost of continuing to wait."""
    request = _request(facts={"deal.last_inbound": _days_ago(10)})

    observation = DelayCostPlugin().contribute(_view(request))[0]

    assert observation.metrics["delay_cost_bp"] == 4_000
    assert observation.metrics["waiting_hours"] == 240


def test_delay_cost_falls_back_to_measured_momentum_loss_when_no_timestamp_exists():
    """Temporal already priced the same silence as lost warmth; use it rather than stay blind."""
    view = _view(_request(), prior={"core.temporal": _prior("core.temporal", drop_bp=7_000)})

    observation = DelayCostPlugin().contribute(view)[0]

    assert observation.metrics["delay_cost_bp"] == 7_000
    assert "waiting_hours" not in observation.metrics


def test_delay_cost_takes_the_stronger_reading_instead_of_adding_them():
    """Elapsed time and momentum loss measure one silence; summing them would double-count it."""
    view = _view(_request(facts={"deal.last_inbound": _days_ago(5)}),
                 prior={"core.temporal": _prior("core.temporal", drop_bp=6_000)})

    observation = DelayCostPlugin().contribute(view)[0]

    assert observation.metrics["delay_cost_bp"] == 6_000       # not 2_000 + 6_000


# ---------------------------------------------------------------------------------------------
# ReversibilityPlugin — the downside nobody counts in hours
# ---------------------------------------------------------------------------------------------

def test_exposure_reports_the_worst_play_because_the_choice_is_not_made_yet():
    """Two harmless read-only plays must not hide one irreversible outbound one."""
    request = _request(plays=(
        _play("log_note", read_only=True),
        _play("send_intro", read_only=False, external=True),
    ))

    observation = ReversibilityPlugin().contribute(_view(request))[0]

    assert observation.metrics["exposure_bp"] == 8_000         # 6,000 irreversible + 2,000 external
    assert observation.metrics["irreversible_play_count"] == 1
    assert observation.metrics["external_recipient_play_count"] == 1
    assert observation.reason_codes == ("irreversible_action_available",)


def test_a_read_only_roster_carries_no_exposure():
    """Nothing here can be got wrong in a way that cannot be undone — an evidenced zero."""
    request = _request(plays=(_play("log_note", read_only=True),))

    observation = ReversibilityPlugin().contribute(_view(request))[0]

    assert observation.metrics["exposure_bp"] == 0
    assert observation.reason_codes == ("roster_is_reversible",)


def test_human_approval_relieves_exposure_because_a_person_reads_it_first():
    """The downside is still real, but the policy catches it before it leaves the building."""
    request = _request(plays=(_play("send_intro", read_only=False),),
                       policies=("human_approval_required",))

    observation = ReversibilityPlugin().contribute(_view(request))[0]

    assert observation.metrics["exposure_bp"] == 3_000         # 6,000 less the 3,000 backstop


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_the_unit_satisfies_the_reasoner_protocol():
    """Part 1 schedules units through one protocol; a unit that drifts off it cannot be run."""
    assert isinstance(CostUnit(), Reasoner)
    assert CostUnit().category is UnitCategory.OPTIMIZATION


def test_the_unit_never_claims_authority_over_shared_metrics():
    """confidence_bp and urgency_bp have named owners; publishing them here re-scores everything."""
    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}

    assert reserved.isdisjoint(CostUnit().publishes)

    result = CostUnit().evaluate(_request(), {})

    assert reserved.isdisjoint(result.metrics)


def test_cost_blends_effort_and_exposure_rather_than_adding_them():
    """An hour of work and a burnt relationship are different currencies; they trade off.

    One two-step irreversible play: effort 2,400bp, exposure 6,000bp, blended 60/40 → 3,840bp.
    """
    result = CostUnit().evaluate(
        _request(plays=(_play("send_nudge", steps=("Draft", "Send"), read_only=False),)), {})

    assert result.metrics["effort_bp"] == 2_400
    assert result.metrics["exposure_bp"] == 6_000
    assert result.metrics["cost_bp"] == 3_840


def test_an_unknown_cost_of_inaction_is_reported_as_unknown():
    """Zero here is the absence of evidence, and the reason code has to say so out loud."""
    result = CostUnit().evaluate(_request(), {})

    assert result.metrics["do_nothing_cost_bp"] == 0
    assert "do_nothing_cost_unknown" in result.reason_codes


def test_untaken_headroom_corroborates_delay_without_double_counting_it():
    """Opportunity already priced the same silence; the stronger reading leads, the weaker lifts.

    Headroom 6,600bp leads, ten days of delay (4,000bp) adds a quarter → 7,600bp of doing nothing.
    """
    prior = {"core.opportunity": _prior("core.opportunity", opportunity_bp=6_600)}
    result = CostUnit().evaluate(_request(facts={"deal.last_inbound": _days_ago(10)}), prior)

    assert result.metrics["delay_cost_bp"] == 4_000
    assert result.metrics["do_nothing_cost_bp"] == 7_600


def test_the_gap_saturates_at_zero_when_acting_is_worth_it():
    """*How comfortably* worth it something is is a ranking question, and ranking is Part 3's."""
    prior = {"core.opportunity": _prior("core.opportunity", opportunity_bp=9_000)}
    result = CostUnit().evaluate(_request(), prior)

    assert result.metrics["cost_benefit_gap_bp"] == 0
    assert result.matched is False
    assert "cost_within_tolerance" in result.reason_codes


# ---------------------------------------------------------------------------------------------
# Adjustments and checks — what this unit is allowed to do to a candidate
# ---------------------------------------------------------------------------------------------

def test_a_play_whose_steps_outgrew_its_declared_effort_is_corrected():
    """Steps get added to a play long after its effort_bp was agreed; scoring must follow.

    Five steps imply 6,000bp against a declared 1,200bp — a 4,800bp drift, capped at the 3,000bp
    ceiling because this unit audits a declaration, it does not replace the author's judgement.
    """
    request = _request(plays=(_play("full_review", steps=("A", "B", "C", "D", "E"), effort=1_200),))

    result = CostUnit().evaluate(request, {})

    assert len(result.adjustments) == 1
    adjustment = result.adjustments[0]
    assert (adjustment.play_id, adjustment.component) == ("full_review", "effort")
    assert adjustment.delta_bp == 3_000
    assert adjustment.reason_code == "declared_effort_understated"


def test_a_play_that_declared_its_effort_honestly_is_left_alone():
    """Small drift is authoring noise; correcting it would churn scores for no information."""
    request = _request(plays=(_play("send_nudge", steps=("Draft", "Send"), effort=2_400),))

    assert CostUnit().evaluate(request, {}).adjustments == ()


def test_an_overstated_effort_is_corrected_downwards_too():
    """The audit runs both ways — a play priced as harder than it is gets unfairly buried."""
    request = _request(plays=(_play("log_note", steps=("Log it",), effort=8_000),))

    adjustment = CostUnit().evaluate(request, {}).adjustments[0]

    assert adjustment.delta_bp == -3_000
    assert adjustment.reason_code == "declared_effort_overstated"


def test_a_play_costing_more_than_it_can_return_is_warned_never_eliminated():
    """Price is one voice at the table.

    An eight-step irreversible outbound audit costs 8,960bp blended, against a 4,000×3,000 expected
    benefit of 1,200bp and no evidenced cost of waiting. That is a clear overspend — and it still
    leaves the play in contention, with the ledger attached for whoever decides.
    """
    request = _request(plays=(_play(
        "run_full_audit", steps=tuple("step_%d" % i for i in range(8)), effort=9_600,
        impact=4_000, success=3_000, read_only=False, external=True),))

    result = CostUnit().evaluate(request, {})

    assert len(result.checks) == 1
    check = result.checks[0]
    assert check.stage == COST_BENEFIT_STAGE
    assert check.outcome is CheckOutcome.WARN
    assert check.outcome is not CheckOutcome.ELIMINATE
    assert check.reason_code == "cost_exceeds_expected_benefit"
    assert check.evaluator_id == "core.cost"
    assert check.detail["estimated_cost_bp"] == 8_960
    assert check.detail["expected_benefit_bp"] == 1_200
    assert result.matched is True


def test_an_expensive_play_is_not_warned_when_the_silence_costs_more():
    """Expensive is exactly the right call when doing nothing is worse — that is the whole point."""
    plays = (_play("run_full_audit", steps=tuple("step_%d" % i for i in range(8)), effort=9_600,
                   impact=4_000, success=3_000, read_only=False, external=True),)
    prior = {"core.opportunity": _prior("core.opportunity", opportunity_bp=9_500)}

    result = CostUnit().evaluate(_request(plays=plays), prior)

    assert result.checks == ()
    assert result.matched is False


def test_checks_and_adjustments_are_emitted_in_play_id_order():
    """Nothing downstream may depend on manifest or dict order to reproduce a hash."""
    plays = (
        _play("zeta_audit", steps=tuple("s%d" % i for i in range(9)), effort=1_000,
              impact=1_000, success=1_000, read_only=False),
        _play("alpha_audit", steps=tuple("s%d" % i for i in range(9)), effort=1_000,
              impact=1_000, success=1_000, read_only=False),
    )

    result = CostUnit().evaluate(_request(plays=plays), {})

    assert [item.play_id for item in result.adjustments] == ["alpha_audit", "zeta_audit"]
    assert [item.play_id for item in result.checks] == ["alpha_audit", "zeta_audit"]


# ---------------------------------------------------------------------------------------------
# Determinism and one real situation, end to end
# ---------------------------------------------------------------------------------------------

def test_the_same_situation_reasons_to_the_same_bytes_twice():
    """Replay is the audit story; a unit that drifts between runs cannot be re-examined later."""
    request = _request(plays=(_play("log_note"), _play("send_intro", read_only=False)),
                       facts={"deal.last_inbound": _days_ago(6)})
    prior = {"core.opportunity": _prior("core.opportunity", opportunity_bp=5_000)}

    first = CostUnit().evaluate(request, prior)
    second = CostUnit().evaluate(request, prior)

    assert first.semantic_hash == second.semantic_hash
    assert dict(first.metrics) == dict(second.metrics)


def test_chasing_a_ten_day_silent_deal_reads_as_cheap_against_what_silence_costs():
    """The real Acme scenario: two plays on the shelf, one quiet buyer, ten days gone.

    * ``log_note`` — one step, read-only. ``send_nudge`` — two steps, irreversible.
    * Effort floor 1,200bp (log the note), exposure ceiling 6,000bp (the nudge cannot be unsent).
    * Blended 60/40 that is 3,120bp to act.
    * Ten days of silence prices at 4,000bp, and Opportunity found 6,600bp of headroom sitting
      unworked → 7,600bp to keep waiting.
    * Acting costs less than half of not acting: no warning, no correction, nothing blocked.
    """
    request = _request(
        plays=(_play("log_note", steps=("Log the call",), effort=1_200),
               _play("send_nudge", steps=("Draft the note", "Send it"), effort=2_400,
                     impact=7_000, success=6_000, read_only=False)),
        facts={"deal.last_inbound": _days_ago(10)},
    )
    prior = {"core.opportunity": _prior("core.opportunity", opportunity_bp=6_600)}

    result = CostUnit().evaluate(request, prior)

    assert result.status is ResultStatus.COMPLETED
    assert dict(result.metrics) == {
        "effort_bp": 1_200,
        "exposure_bp": 6_000,
        "cost_bp": 3_120,
        "delay_cost_bp": 4_000,
        "do_nothing_cost_bp": 7_600,
        "cost_benefit_gap_bp": 0,
    }
    assert result.matched is False
    assert result.checks == ()
    assert result.adjustments == ()
    assert "waiting_has_a_price" in result.reason_codes
    assert {finding.finding_id for finding in result.findings} == {
        "cost.step_effort", "cost.delay_cost", "cost.reversibility_exposure", "cost.ledger"}
