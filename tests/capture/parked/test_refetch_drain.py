"""G2 · L1.3.8-U1 — the drain cycle, end to end, with the database taken out.

The spec's acceptance for this unit is two sentences and both are here:

    "a fixture attachment that fails first fetch is present after one drain cycle"
    "after 5 failures it appears in the admin console rather than vanishing"

Everything else in this file exists because the failure mode this component replaces was SILENT.
A refetch that quietly loops forever, or quietly marks an event emitted with an empty body, or
quietly drops the recipients off a recovered contract, would look exactly as green as a working
one. So the assertions are about what is OBSERVABLE afterwards — the ledger outcome, the payload,
the prepared seam, the dead-letter queue — rather than about the report's own summary counts.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.documents.base import DocumentResult, DocumentStatus
from genios_engine.capture.parked.refetch import (InMemoryRefetchQueue,
                                                  refetch_parked_attachments)
from genios_engine.capture.parked.refetch_policy import (DEFAULT_POLICY, ParkStatus,
                                                         RefetchCandidate, RefetchPolicy)

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)

#: Carries a PAN, which `preprocess/pii.py` masks unconditionally — the assertion that the
#: recovery ran the text through the masker needs PII the masker actually looks for. (Email
#: addresses are deliberately NOT masked there: sales workflows need them.)
CONTRACT_TEXT = ("Master Services Agreement. Total contract value $84,000 payable annually. "
                 "Counterparty PAN ABCDE1234F on file.")


def park(**overrides) -> RefetchCandidate:
    base = dict(event_id="evt_att", org_id="org_1", reason_code="DOC-05",
                status=ParkStatus.PENDING.value, object_type="email_attachment", source="gmail",
                source_object_id="m123::att456", parent_object_id="m123", connection_id="conn_1",
                parked_at=NOW - timedelta(hours=3), attempts=0, next_attempt_at=None)
    base.update(overrides)
    return RefetchCandidate(**base)


STUB_PAYLOAD = {"subject": "MSA-signed.pdf", "body": "", "mime": "application/pdf",
                "has_attachment": True, "to": ["founder@genios.ai"], "cc": ["cfo@genios.ai"],
                "document": {"status": DocumentStatus.FETCH_FAILED.value,
                             "native_parse_used": False, "ocr_used": False,
                             "ocr_engine": None, "ocr_pages": 0, "confidence_bp": None}}


class FakeFetcher:
    """A provider that answers from a script, and records what it was asked for."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def fetch_attachment(self, message_id: str, attachment_id: str) -> bytes:
        self.calls.append((message_id, attachment_id))
        answer = self.answers.pop(0) if self.answers else b"%PDF-1.7 bytes"
        if isinstance(answer, BaseException):
            raise answer
        return answer


def accepted(text: str = CONTRACT_TEXT) -> DocumentResult:
    return DocumentResult(text=text, native_parse_used=True, ocr_used=False, ocr_engine=None,
                          ocr_pages=1, confidence_bp=10_000,
                          status=DocumentStatus.ACCEPTED.value)


def extractor_returning(result: DocumentResult):
    def _extract(*, mime, data, filename, ocr):
        return result
    return _extract


def queue_with(*candidates, payload: dict | None = None) -> InMemoryRefetchQueue:
    queue = InMemoryRefetchQueue()
    for candidate in candidates:
        queue.add(candidate, payload=dict(payload if payload is not None else STUB_PAYLOAD))
    return queue


def drain(queue, *, fetcher=None, extract=None, now=NOW, policy=DEFAULT_POLICY, org_id=None):
    return refetch_parked_attachments(
        queue, connector_for=lambda _c: fetcher if fetcher is not None else FakeFetcher(),
        eval_time=now, policy=policy, org_id=org_id,
        extract=extract if extract is not None else extractor_returning(accepted()))


# ── the acceptance criteria ──────────────────────────────────────────────────────────────────

@pytest.mark.gate
def test_an_attachment_that_failed_its_first_fetch_is_present_after_one_drain_cycle():
    """The spec's first acceptance sentence, asserted on the DATA rather than on the report."""
    queue = queue_with(park())
    report = drain(queue)

    assert report.claimed == 1 and report.recovered == 1
    # present: the event is emitted, its payload carries the document text, and the L1→L2 seam
    # (which is what `context/runner.py::_pull` actually reads) carries it too.
    assert queue.outcomes["evt_att"] == "emitted"
    assert queue.candidates["evt_att"].status == ParkStatus.RECOVERED.value
    assert "84,000" in queue.payloads["evt_att"]["body"]
    prepared = queue.recovered["evt_att"].prepared
    assert "Master Services Agreement" in prepared.clean_text
    # and the conversation it belonged to survived the recovery
    assert queue.payloads["evt_att"]["to"] == ["founder@genios.ai"]
    assert queue.payloads["evt_att"]["cc"] == ["cfo@genios.ai"]


