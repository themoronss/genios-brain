"""S3.F3.2 · Rule 11 — activity is not outcome. The tail of the walk, enforced.

    pytest tests/executive/test_activity_is_not_outcome.py -q

⛔ WHAT `M12.C2.U04` ASKED FOR AND WHAT THIS IS INSTEAD.

The unit said: *"one situation walks signal → card → approval → execution → verified outcome, and the
walk is a test, not a demo."* `tests/test_e2e_all_layers.py` already walks to `run_executive` and stops.

I planned to extend it. Measuring first changed the answer twice:

  1. **The rule is already enforced, in two places**, and neither had a test naming it as that rule —
     `lifecycle.next_state` refuses to promote to COMPLETED, and `collect.classify_outcome` refuses to
     label an unproven completion `succeeded`.
  2. ⛔ **The existing walk is `pg`-gated**, so an assertion added there is skipped in every run without
     `GENIOS_TEST_DATABASE_URL`. My own plan listed that as unsound verify #3. Putting the tail behind
     the same gate would have been writing a test that mostly does not run.

So the tail is pinned here, pure, running everywhere. The `pg` walk keeps its job — proving the seams
line up on real persisted output — and this proves the rule.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.execution import ExecutionState
from genios_engine.executive.collect import (LABEL_COMPLETED_UNPROVEN, LABEL_EXPIRED_IN_PROGRESS,
                                             LABEL_EXPIRED_UNTOUCHED, LABEL_NEUTRAL, LABEL_POSITIVE,
                                             LABEL_SUCCEEDED, classify_outcome)
from genios_engine.executive.execution_guard import GuardAction, GuardVerdict
from genios_engine.executive.lifecycle import next_state
from genios_engine.executive.monitor import ProgressReport

pytestmark = pytest.mark.unit


def _report(progress_bp: int, outcome_kind: str | None = None) -> ProgressReport:
    return ProgressReport(completed_action_ids=(), current_stage=0, progress_bp=progress_bp,
                          stalled=False, last_progress_at=None, outcome_kind=outcome_kind,
                          outcome_observed_at=None, detail="")


_PROCEED = GuardVerdict(action=GuardAction.PROCEED, reason_code="ok", detail="")


# =================================================================================================
# 1 · ⛔ THE RULE: a sweep may recognise work, never declare it finished
# =================================================================================================
def test_every_step_ticked_with_no_evidence_goes_to_WAITING_not_COMPLETED():
    """⛔ THE ASSERTION THAT CARRIES RULE 11. `lifecycle.next_state`'s own comment: *"a sweep may
    recognise work in flight, it may never decide on someone's behalf that they have finished."*"""
    moved = next_state(ExecutionState.RUNNING, _PROCEED, _report(10_000))
    assert moved is ExecutionState.WAITING
    assert moved is not ExecutionState.COMPLETED


def test_no_progress_report_can_ever_promote_to_COMPLETED():
    """⛔ Swept across the whole progress range and both evidence states. COMPLETED must be reachable
    only from a guard verdict — never from a sweep reading a progress number."""
    for bp in (0, 1, 5_000, 9_999, 10_000):
        for kind in (None, "signed_document", "reply_received"):
            for state in (ExecutionState.PENDING, ExecutionState.RUNNING, ExecutionState.WAITING):
                moved = next_state(state, _PROCEED, _report(bp, kind))
                assert moved is not ExecutionState.COMPLETED, (state, bp, kind)


def test_some_progress_promotes_to_RUNNING():
    """A sweep MAY recognise work in flight — that half is allowed."""
    assert next_state(ExecutionState.PENDING, _PROCEED, _report(1)) is ExecutionState.RUNNING


def test_no_progress_moves_nothing():
    assert next_state(ExecutionState.PENDING, _PROCEED, _report(0)) is None


def test_a_terminal_verdict_leads_and_progress_gets_no_say():
    """⛔ *"The guard's verdict leads, because it is the unit with the authority to end things."* A
    progress report must not be able to override an ending."""
    for action in GuardAction:
        verdict = GuardVerdict(action=action, reason_code="r", detail="")
        if verdict.terminal_state is None:
            continue
        moved = next_state(ExecutionState.RUNNING, verdict, _report(10_000, "signed_document"))
        assert moved in (verdict.terminal_state, None)


