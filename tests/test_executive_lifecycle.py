"""Layer 5 · the operational half — guard, reminder, monitor, escalation, tracking, collection.

The scenarios here are the ones that decide whether people keep the product. A reminder about
something that already happened, an escalation to a person who left, a nudge on a closed-lost
deal: each is individually survivable and collectively fatal, so each gets a named test.

Everything is DB-free. The guard takes a ``ValidationInput`` rather than a connection precisely
so these branches are reachable without Postgres — and so a suppression decision can be replayed
years later from the inputs that produced it.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.contracts.execution import (
    AudienceClass,
    ChannelClass,
    ExecutionState,
)
from genios_engine.executive.assignment import (
    StaticSeatDirectory,
    resolve_escalation_target,
    resolve_owner,
)
from genios_engine.executive.collect import (
    LABEL_CANCELLED_BY_HUMAN,
    LABEL_CANCELLED_BY_WORLD,
    LABEL_COMPLETED_UNPROVEN,
    LABEL_EXPIRED_IN_PROGRESS,
    LABEL_EXPIRED_UNTOUCHED,
    LABEL_SUCCEEDED,
    collect_outcome,
)
from genios_engine.executive.communication import band_of, plan_communication, projected_score
from genios_engine.executive.escalation import EscalationConfigError, build_ladder, due_rungs
from genios_engine.executive.execution import build_from_decision
from genios_engine.executive.execution_guard import (
    GuardAction,
    ValidationInput,
    validate,
    validate_for_delivery,
)
from genios_engine.executive.lifecycle import LifecycleError, next_state, transition
from genios_engine.executive.monitor import observe
from genios_engine.executive.reminder import ReminderState, decide_reminder, elapsed_bp

from genios_engine.platform.canonical import semantic_hash

from tests.test_executive_execution import DIRECTORY, NOW, build, make_decision


def live(**overrides) -> ValidationInput:
    base = {"now": NOW + timedelta(days=1), "state": ExecutionState.PENDING}
    return ValidationInput(**{**base, **overrides})


# --- the guard: the reason the product is trusted ------------------------------------------

def test_the_world_doing_it_first_completes_rather_than_reminds():
    """The failure that kills a reminder engine: nudging somebody about work already done."""
    execution = build().require()
    verdict = validate(execution, live(
        observed_events={"prospect_reply": NOW + timedelta(hours=6)}))
    assert verdict.action is GuardAction.COMPLETE
    assert verdict.reason_code == "outcome_observed"
    assert verdict.terminal_state is ExecutionState.COMPLETED


def test_an_event_that_predates_the_commitment_proves_nothing():
    """The event that *caused* a recommendation is often the same kind as the event that would
    prove it resolved. Counting history would mark every commitment complete on day zero."""
    execution = build().require()
    verdict = validate(execution, live(
        observed_events={"prospect_reply": NOW - timedelta(days=2)}))
    assert verdict.action is GuardAction.PROCEED


def test_revoked_authority_outranks_everything_else():
    execution = build().require()
    verdict = validate(execution, live(authority_valid=False, subject_status="closed_lost",
                                       dismissed=True))
    assert verdict.reason_code == "authority_revoked"
    assert verdict.terminal_state is ExecutionState.CANCELLED


def test_a_closed_deal_stops_the_chasing():
    execution = build().require()
    assert validate(execution, live(subject_status="closed_lost")).reason_code == "subject_closed"


def test_a_departed_owner_reroutes_rather_than_cancels():
    """When a rep leaves, their commitments are exactly what must not disappear with them."""
    execution = build().require()
    verdict = validate(execution, live(owner_active=False))
    assert verdict.action is GuardAction.REROUTE
    assert verdict.terminal_state is None


def test_a_stale_owner_before_first_delivery_is_re_planned_not_rerouted():
    execution = build().require()
    verdict = validate_for_delivery(
        execution, live(state=ExecutionState.CREATED, owner_active=False))
    assert verdict.action is GuardAction.SUPPRESS
    assert verdict.reason_code == "owner_inactive_at_build"


def test_a_blocked_commitment_is_not_nudged_but_is_not_closed():
    execution = build().require()
    verdict = validate(execution, live(state=ExecutionState.BLOCKED))
    assert verdict.action is GuardAction.SUPPRESS and verdict.terminal_state is None


def test_deadline_without_evidence_expires_it_rather_than_cancelling_it():
    """`expired` and `cancelled` mean different things to whatever learns from this: only the
    first is evidence the window was too short."""
    execution = build().require()
    verdict = validate(execution, live(now=execution.deadline_at + timedelta(hours=1)))
    assert verdict.terminal_state is ExecutionState.EXPIRED
    assert verdict.reason_code == "deadline_passed"


def test_guard_defaults_to_refusing_not_to_proceeding():
    execution = build().require()
    for bad in (live(dismissed=True), live(subject_missing=True),
                live(superseded_by="exec_newer"), live(authority_valid=False)):
        assert validate(execution, bad).action is not GuardAction.PROCEED


# --- reminders: business relevance, not a calendar ------------------------------------------

def test_nothing_is_due_on_the_first_quiet_hours():
    execution = build().require()
    decision = decide_reminder(execution, state=ExecutionState.PENDING,
                               history=ReminderState(), now=NOW + timedelta(hours=2))
    assert not decision.should_remind and decision.reason_code == "nothing_due"
    assert decision.next_check_at > NOW


def test_a_promised_ladder_rung_is_the_strongest_trigger():
    execution = build().require()
    first_rung = execution.escalation[0]
    decision = decide_reminder(execution, state=ExecutionState.PENDING, history=ReminderState(),
                               now=first_rung.fires_at + timedelta(minutes=1))
    assert decision.should_remind and decision.escalating
    assert decision.escalation_day == first_rung.day_offset


def test_a_fired_rung_does_not_fire_twice():
    execution = build().require()
    first_rung = execution.escalation[0]
    history = ReminderState(fired_escalation_days=frozenset({first_rung.day_offset}))
    assert not due_rungs(execution, now=first_rung.fires_at + timedelta(minutes=1),
                         fired_days=history.fired_escalation_days)


def test_cooldown_prevents_two_reminders_in_one_day():
    execution = build().require()
    at = execution.escalation[0].fires_at + timedelta(minutes=1)
    decision = decide_reminder(execution, state=ExecutionState.PENDING,
                               history=ReminderState(reminder_count=1, last_reminded_at=at),
                               now=at + timedelta(hours=2))
    assert not decision.should_remind and decision.reason_code == "cooldown"


def test_fatigue_hands_over_to_escalation_rather_than_tapering():
    """A fifth identical nudge does not produce action; it produces a filter rule."""
    execution = build().require()
    decision = decide_reminder(
        execution, state=ExecutionState.PENDING,
        history=ReminderState(reminder_count=4,
                              last_reminded_at=NOW - timedelta(days=2)),
        now=execution.deadline_at - timedelta(hours=1))
    assert not decision.should_remind and decision.reason_code == "fatigue_cap"


def test_unowned_work_is_nudged_when_somebody_mans_the_queue():
    """Nobody OWNS it and somebody still has to do something about it.

    This is the case that describes every commitment in production. `deal.owner`,
    `relationship.owner` and `commitment.actor` have no producer anywhere in the engine, so
    ownership resolution falls to rule 3 for 100% of commitments, of every tenant, forever
    (measured 2026-08-30: 203/203 rows, `routing_rule='rule3_admin_queue'`). While remindability
    was derived from ownership that made the entire Reminder Unit unreachable: 170 commitments
    sat `pending` for a week and `execution_events` held not one `execution.reminded` row.

    The commitment is still UNOWNED — `assignee` stays None and the audience stays the admin
    queue, so nothing pretends somebody promised this. It is simply also REACHABLE, because an
    active admin is a real person, and that is what earns the right to nudge.
    """
    execution = build(facts={}).require()
    assert execution.communication.audience is AudienceClass.ADMIN_QUEUE
    assert execution.communication.assignee is None          # nobody owns it, and we say so
    assert execution.communication.queue_seat == "seat_mgr"   # somebody can still be reached
    assert execution.remindable and execution.escalation

    decision = decide_reminder(execution, state=ExecutionState.PENDING, history=ReminderState(),
                               now=NOW + timedelta(days=5))
    assert decision.should_remind and decision.reason_code != "not_remindable"


def test_a_commitment_nobody_at_all_can_receive_is_tracked_but_never_nudged():
    """The invariant the test above must not be allowed to erase.

    An org with no active admin has genuinely nobody on the other end. The commitment is still
    built, still stored, still counted and still expires with an outcome record — it is only
    never spoken about, because a nudge with no recipient is a message sent into an empty room.
    """
    nobody = build_from_decision(
        make_decision(), org_id="org_1", reasoning_run_id="run_1", config_snapshot_id="cfg_1",
        decision_hash=semantic_hash({"fixture": "nobody"}), eval_time=NOW, directory=StaticSeatDirectory({}),
        facts={}, available_channels={"slack", "in_app"}, subject_ref="deal_9").require()
    assert nobody.communication.reason_code == "unrouted_rule3_unrouted"
    assert nobody.remindable is False and nobody.escalation == ()

    decision = decide_reminder(nobody, state=ExecutionState.PENDING, history=ReminderState(),
                               now=NOW + timedelta(days=5))
    assert not decision.should_remind and decision.reason_code == "not_remindable"


def test_the_deadline_warning_scales_with_the_window_not_the_clock():
    """A two-day commitment and a fortnight-long one are not both urgent two days out."""
    short = build(decision=make_decision(window_days=2)).require()
    long = build(decision=make_decision(window_days=14)).require()
    at = NOW + timedelta(days=2, hours=-1)
    assert elapsed_bp(short, at) > elapsed_bp(long, at)
    assert elapsed_bp(short, at) >= 7_500 > elapsed_bp(long, at)


def test_elapsed_fraction_is_clamped_and_integral():
    execution = build().require()
    assert elapsed_bp(execution, NOW - timedelta(days=5)) == 0
    assert elapsed_bp(execution, execution.deadline_at + timedelta(days=5)) == 10_000
    assert isinstance(elapsed_bp(execution, NOW + timedelta(days=3)), int)


# --- monitoring -----------------------------------------------------------------------------

def test_progress_is_counted_from_ticked_steps():
    execution = build().require()
    report = observe(execution, now=NOW + timedelta(hours=4),
                     action_completions={"a1": NOW + timedelta(hours=1)})
    assert report.progress_bp == 10_000 // 3
    assert report.current_stage == execution.actions[1].stage


def test_all_steps_done_with_no_evidence_is_its_own_state():
    """A play people are happy to finish and that never produces its outcome is the most
    expensive failure mode there is; merging it into 'succeeded' hides it permanently."""
    execution = build().require()
    completions = {action.action_id: NOW + timedelta(hours=1) for action in execution.actions}
    report = observe(execution, now=NOW + timedelta(hours=4), action_completions=completions)
    assert report.steps_complete and report.done_but_unproven
    assert not report.outcome_observed


def test_observed_evidence_beats_ticked_boxes():
    execution = build().require()
    report = observe(execution, now=NOW + timedelta(days=1),
                     observed_events={"meeting_booked": NOW + timedelta(hours=8)})
    assert report.outcome_observed and report.progress_bp == 10_000


def test_a_stall_is_proportional_to_the_window():
    execution = build().require()
    fresh = observe(execution, now=NOW + timedelta(hours=6))
    stale = observe(execution, now=NOW + timedelta(days=9))
    assert not fresh.stalled and stale.stalled


# --- escalation -----------------------------------------------------------------------------

def test_urgency_compresses_the_ladder_without_changing_its_shape():
    standard = build_ladder(eval_time=NOW, expires_at=NOW + timedelta(days=60), band="standard")
    critical = build_ladder(eval_time=NOW, expires_at=NOW + timedelta(days=60), band="critical")
    assert [step.day_offset for step in standard] == [1, 3, 7, 14]
    assert [step.day_offset for step in critical] == [1, 2, 4, 7]
    assert [step.action for step in critical] == [step.action for step in standard]


def test_the_ladder_stops_at_the_decision_expiry():
    ladder = build_ladder(eval_time=NOW, expires_at=NOW + timedelta(days=5), band="standard")
    assert [step.day_offset for step in ladder] == [1, 3]


def test_a_ladder_collision_keeps_the_stronger_rung():
    tight = {"ladder": [{"day": 1, "action": "notify", "audience": "owner", "interrupt": False},
                        {"day": 1, "action": "escalate", "audience": "manager",
                         "interrupt": True}]}
    ladder = build_ladder(eval_time=NOW, expires_at=NOW + timedelta(days=30), band="standard",
                          cfg=tight)
    assert len(ladder) == 1 and ladder[0].action.value == "escalate"


def test_a_malformed_ladder_is_rejected_not_silently_defaulted():
    """An org that believes it changed its escalation policy and did not would only find out on
    the day the policy mattered."""
    for bad in ({"ladder": [{"day": 1, "action": "shout", "audience": "owner"}]},
                {"ladder": [{"day": -1, "action": "notify", "audience": "owner"}]},
                {"ladder": [{"day": 1, "action": "notify", "audience": "nobody"}]}):
        with pytest.raises(EscalationConfigError):
            build_ladder(eval_time=NOW, expires_at=NOW + timedelta(days=30), band="standard",
                         cfg=bad)


# --- ownership and channel -------------------------------------------------------------------

def test_ownership_rules_are_ordered_and_named():
    assert resolve_owner(facts={"deal.owner": {"value": "rep@acme.io"}}, attrs={},
                         directory=DIRECTORY).reason_code == "rule1_owner"
    assert resolve_owner(facts={"commitment.actor": {"value": "rep@acme.io"}}, attrs={},
                         directory=DIRECTORY).reason_code == "rule2_actor"
    # Nobody owns it, so it is not ROUTED — but an org with an active admin has somewhere to
    # show it. The reason code distinguishes the two, because "no owner" and "no admin either"
    # are different problems and merging them hid the second behind the first.
    unowned = resolve_owner(facts={}, attrs={}, directory=DIRECTORY)
    assert unowned.reason_code == "rule3_admin_queue"
    assert unowned.routed is False and unowned.seat_id is None
    assert unowned.recipient is not None


def test_an_off_seat_owner_falls_through_rather_than_being_force_matched():
    """Pushing to a dead seat looks identical to delivering successfully — the worst possible
    failure for a commitment."""
    assignment = resolve_owner(facts={"deal.owner": {"value": "gone@acme.io"}}, attrs={},
                               directory=DIRECTORY)
    assert not assignment.routed and assignment.audience is AudienceClass.ADMIN_QUEUE


def test_escalation_degrades_explicitly_at_every_step():
    assert resolve_escalation_target(audience=AudienceClass.MANAGER, owner_seat="seat_rep",
                                     directory=DIRECTORY).seat_id == "seat_mgr"
    flat = StaticSeatDirectory({"seat_a": {"active": True, "role": "admin"}})
    assert resolve_escalation_target(audience=AudienceClass.MANAGER, owner_seat="seat_x",
                                     directory=flat).reason_code == "admin_fallback"
    empty = StaticSeatDirectory({})
    fallback = resolve_escalation_target(audience=AudienceClass.EXECUTIVE, owner_seat="seat_x",
                                         directory=empty)
    assert fallback.reason_code == "escalation_target_unavailable"


def test_interruption_requires_both_a_high_band_and_real_confidence():
    """A 92-score conclusion the reasoner is 40% sure of is a hypothesis, and hypotheses do not
    get to buzz someone's phone."""
    execution = build().require()
    assert execution.communication.interrupt

    unsure = build(decision=make_decision(confidence_bp=3_000)).require()
    assert not unsure.communication.interrupt
    assert unsure.communication.reason_code.endswith("low_confidence")