@pytest.mark.gate
def test_after_five_failures_it_appears_in_the_admin_console_rather_than_vanishing():
    """The spec's second acceptance sentence. Five cycles, each one a transient failure, each one
    separated by the backoff the previous cycle scheduled."""
    queue = queue_with(park())
    fetcher = FakeFetcher(*[RuntimeError("ReadTimeout: upstream took too long")] * 5)
    clock = NOW
    for _ in range(5):
        drain(queue, fetcher=fetcher, now=clock)
        clock = queue.candidates["evt_att"].next_attempt_at or clock + timedelta(days=1)

    assert len(fetcher.calls) == 5, "the ladder ran exactly five times, not more"
    dead = queue.dead_letters(org_id="org_1")
    assert [d.event_id for d in dead] == ["evt_att"]
    assert dead[0].attempts == 5
    assert "ReadTimeout" in (dead[0].last_error or "")
    assert queue.outcomes["evt_att"] == "parked", "never emitted with an empty body"

    # and it is TERMINAL: a sixth cycle does not touch it
    drain(queue, fetcher=FakeFetcher(), now=clock + timedelta(days=1))
    assert len(fetcher.calls) == 5


# ── boundedness ──────────────────────────────────────────────────────────────────────────────

def test_a_permanently_deleted_attachment_stops_after_one_attempt():
    queue = queue_with(park())
    fetcher = FakeFetcher(RuntimeError("HTTP 404: message not found"))
    report = drain(queue, fetcher=fetcher)

    assert report.dead_lettered == 1 and report.retry_scheduled == 0
    assert queue.candidates["evt_att"].status == ParkStatus.DEAD_LETTER.value
    assert queue.candidates["evt_att"].attempts == 1, "one answer was enough"


def test_bytes_we_cannot_read_stop_the_ladder_and_say_which_capability_is_missing():
    """D1. The two assertions that used to close this test were:

        drain(queue, extract=extractor_returning(unreadable))
        dead = queue.dead_letters()
        assert len(dead) == 1

    i.e. one unreadable answer was a permanent dead letter. That is what turned the first
    heartbeat into a mass write-off: the drain runs with ``ocr=None``, and every DOC-02/04/06 park
    in the backlog is a file the toolchain already failed to read once. Stopping the FAST ladder
    is right — re-downloading a file we cannot parse every ten minutes is not progress — but the
    row stays recoverable on the capability clock, because what has to change for it to succeed
    is our code, and code ships.

    What must not change is the diagnosis: whichever state it lands in, it has to say which
    capability was missing, or "wire an engine" is invisible from the data.
    """
    queue = queue_with(park(reason_code="DOC-06"))
    unreadable = DocumentResult(text="", native_parse_used=False, ocr_used=False, ocr_engine=None,
                                ocr_pages=0, confidence_bp=None,
                                status=DocumentStatus.OCR_UNAVAILABLE.value,
                                detail="no OCR engine is wired")
    drain(queue, extract=extractor_returning(unreadable))

    row = queue.candidates["evt_att"]
    assert row.status == ParkStatus.PENDING.value
    assert row.next_attempt_at == NOW + DEFAULT_POLICY.capability_backoff, \
        "off the ten-minute network ladder, onto the capability clock"
    assert queue.dead_letters() == ()

    recorded = queue.settlements[-1]
    assert DocumentStatus.OCR_UNAVAILABLE.value in (recorded.last_error or "")
    assert "no OCR engine is wired" in (recorded.last_error or "")


def test_an_accepted_status_with_no_text_is_still_treated_as_unreadable():
    """`documents/base.py` makes this impossible by construction; a drain that trusted the status
    word alone would emit an empty body the day that invariant is loosened."""
    queue = queue_with(park())
    lying = DocumentResult(text="   ", native_parse_used=True, ocr_used=False, ocr_engine=None,
                           ocr_pages=1, confidence_bp=10_000,
                           status=DocumentStatus.ACCEPTED.value)
    drain(queue, extract=extractor_returning(lying))
    assert queue.outcomes["evt_att"] == "parked", "the load-bearing half: it is NOT emitted empty"
    # Was `== ParkStatus.DEAD_LETTER.value`. The status is incidental to what this test is
    # about — an empty body must never reach the ledger as `emitted` — and a document whose
    # parser returned whitespace is a CAPABILITY answer like any other, so it defers.
    assert queue.candidates["evt_att"].status == ParkStatus.PENDING.value
    assert queue.candidates["evt_att"].next_attempt_at == NOW + DEFAULT_POLICY.capability_backoff


