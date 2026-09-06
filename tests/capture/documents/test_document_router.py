"""L1.3.4 · Document Router (ALG-01), units U1 (native text) and U2 (OCR) — G2's marker gate.

    Expected: 0 documents with empty text and no `ocr_failed` marker.

That line from doc-09 is the whole of this file. It is phrased as an absence because the failure
is invisible: a scanned contract that extracts to `""` produces no error, no park and no log —
it produces a document that every layer above reads as *"this said nothing"*, which is exactly
what a fax cover sheet also says. The three ways a document used to reach that state, all of them
found by reading the code rather than by anything failing:

1. **an OCR engine that returned no text at high confidence was `accepted`.** Tesseract does
   this on a blank or black scan — it is confident, correctly, that there are no words — and the
   old grade compared confidence *before* it checked for text, so an empty document came out
   stamped as a fact. `FakeOcr("blank:")` is that engine.
2. **an OCR engine that raised took the whole sync with it.** `ocr.ocr()` was called bare, and
   doc-03 states the deploy fact that makes this live rather than theoretical: the Tesseract
   binary is not in the image. Turning `enable_ocr` on there does not produce OCR, it produces
   `TesseractNotFoundError` on the first scanned attachment — inside a batch loop, losing every
   object after it. `FakeOcr("raise:")` is that engine.
3. **a PDF with no readable text layer and no engine was `unsupported`.** Terminal-sounding and
   false: the file is readable, nothing was wired to read it, and the distinction is the one
   that turned a 369-document backlog from "these files are broken" into "install a binary".

U1 (native extraction) is marked ✅ in doc-03 and was verified rather than rewritten; the table
below is that verification, including the two paths that must return None rather than raise.
"""
from __future__ import annotations

import pytest

from genios_engine.capture.documents.base import (EXPLAINED_EMPTY_STATUSES,
                                                  OCR_MIN_CONFIDENCE_BP, DocumentInput,
                                                  DocumentStatus)
from genios_engine.capture.documents.fake import FakeOcr, FakeSpeechEngine
from genios_engine.capture.documents.native import (extract_native_text,
                                                    extract_text_best_effort, process_document)
from genios_engine.capture.documents.ocr_policy import decide_ocr_outcome, is_explained
from genios_engine.capture.documents.router import has_pages, route_document

LONG = "This proposal covers the pilot scope, the pricing and the renewal terms."


# ── U1 · native text extraction (✅ exists — verified, not rewritten) ──────────────────────────

@pytest.mark.parametrize("mime, filename, data, expected", [
    ("text/plain",    "n.txt",  b"hello world",                       "hello world"),
    ("text/markdown", "n.md",   b"# Title\nbody",                     "# Title\nbody"),
    ("",              "n.md",   b"by extension alone",                "by extension alone"),
    ("text/html",     "p.html", b"<p>Hello <b>World</b></p>",         "Hello World"),
    ("text/html",     "p.html", b"<style>x{}</style><p>Body</p>",     "Body"),
    # formats with no modelled parser, and parsers handed bytes they cannot read: None, and
    # NEVER an exception — one unreadable attachment must not end a sync batch.
    ("application/pdf",          "scan.pdf", b"%PDF-1.4 not really a pdf", None),
    ("application/octet-stream", "fw.bin",   b"\x00\x01\x02",              None),
    ("application/vnd.openxmlformats-officedocument.wordprocessingml.document",
     "doc.docx", b"PK\x03\x04 garbage", None),
])
def test_native_extraction_reads_what_it_models_and_returns_none_for_the_rest(
        mime, filename, data, expected):
    assert extract_native_text(mime=mime, data=data, filename=filename) == expected


def test_a_usable_text_layer_never_reaches_ocr():
    """The cheapest read is tried first and the engine is not consulted — an OCR call on a
    digital PDF is a bill and a latency spike for a page we already have."""
    r = route_document(DocumentInput(mime="application/pdf", filename="proposal.pdf",
                                     text_layer=LONG), ocr=FakeOcr())
    assert r.native_parse_used and not r.ocr_used
    assert r.status == DocumentStatus.ACCEPTED.value and r.detail is None


# ── U2 · the OCR grading policy, as a truth table ─────────────────────────────────────────────

