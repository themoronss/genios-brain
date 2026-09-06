"""G2 · L1.3.8-U2 — attachment presence overrides junk confidence on the Gmail fast path.

THE BUG THIS FILE PINS. `_to_batch` gates on the cheap LIST snippet and full-fetches only the
keepers, which is what makes a 2000-message backfill affordable. A message the classifier was
CONFIDENT was junk was never fetched — and a Gmail list entry carries no MIME payload, so `_walk`
found no attachment parts, no `email_attachment` event was ever constructed, and the PDF on that
message did not become a parked stub or a dropped event. It was never an object at all. A
junk-classified email with a real contract attached lost the contract, silently, at the connector.

WHAT THE FIX IS AND IS NOT. It buys the FETCH, not the email: the message still meets the pipeline
gate with the same verdict and is still dropped. What changes is that the attachment gets to be its
own event and be judged on its own merits. The tests below assert both halves, because a "fix" that
also kept the newsletters would be a recall win and a cost regression, and nobody would notice
until the Composio bill.
"""

from __future__ import annotations

import base64

import pytest

from genios_engine.capture.connectors.composio import (ComposioGmailConnector,
                                                       attachment_overrides_junk)
from genios_engine.capture.gate.relevance import RelevanceVerdict

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _part(mime: str, filename: str, att_id: str = "a1") -> dict:
    return {"mimeType": mime, "filename": filename, "body": {"attachmentId": att_id}}


def _connector(*, ocr=None, relevance=None) -> ComposioGmailConnector:
    conn = ComposioGmailConnector.__new__(ComposioGmailConnector)   # skip __init__ (no network)
    conn._ocr = ocr
    conn._relevance = relevance
    conn._account = None
    return conn


# ── the predicate ────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("message, ocr_enabled, expected, why", [
    ({"payload": {"parts": [_part(PDF, "MSA-signed.pdf")]}}, False, True,
     "a PDF is exactly what the spec says must never be fast-path dropped"),
    ({"payload": {"parts": [_part(DOCX, "SOW.docx")]}}, False, True, "office formats too"),
    ({"payload": {"parts": [_part("text/plain", "terms.txt")]}}, False, True, "and plain text"),
    ({"payload": {"parts": [_part("", "MSA-countersigned.pdf")]}}, False, True,
     "a blank mimeType with a .pdf name is a PDF, not an unknown format"),
    ({"payload": {"parts": [_part("application/zip", "export.zip")]}}, False, False,
     "we could not read it even after paying for the download"),
    ({"payload": {"parts": [_part("text/calendar", "invite.ics")]}}, False, False,
     "calendar invites are most of the attachment volume on junk mail"),
    ({"payload": {"parts": [_part("image/png", "invoice-scan.png")]}}, False, False,
     "an image is unreadable with no OCR engine wired"),
    ({"payload": {"parts": [_part("image/png", "invoice-scan.png")]}}, True, True,
     "the same image IS readable once OCR is wired — same test the download path applies"),
    ({"payload": {"parts": [_part("text/plain", "")]}}, False, False,
     "a body part is not an attachment"),
    ({"hasAttachment": True}, False, True,
     "an opaque flag: the only way to learn the type is to fetch"),
    ({"attachmentIds": ["a1"]}, False, True, "same, in another spelling"),
    ({"attachments": []}, False, False, "an empty list is not an attachment"),
    ({"hasAttachment": False}, False, False, "explicitly none"),
    ({"has_attachment": "true"}, False, True, "providers send booleans as strings"),
    ({}, False, False, "no signal at all"),
    ({"payload": {"parts": []}}, False, False, "a payload with no parts"),
    ("not a dict", False, False, "a malformed list entry decides nothing"),
])
def test_the_override_rule_covers_every_attachment_signal(message, ocr_enabled, expected, why):
    assert attachment_overrides_junk(message, [], ocr_enabled=ocr_enabled) is expected, why


def test_a_typed_part_beats_an_opaque_flag_that_disagrees():
    """When the list payload names the parts we can type them, and an unreadable .zip must not be
    rescued by a generic `hasAttachment: true` sitting next to it."""
    message = {"hasAttachment": True,
               "payload": {"parts": [_part("application/zip", "export.zip")]}}
    assert attachment_overrides_junk(message, []) is False


