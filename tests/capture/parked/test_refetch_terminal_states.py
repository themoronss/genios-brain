"""D1 · a terminal state is a decision, and only a real reason may reach it.

THE DEFECT THIS FILE EXISTS FOR. The refetch ladder is bounded at five attempts, but three paths
walked straight past the ladder to a permanent dead letter on the FIRST heartbeat:

  1. `classify_fetch_error` was a bare substring table over arbitrary provider prose. Every
     realistic message a rate-limited, re-authenticating or half-open Composio/Gmail call produces
     — ``"401 Unauthorized: connected account not found, refreshing"``, ``"503 upstream gone"``,
     ``"ConnectionResetError: connection gone away"`` — contains ``not found`` or ``gone``, so it
     was classified PERMANENT and the row was dead-lettered after one attempt. A token refresh
     window is minutes long; the backlog it killed was permanent.
  2. A raise from the CONNECTOR FACTORY — our own resolution of the tenant's connection, before
     any provider was asked anything — was fed through that same string table. A `KeyError:
     connection not found` while a tenant re-authorises is a statement about our process, never
     evidence that an attachment is gone.
  3. A CAPABILITY failure (we fetched the bytes and no engine here can read them) dead-lettered on
     the first answer. That is a fact about this deployment's toolchain at one instant, not about
     the attachment — and the heartbeat calls the drain with ``ocr=None``, so on the first tick
     every DOC-02/04/06 park in the backlog was guaranteed to reach it.

WHY THE GATE COULD NOT SEE ANY OF IT. `aging()` counts ``status='pending'``, and G2 asserts that
0 attachments are stuck there over an hour. Dead-lettering the whole backlog drives that number to
zero. The metric reads BETTER the more documents are lost, so every assertion here is about the
STATE and its AGE — is this row still claimable, on which tick, with what recorded reason — and
never about the report's summary counts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.documents.base import DocumentResult, DocumentStatus
from genios_engine.capture.parked.refetch import (InMemoryRefetchQueue,
                                                  refetch_parked_attachments)
from genios_engine.capture.parked.refetch_policy import (DEFAULT_POLICY, AttemptFailure,
                                                         AttemptResult, ParkStatus,
                                                         RefetchAction, RefetchCandidate,
                                                         classify_fetch_error, plan_refetch,
                                                         settle_attempt, settle_without_attempt)

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
CONTRACT_TEXT = "Master Services Agreement. Total contract value $84,000 payable annually."

STUB_PAYLOAD = {"subject": "MSA-signed.pdf", "body": "", "mime": "application/pdf",
                "has_attachment": True, "to": ["founder@genios.ai"]}


def park(**overrides) -> RefetchCandidate:
    base = dict(event_id="evt_att", org_id="org_1", reason_code="DOC-05",
                status=ParkStatus.PENDING.value, object_type="email_attachment", source="gmail",
                source_object_id="m123::att456", parent_object_id="m123", connection_id="conn_1",
                parked_at=NOW - timedelta(hours=3), attempts=0, next_attempt_at=None)
    base.update(overrides)
    return RefetchCandidate(**base)


def queue_with(*candidates) -> InMemoryRefetchQueue:
    queue = InMemoryRefetchQueue()
    for candidate in candidates:
        queue.add(candidate, payload=dict(STUB_PAYLOAD))
    return queue


def accepted() -> DocumentResult:
    return DocumentResult(text=CONTRACT_TEXT, native_parse_used=True, ocr_used=False,
                          ocr_engine=None, ocr_pages=1, confidence_bp=10_000,
                          status=DocumentStatus.ACCEPTED.value)


def extractor_returning(result: DocumentResult):
    def _extract(*, mime, data, filename, ocr):
        return result
    return _extract


UNREADABLE = DocumentResult(text="", native_parse_used=False, ocr_used=False, ocr_engine=None,
                            ocr_pages=0, confidence_bp=None,
                            status=DocumentStatus.OCR_UNAVAILABLE.value,
                            detail="no OCR engine is wired")


class _Fetcher:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def fetch_attachment(self, message_id, attachment_id):
        self.calls.append((message_id, attachment_id))
        answer = self.answers.pop(0) if self.answers else b"%PDF bytes"
        if isinstance(answer, BaseException):
            raise answer
        return answer


def heartbeat(queue, *, connector_for=None, fetcher=None, extract=None, now=NOW,
              policy=DEFAULT_POLICY):
    """One tick of the drain, called the way `api/routes.py::_drain_attachment_refetch` calls it —
    every org, default policy, and NO ocr engine passed."""
    return refetch_parked_attachments(
        queue,
        connector_for=connector_for or (lambda _c: fetcher if fetcher is not None else _Fetcher()),
        eval_time=now, policy=policy,
        extract=extract if extract is not None else extractor_returning(accepted()))


# ── 1 · the classifier ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("message, why", [
    ("HTTPStatusError: 401 Unauthorized — connected account not found while the token is being "
     "refreshed", "a re-auth window says 'not found' about the CONNECTION, not the attachment"),
    ("ComposioSDKError: 429 Too Many Requests; the requested resource was not found in cache",
     "a rate limiter's own prose carried a permanent marker"),
    ("ConnectionResetError: [Errno 54] connection gone away mid-response",
     "'gone' is a network verb here, not a provider verdict"),
    ("ServiceUnavailable: 503 upstream gone, retry later", "a 5xx is always worth another go"),
    ("ReadTimeout: the read operation timed out after 30s", "a slow provider"),
    ("HTTPError: 502 Bad Gateway", "a proxy hiccup"),
    ("RuntimeError: request id 404abc93 failed to complete", "'404' inside an opaque id"),
])
def test_a_transient_provider_failure_is_never_classified_as_permanent(message, why):
    """The single decision that lets a row leave the ladder early. Anything that might work on the
    next tick must stay TRANSIENT, because the ladder bounds an unknown error at five attempts
    while a mis-classified PERMANENT costs a real attachment forever."""
    assert classify_fetch_error(message) is AttemptFailure.TRANSIENT, why


@pytest.mark.parametrize("message", [
    "HTTP 404 while fetching attachment",
    "HTTP 410: the resource is gone",
    "RuntimeError: message not found",
    "attachmentNotFound",
    "the message has been deleted",
    "the attachment is gone",
    # The trap a broad transient marker sets: "unavailable" is a transient word and "no longer
    # available" is a permanent phrase, and a bare "unavailable" marker would swallow it.
    "this attachment is no longer available",
])
def test_a_genuinely_gone_attachment_is_still_permanent(message):
    """The fix must not make the classifier useless: spending five downloads to re-learn a 404 is
    not diligence either."""
    assert classify_fetch_error(message) is AttemptFailure.PERMANENT


# ── 2 · our own failures are never evidence about the attachment ─────────────────────────────

def test_a_connector_factory_that_raises_is_retryable_whatever_it_says():
    """`_attachment_connector_for` reads the tenant's connection registry. A raise from it happens
    on OUR side of the wire — a connection row being rewritten by a reconnect, a registry not yet
    warm — and routing its message through the provider-error table let 'connection not found'
    dead-letter the org's whole backlog."""
    queue = queue_with(park())

    def _explode(_candidate):
        raise KeyError("connection not found: conn_1")

    report = heartbeat(queue, connector_for=_explode)

    assert report.dead_lettered == 0 and report.retry_scheduled == 1
    row = queue.candidates["evt_att"]
    assert row.status == ParkStatus.PENDING.value
    assert row.next_attempt_at == NOW + timedelta(seconds=600)


