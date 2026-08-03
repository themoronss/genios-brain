from __future__ import annotations

from .base import (OCR_MIN_CONFIDENCE, DocumentInput, DocumentResult, OcrEngine)

# Formats we can parse natively (no OCR).
_NATIVE_MIMES = {
    "text/plain", "text/html", "application/pdf", "text/markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # pptx
}
_MIN_NATIVE_CHARS = 20


def route_document(doc: DocumentInput, ocr: OcrEngine | None = None) -> DocumentResult:
    """Native text if usable; else OCR (if an engine is given); low-quality OCR parks."""
    # native path
    if doc.text_layer and len(doc.text_layer.strip()) >= _MIN_NATIVE_CHARS:
        return DocumentResult(text=doc.text_layer, native_parse_used=True, ocr_used=False,
                              ocr_engine=None, ocr_pages=0, avg_confidence=None,
                              status="accepted")

    # OCR path (scanned / image-only / insufficient text)
    if doc.image_ref is not None and ocr is not None:
        r = ocr.ocr(doc.image_ref)
        status = "accepted" if r.avg_confidence >= OCR_MIN_CONFIDENCE else "ocr_review_required"
        return DocumentResult(text=r.text, native_parse_used=False, ocr_used=True,
                              ocr_engine=r.engine, ocr_pages=r.pages,
                              avg_confidence=r.avg_confidence, status=status)

    # can't parse (unsupported binary, or scanned with no OCR engine wired)
    return DocumentResult(text="", native_parse_used=False, ocr_used=False,
                          ocr_engine=None, ocr_pages=0, avg_confidence=None,
                          status="unsupported")
