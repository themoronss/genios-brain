from __future__ import annotations

from genios_engine.capture.documents.base import DocumentInput
from genios_engine.capture.documents.fake import FakeOcr
from genios_engine.capture.documents.router import route_document


def test_text_pdf_parses_natively_without_ocr():
    doc = DocumentInput(mime="application/pdf", filename="proposal.pdf",
                        text_layer="This proposal covers the pilot scope and pricing.")
    r = route_document(doc, ocr=FakeOcr())
    assert r.native_parse_used and not r.ocr_used
    assert r.status == "accepted"


def test_scanned_good_quality_routes_through_ocr_and_accepts():
    doc = DocumentInput(mime="application/pdf", filename="scan.pdf", image_ref="good:page4")
    r = route_document(doc, ocr=FakeOcr())
    assert r.ocr_used and r.ocr_engine == "fake-ocr"
    assert r.status == "accepted" and "September" in r.text


def test_scanned_low_confidence_parks_for_review():
    doc = DocumentInput(mime="application/pdf", filename="scan.pdf", image_ref="weak:page4")
    r = route_document(doc, ocr=FakeOcr())
    assert r.ocr_used
    assert r.status == "ocr_review_required"      # never used blindly as a fact


def test_scanned_without_ocr_engine_says_so_instead_of_unsupported():
    """"We had no engine wired" must not be reported as "this file cannot be read".

    Both used to return `unsupported`, so 369 of the design partner's documents — ordinary
    scanned PDFs a wired Tesseract would read — carried a terminal-sounding label, and the
    one-line fix was invisible from the data.
    """
    doc = DocumentInput(mime="application/pdf", filename="scan.pdf", image_ref="good:p1")
    r = route_document(doc, ocr=None)
    assert r.status == "ocr_unavailable"
    assert not r.ocr_used and r.ocr_engine is None


def test_a_file_with_no_pages_at_all_is_genuinely_unsupported():
    """The distinction only means something if the other branch still exists."""
    doc = DocumentInput(mime="application/octet-stream", filename="firmware.bin")
    r = route_document(doc, ocr=None)
    assert r.status == "unsupported"
