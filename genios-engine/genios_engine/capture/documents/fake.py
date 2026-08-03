from __future__ import annotations

from .base import OcrResult


class FakeOcr:
    """Deterministic OCR for dev/tests — no Tesseract binary needed. The image_ref
    encodes the outcome: 'good:...' → high confidence, 'weak:...' → low confidence."""
    name = "fake-ocr"

    def ocr(self, image_ref: str) -> OcrResult:
        if image_ref.startswith("weak:"):
            return OcrResult(text="blurr d cntract renews 30 sept",
                             avg_confidence=0.42, pages=1, engine=self.name)
        return OcrResult(text="Agreement renews automatically on 30 September.",
                         avg_confidence=0.91, pages=1, engine=self.name)