def test_a_crash_between_claim_and_settle_still_burns_an_attempt():
    """The lease is what bounds a drain that dies mid-fetch. Without it, a document that crashes
    the process is retried forever and every cycle reports progress."""
    queue = queue_with(park())

    class Exploding:
        def fetch_attachment(self, message_id, attachment_id):
            raise KeyboardInterrupt("killed mid-fetch")

    with pytest.raises(KeyboardInterrupt):
        refetch_parked_attachments(queue, connector_for=lambda _c: Exploding(), eval_time=NOW,
                                   extract=extractor_returning(accepted()))
    assert queue.candidates["evt_att"].attempts == 1
    assert queue.candidates["evt_att"].next_attempt_at == NOW + DEFAULT_POLICY.lease


def test_a_missing_connector_is_retried_not_dead_lettered():
    """A disconnected source is usually reconnected; the ladder bounds it anyway."""
    queue = queue_with(park())
    report = refetch_parked_attachments(queue, connector_for=lambda _c: None, eval_time=NOW,
                                        extract=extractor_returning(accepted()))
    assert report.dead_lettered == 0 and report.retry_scheduled == 1
    assert queue.candidates["evt_att"].status == ParkStatus.PENDING.value


# ── selection and idempotency ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("row, claimed, why", [
    (park(), 1, "a due DOC-05 attachment"),
    (park(reason_code="DOC-02"), 1, "unsupported is a refetch reason too"),
    (park(reason_code="low_relevance"), 0, "not a document park"),
    (park(object_type="email_message"), 0, "the email, not its attachment"),
    (park(status=ParkStatus.RECOVERED.value), 0, "already recovered"),
    (park(status=ParkStatus.DEAD_LETTER.value), 0, "already given up on"),
    (park(parked_at=NOW - timedelta(minutes=2)), 0, "younger than the ten-minute floor"),
    (park(next_attempt_at=NOW + timedelta(hours=1)), 0, "still inside its backoff"),
    # CORRECTED, not weakened. This row read `0, "already exhausted"` and it encoded a black
    # hole: a park is only left `status='pending'` with `attempts == max_attempts` when a drain
    # was killed between the lease and the settlement on the final rung, and refusing to claim it
    # meant no later heartbeat could ever settle it. `read_aging` counts pending parks and never
    # looks at the attempt count, so the row stayed STUCK — permanently — in the one number G2
    # asserts is zero, and `RefetchPolicy.lease` promises the opposite in so many words: *"a
    # process that dies mid-fetch leaves a row that is bounded and re-attemptable, not one that
    # is invisible forever."* The bound belongs to `plan_refetch`, which returns DEAD_LETTER for
    # it before any I/O; claiming it once is how it reaches that decision.
    (park(attempts=5), 1, "exhausted — claimed once so the ladder can terminate it"),
])
def test_only_due_refetchable_attachments_are_claimed(row, claimed, why):
    queue = queue_with(row)
    assert drain(queue).claimed == claimed, why


def test_an_exhausted_park_is_claimed_once_and_then_never_again():
    """The other half of the corrected row: claiming a bounded-out park must SETTLE it, or the
    claim has traded a permanent pending row for a permanent claim loop."""
    queue = queue_with(park(attempts=5))
    first = drain(queue)
    assert first.claimed == 1 and first.dead_lettered == 1
    assert queue.candidates["evt_att"].status == ParkStatus.DEAD_LETTER.value
    later = drain(queue, now=NOW + timedelta(days=1))
    assert later.claimed == 0, "a settled park was claimed a second time"


def test_a_second_drain_does_not_re_emit_a_recovered_event():
    queue = queue_with(park())
    drain(queue)
    later = drain(queue, now=NOW + timedelta(days=1))
    assert later.claimed == 0
    assert queue.outcomes["evt_att"] == "emitted"


def test_the_org_filter_leaves_other_tenants_alone():
    queue = queue_with(park(), park(event_id="evt_other", org_id="org_2"))
    report = drain(queue, org_id="org_1")
    assert report.claimed == 1
    assert queue.candidates["evt_other"].status == ParkStatus.PENDING.value


def test_one_unrecoverable_attachment_does_not_stop_the_others():
    queue = queue_with(park(event_id="evt_a"), park(event_id="evt_b"))
    fetcher = FakeFetcher(RuntimeError("HTTP 404: not found"), b"%PDF bytes")
    report = drain(queue, fetcher=fetcher)
    assert (report.claimed, report.recovered, report.dead_lettered) == (2, 1, 1)


def test_a_provider_that_returns_no_bytes_is_a_transient_failure():
    queue = queue_with(park())
    report = drain(queue, fetcher=FakeFetcher(b""))
    assert report.retry_scheduled == 1
    assert queue.candidates["evt_att"].next_attempt_at == NOW + timedelta(seconds=600)