@pytest.mark.parametrize("text, confidence_bp, engine_error, status, why", [
    ("Agreement renews.", 9_100, None,       DocumentStatus.ACCEPTED.value,
     "confident text is a fact"),
    ("blurr d cntract",   4_200, None,       DocumentStatus.OCR_REVIEW_REQUIRED.value,
     "real text below the floor is a review item, not a fact"),
    ("Agreement renews.", OCR_MIN_CONFIDENCE_BP, None, DocumentStatus.ACCEPTED.value,
     "the floor is inclusive"),
    ("Agreement renews.", OCR_MIN_CONFIDENCE_BP - 1, None,
     DocumentStatus.OCR_REVIEW_REQUIRED.value, "one bp under the floor parks"),
    ("",                  9_900, None,       DocumentStatus.OCR_FAILED.value,
     "DEFECT 1: empty text outranks high confidence, or an empty doc is stamped accepted"),
    ("   \n\t ",          9_900, None,       DocumentStatus.OCR_FAILED.value,
     "whitespace is not text"),
    ("",                  0,     None,       DocumentStatus.OCR_FAILED.value,
     "empty and unsure is still a failed read, not a park-for-review"),
    ("partial text",      9_900, "TesseractNotFoundError", DocumentStatus.OCR_FAILED.value,
     "DEFECT 2: a raised engine is a failure whatever it managed to return"),
])
def test_ocr_outcomes_are_graded_in_the_order_that_makes_empty_impossible(
        text, confidence_bp, engine_error, status, why):
    outcome = decide_ocr_outcome(text=text, confidence_bp=confidence_bp,
                                 engine_error=engine_error)
    assert outcome.status == status, why
    assert outcome.detail or outcome.status == DocumentStatus.ACCEPTED.value


# ── U2 · the router's six endings, and the invariant over all of them ─────────────────────────

def _route(**kw):
    ocr = kw.pop("ocr", None)
    return route_document(DocumentInput(**kw), ocr=ocr)


ROUTES = [
    ("native text layer",
     dict(mime="application/pdf", filename="p.pdf", text_layer=LONG, ocr=FakeOcr()),
     DocumentStatus.ACCEPTED.value, True),
    ("scan read confidently",
     dict(mime="application/pdf", filename="s.pdf", image_ref="good:p4", ocr=FakeOcr()),
     DocumentStatus.ACCEPTED.value, True),
    ("scan read weakly",
     dict(mime="application/pdf", filename="s.pdf", image_ref="weak:p4", ocr=FakeOcr()),
     DocumentStatus.OCR_REVIEW_REQUIRED.value, True),
    ("scan read as nothing (DEFECT 1)",
     dict(mime="application/pdf", filename="s.pdf", image_ref="blank:p4", ocr=FakeOcr()),
     DocumentStatus.OCR_FAILED.value, False),
    ("engine raised (DEFECT 2)",
     dict(mime="application/pdf", filename="s.pdf", image_ref="raise:p4", ocr=FakeOcr()),
     DocumentStatus.OCR_FAILED.value, False),
    ("scan with no engine wired",
     dict(mime="application/pdf", filename="s.pdf", image_ref="good:p1"),
     DocumentStatus.OCR_UNAVAILABLE.value, False),
    ("pdf with no readable text layer and no engine (DEFECT 3)",
     dict(mime="application/pdf", filename="s.pdf", text_layer="  12  "),
     DocumentStatus.OCR_UNAVAILABLE.value, False),
    ("image with no engine (DEFECT 3)",
     dict(mime="image/png", filename="invoice-scan.png"),
     DocumentStatus.OCR_UNAVAILABLE.value, False),
    ("a recording, with no speech engine anywhere (U3)",
     dict(mime="audio/mpeg", filename="standup.mp3"),
     DocumentStatus.TRANSCRIPTION_UNAVAILABLE.value, False),
    ("a format with no text, no pages and no audio",
     dict(mime="application/octet-stream", filename="firmware.bin"),
     DocumentStatus.UNSUPPORTED.value, False),
]


@pytest.mark.parametrize("label, kwargs, status, has_text",
                         ROUTES, ids=[r[0] for r in ROUTES])
def test_every_route_ends_in_the_status_that_names_what_happened(label, kwargs, status, has_text):
    r = _route(**kwargs)
    assert r.status == status, label
    assert bool(r.text.strip()) is has_text, label


@pytest.mark.parametrize("label, kwargs, status, has_text",
                         ROUTES, ids=[r[0] for r in ROUTES])
