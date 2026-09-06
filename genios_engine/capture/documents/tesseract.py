from __future__ import annotations

import shutil

from .base import BP_FULL, OcrResult

# Tesseract (English) behind the OcrEngine interface. Runs server-side, and in
# production as an ASYNC worker — never in the API request thread. Lazy import so
# dev/tests don't require the binary; wire this when OCR is enabled.

#: The binary the lazy import ultimately shells out to. Named here so the availability probe
#: and the engine agree about what "installed" means.
TESSERACT_BINARY = "tesseract"


def tesseract_available() -> bool:
    """Is the OCR binary actually on this host?

    Doc-03's gap statement is two clauses and the second one is the operational half: *"the
    Tesseract binary is not present in the deploy image."* Without this probe, turning
    `enable_ocr` on in that image wires an engine that raises on its first call — a config flag
    whose only effect is to convert empty documents into failed ones. `enablement.py` asks this
    question before wiring anything, so "off" and "impossible" stay distinguishable.
    """
    return shutil.which(TESSERACT_BINARY) is not None


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
        # Tesseract reports integer percentages. `sum // len` in basis points is that number
        # exactly; the previous `/ 100.0` introduced a float purely to lose precision on the
        # way to a `>=` comparison that decides whether a contract is quotable.
        confidence_bp = (sum(confs) * (BP_FULL // 100)) // len(confs) if confs else 0
        return OcrResult(text=" ".join(words), confidence_bp=confidence_bp, pages=1,
                         engine=self.name)
