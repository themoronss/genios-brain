"""L1 rebuild G3 — a big attachment never stalls a sync, and a long one is read in full.

Before: no byte ceiling (a 25 MB file was downloaded and parsed inside the page), and a text longer
than the `document` profile's one call (40,000 characters) made `assemble_call` raise — inside a
capture that is two retries and the poison queue: the contract was lost.

Now:
  * over `_MAX_ATTACHMENT_BYTES` the file is not downloaded; it becomes a `too_large` stub the gate
    parks as DOC-10, for the refetch ladder;
  * a text over `_ATTACHMENT_CHUNK_CHARS` becomes one event per section-aware piece, each under the
    ceiling, in order, with its offsets into the whole file — nothing cut;
  * whatever still reaches the extractor too long parks as `extraction_oversized`, with no call.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

from genios_engine.capture.connectors import composio as C
from genios_engine.capture.documents.chunking import sections_within
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.rules import content_integrity_rule


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


class _Gmail(C.ComposioGmailConnector):
    def __init__(self):
        self._ocr = None
        self._relevance = None
        self._account = None
        self.downloads: list[str] = []

    def _attachment_bytes(self, mid, attachment_id, file_name=None):
        self.downloads.append(attachment_id)
        return b"small file"


def _message(*parts) -> dict:
    return {"id": "m1", "from": "legal@vendor.test", "subject": "Signed MSA",
            "payload": {"parts": [{"mimeType": "text/plain", "filename": "",
                                   "body": {"data": _b64("Please find attached.")}},
                                  *parts]}}


def _contract(chars: int) -> str:
    clause = "The supplier shall deliver the services described in Schedule 2. "
    sections = []
    for n in range(1, 400):
        sections.append(f"\n\n{n}. CLAUSE {n}\n\n" + clause * 12)
        if sum(map(len, sections)) > chars:
            break
    return "".join(sections)


def test_a_file_over_the_byte_ceiling_is_not_downloaded_and_parks_as_doc10():
    conn = _Gmail()
    part = {"mimeType": "application/pdf", "filename": "deck.pdf",
            "body": {"attachmentId": "att_big", "size": C._MAX_ATTACHMENT_BYTES + 1}}
    objs = conn._to_objects(_message(part), fetch_full=False)

    att = [o for o in objs if o.object_type == "email_attachment"]
    assert conn.downloads == [], "the sync must not download a file over the ceiling"
    assert len(att) == 1 and att[0].raw["document"]["status"] == "too_large"
    ctx = GateContext(event=None, prepared=None, raw=att[0].raw)
    assert content_integrity_rule(ctx) == ("DOC-10", "park")


def test_a_file_under_the_ceiling_is_downloaded_as_before():
    conn = _Gmail()
    part = {"mimeType": "text/plain", "filename": "notes.txt",
            "body": {"attachmentId": "att_small", "size": 2_000}}
    conn._to_objects(_message(part), fetch_full=False)
    assert conn.downloads == ["att_small"]


def test_a_long_attachment_becomes_ordered_pieces_that_cover_it_all():
    text = _contract(C._ATTACHMENT_CHUNK_CHARS * 2 + 5_000)
    part = {"mimeType": "text/plain", "filename": "MSA.txt", "body": {"data": _b64(text)}}
    objs = _Gmail()._to_objects(_message(part), fetch_full=False)

    pieces = [o for o in objs if o.object_type == "email_attachment"]
    assert len(pieces) >= 3
    assert [o.source_object_id.rsplit("#c", 1)[1] for o in pieces] == [
        str(i) for i in range(len(pieces))]
    assert all(len(o.raw["body"]) <= C._ATTACHMENT_CHUNK_CHARS for o in pieces)
    assert all(o.raw["chunk"]["count"] == len(pieces) for o in pieces)
    assert all(o.parent_object_id == "m1" for o in pieces)
    # nothing cut: every character of the file is inside some piece, at its own offset
    covered = sum(o.raw["chunk"]["end_offset"] - o.raw["chunk"]["start_offset"] for o in pieces)
    assert covered >= len(text.strip()) - len(pieces) * 4
    for o in pieces:
        start = o.raw["chunk"]["start_offset"]
        assert text[start:start + 40].strip()[:20] == o.raw["body"].strip()[:20]


def test_a_short_attachment_is_one_event_with_the_same_id_as_before():
    part = {"mimeType": "text/plain", "filename": "notes.txt", "body": {"data": _b64("short")}}
    objs = _Gmail()._to_objects(_message(part), fetch_full=False)
    att = [o for o in objs if o.object_type == "email_attachment"]
    assert len(att) == 1 and "#c" not in att[0].source_object_id and "chunk" not in att[0].raw


def test_sections_within_keeps_every_piece_under_the_cap():
    text = _contract(100_000)
    pieces = sections_within(text, max_chars=10_000)
    assert pieces and all(len(p.text) <= 10_000 for p in pieces)
    assert [p.index for p in pieces] == list(range(len(pieces)))


def test_content_too_long_for_one_call_parks_with_no_model_call():
    """Through `extract` itself (the call site), not only the helper: an over-long content returns a
    park row and the model is never asked."""
    from types import SimpleNamespace

    from genios_engine.capture.semantic import extractor as X
    from genios_engine.capture.semantic.profiles import PROFILES

    class _NoCall:
        model = "m"
        temperature = 0

        def call(self, *a, **kw):
            raise AssertionError("an oversized content must not reach the model")

    profile = PROFILES["document"]
    request = SimpleNamespace(
        event_id="evt_long", org_id="o", source="gmail", profile=profile,
        content="word " * (profile.max_input_chars // 4),
        eval_time=datetime(2026, 10, 1, tzinfo=timezone.utc))
    out = X.extract(request, llm=_NoCall())
    assert out.result is None and out.parked is not None
    assert out.parked.reason_code == X.PARK_OVERSIZED
    assert out.parked.trace[0]["content_chars"] > profile.max_input_chars