def test_attachment_objects_built_by_the_light_pass_are_also_a_signal():
    """The light pass sees the list entry in two shapes; reading only the raw payload would make
    the override depend on which one the provider happened to send."""
    conn = _connector()
    light = conn._to_objects({"id": "m1", "from": "a@b.io", "subject": "s",
                              "payload": {"parts": [_part(PDF, "deck.pdf")]}},
                             fetch_full=False)
    assert any(o.object_type == "email_attachment" for o in light)
    assert attachment_overrides_junk({"id": "m1"}, light) is True


# ── the fast path ────────────────────────────────────────────────────────────────────────────

class _Classifier:
    """The S2 gate, primed, answering `drop` for every message.

    `relevance` is a RELEVANCE score, so CONFIDENT junk is a LOW one: `_skip_body` leaves the body
    unfetched only below `DROP_BELOW_RELEVANCE` (0.25), and anything above it is a drop the gate
    is unsure enough about that it will park — and a park needs a body. The default here is
    therefore 0.05, the confident-junk case this component is about.
    """

    def __init__(self, relevance: float = 0.05):
        self.relevance = relevance
        self.primed: list = []

    def prime(self, objects):
        self.primed.extend(objects)

    def verdict_for(self, source_object_id):
        return RelevanceVerdict(relevant=False, relevance=self.relevance, disposition="drop")


class _Gmail(ComposioGmailConnector):
    """A connector whose network is a dict: `_full_message` returns the MIME payload the LIST
    response deliberately does not carry, which is the whole asymmetry the bug lived in."""

    def __init__(self, full: dict, *, ocr=None, relevance=None):
        self._ocr = ocr
        self._relevance = relevance
        self._account = None
        self._full = full
        self.full_fetches: list[str] = []

    def _full_message(self, mid):
        self.full_fetches.append(mid)
        return self._full

    def _attachment_bytes(self, mid, attachment_id):
        return b"%PDF-1.7 fake contract bytes"


_FULL_WITH_PDF = {"id": "m1", "from": "deals@vendor.io", "subject": "Q3 promo",
                  "payload": {"parts": [
                      {"mimeType": "text/plain", "filename": "", "body": {"data": _b64("hi")}},
                      _part(PDF, "MSA-signed.pdf")]}}


def _list_entry(**overrides) -> dict:
    entry = {"id": "m1", "from": "deals@vendor.io", "subject": "Q3 promo",
             "messageText": "Big savings this quarter"}
    entry.update(overrides)
    return entry


@pytest.mark.gate
def test_a_confidently_junk_message_with_an_attachment_is_still_full_fetched():
    """The spec's sentence, as a behaviour: the contract survives a confident junk verdict."""
    conn = _Gmail(_FULL_WITH_PDF, relevance=_Classifier())
    batch = conn._to_batch({"data": {"messages": [_list_entry(hasAttachment=True)]}})

    assert conn.full_fetches == ["m1"], "the attachment signal forced the body fetch"
    attachments = [o for o in batch.objects if o.object_type == "email_attachment"]
    assert len(attachments) == 1
    assert attachments[0].raw["subject"] == "MSA-signed.pdf"
    assert attachments[0].parent_object_id == "m1", "still linked to the message it rode in on"


def test_the_email_itself_is_not_rescued_by_its_attachment():
    """Only the fetch is bought. The message still carries the junk verdict the classifier gave
    it and is dropped by the pipeline gate — this is a recall fix, not a filter rollback."""
    classifier = _Classifier()
    conn = _Gmail(_FULL_WITH_PDF, relevance=classifier)
    batch = conn._to_batch({"data": {"messages": [_list_entry(hasAttachment=True)]}})

    email = [o for o in batch.objects if o.object_type == "email_message"]
    assert len(email) == 1
    assert classifier.verdict_for(email[0].source_object_id).disposition == "drop"