def test_routine_work_waits_for_the_digest():
    routine = build(decision=make_decision(utility_bp=5_000)).require()
    assert routine.communication.channel_class is ChannelClass.DIGEST
    assert not routine.communication.interrupt


def test_an_org_with_no_channels_still_gets_a_tracked_commitment():
    quiet = build(channels=set()).require()
    assert quiet.communication.channel_class is ChannelClass.IN_APP
    assert quiet.communication.reason_code == "no_channel_registered"
    assert quiet.remindable


def test_score_projection_matches_the_authority_sql_rounding_law():
    """Half-up, integer, identical to AUTHORITATIVE_SCORE_SQL. A second rounding rule here would
    make a card Postgres considers authoritative fall one point short of a band in Python."""
    assert projected_score(8_849) == 88 and projected_score(8_850) == 89
    assert band_of(8_500) == "critical" and band_of(8_449) == "high"
    # The band boundary sits where the projection rounds up to 70, not at a round 7000 bp.
    assert band_of(6_950) == "high" and band_of(6_949) == "standard"


def test_an_unrouted_commitment_cannot_be_planned_with_an_assignee():
    from genios_engine.executive.assignment import Assignment
    from genios_engine.executive.interpret import ExecutionType
    execution = build().require()
    plan = plan_communication(
        _context_of(execution),
        Assignment(None, AudienceClass.ADMIN_QUEUE, "rule3_unrouted"),
        available_channels={"slack"})
    assert plan.assignee is None and plan.audience is AudienceClass.ADMIN_QUEUE
    assert ExecutionType.TASK  # the enum is the vocabulary this plan was classified against


