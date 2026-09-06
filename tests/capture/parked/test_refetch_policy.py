"""G2 · L1.3.8-U1 — the refetch ladder's arithmetic, one row per stated condition.

The ladder's only interesting properties are properties of its decisions: that it terminates,
that a deleted attachment stops immediately instead of costing five downloads, that a park too
young to have settled is left alone, and that a claim which was never fetched refunds its
attempt. All of those are pure, so all of them are tested here — no database, no clock, no
provider — and `test_refetch_drain.py` then drives the same decisions through the loop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.parked.refetch_policy import (DEFAULT_POLICY, AttemptFailure,
                                                         AttemptResult, ParkStatus,
                                                         RefetchAction, RefetchCandidate,
                                                         RefetchPolicy, backoff_after,
                                                         classify_fetch_error,
                                                         parse_attachment_ref, plan_refetch,
                                                         settle_attempt, settle_without_attempt,
                                                         with_attempts)

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)


def candidate(**overrides) -> RefetchCandidate:
    """A DOC-05 Gmail attachment parked two hours ago — the shape every row here starts from."""
    base = dict(event_id="evt_1", org_id="org_1", reason_code="DOC-05",
                status=ParkStatus.PENDING.value, object_type="email_attachment", source="gmail",
                source_object_id="m123::att456", parent_object_id="m123",
                connection_id="conn_1", parked_at=NOW - timedelta(hours=2), attempts=0,
                next_attempt_at=None, filename="MSA-signed.pdf", mime="application/pdf")
    base.update(overrides)
    return RefetchCandidate(**base)


# ── the ladder ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("attempt, expected_seconds", [
    (1, 600),           # ten minutes after the first failure
    (2, 1_800),
    (3, 7_200),
    (4, 21_600),
    (5, 21_600),        # past the ladder: the last rung is reused, never an IndexError
    (99, 21_600),
    (0, 600),           # not a real attempt number; clamped to the first rung
    (-3, 600),
])
def test_backoff_ladder_is_bounded_at_both_ends(attempt, expected_seconds):
    assert backoff_after(attempt) == timedelta(seconds=expected_seconds)


def test_a_ladder_with_no_rungs_is_refused_rather_than_silently_infinite():
    with pytest.raises(ValueError, match="no rungs"):
        backoff_after(1, RefetchPolicy(backoff_seconds=()))


def test_the_ladder_never_shortens_a_wait():
    """Monotonic on purpose: a backoff that got shorter as attempts accumulated would hammer the
    provider hardest exactly when it is least likely to answer."""
    waits = [backoff_after(n) for n in range(1, len(DEFAULT_POLICY.backoff_seconds) + 1)]
    assert waits == sorted(waits) and len(set(waits)) == len(waits)


# ── addressing ───────────────────────────────────────────────────────────────────────────────

def test_a_composite_id_resolves_to_message_and_attachment():
    ref = parse_attachment_ref(candidate())
    assert (ref.message_id, ref.attachment_id) == ("m123", "att456")
    assert ref.is_fetchable


def test_an_id_whose_tail_is_the_filename_is_recognised_as_unaddressable():
    """`_attachment_stub` falls back to the FILENAME when Gmail gave the part no attachmentId.
    A filename cannot be handed to attachments.get, and pretending otherwise buys five 404s."""
    ref = parse_attachment_ref(candidate(source_object_id="m123::MSA-signed.pdf"))
    assert ref.attachment_id is None and not ref.is_fetchable
    assert ref.filename == "MSA-signed.pdf"          # still reported, so the row is identifiable


@pytest.mark.parametrize("row, why", [
    (candidate(object_type="email_message"), "an email is not an attachment"),
    (candidate(source_object_id="m123"), "no composite separator at all"),
])
def test_rows_that_are_not_addressable_attachments_return_no_ref(row, why):
    assert parse_attachment_ref(row) is None, why


def test_a_missing_message_half_falls_back_to_the_parent_message_id():
    ref = parse_attachment_ref(candidate(source_object_id="::att456", parent_object_id="m999"))
    assert ref.message_id == "m999" and ref.is_fetchable


# ── the plan ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("row, action, reason_fragment", [
    (candidate(), RefetchAction.ATTEMPT, "due"),
    (candidate(reason_code="DOC-02"), RefetchAction.ATTEMPT, "due"),
    (candidate(reason_code="DOC-06"), RefetchAction.ATTEMPT, "due"),
    (candidate(reason_code="low_relevance"), RefetchAction.SKIP, "not a refetch reason"),
    (candidate(status="recovered"), RefetchAction.SKIP, "already settled"),
    (candidate(status="dead_letter"), RefetchAction.SKIP, "already settled"),
    (candidate(object_type="email_message"), RefetchAction.SKIP, "not a fetchable attachment"),
    (candidate(parked_at=NOW - timedelta(minutes=3)), RefetchAction.WAIT, "too recently"),
    (candidate(next_attempt_at=NOW + timedelta(minutes=5)), RefetchAction.WAIT, "backoff"),
    (candidate(attempts=5), RefetchAction.DEAD_LETTER, "exhausted"),
    (candidate(attempts=9), RefetchAction.DEAD_LETTER, "exhausted"),
    (candidate(source_object_id="m123::MSA-signed.pdf"), RefetchAction.DEAD_LETTER,
     "only a filename"),
])
def test_plan_covers_every_stated_condition(row, action, reason_fragment):
    plan = plan_refetch(row, eval_time=NOW)
    assert plan.action is action
    assert reason_fragment in plan.reason


def test_an_elapsed_backoff_is_due_again():
    plan = plan_refetch(candidate(attempts=2, next_attempt_at=NOW - timedelta(seconds=1)),
                        eval_time=NOW)
    assert plan.action is RefetchAction.ATTEMPT and plan.attempt_number == 3


def test_boundedness_is_checked_before_timing():
    """An exhausted park whose backoff has not elapsed must DEAD-LETTER, not WAIT. Checking
    timing first is how a bounded ladder turns back into a queue that answers 'later' forever."""
    row = candidate(attempts=5, next_attempt_at=NOW + timedelta(hours=6))
    assert plan_refetch(row, eval_time=NOW).action is RefetchAction.DEAD_LETTER


def test_an_attempt_plan_carries_the_lease_and_the_attempt_number():
    plan = plan_refetch(candidate(attempts=1), eval_time=NOW)
    assert plan.attempt_number == 2
    assert plan.lease_until == NOW + DEFAULT_POLICY.lease


def test_the_minimum_park_age_boundary_is_inclusive_at_ten_minutes():
    exactly_ten = candidate(parked_at=NOW - DEFAULT_POLICY.min_park_age)
    a_second_short = candidate(parked_at=NOW - DEFAULT_POLICY.min_park_age
                               + timedelta(seconds=1))
    assert plan_refetch(exactly_ten, eval_time=NOW).action is RefetchAction.ATTEMPT
    assert plan_refetch(a_second_short, eval_time=NOW).action is RefetchAction.WAIT


# ── settlement ───────────────────────────────────────────────────────────────────────────────

def _attempt_plan(**overrides):
    plan = plan_refetch(candidate(**overrides), eval_time=NOW)
    assert plan.action is RefetchAction.ATTEMPT
    return plan


def test_a_successful_attempt_recovers_and_clears_the_ladder():
    settlement = settle_attempt(_attempt_plan(), AttemptResult(ok=True, text_chars=4_200),
                                eval_time=NOW)
    assert settlement.status is ParkStatus.RECOVERED
    assert settlement.next_attempt_at is None and settlement.last_error is None
    assert settlement.attempts == 1


@pytest.mark.parametrize("attempts_before, expected_status, expected_next", [
    (0, ParkStatus.PENDING, NOW + timedelta(seconds=600)),
    (1, ParkStatus.PENDING, NOW + timedelta(seconds=1_800)),
    (2, ParkStatus.PENDING, NOW + timedelta(seconds=7_200)),
    (3, ParkStatus.PENDING, NOW + timedelta(seconds=21_600)),
    (4, ParkStatus.DEAD_LETTER, None),          # the fifth attempt is the last one
])
def test_a_transient_failure_walks_the_ladder_and_then_stops(attempts_before, expected_status,
                                                             expected_next):
    plan = _attempt_plan(attempts=attempts_before)
    settlement = settle_attempt(plan, AttemptResult(ok=False, failure=AttemptFailure.TRANSIENT,
                                                    error="upstream timeout"), eval_time=NOW)
    assert settlement.status is expected_status
    assert settlement.next_attempt_at == expected_next
    assert settlement.attempts == attempts_before + 1
    assert settlement.last_error == "upstream timeout"


def test_a_permanent_failure_is_terminal_on_the_first_answer():
    """The one early exit from the ladder. The provider said the bytes do not exist, and spending
    four more downloads to re-learn a 404 is not diligence."""
    settlement = settle_attempt(_attempt_plan(),
                                AttemptResult(ok=False, failure=AttemptFailure.PERMANENT,
                                              error="404 not found"), eval_time=NOW)
    assert settlement.status is ParkStatus.DEAD_LETTER
    assert settlement.attempts == 1              # not five: one answer was enough
    assert settlement.failure is AttemptFailure.PERMANENT


def test_a_capability_failure_defers_on_the_slow_clock_instead_of_dying():
    """D1. This row used to read:

        @pytest.mark.parametrize("failure", [AttemptFailure.PERMANENT, AttemptFailure.CAPABILITY])
        def test_a_permanent_or_capability_failure_is_terminal_on_the_first_answer(failure):
            ...
            assert settlement.status is ParkStatus.DEAD_LETTER
            assert settlement.attempts == 1              # not five: one answer was enough

    and the CAPABILITY half of it encoded the defect rather than a decision. "One answer was
    enough" is true of PERMANENT — the provider is the authority on whether its own bytes exist —
    and false of CAPABILITY, where the authority is OUR deployment and the answer is only about
    this instant. `DOC-02/04/06` are parked precisely because the toolchain could not read them,
    and `api/routes.py::_drain_attachment_refetch` calls the drain with ``ocr=None``, so the
    first heartbeat was guaranteed to re-learn that for the whole backlog and write every one of
    those parks off permanently in a single pass — with G2 (`pending` older than an hour) reading
    BETTER for the loss, because a dead letter is not pending.
    """
    settlement = settle_attempt(_attempt_plan(),
                                AttemptResult(ok=False, failure=AttemptFailure.CAPABILITY,
                                              error="ocr_unavailable: no engine is wired"),
                                eval_time=NOW)
    assert settlement.status is ParkStatus.PENDING
    assert settlement.next_attempt_at == NOW + DEFAULT_POLICY.capability_backoff
    assert settlement.failure is AttemptFailure.CAPABILITY


def test_a_capability_failure_is_still_bounded_by_the_same_ladder():
    """Deferred is not unbounded: the fifth attempt is the last one for this kind too, and the
    dead letter it writes still names the capability."""
    settlement = settle_attempt(_attempt_plan(attempts=DEFAULT_POLICY.max_attempts - 1),
                                AttemptResult(ok=False, failure=AttemptFailure.CAPABILITY,
                                              error="ocr_unavailable"), eval_time=NOW)
    assert settlement.status is ParkStatus.DEAD_LETTER
    assert settlement.next_attempt_at is None
    assert settlement.failure is AttemptFailure.CAPABILITY


def test_settling_a_plan_that_was_never_an_attempt_is_refused():
    plan = plan_refetch(candidate(status="recovered"), eval_time=NOW)
    with pytest.raises(ValueError, match="only an ATTEMPT plan"):
        settle_attempt(plan, AttemptResult(ok=True, text_chars=1), eval_time=NOW)


def test_a_claim_that_was_never_fetched_refunds_its_attempt():
    """WAIT after a claim means the SQL filter and the policy disagreed. No bytes were requested,
    so the lease is refunded — a race must not cost a retry."""
    plan = plan_refetch(candidate(attempts=2, next_attempt_at=NOW + timedelta(hours=1)),
                        eval_time=NOW)
    settlement = settle_without_attempt(plan, eval_time=NOW)
    assert settlement.status is ParkStatus.PENDING
    assert settlement.attempts == 2 and settlement.next_attempt_at is None


def test_a_dead_letter_plan_settles_terminally_with_its_own_reason():
    plan = plan_refetch(candidate(attempts=5), eval_time=NOW)
    settlement = settle_without_attempt(plan, eval_time=NOW)
    assert settlement.status is ParkStatus.DEAD_LETTER
    assert "exhausted" in (settlement.last_error or "")


def test_settle_without_attempt_refuses_an_attempt_plan():
    with pytest.raises(ValueError, match="settle_attempt"):
        settle_without_attempt(_attempt_plan(), eval_time=NOW)


# ── the failure contract ─────────────────────────────────────────────────────────────────────

def test_a_success_with_no_text_cannot_be_constructed():
    """An 'accepted' document carrying nothing is the exact silent loss this component removes.
    Refusing the value is stronger than remembering to check for it."""
    with pytest.raises(ValueError, match="empty-document failure"):
        AttemptResult(ok=True, text_chars=0)


def test_a_failure_must_name_its_kind():
    with pytest.raises(ValueError, match="failure kind"):
        AttemptResult(ok=False, error="something went wrong")


@pytest.mark.parametrize("message, expected", [
    ("HTTP 404 while fetching attachment", AttemptFailure.PERMANENT),
    ("RuntimeError: message not found", AttemptFailure.PERMANENT),
    ("attachmentNotFound", AttemptFailure.PERMANENT),
    ("the message has been deleted", AttemptFailure.PERMANENT),
    ("resource is gone", AttemptFailure.PERMANENT),
    ("ReadTimeout: upstream took too long", AttemptFailure.TRANSIENT),
    ("429 rate limit exceeded", AttemptFailure.TRANSIENT),
    ("403 forbidden — token expired", AttemptFailure.TRANSIENT),   # a reconnect fixes this
    ("", AttemptFailure.TRANSIENT),
    (None, AttemptFailure.TRANSIENT),
])
def test_fetch_errors_are_classified_into_retry_or_stop(message, expected):
    assert classify_fetch_error(message) is expected


def test_with_attempts_replaces_only_the_count():
    row = candidate(attempts=1)
    assert with_attempts(row, 4) == candidate(attempts=4)
