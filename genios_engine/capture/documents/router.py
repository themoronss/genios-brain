"""L1.3.4 · the Document Router itself (ALG-01) — one document in, one *explained* result out.

Every path through this function ends in a `DocumentResult` whose `status` says what happened,
and the G2 invariant — **no document leaves with empty text and no marker** — is enforced twice:
by construction on each branch, and by `ocr_policy.is_explained` as the last statement in the
function. Belt and braces, because the failure it guards against is invisible in production: an
unmarked empty document does not error, does not park, and does not appear in any report; it
just quietly contains nothing, forever.

The six endings, in the order they are tried:

    text layer >= 20 chars   -> accepted                     the cheapest read, always first
    audio / video            -> transcript.transcribe_media  U3's seam (no provider: P5)
    image + engine           -> ocr, graded by ocr_policy     U2
    image, no engine         -> ocr_unavailable               readable, nothing wired
    pdf/image, no text       -> ocr_unavailable               same fact, reached without a page
    anything else            -> unsupported                   no text layer, no pages, no audio

**Why the engine call is wrapped.** `ocr.ocr()` used to be called bare, and doc-03 states the
deploy fact that makes that a live outage rather than a hypothetical: *"the Tesseract binary is
not present in the deploy image."* Turning `enable_ocr` on in that image does not produce OCR —
it produces `TesseractNotFoundError` on the first scanned attachment, inside a sync batch, which
loses every object after it in the loop. A raised engine is a document-level failure and is
recorded as one (`ocr_failed`), never a batch-level one.

**Why `unsupported` shrank.** It used to be the ending for a PDF with no readable text layer,
which is false and terminal-sounding: a scanned PDF is *readable*, we simply had nothing wired
to read it, and a status of `unsupported` hides a fix that is one config line. `unsupported` now
means what it says — no text layer, no page image, no audio — a .zip, a firmware blob. Formats
that have pages get `ocr_unavailable`, which the gate parks under DOC-06 and which an operator
can act on.
"""
from __future__ import annotations

from .base import DocumentInput, DocumentResult, DocumentStatus, OcrEngine
from .ocr_policy import decide_ocr_outcome, is_explained
from .transcript import SpeechEngine, is_audio, transcribe_media

# Formats we can parse natively (no OCR).
_NATIVE_MIMES = {
    "text/plain", "text/html", "application/pdf", "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
}
_MIN_NATIVE_CHARS = 20

#: Formats that HAVE pages an OCR engine could read. The distinction between "we could not read
#: this" and "we chose not to read this" only exists for these.
_OCRABLE_MIME_PREFIXES = ("image/",)
_OCRABLE_MIMES = frozenset({"application/pdf"})
_OCRABLE_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp",
                       ".heic")


def has_pages(mime: str, filename: str = "") -> bool:
    """True when an OCR engine could, in principle, read this file."""
    m = (mime or "").lower().split(";", 1)[0].strip()
    if m in _OCRABLE_MIMES or m.startswith(_OCRABLE_MIME_PREFIXES):
        return True
    return (filename or "").lower().endswith(_OCRABLE_EXTENSIONS)


def _result(status: DocumentStatus, *, detail: str | None = None, text: str = "",
            native: bool = False, ocr_used: bool = False, engine: str | None = None,
            pages: int = 0, confidence_bp: int | None = None) -> DocumentResult:
    return DocumentResult(text=text, native_parse_used=native, ocr_used=ocr_used,
                          ocr_engine=engine, ocr_pages=pages, confidence_bp=confidence_bp,
                          status=status.value, detail=detail)


def route_document(doc: DocumentInput, ocr: OcrEngine | None = None,
                   speech: SpeechEngine | None = None) -> DocumentResult:
    """Read one document by the cheapest path that can read it, and always say which.

    `speech` is accepted and defaults to None because L1.3.4-U3 has no connector to supply an
    engine (source P5 is in no wave). The seam is here so that audio arriving today is parked
    with a true reason instead of mislabelled `unsupported`, and so the day P5 lands the only
    change is at the call site.
    """
    if doc.text_layer and len(doc.text_layer.strip()) >= _MIN_NATIVE_CHARS:
        return _result(DocumentStatus.ACCEPTED, text=doc.text_layer, native=True)

    if doc.media_ref is not None or is_audio(doc.mime, doc.filename):
        t = transcribe_media(media_ref=doc.media_ref or doc.filename, engine=speech)
        return DocumentResult(text=t.text, native_parse_used=False, ocr_used=False,
                              ocr_engine=t.engine, ocr_pages=0, confidence_bp=None,
                              status=t.status, detail=t.detail)

    if doc.image_ref is not None and ocr is not None:
        try:
            r = ocr.ocr(doc.image_ref)
        except Exception as exc:                   # one unreadable page must not kill a batch
            return _result(DocumentStatus.OCR_FAILED, ocr_used=True,
                           engine=getattr(ocr, "name", None), confidence_bp=0,
                           detail=f"ocr engine raised: {type(exc).__name__}: {exc}")
        outcome = decide_ocr_outcome(text=r.text, confidence_bp=r.confidence_bp)
        return DocumentResult(text=r.text if not outcome.is_failure else "",
                              native_parse_used=False, ocr_used=True, ocr_engine=r.engine,
                              ocr_pages=r.pages, confidence_bp=r.confidence_bp,
                              status=outcome.status, detail=outcome.detail)

    # Two very different failures, historically collapsed into one terminal-sounding label.
    # `unsupported` reads as "this file cannot be read"; for 369 of this org's documents the
    # truth was "we have pages and no engine wired", which Tesseract would have read. Keeping
    # them distinct is what makes the fix visible from the data instead of a code review.
    if doc.image_ref is not None or has_pages(doc.mime, doc.filename):
        return _result(DocumentStatus.OCR_UNAVAILABLE,
                       detail="the file has pages and no OCR engine is wired for this org")

    result = _result(DocumentStatus.UNSUPPORTED,
                     detail="no text layer, no page image and no audio in this format")
    # The G2 postcondition, asserted rather than assumed. Unreachable by construction today;
    # it exists so that a seventh branch added later cannot reintroduce the silent empty.
    if not is_explained(result):                                       # pragma: no cover
        return _result(DocumentStatus.UNSUPPORTED, detail="empty text with no reason recorded")
    return result


__all__ = ["route_document", "has_pages"]