def test_G2_no_document_is_ever_empty_without_saying_why(label, kwargs, status, has_text):
    """The gate itself: `0 documents with empty text and no marker`, asserted on every branch."""
    r = _route(**kwargs)
    assert is_explained(r), label
    if not r.text.strip():
        assert r.status in EXPLAINED_EMPTY_STATUSES
        assert r.detail, "an empty document must carry a readable reason, not just a status"


def test_a_blank_read_reports_no_text_rather_than_the_whitespace_it_got():
    """`ocr_failed` and a body of `"   \\n "` would put whitespace into the graph as content."""
    r = _route(mime="image/png", filename="s.png", image_ref="blank:p1", ocr=FakeOcr())
    assert r.text == "" and r.ocr_used and r.confidence_bp == 9_900


def test_the_engine_that_raises_is_recorded_and_does_not_escape():
    """The deploy image has no Tesseract binary. That must cost one document, not one batch."""
    r = _route(mime="image/png", filename="s.png", image_ref="raise:p1", ocr=FakeOcr())
    assert r.status == DocumentStatus.OCR_FAILED.value
    assert "tesseract is not installed" in (r.detail or "")
    assert r.ocr_engine == "fake-ocr" and r.ocr_used


@pytest.mark.parametrize("mime, filename, expected", [
    ("application/pdf",          "x.pdf",  True),
    ("image/png",                "x.png",  True),
    ("image/tiff",               "x.tiff", True),
    ("application/octet-stream", "x.pdf",  True),      # extension when the mime is useless
    ("application/octet-stream", "x.zip",  False),
    ("text/plain",               "x.txt",  False),
    ("",                         "",       False),
])
def test_only_formats_that_have_pages_get_the_recoverable_status(mime, filename, expected):
    """`ocr_unavailable` means "we could have read this". Claiming it for a .zip would put an
    unfixable file in a queue whose whole promise is that wiring an engine empties it."""
    assert has_pages(mime, filename) is expected


# ── confidence is basis points, and the floor is compared in them ─────────────────────────────

def test_confidence_crosses_the_boundary_as_an_integer_and_never_as_a_ratio():
    good = _route(mime="image/png", filename="s.png", image_ref="good:p1", ocr=FakeOcr())
    weak = _route(mime="image/png", filename="s.png", image_ref="weak:p1", ocr=FakeOcr())
    assert (good.confidence_bp, weak.confidence_bp) == (9_100, 4_200)
    assert all(isinstance(r.confidence_bp, int) for r in (good, weak))
    assert good.confidence_bp >= OCR_MIN_CONFIDENCE_BP > weak.confidence_bp


# ── the doors: uploads read a scanned file exactly like email and Drive do ─────────────────────

def test_the_upload_door_still_reports_nothing_honestly_when_no_engine_is_wired():
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert extract_text_best_effort(mime="image/png", data=png, filename="scan.png") == ""
    r = process_document(mime="image/png", data=png, filename="scan.png")
    assert r.status == DocumentStatus.OCR_UNAVAILABLE.value and r.detail


def test_a_wired_engine_actually_runs_on_uploaded_image_bytes():
    """`image_ref` was never set by any caller, so the OCR branch was unreachable engine-wide.
    The bytes are materialised for the engine, which is what makes U2 a live path at all."""
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    out = extract_text_best_effort(mime="image/png", data=png, filename="invoice.png",
                                  ocr=FakeOcr())
    assert "Agreement renews" in out


def test_a_scanned_pdf_whose_rasterizer_is_missing_says_so_instead_of_unsupported():
    """poppler/pdf2image absent used to return None, and the caller then reported `unsupported` —
    a terminal verdict on a file whose only problem is a missing package on the host."""
    r = process_document(mime="application/pdf", data=b"%PDF-1.4 scanned", filename="scan.pdf",
                         ocr=FakeOcr())
    assert r.status == DocumentStatus.OCR_FAILED.value
    assert r.ocr_used and r.text == "" and "pdf rasteriz" in (r.detail or "")
    assert is_explained(r)


def test_the_speech_seam_is_reachable_from_the_document_path():
    """U3 is descoped (no connector), but the seam is wired: a recording handed a speech engine
    is transcribed by the same call the connectors already make."""
    r = process_document(mime="audio/mpeg", data=b"\x00\x01", filename="call.mp3",
                         media_ref="meeting-1", speech=FakeSpeechEngine())
    assert r.status == DocumentStatus.ACCEPTED.value and "Rohit" in r.text
