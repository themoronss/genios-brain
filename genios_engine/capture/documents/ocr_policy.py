"""L1.3.4-U2 · the OCR outcome policy — *an empty document always says why it is empty.*

This is the decision half of U2, split from the I/O half on purpose. `router.py` and
`native.py` open temp files, rasterize PDFs and call an engine that shells out to a binary;
none of that is testable as a truth table. What IS a truth table is the four-line question
asked afterwards — **did the engine raise, did it return anything, was it confident, and
therefore is this a fact, a review item, or a failure** — and that question is the one the G2
gate counts. So it lives here, pure: no engine, no file, no clock, no float.

**Why `ocr_failed` had to be invented rather than reused.** Before this the package had two
empty-text endings, `unsupported` ("we cannot read this format") and `ocr_unavailable` ("no
engine was wired"), and a third state fell through the gap between them: an engine WAS wired,
it DID run, and it produced nothing — the binary is missing from the deploy image and
`pytesseract` raised, the page rasterized to noise, the scan is a black rectangle. That state
was reported as `unsupported`, which is terminal-sounding and false: the file is fine, the read
failed, and a retry after fixing the image would succeed. Worse, the exception case never
reached a status at all — `ocr.ocr()` was called unguarded, so on a deploy image without the
Tesseract binary the *first scanned attachment killed the sync batch*. Doc-03 names the exact
deploy state ("the Tesseract binary is not present in the deploy image") and the exact rule:
**a failed OCR emits a low-confidence marker, never nothing.**

**Empty text outranks high confidence.** The order of the checks is load-bearing. An engine may
return `("", 9900)` — Tesseract does, on a blank scan, because it is highly confident there are
no words — and taking the confidence branch first would stamp `accepted` on an empty document,
which is the one outcome this whole component exists to make impossible. Emptiness is checked
before confidence, always.
"""
from __future__ import annotations

from dataclasses import dataclass

from .base import (EXPLAINED_EMPTY_STATUSES, OCR_MIN_CONFIDENCE_BP, DocumentResult,
                   DocumentStatus)


@dataclass(frozen=True)
class OcrOutcome:
    """The verdict on one OCR read: the status word, and the phrase that explains it.

    Frozen because it is evidence about a read that already happened — a caller that could
    edit the detail after the fact could make a failure describe itself as a success.
    """

    status: str
    detail: str | None

    @property
    def is_failure(self) -> bool:
        """True when no usable text came back at all (as opposed to weak text)."""
        return self.status == DocumentStatus.OCR_FAILED.value


def decide_ocr_outcome(*, text: str, confidence_bp: int,
                       engine_error: str | None = None) -> OcrOutcome:
    """Grade one OCR read. Pure: the same three inputs always give the same verdict.

    The cascade, in the order the checks must run:

    ==========================  ==========================  ===============================
    condition                   status                      why this order
    ==========================  ==========================  ===============================
    the engine raised           ``ocr_failed``              a crash is not a blank page
    no non-whitespace text      ``ocr_failed``              beats confidence, see module doc
    ``confidence_bp`` < floor   ``ocr_review_required``     real text, not quotable yet
    otherwise                   ``accepted``                a fact
    ==========================  ==========================  ===============================

    `engine_error` is the *string* of the exception, not the exception: this unit never sees an
    engine and must stay importable without one.
    """
    if engine_error:
        return OcrOutcome(status=DocumentStatus.OCR_FAILED.value,
                          detail=f"ocr engine raised: {engine_error}")
    if not (text or "").strip():
        return OcrOutcome(status=DocumentStatus.OCR_FAILED.value,
                          detail="ocr engine returned no text")
    if confidence_bp < OCR_MIN_CONFIDENCE_BP:
        return OcrOutcome(status=DocumentStatus.OCR_REVIEW_REQUIRED.value,
                          detail=f"ocr confidence {confidence_bp}bp below "
                                 f"{OCR_MIN_CONFIDENCE_BP}bp floor")
    return OcrOutcome(status=DocumentStatus.ACCEPTED.value, detail=None)


def is_explained(result: DocumentResult) -> bool:
    """The G2 gate, as a predicate over one result.

    *"0 documents with empty text and no marker"* — a result passes if it has text, or if its
    status is one of the seven that name a reason for having none. A result that is empty and
    `accepted` fails, which is the only combination the invariant forbids.

    Exposed rather than kept private because it is the assertion the acceptance suite makes and
    the guard `router.route_document` runs on its own way out: a unit that can check its own
    postcondition should, and the same function must be the one the gate uses, or the gate is
    checking a second implementation of the rule.
    """
    if (result.text or "").strip():
        return True
    return result.status in EXPLAINED_EMPTY_STATUSES
