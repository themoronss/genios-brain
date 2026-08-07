"""Executable contract for the Policy Unit (Layer 4 · Part 2, Optimization).

This is the only unit in Part 2 that is allowed to remove an option, so three properties are
load-bearing and pinned here in detail:

* **A rule the tenant never declared is not a rule.** Silence must mean silence — an invented
  default policy is indistinguishable downstream from one a customer actually wrote.
* **Breaches fail closed, concerns do not.** "The business forbids this" eliminates; "we cannot
  show this is allowed" warns. Collapsing the two in either direction is a business incident.
* **A rule only governs the plays it reaches.** A do-not-contact record must not stop somebody
  logging an internal note, and an approval threshold must not flag a play that already routes
  through a human.

Everything else fixes arithmetic a reviewer should be able to reproduce by hand from the manifest
and the tenant's configured rules.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners.policy_unit import (
    POLICY_STAGE,
    ApprovalThresholdPlugin,
    ContactPermissionPlugin,
    PolicyUnit,
    TimingRulePlugin,
)
from genios_engine.reason.unit import UnitCategory, UnitView

# A Thursday at midday UTC. Frozen, so every timing rule below is reproducible forever.
NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


def _play(play_id: str, *, read_only=True, external=None, tags=(),
          boundary=None) -> PlayDefinition:
    metadata = {}
    if external is not None:
        metadata["external_recipient_required"] = external
    if boundary is not None:
        metadata["execution_boundary"] = boundary
    return PlayDefinition(
        play_id=play_id,
        version="1",
        label=play_id.replace("_", " ").title(),
        steps=("Do the thing",),
        read_only=read_only,
        tags=tuple(tags),
        metadata=metadata,
    )


def _request(*, config=None, facts=None, plays=None) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling",
        version="1.0.0",
        domain="sales",
        root_entity_type="deal",
        goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.policy", "1.0.0", config=config or {}),),
        plays=tuple(plays or (_play("send_nudge", read_only=False, external=True),)),
        policies=(),
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


def _view(request: ReasoningRequest) -> UnitView:
    spec = next(item for item in request.capability.reasoners
                if item.reasoner_id == "core.policy")
    return UnitView(request=request, spec=spec, prior={})


# ---------------------------------------------------------------------------------------------
# ApprovalThresholdPlugin — the signature the business requires before it commits
# ---------------------------------------------------------------------------------------------

def test_an_undeclared_approval_rule_produces_no_observation():
    """A tenant who never wrote an approval threshold does not have one.

    Inventing a default here would fabricate a policy that no customer agreed to and that nobody
    could find in their handbook when they came to ask why work was blocked.
    """
    assert ApprovalThresholdPlugin().contribute(_view(_request())) == ()


def test_a_deal_under_the_threshold_is_left_alone():
    """The rule exists to catch large commitments; firing under the bar would make it noise."""
    request = _request(config={"approval_threshold_amount": 5_000_000},
                       facts={"deal.value": 1_200_000})

    assert ApprovalThresholdPlugin().contribute(_view(request)) == ()


def test_an_unsigned_commitment_over_the_threshold_is_a_breach():
    """£62,000 against a £50,000 approval bar with nothing signed is an unauthorised commitment."""
    request = _request(config={"approval_threshold_amount": 5_000_000},
                       facts={"deal.value": 6_200_000})

    observation = ApprovalThresholdPlugin().contribute(_view(request))[0]

    assert observation.metrics["blocking_bp"] == 10_000
    assert observation.metrics["value_amount"] == 6_200_000
    assert observation.metrics["threshold_amount"] == 5_000_000
    assert observation.reason_codes == ("approval_threshold_exceeded",)


def test_a_recorded_sign_off_satisfies_the_threshold():
    """The rule asks for a signature, not for silence — once it exists the rule is done."""
    request = _request(config={"approval_threshold_amount": 5_000_000},
                       facts={"deal.value": 6_200_000, "deal.approval_status": "Approved"})

    assert ApprovalThresholdPlugin().contribute(_view(request)) == ()


def test_an_unreadable_deal_value_is_a_concern_and_never_a_breach():
    """"We could not verify this is within the limit" is not "this is forbidden".

    Blocking on a blank CRM field would halt routine work every time a rep skipped a box; staying
    silent would let an unbounded commitment through with no trace that it was unchecked.
    """
    request = _request(config={"approval_threshold_amount": 5_000_000},
                       facts={"deal.value": "about sixty grand"})

    observation = ApprovalThresholdPlugin().contribute(_view(request))[0]

    assert "blocking_bp" not in observation.metrics
    assert observation.metrics["concern_bp"] == 2_000
    assert observation.reason_codes == ("approval_value_unreadable",)


def test_a_missing_deal_value_under_a_declared_threshold_is_reported_as_unverifiable():
    """Absence of the value is absence of assurance, and it must leave a trace."""
    request = _request(config={"approval_threshold_amount": 5_000_000})

    observation = ApprovalThresholdPlugin().contribute(_view(request))[0]

    assert observation.reason_codes == ("approval_value_absent",)


def test_a_malformed_approval_threshold_is_a_deployment_fault():
    """Bad tenant config must fail loudly rather than become a policy nobody can account for."""
    request = _request(config={"approval_threshold_amount": "fifty thousand"})

    with pytest.raises(ValueError, match="approval_threshold_amount"):
        ApprovalThresholdPlugin().contribute(_view(request))


# ---------------------------------------------------------------------------------------------
# ContactPermissionPlugin — whether we may speak to this counterparty at all
# ---------------------------------------------------------------------------------------------

def test_no_do_not_contact_record_produces_no_observation():
    """Most accounts carry no such record; a note on every one of them buries the few that matter."""
    assert ContactPermissionPlugin().contribute(_view(_request())) == ()


def test_an_explicit_negative_do_not_contact_flag_is_treated_as_permission():
    """A recorded "false" is evidence the question was asked and answered."""
    request = _request(facts={"contact.do_not_contact": False})

    assert ContactPermissionPlugin().contribute(_view(request)) == ()


def test_a_do_not_contact_record_is_absolute():
    """Somebody asked us to stop. No deal value makes ignoring that a trade-off worth weighing."""
    request = _request(facts={"contact.do_not_contact": True})

    observation = ContactPermissionPlugin().contribute(_view(request))[0]

    assert observation.metrics["blocking_bp"] == 10_000
    assert observation.reason_codes == ("do_not_contact_on_record",)


def test_a_string_exported_do_not_contact_flag_still_blocks():
    """CRM exports carry booleans as text; reading "true" as absent would be a silent failure."""
    request = _request(facts={"contact.do_not_contact": "TRUE"})

    assert ContactPermissionPlugin().contribute(_view(request))[0].metrics["blocking_bp"] == 10_000


def test_consent_is_only_examined_where_the_organisation_operates_an_opt_in_rule():
    """Not every tenant is under an opt-in regime; imposing one on them would block their business."""
    request = _request(facts={"contact.consent_status": "unknown"})

    assert ContactPermissionPlugin().contribute(_view(request)) == ()


def test_recorded_consent_satisfies_the_opt_in_rule():
    request = _request(config={"require_contact_consent": True},
                       facts={"contact.consent_status": "opt_in"})

    assert ContactPermissionPlugin().contribute(_view(request)) == ()


def test_withdrawn_consent_blocks_exactly_like_a_do_not_contact_record():
    """A refusal is a refusal whichever field the source system happened to write it into."""
    request = _request(config={"require_contact_consent": True},
                       facts={"contact.consent_status": "withdrawn"})

    observation = ContactPermissionPlugin().contribute(_view(request))[0]

    assert observation.metrics["blocking_bp"] == 10_000
    assert observation.reason_codes == ("contact_consent_revoked",)


def test_consent_that_is_simply_not_on_file_is_a_concern_rather_than_a_refusal():
    """Missing consent is usually a data-quality gap, and a gap is not a customer saying no."""
    request = _request(config={"require_contact_consent": True})

    observation = ContactPermissionPlugin().contribute(_view(request))[0]

    assert observation.metrics["concern_bp"] == 3_000
    assert observation.reason_codes == ("contact_consent_not_on_record",)


# ---------------------------------------------------------------------------------------------
# TimingRulePlugin — the calendar the business imposes on itself
# ---------------------------------------------------------------------------------------------

def test_an_organisation_with_no_declared_calendar_is_unconstrained_by_one():
    """No published working day means there is no window to be outside of."""
    assert TimingRulePlugin().contribute(_view(_request())) == ()


def test_midday_inside_declared_working_hours_raises_nothing():
    """Thursday noon against a 9–17 Monday-to-Friday week is the ordinary case."""
    request = _request(config={"working_hours_start_hour": 9, "working_hours_end_hour": 17})

    assert TimingRulePlugin().contribute(_view(request)) == ()


def test_acting_outside_declared_working_hours_is_a_concern_not_a_prohibition():
    """A message drafted out of hours should usually wait until morning; it is not misconduct.

    Treating the clock as a prohibition would make the system inert for two-thirds of every day.
    """
    request = _request(config={"working_hours_start_hour": 13, "working_hours_end_hour": 17})

    observation = TimingRulePlugin().contribute(_view(request))[0]

    assert observation.metrics["concern_bp"] == 3_000
    assert observation.metrics["local_hour"] == 12
    assert observation.reason_codes == ("outside_declared_working_hours",)


def test_a_day_the_organisation_does_not_work_is_outside_its_hours():
    """The working week is part of the working day; noon on a non-working Thursday still waits."""
    request = _request(config={"working_hours_start_hour": 9, "working_hours_end_hour": 17,
                               "working_days": [0, 1, 2]})

    observation = TimingRulePlugin().contribute(_view(request))[0]

    assert observation.metrics["local_weekday"] == 3
    assert observation.reason_codes == ("outside_declared_working_hours",)


def test_an_overnight_working_window_wraps_past_midnight():
    """An operations desk running 22:00–06:00 has a real working day; noon is outside it."""
    request = _request(config={"working_hours_start_hour": 22, "working_hours_end_hour": 6})

    assert TimingRulePlugin().contribute(_view(request))[0].metrics["local_hour"] == 12


def test_a_declared_blackout_date_is_a_breach():
    """Somebody wrote the date down precisely so that nothing goes out on it."""
    request = _request(config={"blackout_dates": ["2026-08-06", "2026-12-25"]})

    observation = TimingRulePlugin().contribute(_view(request))[0]

    assert observation.metrics["blocking_bp"] == 10_000
    assert observation.reason_codes == ("inside_declared_blackout",)


def test_a_blackout_is_judged_in_the_organisations_own_calendar():
    """Noon UTC is already tomorrow in Sydney, and the freeze is the business's date, not UTC's."""
    request = _request(config={"blackout_dates": ["2026-08-07"], "org_utc_offset_minutes": 720})

    assert TimingRulePlugin().contribute(_view(request))[0].reason_codes == (
        "inside_declared_blackout",)


def test_a_malformed_blackout_date_is_a_deployment_fault():
    """A freeze nobody can parse is a freeze that silently does not happen."""
    request = _request(config={"blackout_dates": ["christmas eve"]})

    with pytest.raises(ValueError, match="blackout_dates"):
        TimingRulePlugin().contribute(_view(request))


# ---------------------------------------------------------------------------------------------
# The assembled unit
# ---------------------------------------------------------------------------------------------

def test_the_unit_satisfies_the_reasoner_protocol():
    """Part 1 schedules units through one protocol; a unit that drifts off it cannot be run."""
    assert isinstance(PolicyUnit(), Reasoner)
    assert PolicyUnit().category is UnitCategory.OPTIMIZATION


def test_the_unit_never_claims_authority_over_shared_metrics():
    """confidence_bp and urgency_bp have named owners; publishing them here re-scores everything."""
    reserved = {"confidence_bp", "urgency_bp", "priority_override_bp"}

    assert reserved.isdisjoint(PolicyUnit().publishes)

    result = PolicyUnit().evaluate(_request(), {})

    assert reserved.isdisjoint(result.metrics)


def test_a_situation_no_rule_touches_reads_as_fully_compliant_and_says_so():
    """Full compliance has to be stated, not inferred from an empty result."""
    result = PolicyUnit().evaluate(_request(), {})

    assert dict(result.metrics) == {"compliance_bp": 10_000, "policy_violations": 0,
                                    "policy_concerns": 0, "rules_triggered": 0}
    assert result.matched is False
    assert "organisation_policy_clear" in result.reason_codes
    assert result.checks == ()


def test_one_breach_takes_compliance_to_zero_whatever_else_is_true():
    """Being 70% compliant with a do-not-contact record is not a softer form of complying."""
    request = _request(config={"require_contact_consent": True},
                       facts={"contact.do_not_contact": True})

    result = PolicyUnit().evaluate(request, {})

    assert result.metrics["compliance_bp"] == 0
    assert result.metrics["policy_violations"] == 1
    assert result.metrics["policy_concerns"] == 1        # consent is missing as well
    assert "organisation_policy_violated" in result.reason_codes


def test_stacked_concerns_erode_compliance_but_can_never_impersonate_a_prohibition():
    """Two soft concerns are a worse evidential position than one, and still not a breach.

    3,000bp of missing consent plus 3,000bp of out-of-hours leaves 4,000bp — above the 2,500bp
    floor that keeps the bottom of the scale reserved for rules the business actually forbids.
    """
    request = _request(config={"require_contact_consent": True,
                               "working_hours_start_hour": 13,
                               "working_hours_end_hour": 17})

    result = PolicyUnit().evaluate(request, {})

    assert result.metrics["compliance_bp"] == 4_000
    assert result.metrics["policy_violations"] == 0
    assert result.metrics["policy_concerns"] == 2
    assert "organisation_policy_concern" in result.reason_codes


def test_the_soft_floor_holds_when_concerns_would_otherwise_bottom_out():
    """However many things we cannot verify, unverified is never the same as forbidden."""
    request = _request(config={"require_contact_consent": True,
                               "missing_consent_concern_bp": 9_000,
                               "working_hours_start_hour": 13,
                               "working_hours_end_hour": 17,
                               "outside_hours_concern_bp": 9_000})

    result = PolicyUnit().evaluate(request, {})

    assert result.metrics["compliance_bp"] == 2_500
    assert result.metrics["policy_violations"] == 0


# ---------------------------------------------------------------------------------------------
# Checks — the fail-closed path, and the limits on its reach
# ---------------------------------------------------------------------------------------------

def test_a_breached_rule_eliminates_every_play_it_reaches():
    """This is the fail-closed path: a forbidden action is not a trade-off for Part 3 to weigh."""
    request = _request(facts={"contact.do_not_contact": True},
                       plays=(_play("send_nudge", read_only=False, external=True),))

    check = PolicyUnit().evaluate(request, {}).checks[0]

    assert check.stage == POLICY_STAGE
    assert check.outcome is CheckOutcome.ELIMINATE
    assert check.reason_code == "do_not_contact_on_record"
    assert check.evaluator_id == "core.policy"
    assert check.detail["rule"] == "policy.do_not_contact"


def test_a_contact_rule_leaves_internal_record_keeping_alone():
    """Compliance work does not stop during a do-not-contact; logging a note reaches nobody.

    The internal play gets no check at all rather than a PASS — this unit never asked a question
    about it, and recording an answer would imply it had.
    """
    request = _request(facts={"contact.do_not_contact": True},
                       plays=(_play("log_note", read_only=True),
                              _play("send_nudge", read_only=False, external=True)))

    checks = PolicyUnit().evaluate(request, {}).checks

    assert [item.play_id for item in checks] == ["send_nudge"]


def test_an_undeclared_side_effect_is_read_as_reaching_the_counterparty():
    """Fail closed: a play that changes something and declares nothing is assumed to be outbound."""
    request = _request(facts={"contact.do_not_contact": True},
                       plays=(_play("update_stage", read_only=False),))

    assert PolicyUnit().evaluate(request, {}).checks[0].outcome is CheckOutcome.ELIMINATE


def test_a_play_that_already_routes_through_a_human_satisfies_the_approval_threshold():
    """The threshold exists to put a person in the loop; a play that does is not in breach of it.

    Flagging it anyway would train reviewers to ignore this unit, which is the expensive failure.
    """
    request = _request(
        config={"approval_threshold_amount": 5_000_000},
        facts={"deal.value": 6_200_000},
        plays=(_play("draft_for_vp", read_only=False, external=True,
                     boundary="human_approval_required"),))

    result = PolicyUnit().evaluate(request, {})

    assert result.metrics["policy_violations"] == 1     # the org rule is still breached
    assert result.checks == ()                          # but this play is not the breach


def test_a_concern_warns_and_leaves_the_play_in_contention():
    """"We cannot show this is allowed" must not quietly do the work of "this is forbidden"."""
    request = _request(config={"require_contact_consent": True})

    check = PolicyUnit().evaluate(request, {}).checks[0]

    assert check.outcome is CheckOutcome.WARN
    assert check.outcome is not CheckOutcome.ELIMINATE
    assert check.reason_code == "contact_consent_not_on_record"


def test_checks_are_emitted_in_play_id_order():
    """Nothing downstream may depend on manifest or dict order to reproduce a hash."""
    request = _request(facts={"contact.do_not_contact": True},
                       plays=(_play("zeta_send", read_only=False, external=True),
                              _play("alpha_send", read_only=False, external=True)))

    checks = PolicyUnit().evaluate(request, {}).checks

    assert [item.play_id for item in checks] == ["alpha_send", "zeta_send"]


# ---------------------------------------------------------------------------------------------
# Determinism and one real situation, end to end
# ---------------------------------------------------------------------------------------------

def test_the_same_situation_reasons_to_the_same_bytes_twice():
    """Replay is the audit story; a unit that drifts between runs cannot be re-examined later."""
    request = _request(config={"approval_threshold_amount": 5_000_000,
                               "require_contact_consent": True,
                               "working_hours_start_hour": 13,
                               "working_hours_end_hour": 17},
                       facts={"deal.value": 6_200_000})

    first = PolicyUnit().evaluate(request, {})
    second = PolicyUnit().evaluate(request, {})

    assert first.semantic_hash == second.semantic_hash
    assert dict(first.metrics) == dict(second.metrics)


def test_the_unsigned_acme_renewal_during_the_close_period_is_blocked_with_its_reasons():
    """The real scenario this unit was built for.

    Acme's renewal is worth £62,000 against a £50,000 approval bar and carries no sign-off, and the
    finance team declared 6 August a communications blackout. Two independent organisation rules are
    breached, so compliance is zero and both outbound plays leave the contest — while ``log_note``,
    which reaches nobody, stays available so the account team can still record what happened.
    """
    request = _request(
        config={"approval_threshold_amount": 5_000_000,
                "blackout_dates": ["2026-08-06"],
                "working_hours_start_hour": 9,
                "working_hours_end_hour": 17},
        facts={"deal.value": 6_200_000, "deal.approval_status": "pending"},
        plays=(_play("send_renewal_quote", read_only=False, external=True),
               _play("log_note", read_only=True, external=False),
               _play("email_champion", read_only=False, external=True)),
    )

    result = PolicyUnit().evaluate(request, {})

    assert result.status is ResultStatus.COMPLETED
    assert dict(result.metrics) == {"compliance_bp": 0, "policy_violations": 2,
                                    "policy_concerns": 0, "rules_triggered": 2}
    assert result.matched is True
    assert set(result.reason_codes) == {"approval_threshold_exceeded",
                                        "inside_declared_blackout",
                                        "organisation_policy_violated"}
    assert {(item.play_id, item.reason_code) for item in result.checks} == {
        ("email_champion", "approval_threshold_exceeded"),
        ("email_champion", "inside_declared_blackout"),
        ("send_renewal_quote", "approval_threshold_exceeded"),
        ("send_renewal_quote", "inside_declared_blackout"),
    }
    assert all(item.outcome is CheckOutcome.ELIMINATE for item in result.checks)
    assert {finding.finding_id for finding in result.findings} == {
        "policy.approval_threshold", "policy.blackout", "policy.compliance"}
