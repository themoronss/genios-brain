from __future__ import annotations

from .base import OcrResult

# Tesseract (English) behind the OcrEngine interface. Runs server-side, and in
# production as an ASYNC worker — never in the API request thread. Lazy import so
# dev/tests don't require the binary; wire this when OCR is enabled.


class TesseractOcr:
    name = "tesseract-eng"

    def __init__(self, lang: str = "eng") -> None:
        self._lang = lang

    def ocr(self, image_ref: str) -> OcrResult:
        import pytesseract          # lazy: needs the tesseract binary + pytesseract
        from PIL import Image

        img = Image.open(image_ref)
        data = pytesseract.image_to_data(img, lang=self._lang,
                                         output_type=pytesseract.Output.DICT)
        words = [w for w in data["text"] if w.strip()]
        confs = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) >= 0]
        avg = (sum(confs) / len(confs) / 100.0) if confs else 0.0
        return OcrResult(text=" ".join(words), avg_confidence=avg, pages=1, engine=self.name)
