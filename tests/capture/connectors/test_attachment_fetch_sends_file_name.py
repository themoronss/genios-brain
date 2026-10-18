"""STEP-18 B19 · a Gmail attachment is fetched, not refused.

    pytest tests/capture/connectors/test_attachment_fetch_sends_file_name.py -q

⛔ WHAT WAS WRONG. Composio's `GMAIL_GET_ATTACHMENT` requires `file_name` (toolkit 20260915_00:
"Desired filename for the downloaded attachment. This is a required string field"), and the
connector sent only `message_id` and `attachment_id` — with the toolkit version unpinned
(`dangerously_skip_version_check=True`). Every fetch was refused: "Invalid request data provided -
Value error, Missing required fields: file_name". On the design partner's org, 88 of 88 stored
refetch errors were that sentence; 50 dead-lettered after five tries; 0 ever recovered. Capture
swallowed the same refusal into an empty stub, so no attachment was read at all.

AND WHAT IS NOT YET KNOWN. The toolkit documents its `data` only as "data from the action
execution". So a response with no bytes the connector can read fails LOUDLY and names its own
shape — keys and value types, never a value — and the first refetch after the deploy writes that
shape into `parked_events.refetch_last_error`, where it can be read back without reading content.
"""

from __future__ import annotations

import base64

import pytest

from genios_engine.capture.connectors.composio import ComposioGmailConnector


class _Recording(ComposioGmailConnector):
    def __init__(self, response):
        self._ocr = None
        self._relevance = None
        self._account = None
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    def _execute(self, slug, arguments):
        self.calls.append((slug, dict(arguments)))
        return self._response


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def test_the_fetch_sends_the_field_the_toolkit_requires():
    conn = _Recording({"data": {"data": _b64("pdf bytes")}})
    assert conn.fetch_attachment("m1", "a1") == b"pdf bytes"
    slug, args = conn.calls[0]
    assert slug == "GMAIL_GET_ATTACHMENT"
    assert args["message_id"] == "m1" and args["attachment_id"] == "a1"
    assert isinstance(args.get("file_name"), str) and args["file_name"].strip(), (
        "file_name is required by GMAIL_GET_ATTACHMENT and must never be empty or None")


def test_the_attachments_own_name_is_sent_when_the_caller_has_it():
    conn = _Recording({"data": {"data": _b64("x")}})
    conn.fetch_attachment("m1", "a1", file_name="Phase-1 review.pdf")
    assert conn.calls[0][1]["file_name"] == "Phase-1 review.pdf"


def test_the_capture_path_passes_the_filename_through():
    conn = _Recording({"data": {"data": _b64("x")}})
    assert conn._attachment_bytes("m1", "a1", "MSA.pdf") == b"x"
    assert conn.calls[0][1]["file_name"] == "MSA.pdf"


def test_a_response_with_no_readable_bytes_names_its_shape_and_never_a_value():
    """The shape is what the next change needs; a value would be content in an error log."""
    conn = _Recording({"successful": True,
                       "data": {"file": {"name": "Khushi-term-sheet.pdf",
                                         "s3url": "https://s3.example/secret?sig=abc",
                                         "size": 48211}}})
    with pytest.raises(RuntimeError, match="no attachment data") as err:
        conn.fetch_attachment("m1", "a1")
    text = str(err.value)
    for key in ("data", "file", "name", "s3url", "size"):
        assert key in text, f"the shape omits the key {key!r}: {text}"
    for leaked in ("Khushi", "term-sheet", "s3.example", "sig=abc", "48211"):
        assert leaked not in text, f"the error leaked a value ({leaked!r}): {text}"


def test_the_sync_path_still_swallows_a_refusal():
    """`_attachment_bytes` keeps its contract: one unreadable file never aborts a batch."""
    conn = _Recording({"successful": False, "error": "Missing required fields: file_name"})
    assert conn._attachment_bytes("m1", "a1", "x.pdf") == b""