# ── 3 · a transient failure survives a heartbeat as retryable ────────────────────────────────

def test_a_transient_failure_survives_the_first_heartbeat_as_retryable():
    """The property D1 names, asserted on the STATE and its AGE rather than on the metric: after a
    tick the park is still pending, still the same age, and claimable again once its backoff
    elapses."""
    queue = queue_with(park())
    parked_at = queue.candidates["evt_att"].parked_at

    first = heartbeat(queue, fetcher=_Fetcher(
        RuntimeError("401 Unauthorized: connected account not found, token refreshing")))
    assert first.dead_lettered == 0
    row = queue.candidates["evt_att"]
    assert row.status == ParkStatus.PENDING.value, "one bad tick must not be terminal"
    assert row.parked_at == parked_at, "the park's own age is not reset by an attempt"
    assert row.next_attempt_at == NOW + timedelta(seconds=600)

    aging = queue.aging(eval_time=NOW, policy=DEFAULT_POLICY)
    assert aging.pending == 1, "a retryable park stays visible to the gate, not hidden as dead"

    later = NOW + timedelta(seconds=601)
    second = heartbeat(queue, now=later, fetcher=_Fetcher(b"%PDF bytes"))
    assert second.claimed == 1 and second.recovered == 1
    assert queue.outcomes["evt_att"] == "emitted"