def test_without_a_proceed_verdict_and_a_report_nothing_moves():
    blocked = GuardVerdict(action=GuardAction.PROCEED, reason_code="ok", detail="")
    assert next_state(ExecutionState.RUNNING, blocked, None) is None


# =================================================================================================
# 2 · ⛔ and a completion with no evidence is never called a success
# =================================================================================================
def test_completed_without_evidence_is_labelled_unproven_not_succeeded():
    """⛔ THE SECOND ENFORCEMENT POINT. Even once something reaches COMPLETED, the label distinguishes
    *"the success evidence landed"* from *"the steps were ticked"*."""
    label = classify_outcome(terminal_state=ExecutionState.COMPLETED, reason_code="done",
                             outcome_kind=None, progress_bp=10_000)
    assert label == LABEL_COMPLETED_UNPROVEN
    assert label != LABEL_SUCCEEDED


def test_completed_with_evidence_is_a_success():
    assert classify_outcome(terminal_state=ExecutionState.COMPLETED, reason_code="done",
                            outcome_kind="signed_document", progress_bp=10_000) == LABEL_SUCCEEDED


def test_only_a_proven_completion_counts_as_positive_for_learning():
    """⛔ THE CONSEQUENCE THAT MAKES THE DISTINCTION MATTER. If `completed_unproven` counted as
    positive, a play whose steps people happily do and whose outcome never arrives would calibrate as
    a good play — and L6 would learn to recommend it more."""
    assert LABEL_SUCCEEDED in LABEL_POSITIVE
    assert LABEL_COMPLETED_UNPROVEN not in LABEL_POSITIVE
    assert LABEL_COMPLETED_UNPROVEN in LABEL_NEUTRAL


def test_an_expiry_distinguishes_untouched_from_in_progress():
    """*"The deadline passed with no completion evidence"* is not one fact. Nobody started it and
    somebody tried and ran out of time are different lessons."""
    assert classify_outcome(terminal_state=ExecutionState.EXPIRED, reason_code="deadline",
                            outcome_kind=None, progress_bp=0) == LABEL_EXPIRED_UNTOUCHED
    assert classify_outcome(terminal_state=ExecutionState.EXPIRED, reason_code="deadline",
                            outcome_kind=None, progress_bp=6_000) == LABEL_EXPIRED_IN_PROGRESS


def test_every_terminal_state_produces_a_label():
    """⛔ Totality. An unlabelled ending is an outcome L6 cannot learn from, and the fallback must be a
    real label rather than None."""
    for state in ExecutionState:
        label = classify_outcome(terminal_state=state, reason_code="whatever",
                                 outcome_kind=None, progress_bp=0)
        assert isinstance(label, str) and label


# =================================================================================================
# 3 · the report names the gap the rule exists to expose
# =================================================================================================
def test_done_but_unproven_is_a_named_state_not_an_inference():
    """⛔ *"A play that reliably reaches this state is a play whose steps people are happy to do and
    whose outcome never arrives, and no amount of completion rate will surface that."*"""
    assert _report(10_000).done_but_unproven is True
    assert _report(10_000, "signed_document").done_but_unproven is False
    assert _report(9_999).done_but_unproven is False


def test_outcome_observed_is_the_only_proof_that_counts():
    assert _report(0, "signed_document").outcome_observed is True
    assert _report(10_000).outcome_observed is False


def test_steps_complete_and_outcome_observed_are_separate_questions():
    """Collapsing them is the whole defect. One is activity, the other is outcome."""
    r = _report(10_000)
    assert r.steps_complete is True and r.outcome_observed is False


# =================================================================================================
# 4 · ⛔ the four reasons not to send stay four
# =================================================================================================
def test_the_guard_says_more_than_a_boolean():
    """⛔ *"'Do not send' covers four genuinely different situations — the work is done, the deal is
    dead, the clock ran out, the owner left — and collapsing them into one flag would make the
    difference invisible in exactly the reports where it matters."*"""
    assert len(list(GuardAction)) > 2
    assert GuardAction.PROCEED.value == "proceed"


def test_the_existing_walk_still_owns_the_seams():
    """This file proves the RULE; `test_e2e_all_layers.py` proves the seams line up on real persisted
    output. Neither replaces the other, and the walk must not quietly lose its executive stage."""
    from pathlib import Path

    walk = (Path(__file__).resolve().parents[2] / "tests" / "test_e2e_all_layers.py").read_text()
    assert "run_executive" in walk
    assert "pg_store" in walk
