"""Layer 5 · the Execution Object contract and the build path.

DB-free by construction: every unit under test takes its world as an argument. What is asserted
here is not "the code runs" but the four properties the layer's correctness rests on —

  * identity is the decision plus the plan, never the routing,
  * a read-only play can never produce an action that changes the outside world,
  * autonomy is granted per action and refused for the plan if any action needs a person,
  * a commitment never outlives the decision that authorised it.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.execution import (
    ALLOWED_TRANSITIONS,
    EXECUTION_VERSION,
    OPEN_STATES,
    TERMINAL_STATES,
    ActionKind,
    AudienceClass,
    ChannelClass,
    CommunicationPlan,
    EscalationAction,
    EscalationStep,
    ExecutionObject,
    ExecutionState,
    PlannedAction,
    can_transition,
)
from genios_engine.contracts.reasoning import (
    CandidateDisposition,
    DecisionCandidate,
    DecisionOutcome,
    ReasoningDecision,
)
from genios_engine.executive.assignment import StaticSeatDirectory
from genios_engine.executive.execution import build_from_decision
from genios_engine.platform.canonical import canonical_dumps, semantic_hash

NOW = datetime(2026, 8, 6, 9, 0, tzinfo=timezone.utc)
DECISION_HASH = semantic_hash({"fixture": "l5"})

DIRECTORY = StaticSeatDirectory({
    "seat_rep": {"email": "rep@acme.io", "active": True, "role": "member",
                 "manager_seat_id": "seat_mgr"},
    "seat_mgr": {"email": "mgr@acme.io", "active": True, "role": "admin"},
    "seat_gone": {"email": "gone@acme.io", "active": False, "role": "member"},
})

STEPS = ("Review the latest verified customer priority and cooling evidence.",
         "Draft a concise value-led follow-up grounded in that priority.",
         "Propose one concrete next step and leave the draft for human approval.")


def make_decision(*, read_only: bool = True, steps: tuple[str, ...] = STEPS,
                  utility_bp: int = 8_800, confidence_bp: int = 7_400,
                  outcome: DecisionOutcome = DecisionOutcome.DECISION,
                  window_days: int = 14, expires_in_days: int = 30,
                  tags: tuple[str, ...] = ("draft", "human_approval"),
                  metadata: dict | None = None) -> ReasoningDecision:
    if outcome is not DecisionOutcome.DECISION:
        return ReasoningDecision(
            outcome=outcome, capability_id="deal_cooling", capability_version="1.0.0",
            context_snapshot_id="ctx_1", candidates=(), selected_candidate_id=None,
            confidence_bp=confidence_bp, uncertainty=(),
            do_nothing_consequence="Nothing changes.",
            expires_at=NOW + timedelta(days=expires_in_days))
    candidate = DecisionCandidate(
        play_id="restore_momentum", play_version="1.0.0",
        disposition=CandidateDisposition.ELIGIBLE, utility_bp=utility_bp,
        confidence_bp=confidence_bp,
        score_components={"impact": 8_000, "urgency": 8_600, "success": 5_500},
        rank_position=1, evidence_ids=("ev_a", "ev_b"),
        parameters={"label": "Restore momentum on the Acme deal", "steps": steps,
                    "read_only": read_only, "tags": tags,
                    "metadata": metadata if metadata is not None else {
                        "artifact_kind": "draft_reengagement_email",
                        "execution_boundary": "human_approval_required",
                        "external_recipient_required": True},
                    "success_events": ("prospect_reply", "meeting_booked"),
                    "window_days": window_days})
    return ReasoningDecision(
        outcome=DecisionOutcome.DECISION, capability_id="deal_cooling",
        capability_version="1.0.0", context_snapshot_id="ctx_1", candidates=(candidate,),
        selected_candidate_id=candidate.candidate_id, confidence_bp=confidence_bp,
        uncertainty=("deal value unknown",),
        do_nothing_consequence="The Acme deal slips past quarter end.",
        expires_at=NOW + timedelta(days=expires_in_days), outcome_window_days=window_days)


def build(*, facts: dict | None = None, channels: set | None = None, eval_time=NOW,
          decision: ReasoningDecision | None = None, cfg: dict | None = None,
          decision_hash: str = DECISION_HASH):
    # `decision_hash` defaults to a fixture rather than to the decision's own hash so a test can
    # vary the *plan* while holding the *decision* fixed — which is the only way to isolate the
    # claim that identity covers both. Callers that need two genuinely distinct commitments
    # (the sweep tests) pass their own.
    return build_from_decision(
        decision or make_decision(), org_id="org_1", reasoning_run_id="run_1",
        config_snapshot_id="cfg_1", decision_hash=decision_hash, eval_time=eval_time,
        directory=DIRECTORY,
        facts=facts if facts is not None else {"deal.owner": {"value": "rep@acme.io"}},
        available_channels=channels if channels is not None else {"slack", "in_app"},
        subject_ref="deal_9", subject_type="deal", subject_label="Acme", cfg=cfg)


# --- identity ------------------------------------------------------------------------------

def test_identity_ignores_routing_but_audit_hash_does_not():
    """Reassigning a commitment must not mint a second one for the ladder to chase separately —
    while the audit hash must still record that the routing changed."""
    original = build().require()
    moved = dataclasses.replace(
        original,
        communication=CommunicationPlan(
            audience=AudienceClass.MANAGER, channel_class=ChannelClass.EMAIL,
            channel_id="email", interrupt=False, tone="formal", format_kind="card",
            reason_code="manual_reassign", assignee="seat_mgr"))
    assert moved.execution_id == original.execution_id
    assert moved.plan_hash == original.plan_hash
    assert moved.semantic_hash != original.semantic_hash


def test_identity_is_stable_across_rebuilds():
    """The sweep runs on a timer. Two runs over the same decision at the same instant must
    produce one commitment, or the unique index is doing work the artifact should have done."""
    assert build().require().execution_id == build().require().execution_id


def test_a_different_plan_is_a_different_commitment():
    shorter = make_decision(steps=STEPS[:2])
    assert build().require().execution_id != build(decision=shorter).require().execution_id


def test_round_trips_through_storage_byte_identically():
    import json
    original = build().require()
    restored = ExecutionObject.from_semantic_dict(
        json.loads(canonical_dumps(original.to_semantic_dict())))
    assert restored.semantic_hash == original.semantic_hash
    assert restored.execution_id == original.execution_id
    assert restored.describe() == original.describe()


# --- the read-only boundary ----------------------------------------------------------------

def test_read_only_play_never_produces_an_external_effect():
    """The single invariant that cannot be allowed to fail: a read-only play may not send,
    schedule or write to a system of record, whatever its step text says."""
    loud = make_decision(steps=("Send the renewal notice to the customer.",
                                "Log the outcome in the CRM.",
                                "Book the follow-up call."))
    execution = build(decision=loud).require()
    assert execution.read_only
    assert all(not action.external_effect for action in execution.actions)
    assert all(action.requires_approval for action in execution.actions)


def test_read_only_downgrade_is_recorded_not_hidden():
    loud = make_decision(steps=("Send the renewal notice to the customer.",))
    action = build(decision=loud).require().actions[0]
    assert action.kind is ActionKind.DRAFT
    assert action.metadata["declared_kind"] == "send"
    assert action.metadata["read_only_downgrade"] is True


def test_contract_refuses_a_read_only_action_with_an_external_kind():
    with pytest.raises(ValueError, match="read-only"):
        PlannedAction(ordinal=1, stage=0, action_id="a1", label="Send it",
                      kind=ActionKind.SEND, read_only=True)


# --- autonomy ------------------------------------------------------------------------------

def test_autonomy_is_refused_when_any_action_needs_a_person():
    execution = build().require()
    assert execution.autonomy_allowed is False
    with pytest.raises(ValueError, match="require a human"):
        dataclasses.replace(execution, autonomy_allowed=True)


def test_human_gate_is_forced_when_the_pack_forgets_to_declare_a_boundary():
    """Three independent ways to fail closed; a pack author omitting the key still gets a gate."""
    silent = make_decision(tags=(), metadata={"artifact_kind": "monitor_only",
                                              "external_recipient_required": False})
    assert build(decision=silent).require().approval_gates


# --- the clock -----------------------------------------------------------------------------

def test_a_commitment_never_outlives_its_decision():
    execution = build(decision=make_decision(window_days=30, expires_in_days=7)).require()
    assert execution.deadline_at <= execution.expires_at
    assert all(step.fires_at <= execution.expires_at for step in execution.escalation)


def test_expired_decision_is_refused_not_clamped():
    result = build(decision=make_decision(expires_in_days=30),
                   eval_time=NOW + timedelta(days=31))
    assert not result.built
    assert result.reason_code == "decision_expired"


def test_action_deadlines_are_ordered_and_bounded():
    execution = build().require()
    deadlines = [action.deadline_at for action in execution.actions]
    assert deadlines == sorted(deadlines)
    assert deadlines[-1] == execution.deadline_at
    assert all(NOW <= item <= execution.expires_at for item in deadlines)


# --- non-decisions -------------------------------------------------------------------------

@pytest.mark.parametrize("outcome,code", [
    (DecisionOutcome.NO_ACTION, "outcome_no_action"),
    (DecisionOutcome.DEFER, "outcome_defer"),
    (DecisionOutcome.INSUFFICIENT_CONTEXT, "outcome_insufficient_context"),
    (DecisionOutcome.FAILED, "outcome_failed"),
])
def test_non_decisions_never_become_commitments(outcome, code):
    """`no_action` means the reasoner looked and concluded nothing should happen. Turning that
    into a task would be the system inventing work for someone."""
    result = build(decision=make_decision(outcome=outcome))
    assert not result.built and result.reason_code == code


def test_a_play_with_no_steps_is_refused_not_padded():
    result = build(decision=make_decision(steps=()))
    assert not result.built and result.reason_code == "no_steps"


# --- the plan shape ------------------------------------------------------------------------

def test_dependencies_only_point_backwards_and_waves_are_independent():
    execution = build().require()
    seen: set[str] = set()
    for action in execution.actions:
        assert all(dep in seen for dep in action.depends_on)
        seen.add(action.action_id)
    for wave in execution.stages:
        ids = {action.action_id for action in wave}
        assert all(not (ids & set(action.depends_on)) for action in wave)


def test_leading_preparation_steps_share_a_wave():
    """Gathering the history and looking up a stakeholder do not depend on each other; making
    them sequential would push every downstream deadline out for no reason."""
    parallel = make_decision(steps=("Identify the verified stakeholder on the account.",
                                    "Summarize the last agreed next step.",
                                    "Draft the outreach note."))
    execution = build(decision=parallel).require()
    assert [a.stage for a in execution.actions] == [0, 0, 1]


def test_success_evidence_attaches_only_to_the_final_action():
    execution = build().require()
    assert execution.actions[-1].completion_events
    assert all(not action.completion_events for action in execution.actions[:-1])


# --- the state machine ---------------------------------------------------------------------

def test_terminal_states_only_lead_to_archived():
    for state in (ExecutionState.COMPLETED, ExecutionState.CANCELLED):
        assert ALLOWED_TRANSITIONS[state] == (ExecutionState.ARCHIVED,)
    assert ALLOWED_TRANSITIONS[ExecutionState.ARCHIVED] == ()


def test_expired_work_can_be_picked_back_up():
    """A human who resumes lapsed work has demonstrably not finished with it; refusing them
    would just make them create a duplicate by hand."""
    assert can_transition(ExecutionState.EXPIRED, ExecutionState.RUNNING)


def test_open_and_terminal_states_partition_the_machine():
    assert not (OPEN_STATES & TERMINAL_STATES)
    assert OPEN_STATES | TERMINAL_STATES | {ExecutionState.CREATED} == set(ExecutionState)


def test_escalation_ladder_is_strictly_increasing():
    execution = build().require()
    offsets = [step.day_offset for step in execution.escalation]
    assert offsets == sorted(set(offsets))
    with pytest.raises(ValueError, match="strictly increasing"):
        dataclasses.replace(execution, escalation=tuple(reversed(execution.escalation)))


def test_version_is_stamped():
    assert build().require().version == EXECUTION_VERSION


def test_escalation_step_rejects_a_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        EscalationStep(day_offset=1, action=EscalationAction.NOTIFY,
                       audience=AudienceClass.OWNER, interrupt=False,
                       fires_at=datetime(2026, 8, 7, 9, 0), reason_code="ladder_day1")