def test_five_transient_ticks_are_still_bounded_and_name_the_kind_they_died_of():
    """Bounded is half the contract; the other half is that the dead letter says WHICH ladder ran
    out, because 'the queue is full of timeouts' and 'the queue is full of 404s' have different
    fixes."""
    queue = queue_with(park())
    at = NOW
    for _ in range(DEFAULT_POLICY.max_attempts):
        heartbeat(queue, now=at, fetcher=_Fetcher(RuntimeError("ReadTimeout: upstream slow")))
        at += timedelta(hours=12)

    row = queue.candidates["evt_att"]
    assert row.status == ParkStatus.DEAD_LETTER.value
    assert row.attempts == DEFAULT_POLICY.max_attempts
    dead = queue.dead_letters()
    assert len(dead) == 1 and dead[0].failure_kind == AttemptFailure.TRANSIENT.value


def test_an_exhausted_ladder_is_recorded_as_transient_not_permanent():
    """`settle_without_attempt` stamped PERMANENT on every dead letter it wrote, including the one
    that means 'we tried five times'. That is the console reading 'the attachment is gone' about
    an attachment nobody ever proved was gone."""
    plan = plan_refetch(park(attempts=DEFAULT_POLICY.max_attempts), eval_time=NOW)
    assert plan.action is RefetchAction.DEAD_LETTER
    settlement = settle_without_attempt(plan, eval_time=NOW)
    assert settlement.status is ParkStatus.DEAD_LETTER
    assert settlement.failure is AttemptFailure.TRANSIENT


def test_an_unaddressable_reference_is_still_recorded_as_permanent():
    """The one non-attempt dead letter that IS a statement about the object: the parked composite
    id carries a filename where a provider attachment id belongs, so no request can be built."""
    plan = plan_refetch(park(source_object_id="m123::MSA.pdf", filename="MSA.pdf"), eval_time=NOW)
    assert plan.action is RefetchAction.DEAD_LETTER
    assert settle_without_attempt(plan, eval_time=NOW).failure is AttemptFailure.PERMANENT


# ── 4 · a capability gap is our gap, and it is not permanent ─────────────────────────────────

def test_a_capability_gap_is_deferred_not_dead_lettered_on_the_first_heartbeat():
    """A DOC-06 park says 'this file has pages and no engine was wired'. The heartbeat drains with
    ``ocr=None``, so the FIRST tick after this component shipped was guaranteed to re-learn that
    for every such park — and it wrote every one of them off permanently."""
    queue = queue_with(park(reason_code="DOC-06"))
    report = heartbeat(queue, extract=extractor_returning(UNREADABLE))

    assert report.dead_lettered == 0
    row = queue.candidates["evt_att"]
    assert row.status == ParkStatus.PENDING.value
    assert row.next_attempt_at == NOW + DEFAULT_POLICY.capability_backoff, \
        "a toolchain gap is re-checked on the capability clock, not on the network one"
    assert queue.aging(eval_time=NOW, policy=DEFAULT_POLICY).pending == 1


