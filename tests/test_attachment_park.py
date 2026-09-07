from __future__ import annotations

import base64

from genios_engine.capture.connectors.composio import ComposioGmailConnector
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event

# Gmail attachments used to be SILENTLY dropped: an unsupported MIME (csv/zip/screenshot) or a
# failed download hit a bare `continue` — no event, no park, no trace, batch reports success, so
# an invoice/contract just vanished. Now a real named file lands as a stub that PARKS (DOC-02
# unsupported / DOC-05 fetch_failed, reviewable + retryable). Inline signature images / pixels
# stay skipped so the parked queue doesn't flood.


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def _msg(parts: list[dict], mid: str = "m1", sender: str = "vendor@acme.io") -> dict:
    return {"id": mid, "payload": {"parts": parts}, "from": sender, "subject": "hi"}


def _conn() -> ComposioGmailConnector:
    conn = ComposioGmailConnector.__new__(ComposioGmailConnector)   # skip __init__ (no network)
    conn._ocr = None
    return conn


def _park_reason(att):
    res = capture_event(att, org_id="o", connection_id="c", repo=InMemorySourceEventRepository())
    return res.outcome, res.trace.records[-1].reason_code


def test_unsupported_named_attachment_becomes_a_stub_that_parks():
    conn = _conn()
    parts = [{"mimeType": "text/plain", "filename": "", "body": {"data": _b64("Hello.")}},
             {"mimeType": "application/zip", "filename": "export.zip", "body": {"attachmentId": "a1"}}]
    objs = conn._to_objects(_msg(parts))
    atts = [o for o in objs if o.object_type == "email_attachment"]
    assert len(atts) == 1
    assert atts[0].raw["document"]["status"] == "unsupported"
    assert atts[0].raw["has_attachment"] is True and atts[0].raw["body"] == ""
    assert _park_reason(atts[0]) == ("parked", "DOC-02")        # NOT silently dropped


def test_worthy_attachment_failed_download_parks_as_retryable(monkeypatch):
    conn = _conn()
    monkeypatch.setattr(conn, "_attachment_bytes", lambda *a, **k: b"")   # simulate a failed download
    parts = [{"mimeType": "application/pdf", "filename": "invoice.pdf", "body": {"attachmentId": "a9"}}]
    objs = conn._to_objects(_msg(parts, mid="m2"))
    atts = [o for o in objs if o.object_type == "email_attachment"]
    assert len(atts) == 1
    assert atts[0].raw["document"]["status"] == "fetch_failed"
    assert _park_reason(atts[0]) == ("parked", "DOC-05")        # retryable, never silent


def test_inline_signature_image_is_still_skipped_no_flood():
    conn = _conn()
    parts = [{"mimeType": "image/png", "filename": "image001.png", "body": {"attachmentId": "a2"}}]
    objs = conn._to_objects(_msg(parts, mid="m3"))
    assert all(o.object_type != "email_attachment" for o in objs)     # no stub → no parked-queue flood


def test_real_screenshot_invoice_parks_as_ocr_unavailable_not_unsupported():
    """A screenshot invoice with no OCR engine is READABLE IN PRINCIPLE, and the park code has to
    say so. `unsupported` (DOC-02) means nothing can ever read this file; `ocr_unavailable`
    (DOC-06) means the engine is not wired on this host — one config line and a redeploy. The two
    read identically in a queue and are opposite facts about the same file, and production filed
    681 of these under the terminal one, which is why the OCR gap was invisible."""
    conn = _conn()
    parts = [{"mimeType": "image/png", "filename": "invoice-scan.png", "body": {"attachmentId": "a3"}}]
    objs = conn._to_objects(_msg(parts, mid="m4"))
    atts = [o for o in objs if o.object_type == "email_attachment"]
    assert len(atts) == 1 and atts[0].raw["document"]["status"] == "ocr_unavailable"
    assert _park_reason(atts[0]) == ("parked", "DOC-06")       # in NEEDS_REFETCH → drainable


def test_a_scanned_pdf_whose_download_is_skipped_is_not_called_unsupported():
    """The same distinction reached by extension rather than by MIME: some senders attach a PDF
    with a generic `application/octet-stream` type, and the pre-download skip judges it on the
    filename. It has pages either way."""
    conn = _conn()
    parts = [{"mimeType": "application/octet-stream", "filename": "PO-8841.pdf",
              "body": {"attachmentId": "a4"}}]
    objs = conn._to_objects(_msg(parts, mid="m5"))
    atts = [o for o in objs if o.object_type == "email_attachment"]
    assert len(atts) == 1 and atts[0].raw["document"]["status"] == "ocr_unavailable"


def test_a_true_binary_is_still_terminal_unsupported():
    """The other half of the rule: a .zip has no pages, no text layer and no audio. Widening
    DOC-06 to everything would put files nothing can read into a retry ladder for ever."""
    conn = _conn()
    parts = [{"mimeType": "application/zip", "filename": "export.zip", "body": {"attachmentId": "a5"}}]
    objs = conn._to_objects(_msg(parts, mid="m6"))
    atts = [o for o in objs if o.object_type == "email_attachment"]
    assert len(atts) == 1 and atts[0].raw["document"]["status"] == "unsupported"