def _context_of(execution):
    """Rebuild the interpreter's view of a commitment for direct unit calls."""
    from genios_engine.executive.interpret import ExecutionContext, ExecutionType
    metadata = dict(execution.metadata)
    return ExecutionContext(
        org_id=execution.org_id, goal=execution.goal,
        steps=tuple(action.label for action in execution.actions),
        execution_type=ExecutionType(metadata["execution_type"]),
        capability_id=execution.capability_id,
        capability_version=execution.capability_version,
        play_id=metadata["play_id"], play_version=metadata["play_version"],
        decision_hash=execution.decision_hash, candidate_id=execution.candidate_id,
        context_snapshot_id=execution.context_snapshot_id,
        reasoning_run_id=execution.reasoning_run_id,
        config_snapshot_id=execution.config_snapshot_id, expires_at=execution.expires_at,
        do_nothing_consequence=execution.do_nothing_consequence,
        priority_bp=execution.priority_bp, confidence_bp=execution.confidence_bp,
        urgency_bp=execution.priority_bp, window_days=7, read_only=execution.read_only,
        requires_human=True, external_recipient_required=False)


# --- the state machine in motion ---------------------------------------------------------

def test_an_illegal_move_raises_rather_than_landing():
    with pytest.raises(LifecycleError, match="terminal"):
        transition(ExecutionState.ARCHIVED, ExecutionState.RUNNING, reason_code="x",
                   actor="system", at=NOW)


