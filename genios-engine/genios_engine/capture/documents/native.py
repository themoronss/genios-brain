from __future__ import annotations

import io
from html.parser import HTMLParser

from .base import DocumentInput, DocumentResult, OcrEngine
from .router import route_document

# Native text extraction — NO OCR. If a document already has a text layer (HTML, digital
# PDF, docx, txt/md), we pull it straight out; Tesseract is only the fallback for scanned
# images with no text layer.

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class _HTMLText(HTMLParser):
    _SKIP = {"script", "style", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self._parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self._parts)


def _html_to_text(s: str) -> str:
    p = _HTMLText()
    p.feed(s)
    return p.text()


def _docx_to_text(raw: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(raw))
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for tbl in doc.tables:
        for row in tbl.rows:
            parts += [c.text.strip() for c in row.cells if c.text.strip()]
    return "\n".join(parts)


def _pdf_to_text(raw: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((pg.extract_text() or "") for pg in reader.pages).strip()


def extract_native_text(*, mime: str, data: bytes | str, filename: str = "") -> str | None:
    """Return the document's text layer, or None if it has none (scanned image →
    OCR fallback) or the format is unsupported. Never raises."""
    mime = (mime or "").lower()
    name = (filename or "").lower()
    raw = data.encode() if isinstance(data, str) else data
    txt = data if isinstance(data, str) else data.decode(errors="ignore")
    try:
        if mime in ("text/plain", "text/markdown") or name.endswith((".txt", ".md")):
            return txt
        if mime == "text/html" or name.endswith((".html", ".htm")):
            return _html_to_text(txt)
        if mime == _DOCX or name.endswith(".docx"):
            return _docx_to_text(raw)
        if mime == "application/pdf" or name.endswith(".pdf"):
            return _pdf_to_text(raw)
    except Exception:
        return None
    return None


def process_document(*, mime: str, data: bytes | str, filename: str = "",
                     image_ref: str | None = None,
                     ocr: OcrEngine | None = None) -> DocumentResult:
    """Full path: native text if the format has it, else OCR (if wired), else unsupported."""
    text = extract_native_text(mime=mime, data=data, filename=filename)
    doc = DocumentInput(mime=mime, filename=filename, text_layer=text, image_ref=image_ref)
    return route_document(doc, ocr=ocr)