def test_the_filename_and_mime_come_from_the_stub_payload():
    """Neither is a column on the ledger; both decide the extractor and the addressability check."""
    queue = queue_with(park())
    seen: dict = {}

    def _extract(*, mime, data, filename, ocr):
        seen.update(mime=mime, filename=filename, data=data)
        return accepted()

    drain(queue, fetcher=FakeFetcher(b"%PDF bytes"), extract=_extract)
    assert seen["filename"] == "MSA-signed.pdf" and seen["mime"] == "application/pdf"
    assert seen["data"] == b"%PDF bytes"


# ── the observable surfaces ──────────────────────────────────────────────────────────────────

def test_recovered_text_is_pii_masked_before_it_reaches_the_seam():
    """`prepared_content` is the one place Layer 1 promises there is no raw PII. A recovery that
    skipped `preprocess` would put a contract's contact details there in clear."""
    queue = queue_with(park())
    drain(queue)
    clean = queue.recovered["evt_att"].prepared.clean_text
    assert "ABCDE1234F" not in clean and "[PAN]" in clean
    assert "MSA-signed.pdf" in clean, "the filename is prepended exactly as ingestion does it"


def test_the_backlog_is_ageable_and_the_stuck_count_is_the_gate_number():
    fresh = park(event_id="evt_fresh", parked_at=NOW - timedelta(minutes=20))
    old = park(event_id="evt_old", parked_at=NOW - timedelta(hours=9))
    email = park(event_id="evt_mail", object_type="email_message",
                 parked_at=NOW - timedelta(hours=9))
    queue = queue_with(fresh, old, email)

    aging = queue.aging(eval_time=NOW, policy=DEFAULT_POLICY)
    assert aging.pending == 3
    assert aging.stuck == 2                    # both of the nine-hour parks
    assert aging.stuck_attachments == 1        # G2 counts attachments
    assert aging.stuck_after_seconds == 3_600
    by_type = {(r.reason_code, r.object_type): r for r in aging.rows}
    assert by_type[("DOC-05", "email_attachment")].oldest_age_seconds == 9 * 3_600


def test_a_recovered_attachment_leaves_the_backlog():
    queue = queue_with(park())
    assert queue.aging(eval_time=NOW, policy=DEFAULT_POLICY).pending == 1
    drain(queue)
    assert queue.aging(eval_time=NOW, policy=DEFAULT_POLICY).pending == 0


def test_requeue_puts_a_capability_dead_letter_back_on_the_ladder():
    """`ocr_unavailable` means "not yet", not "lost". The day an engine is wired somebody has to
    be able to say so to the whole backlog at once.

    Reaching that dead letter now takes the whole ladder rather than one answer (D1: a capability
    gap defers on `capability_backoff` while attempts remain), so the test walks it. The requeue
    is still the operator's lever for the class that DID run out — and it is now a lever nobody
    has to remember, because the deferred rows drain themselves.
    """
    queue = queue_with(park(reason_code="DOC-06"))
    unreadable = DocumentResult(text="", native_parse_used=False, ocr_used=False, ocr_engine=None,
                                ocr_pages=0, confidence_bp=None,
                                status=DocumentStatus.OCR_UNAVAILABLE.value, detail="no engine")
    at = NOW
    for _ in range(DEFAULT_POLICY.max_attempts):
        drain(queue, now=at, extract=extractor_returning(unreadable))
        at += DEFAULT_POLICY.capability_backoff + timedelta(minutes=1)
    dead = queue.dead_letters()
    assert len(dead) == 1 and dead[0].failure_kind == "capability"

    assert queue.requeue_dead_letters(eval_time=at, reason_codes=frozenset({"DOC-06"})) == 1
    assert queue.candidates["evt_att"].attempts == 0
    report = drain(queue, now=at + timedelta(minutes=1))
    assert report.recovered == 1


def test_a_custom_policy_changes_the_bounds_it_states():
    """The bounds are a value, not module constants — an operator draining a backlog faster must
    not have to edit the module."""
    tight = RefetchPolicy(min_park_age=timedelta(0), max_attempts=2,
                          backoff_seconds=(60,), lease=timedelta(minutes=1))
    queue = queue_with(park(parked_at=NOW))
    fetcher = FakeFetcher(RuntimeError("timeout"), RuntimeError("timeout"))
    drain(queue, fetcher=fetcher, policy=tight)
    assert queue.candidates["evt_att"].next_attempt_at == NOW + timedelta(seconds=60)
    drain(queue, fetcher=fetcher, now=NOW + timedelta(seconds=61), policy=tight)
    assert queue.candidates["evt_att"].status == ParkStatus.DEAD_LETTER.value