def test_a_no_op_move_is_refused():
    with pytest.raises(LifecycleError):
        transition(ExecutionState.PENDING, ExecutionState.PENDING, reason_code="x",
                   actor="system", at=NOW)


def test_the_sweep_recognises_work_in_flight_but_never_finishes_it_for_you():
    execution = build().require()
    verdict = validate(execution, live())
    started = observe(execution, now=NOW + timedelta(hours=4),
                      action_completions={"a1": NOW + timedelta(hours=1)})
    assert next_state(ExecutionState.PENDING, verdict, started) is ExecutionState.RUNNING

    completions = {action.action_id: NOW + timedelta(hours=1) for action in execution.actions}
    done = observe(execution, now=NOW + timedelta(hours=4), action_completions=completions)
    assert next_state(ExecutionState.RUNNING, verdict, done) is ExecutionState.WAITING
    assert next_state(ExecutionState.WAITING, verdict, done) is None


def test_a_terminal_verdict_moves_the_commitment_even_from_blocked():
    execution = build().require()
    verdict = validate(execution, live(state=ExecutionState.BLOCKED,
                                       observed_events={"prospect_reply": NOW + timedelta(1)}))
    assert next_state(ExecutionState.BLOCKED, verdict) is ExecutionState.COMPLETED


# --- what layer 7 gets ----------------------------------------------------------------------