def test_a_capability_gap_recovers_by_itself_once_the_engine_lands():
    """The whole point of not dead-lettering it: nobody has to remember to POST the requeue
    route for the backlog to drain the day an engine is wired."""
    queue = queue_with(park(reason_code="DOC-06"))
    heartbeat(queue, extract=extractor_returning(UNREADABLE))

    later = NOW + DEFAULT_POLICY.capability_backoff + timedelta(minutes=1)
    report = heartbeat(queue, now=later)                    # an engine landed; extraction accepts
    assert report.recovered == 1
    assert queue.candidates["evt_att"].status == ParkStatus.RECOVERED.value


def test_a_capability_gap_still_terminates_after_the_ladder():
    """Bounded: five downloads of a file we cannot read, spread across the capability clock, and
    then a dead letter that names the capability rather than pretending the file is gone."""
    queue = queue_with(park(reason_code="DOC-06"))
    at = NOW
    for _ in range(DEFAULT_POLICY.max_attempts):
        heartbeat(queue, now=at, extract=extractor_returning(UNREADABLE))
        at += DEFAULT_POLICY.capability_backoff + timedelta(minutes=1)

    row = queue.candidates["evt_att"]
    assert row.status == ParkStatus.DEAD_LETTER.value
    dead = queue.dead_letters()
    assert len(dead) == 1
    assert dead[0].failure_kind == AttemptFailure.CAPABILITY.value
    assert DocumentStatus.OCR_UNAVAILABLE.value in (dead[0].last_error or "")
    assert "no OCR engine is wired" in (dead[0].last_error or "")


# ── 5 · idempotence ──────────────────────────────────────────────────────────────────────────

def test_settling_the_same_failure_twice_lands_the_same_row():
    """Two drains that raced to the same conclusion must converge, not accumulate: the settlement
    is derived from the PLAN's attempt number, so re-applying it is an overwrite."""
    plan = plan_refetch(park(attempts=1), eval_time=NOW)
    result = AttemptResult(ok=False, failure=AttemptFailure.TRANSIENT, error="ReadTimeout")
    first = settle_attempt(plan, result, eval_time=NOW)
    second = settle_attempt(plan, result, eval_time=NOW)
    assert first == second

    queue = queue_with(park(attempts=1))
    queue.persist_settlement(first)
    after_one = queue.candidates["evt_att"]
    queue.persist_settlement(second)
    assert queue.candidates["evt_att"] == after_one


def test_a_permanent_verdict_survives_the_connection_id_it_is_reported_with():
    """The failure mode a loose transient marker introduces, going the other way. Composio quotes
    the connection on every error, so a marker like `connection_id` or a bare `connection` would
    make EVERY provider answer retryable — including a real 404 — and the ladder would spend five
    downloads on every deleted attachment in the backlog, forever, on every requeue."""
    assert classify_fetch_error(
        "ToolExecutionError on connection conn_1abc for connection_id=conn_1abc: "
        "GMAIL_GET_ATTACHMENT returned 404, message not found") is AttemptFailure.PERMANENT


# ── 6 · a lease burned on the LAST rung must not become a permanent black hole ────────────────
#
# THE DEFECT. `RefetchPolicy.lease`'s own docstring states the invariant:
#
#     the attempt count is incremented and `next_attempt_at` pushed out BEFORE the network call,
#     so a process that dies mid-fetch leaves a row that is bounded and re-attemptable, not one
#     that is invisible forever
#
# It held on every rung but the last. Both claims — `_CLAIM_SQL` and
# `InMemoryRefetchQueue.claim_due` — filtered `refetch_attempts < max_attempts`, and
# `plan_refetch`'s terminal branch for `attempts >= max_attempts` was therefore UNREACHABLE from
# the drain: the only way a row reached it was by being handed to `plan_refetch` directly, which
# is what the test above does. So a drain killed between the lease and the settlement on attempt
# five left a row at `status='pending'` with `refetch_attempts = 5`, which no later heartbeat
# could ever claim.
#
# And it is the G2 number: `read_aging` counts `status='pending'` by reason code and does not look
# at the attempt count, so that row is STUCK, permanently, in the metric the gate asserts is zero.

