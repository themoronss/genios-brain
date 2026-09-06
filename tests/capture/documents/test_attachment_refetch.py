"""G2 · document acquisition — the FIRST clause of the gate, now a real assertion.

    pytest tests/capture/structural tests/capture/documents tests/capture/structured -q
    python scripts/l1_s1_report.py --org <pilot> --since 30d

Expected on the pilot: **0** attachments stuck in `NEEDS_REFETCH` for more than an hour, and
**0** documents carrying empty text with no `ocr_failed` marker.

The second clause has been a real gate since L1.3.4 landed:
`test_document_router.py::test_G2_no_document_is_ever_empty_without_saying_why` asserts it on
every branch of the router.

THE FIRST CLAUSE WAS STILL A PLACEHOLDER, AND THAT WAS THE DEFECT. This file called
`l1_pending(W2, G2, "capture/ attachment resolver refetch drain (L1.3.8)")` — a declared skip
naming a wave that had not landed. L1.3.8 HAS landed: `capture/parked/refetch.py` owns the queue,
`refetch_parked_attachments` is the drain, `PostgresRefetchQueue` is the real one, and
`api/routes.py::_drain_attachment_refetch` runs it on the heartbeat. `tests/conftest.py::l1_pending`
states the contract this file was breaking, in its own words:

    A skip is not a pass — the plan says so in those words — so these are counted, not ignored …
    and the wave that lands the code deletes the placeholder and writes the gate.

So the gate command reported ``1 skipped`` for a component that was in production. The whole point
of the placeholder mechanism is that a skip means "not built yet"; a stale one means "built, and
nobody checked", which is the more expensive of the two and reads identically.

WHAT THE GATE ASSERTS. The clause is *attachments stuck in NEEDS_REFETCH* — so the property is
that a NEEDS_REFETCH park LEAVES that state, in both directions: recovered when the bytes arrive
and are readable, dead-lettered when the ladder runs out. A park that only ever leaves on success
would satisfy "it can be recovered" while the stuck count grew from everything that could not be.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.documents.base import DocumentResult, DocumentStatus
from genios_engine.capture.parked.drain import NEEDS_REFETCH
from genios_engine.capture.parked.refetch import (DEFAULT_POLICY, InMemoryRefetchQueue,
                                                  refetch_parked_attachments)
from genios_engine.capture.parked.refetch_policy import ParkStatus, RefetchCandidate

WAVE = "W2"
GATE = "G2"

NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)
ORG = "org_g2_refetch"
CONTRACT = ("Master Services Agreement. Total contract value $84,000, payable annually, "
            "with a ninety day notice-and-cure period.")


def _parked_attachment(*, event_id: str = "evt_att", reason: str = "DOC-05",
                       attempts: int = 0,
                       parked_at: datetime | None = None) -> RefetchCandidate:
    """The stub `connectors/composio.py::_attachment_stub` writes: an id, a name, no bytes."""
    return RefetchCandidate(
        event_id=event_id, org_id=ORG, reason_code=reason, status=ParkStatus.PENDING.value,
        object_type="email_attachment", source="gmail",
        source_object_id="m123::att456", parent_object_id="m123", connection_id="conn_1",
        parked_at=parked_at or (NOW - timedelta(hours=3)), attempts=attempts,
        filename="MSA-signed.pdf", mime="application/pdf")


#: The stub payload the pipeline retained — `body: ""` is why re-adjudicating it cannot work and
#: why this class needs the connector rather than the drain.
_STUB_PAYLOAD = {"subject": "MSA-signed.pdf", "body": "", "mime": "application/pdf",
                 "has_attachment": True, "to": ["founder@genios.ai"],
                 "document": {"status": DocumentStatus.FETCH_FAILED.value}}


class _Connector:
    """A tenant connector that either hands back bytes or refuses, on demand."""

    source = "gmail"

    def __init__(self, data: bytes | None = b"%PDF-1.4 contract bytes",
                 error: str | None = None) -> None:
        self._data, self._error = data, error
        self.calls: list[tuple[str, str]] = []

    def fetch_attachment(self, message_id: str, attachment_id: str) -> bytes:
        self.calls.append((message_id, attachment_id))
        if self._error is not None:
            raise RuntimeError(self._error)
        return self._data or b""


def _extractor_reading(text: str):
    def _extract(*, mime: str, data: bytes, filename: str, ocr):
        return DocumentResult(text=text, status=DocumentStatus.ACCEPTED.value,
                              native_parse_used=True, ocr_used=False, ocr_engine=None,
                              ocr_pages=0, confidence_bp=10_000)
    return _extract


def _drain(queue, connector, *, eval_time=NOW, extract=None):
    return refetch_parked_attachments(queue, connector_for=lambda *_a, **_k: connector,
                                      eval_time=eval_time,
                                      extract=extract or _extractor_reading(CONTRACT))


def _queue_with(candidate: RefetchCandidate) -> InMemoryRefetchQueue:
    queue = InMemoryRefetchQueue()
    queue.add(candidate, payload=dict(_STUB_PAYLOAD))
    return queue


@pytest.mark.gate
def test_a_needs_refetch_attachment_is_retried_and_leaves_that_state():
    """L1.3.8-U1, the gate clause itself: the park does not stay `pending`."""
    queue = _queue_with(_parked_attachment())
    connector = _Connector()

    report = _drain(queue, connector)

    assert connector.calls == [("m123", "att456")], "the provider was never asked"
    assert report.claimed == 1 and report.recovered == 1, report
    assert queue.candidates["evt_att"].status == ParkStatus.RECOVERED.value


@pytest.mark.gate
def test_the_recovered_document_carries_the_text_the_stub_never_had():
    """"Left NEEDS_REFETCH" is worth nothing if the row leaves empty — that is the same silent
    loss with a green queue. The recovered payload and the prepared seam must both carry it."""
    queue = _queue_with(_parked_attachment())
    _drain(queue, _Connector())

    recovered = queue.recovered["evt_att"]
    assert recovered.text_chars == len(CONTRACT)
    assert recovered.payload["body"] == CONTRACT
    assert recovered.payload["subject"] == "MSA-signed.pdf", "the stub's own facts were lost"
    assert recovered.payload["to"] == ["founder@genios.ai"], "the conversation was lost"
    assert CONTRACT in recovered.prepared.clean_text, "L2 reads prepared_content, not the payload"
    assert recovered.payload["document"]["recovered_by"] == "l1_3_8_attachment_resolver"


@pytest.mark.gate
def test_the_event_is_re_emitted_so_a_layer_above_can_see_the_contract():
    """A recovered document that leaves `source_events.outcome='parked'` is recovered into a
    place nothing reads."""
    queue = _queue_with(_parked_attachment())
    _drain(queue, _Connector())
    assert queue.outcomes["evt_att"] == "emitted"


#: Every NEEDS_REFETCH code, driven through the whole drain. Named individually so a failure
#: says WHICH class of park is stuck rather than that "the queue" is.
@pytest.mark.gate
@pytest.mark.parametrize("reason", sorted(NEEDS_REFETCH))
def test_every_needs_refetch_code_leaves_the_state_when_the_bytes_arrive(reason):
    queue = _queue_with(_parked_attachment(reason=reason))
    report = _drain(queue, _Connector())
    assert report.recovered == 1, f"{reason} was not drained: {report}"
    assert queue.candidates["evt_att"].status != ParkStatus.PENDING.value


@pytest.mark.gate
def test_a_park_that_cannot_be_recovered_ALSO_leaves_the_state():
    """The other direction, and the one a success-only gate would miss: the stuck count is what
    G2 measures, and a park that can never succeed must terminate rather than accumulate."""
    exhausted = _parked_attachment(attempts=DEFAULT_POLICY.max_attempts)
    queue = _queue_with(exhausted)

    report = _drain(queue, _Connector(error="429 Too Many Requests"))

    assert report.dead_lettered == 1, report
    assert queue.candidates["evt_att"].status == ParkStatus.DEAD_LETTER.value


@pytest.mark.gate
def test_nothing_is_left_stuck_after_the_ladder_is_walked_to_its_end():
    """The gate's actual number — *0 attachments stuck over 1h* — driven end to end: a park that
    fails every time must reach a terminal state within `max_attempts` cycles, and the aging
    surface must then report zero stuck."""
    queue = _queue_with(_parked_attachment())
    connector = _Connector(error="500 Internal Server Error")

    at = NOW
    for _ in range(DEFAULT_POLICY.max_attempts + 1):
        _drain(queue, connector, eval_time=at)
        at += timedelta(days=1)                     # past every rung of the ladder

    assert queue.candidates["evt_att"].status == ParkStatus.DEAD_LETTER.value
    aging = queue.aging(eval_time=at, policy=DEFAULT_POLICY, org_id=ORG)
    assert aging.stuck_attachments == 0, (
        f"an attachment is still stuck after the ladder ran out: {aging}")
    assert connector.calls, "the provider was never asked, so nothing was proved"


@pytest.mark.gate
def test_a_park_too_young_to_have_settled_is_not_attempted_and_is_not_stuck():
    """`min_park_age` exists because the sync that parked it may still be running. A park inside
    that window is neither retried nor counted as stuck — otherwise every fresh park would fail
    the gate for ten minutes."""
    fresh = _parked_attachment(parked_at=NOW - timedelta(minutes=1))
    queue = _queue_with(fresh)
    connector = _Connector()

    report = _drain(queue, connector)

    assert connector.calls == [], "a park younger than min_park_age reached the provider"
    assert report.recovered == 0
    aging = queue.aging(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG)
    assert aging.stuck_attachments == 0, aging
