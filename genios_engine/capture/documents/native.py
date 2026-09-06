from __future__ import annotations

import io
from html.parser import HTMLParser

from .base import DocumentInput, DocumentResult, DocumentStatus, OcrEngine
from .ocr_policy import decide_ocr_outcome
from .router import route_document
from .transcript import SpeechEngine

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


def _ocr_image_bytes(mime: str, data: bytes, filename: str, ocr: OcrEngine) -> DocumentResult:
    """Materialise raw image bytes to a short-lived temp file and OCR them — route_document's OCR
    branch needs an image_ref, and before this no caller ever set one, so OCR was dormant."""
    import os
    import tempfile
    suffix = "." + ((mime or "").split("/", 1)[-1] or "img").split(";")[0]
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return route_document(DocumentInput(mime=mime, filename=filename, image_ref=path), ocr=ocr)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _ocr_pdf_bytes(data: bytes, ocr: OcrEngine) -> DocumentResult:
    """Rasterize a scanned PDF's pages (poppler via pdf2image) and OCR each, concatenating the text.

    ALWAYS returns a result, never None. It used to return None on every failure — a missing
    rasterizer, a corrupt PDF, a page that read as nothing — and the caller then fell through to
    `route_document`, which saw a PDF with no text layer and no image_ref and reported
    `unsupported`. That is a lie in the one direction that costs: an engine WAS wired and DID
    run, so the file is not unsupported, the read failed, and the difference is what tells an
    operator whether to install poppler or to go looking at the source document.
    """
    engine_name = getattr(ocr, "name", None)

    def failed(detail: str, pages: int = 0) -> DocumentResult:
        return DocumentResult(text="", native_parse_used=False, ocr_used=True,
                              ocr_engine=engine_name, ocr_pages=pages, confidence_bp=0,
                              status=DocumentStatus.OCR_FAILED.value, detail=detail)

    try:
        from pdf2image import convert_from_bytes
    except Exception as exc:                             # pdf2image/poppler not installed
        return failed(f"pdf rasterization unavailable: {type(exc).__name__}: {exc}")
    try:
        images = convert_from_bytes(data)
    except Exception as exc:                             # corrupt PDF / poppler failure
        return failed(f"pdf rasterization failed: {type(exc).__name__}: {exc}")

    import os
    import tempfile
    texts: list[str] = []
    confs: list[int] = []
    errors: list[str] = []
    for img in images:
        fd, path = tempfile.mkstemp(suffix=".png")
        try:
            with os.fdopen(fd, "wb") as f:
                img.save(f, "PNG")
            r = ocr.ocr(path)
        except Exception as exc:                         # one bad page, not a dead batch
            errors.append(f"{type(exc).__name__}: {exc}")
            continue
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        if r.text:
            texts.append(r.text)
        confs.append(r.confidence_bp)
    if not texts:
        return failed("ocr read no text from any rasterized page"
                      + (f" ({errors[0]})" if errors else ""), pages=len(images))
    # Integer mean in basis points — the page confidences are already on that scale.
    avg_bp = sum(confs) // len(confs) if confs else 0
    outcome = decide_ocr_outcome(text="\n".join(texts), confidence_bp=avg_bp)
    return DocumentResult(text="\n".join(texts), native_parse_used=False, ocr_used=True,
                          ocr_engine=engine_name, ocr_pages=len(texts), confidence_bp=avg_bp,
                          status=outcome.status, detail=outcome.detail)


def process_document(*, mime: str, data: bytes | str, filename: str = "",
                     image_ref: str | None = None, media_ref: str | None = None,
                     ocr: OcrEngine | None = None,
                     speech: SpeechEngine | None = None) -> DocumentResult:
    """Full path: native text if the format has it, else OCR (if wired), else a marked failure.

    OCR actually RUNS when an engine is wired (before, no caller set `image_ref`, so it was
    dormant engine-wide): an image's bytes are materialised to a temp file, and a scanned PDF's
    pages are rasterized (poppler) and OCR'd. A missing OCR toolchain now falls back to
    `ocr_failed` with the reason, never a crash and never a silent `unsupported`.

    `speech` is threaded to the router for L1.3.4-U3's seam; no connector supplies one yet
    (source P5 is unbuilt), so audio arrives here and parks as `transcription_unavailable`.
    """
    text = extract_native_text(mime=mime, data=data, filename=filename)
    if (image_ref is None and ocr is not None and not (text and text.strip())
            and isinstance(data, (bytes, bytearray))):
        lower = (mime or "").lower()
        if lower.startswith("image/"):
            return _ocr_image_bytes(mime, data, filename, ocr)
        if lower == "application/pdf" or filename.lower().endswith(".pdf"):
            return _ocr_pdf_bytes(data, ocr)          # always marked: ocr_failed, never a silent empty
    doc = DocumentInput(mime=mime, filename=filename, text_layer=text, image_ref=image_ref,
                        media_ref=media_ref)
    return route_document(doc, ocr=ocr, speech=speech)


# text-ish formats we decode straight to utf-8 when there is no modelled parser (csv/json/logs/yaml).
# NOT html — that must be tag-stripped (extract_native_text), never returned raw.
_PLAINTEXT_EXTS = ("txt", "md", "markdown", "csv", "tsv", "json", "log", "yaml", "yml")


def extract_text_best_effort(*, mime: str, data: bytes | str, filename: str = "",
                             ocr: OcrEngine | None = None) -> str:
    """Best-effort document text for the intake doors (dashboard uploads): the full native (+OCR
    when wired) path — IDENTICAL to email/Drive attachments — then a stripped-native recovery for
    short text layers, then a utf-8 fallback for plain-text formats with no modelled parser. Returns
    "" (never None) for a binary/scanned file that yields nothing, so the caller can honestly report
    "no extractable text" instead of indexing decoded garbage. (The upload door was pypdf-only before
    this — inconsistent with email/Drive, and it utf-8-decoded binaries into garbage.)"""
    r = process_document(mime=mime or "", data=data, filename=filename, ocr=ocr)
    if r.text and r.text.strip():
        return r.text
    # process_document rejects a native text layer under _MIN_NATIVE_CHARS and formats it doesn't
    # model — recover a stripped layer (short html, tiny pdf/docx) before the raw-decode fallback.
    native = extract_native_text(mime=mime or "", data=data, filename=filename)
    if native and native.strip():
        return native
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in _PLAINTEXT_EXTS:
        return data.decode("utf-8", errors="ignore") if isinstance(data, (bytes, bytearray)) else str(data)
    return ""