@pytest.mark.parametrize("state,reason,events,completions,label", [
    (ExecutionState.COMPLETED, "outcome_observed", {"prospect_reply": 1}, 3, LABEL_SUCCEEDED),
    (ExecutionState.COMPLETED, "outcome_observed", {}, 3, LABEL_COMPLETED_UNPROVEN),
    (ExecutionState.EXPIRED, "deadline_passed", {}, 0, LABEL_EXPIRED_UNTOUCHED),
    (ExecutionState.EXPIRED, "deadline_passed", {}, 1, LABEL_EXPIRED_IN_PROGRESS),
    (ExecutionState.CANCELLED, "human_dismissed", {}, 0, LABEL_CANCELLED_BY_HUMAN),
    (ExecutionState.CANCELLED, "subject_closed", {}, 0, LABEL_CANCELLED_BY_WORLD),
])
def test_endings_are_labelled_by_who_or_what_ended_them(state, reason, events, completions,
                                                        label):
    execution = build().require()
    at = NOW + timedelta(days=2)
    report = observe(
        execution, now=at,
        action_completions={action.action_id: NOW + timedelta(hours=1)
                            for action in execution.actions[:completions]},
        observed_events={kind: NOW + timedelta(days=days) for kind, days in events.items()})
    outcome = collect_outcome(execution, terminal_state=state, reason_code=reason, closed_at=at,
                              report=report, reminders_sent=2, escalations_fired=1)
    assert outcome.label == label
    assert outcome.positive is (label == LABEL_SUCCEEDED)
    # The cost of the recommendation travels with its result: a play that succeeds once per four
    # reminders is not obviously better than one that fails quietly.
    assert outcome.reminders_sent == 2 and outcome.escalations_fired == 1


def test_an_outcome_cannot_close_before_it_was_created():
    execution = build().require()
    report = observe(execution, now=NOW)
    with pytest.raises(ValueError, match="cannot close before"):
        collect_outcome(execution, terminal_state=ExecutionState.EXPIRED,
                        reason_code="deadline_passed", closed_at=NOW - timedelta(days=1),
                        report=report)


def test_the_outcome_record_hashes_deterministically():
    execution = build().require()
    report = observe(execution, now=NOW + timedelta(days=1))
    args = dict(terminal_state=ExecutionState.EXPIRED, reason_code="deadline_passed",
                closed_at=NOW + timedelta(days=1), report=report)
    assert (collect_outcome(execution, **args).semantic_hash
            == collect_outcome(execution, **args).semantic_hash)
