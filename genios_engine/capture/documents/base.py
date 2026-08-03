from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# Threshold below which OCR output is parked for review (not used as a business fact).
# A tunable constant, not a magic number scattered in logic.
OCR_MIN_CONFIDENCE = 0.75


@dataclass
class DocumentInput:
    mime: str
    filename: str
    text_layer: str | None = None       # extractable text if the format has one (PDF/DOCX/...)
    image_ref: str | None = None        # pointer to image bytes for scanned/image docs
    document_hash: str | None = None


@dataclass
class OcrResult:
    text: str
    avg_confidence: float
    pages: int
    engine: str


@dataclass
class DocumentResult:
    text: str
    native_parse_used: bool
    ocr_used: bool
    ocr_engine: str | None
    ocr_pages: int
    avg_confidence: float | None
    status: str                          # accepted | ocr_review_required | unsupported


class OcrEngine(Protocol):
    name: str

    def ocr(self, image_ref: str) -> OcrResult: ...