def _burn_the_lease_and_die(queue, *, now=NOW, policy=DEFAULT_POLICY) -> None:
    """Exactly what a killed drain leaves behind: the claim ran, the settlement never did."""
    claimed = queue.claim_due(eval_time=now, policy=policy, org_id=None, limit=10)
    assert claimed, "the row was not claimable to begin with, so nothing is being simulated"


def test_a_row_whose_last_lease_was_burned_by_a_crash_is_still_claimable():
    """The invariant, at the rung it did not hold on."""
    queue = queue_with(park(attempts=DEFAULT_POLICY.max_attempts - 1))
    _burn_the_lease_and_die(queue)                       # attempt 5 leased, process dies

    row = queue.candidates["evt_att"]
    assert row.attempts == DEFAULT_POLICY.max_attempts
    assert row.status == ParkStatus.PENDING.value, "the crash simulation did not leave it pending"

    # A later heartbeat, well past the lease.
    later = NOW + DEFAULT_POLICY.lease + timedelta(hours=1)
    reclaimed = queue.claim_due(eval_time=later, policy=DEFAULT_POLICY, org_id=None, limit=10)
    assert reclaimed, (
        "a park leased on its final attempt and never settled can never be claimed again: it "
        "stays status='pending' forever and read_aging counts it as STUCK, which is the exact "
        "number G2 asserts is zero")


def test_a_crashed_final_lease_reaches_its_dead_letter_on_the_next_heartbeat():
    """And the settlement it reaches is the right one: bounded out, recorded TRANSIENT, because
    five failures we caused say nothing about whether the attachment exists."""
    queue = queue_with(park(attempts=DEFAULT_POLICY.max_attempts - 1))
    _burn_the_lease_and_die(queue)

    later = NOW + DEFAULT_POLICY.lease + timedelta(hours=1)
    report = heartbeat(queue, now=later, fetcher=_Fetcher(RuntimeError("ReadTimeout")))

    assert report.dead_lettered == 1, report
    row = queue.candidates["evt_att"]
    assert row.status == ParkStatus.DEAD_LETTER.value
    assert row.attempts == DEFAULT_POLICY.max_attempts, (
        "the terminal settlement inflated the attempt count past the ladder")
    dead = queue.dead_letters()
    assert len(dead) == 1 and dead[0].failure_kind == AttemptFailure.TRANSIENT.value


def test_the_crashed_row_costs_no_further_provider_call():
    """A dead letter reached WITHOUT a fetch: the ladder is out, so asking the provider again
    would be spending a download to re-learn a bound we already hold."""
    queue = queue_with(park(attempts=DEFAULT_POLICY.max_attempts - 1))
    _burn_the_lease_and_die(queue)

    fetcher = _Fetcher(RuntimeError("ReadTimeout"))
    heartbeat(queue, now=NOW + DEFAULT_POLICY.lease + timedelta(hours=1), fetcher=fetcher)
    assert fetcher.calls == [], (
        "the bounded-out row was fetched again; `plan_refetch` must reach DEAD_LETTER before "
        "any I/O")


def test_the_backlog_is_empty_once_the_crashed_row_is_settled():
    """The gate's own number, end to end."""
    queue = queue_with(park(attempts=DEFAULT_POLICY.max_attempts - 1))
    _burn_the_lease_and_die(queue)
    later = NOW + DEFAULT_POLICY.lease + timedelta(hours=1)
    heartbeat(queue, now=later, fetcher=_Fetcher(RuntimeError("ReadTimeout")))
    aging = queue.aging(eval_time=later, policy=DEFAULT_POLICY, org_id=None)
    assert aging.stuck_attachments == 0, aging