def test_a_confidently_junk_message_with_no_attachment_is_still_cheap():
    """The regression guard. If the override fired on every message the fast path would be gone
    and a backfill would pay a round-trip per newsletter."""
    conn = _Gmail(_FULL_WITH_PDF, relevance=_Classifier())
    batch = conn._to_batch({"data": {"messages": [_list_entry()]}})

    assert conn.full_fetches == [], "no attachment signal → no body fetch"
    assert all(o.object_type != "email_attachment" for o in batch.objects)


def test_an_unreadable_attachment_does_not_defeat_the_fast_path():
    conn = _Gmail(_FULL_WITH_PDF, relevance=_Classifier())
    conn._to_batch({"data": {"messages": [
        _list_entry(payload={"parts": [_part("application/zip", "export.zip")]})]}})
    assert conn.full_fetches == []


def test_an_unconfident_drop_is_still_full_fetched_without_any_attachment():
    """Pre-existing behaviour that must survive: below DROP_BELOW_RELEVANCE the gate PARKS, and a
    park needs a body to be worth anything."""
    conn = _Gmail(_FULL_WITH_PDF, relevance=_Classifier(relevance=0.90))
    conn._to_batch({"data": {"messages": [_list_entry()]}})
    assert conn.full_fetches == ["m1"]


def test_the_deterministic_prefilter_also_yields_to_an_attachment():
    """PROMOTIONS is a confident deterministic drop that never even costs an LLM call — and it was
    dropping contracts too. The mail is still junk; the file still has to be looked at."""
    promo = _list_entry(labelIds=["CATEGORY_PROMOTIONS"], hasAttachment=True)
    conn = _Gmail(_FULL_WITH_PDF, relevance=_Classifier())
    batch = conn._to_batch({"data": {"messages": [promo]}})
    assert conn.full_fetches == ["m1"]
    assert any(o.object_type == "email_attachment" for o in batch.objects)


def test_a_promotions_message_with_no_attachment_is_still_prefiltered():
    conn = _Gmail(_FULL_WITH_PDF, relevance=_Classifier())
    conn._to_batch({"data": {"messages": [_list_entry(labelIds=["CATEGORY_PROMOTIONS"])]}})
    assert conn.full_fetches == []


# ── the honest fetch (L1.3.8-U1's provider seam) ─────────────────────────────────────────────

class _Executing(ComposioGmailConnector):
    def __init__(self, response):
        self._ocr = None
        self._relevance = None
        self._account = None
        self._response = response

    def _execute(self, slug, arguments):
        if isinstance(self._response, BaseException):
            raise self._response
        return self._response


def test_fetch_attachment_returns_the_decoded_bytes():
    conn = _Executing({"data": {"data": _b64("contract bytes")}})
    assert conn.fetch_attachment("m1", "a1") == b"contract bytes"


@pytest.mark.parametrize("response, match, why", [
    ({"data": {"data": ""}}, "no attachment data", "an empty body is a failure, not a document"),
    ({"successful": False, "error": "404 message not found"}, "404 message not found",
     "Composio reports a tool failure in the envelope rather than by raising"),
    (RuntimeError("ReadTimeout"), "ReadTimeout", "and a transport error propagates"),
])
def test_fetch_attachment_raises_with_the_reason_the_ladder_needs(response, match, why):
    with pytest.raises(Exception, match=match):
        _Executing(response).fetch_attachment("m1", "a1")


def test_fetch_attachment_refuses_a_reference_that_is_only_a_filename():
    with pytest.raises(ValueError, match="only a filename"):
        _Executing({}).fetch_attachment("m1", "")


@pytest.mark.parametrize("response", [
    {"data": {"data": ""}},
    {"successful": False, "error": "404"},
    RuntimeError("boom"),
])
def test_the_sync_path_still_swallows_every_one_of_those(response):
    """`_attachment_bytes` keeps its old contract exactly — one unreadable file must never abort a
    2000-message batch. Only the refetch ladder, which needs the reason, calls the raising one."""
    assert _Executing(response)._attachment_bytes("m1", "a1") == b""


def test_the_sync_path_still_swallows_a_missing_attachment_id():
    assert _Executing({})._attachment_bytes("m1", None) == b""
