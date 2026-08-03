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


def test_scanned_without_ocr_engine_is_unsupported():
    doc = DocumentInput(mime="application/pdf", filename="scan.pdf", image_ref="good:p1")
    r = route_document(doc, ocr=None)
    assert r.status == "unsupported"
