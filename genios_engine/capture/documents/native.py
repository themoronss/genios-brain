from __future__ import annotations

import io
from dataclasses import replace as _dc_replace
from html.parser import HTMLParser

from . import pages as pages_module
from .base import DocumentInput, DocumentResult, DocumentStatus, OcrEngine
from .ocr_policy import decide_ocr_outcome
from .pages import PageMap
from .router import route_document
from .transcript import SpeechEngine

# Native text extraction — NO OCR. If a document already has a text layer (HTML, digital
# PDF, docx, xlsx/xls, pptx, txt/md), we pull it straight out; Tesseract is only the fallback
# for scanned images with no text layer.

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PPTX = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_XLS = "application/vnd.ms-excel"


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


def _sheet_rows(rows: list[list[object]]) -> list[str]:
    """Grid rows → one tab-separated line each, blank rows and trailing blank columns dropped.

    Tab, not comma: a spreadsheet cell routinely contains a comma ("Mumbai, MH", "₹12,00,000")
    and a comma-joined line would read as more columns than the sheet has.
    """
    out: list[str] = []
    for row in rows:
        cells = ["" if v is None else str(v).strip() for v in row]
        while cells and not cells[-1]:                 # ragged right edge is noise, not data
            cells.pop()
        if any(cells):
            out.append("\t".join(cells))
    return out


def _xlsx_to_text(raw: bytes) -> str:
    """One markdown section per worksheet (.xlsx/.xlsm).

    `data_only=True` returns the values Excel last calculated instead of the formulas, because
    "=SUM(B2:B40)" tells a reader nothing and "4820000" is the fact. (A workbook Excel has never
    opened has no cached values; that sheet reads empty, which is honest rather than wrong.)
    `read_only=True` streams the sheet instead of materialising the whole workbook — 10 MiB of
    xlsx is a very large grid.

    The `## Sheet:` heading is not decoration. `chunking.SECTION` splits on markdown headings, so
    this is what lets an evidence span cite *Q3 Pipeline* instead of a character offset.
    """
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    try:
        parts: list[str] = []
        for ws in wb.worksheets:
            rows = _sheet_rows([list(r) for r in ws.iter_rows(values_only=True)])
            if rows:
                parts.append(f"## Sheet: {ws.title}\n" + "\n".join(rows))
        return "\n\n".join(parts)
    finally:
        wb.close()


def _xls_to_text(raw: bytes) -> str:
    """The legacy binary .xls format, which openpyxl cannot read at all — xlrd 2.x reads only
    this one, which is why both libraries are here rather than one."""
    import xlrd
    book = xlrd.open_workbook(file_contents=raw)
    parts: list[str] = []
    for sheet in book.sheets():
        rows = _sheet_rows([sheet.row_values(i) for i in range(sheet.nrows)])
        if rows:
            parts.append(f"## Sheet: {sheet.name}\n" + "\n".join(rows))
    return "\n\n".join(parts)


def _pptx_to_text(raw: bytes) -> str:
    """One markdown section per slide, speaker notes included.

    Notes are where a deck says what it means — the slide shows "₹25k/mo", the note says why the
    number moved — so dropping them would discard the half a reader actually needs. Tables are
    walked cell by cell for the same reason they are in `_docx_to_text`: a pricing grid lives in
    a table, and shape.text alone returns nothing for one.
    """
    from pptx import Presentation
    prs = Presentation(io.BytesIO(raw))
    parts: list[str] = []
    for n, slide in enumerate(prs.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        lines.append("\t".join(cells))
            elif getattr(shape, "has_text_frame", False):
                t = shape.text_frame.text.strip()
                if t:
                    lines.append(t)
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        if notes:
            lines.append(f"Speaker notes: {notes}")
        if lines:
            title = lines[0].splitlines()[0][:80]
            parts.append(f"## Slide {n}: {title}\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _pdf_pages(raw: bytes) -> list[str]:
    """One string per page, in order. The join and its page map are both built from this list, so
    the boundaries and the text can never describe two different documents."""
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    return [(pg.extract_text() or "") for pg in reader.pages]


def _pdf_to_text(raw: bytes) -> str:
    return "\n".join(_pdf_pages(raw)).strip()


def native_page_map(*, mime: str, data: bytes | str, filename: str = "") -> PageMap:
    """The page map for a format that HAS pages, or EMPTY.

    Only PDFs today: a DOCX's page breaks are decided at render time and pypdf is the one parser
    here that reports a page boundary at all. A format with no pages answers EMPTY rather than a
    single-page map, because "page 1 of an email" is a number invented to fill a column.

    NOTE the `.strip()` in `_pdf_to_text`: it removes leading whitespace from the joined text and
    would shift every offset in the map by that much, so the map is built from the STRIPPED
    join — computed here the same way the text is, not from the raw page lengths.
    """
    lower = (mime or "").lower()
    if lower != "application/pdf" and not (filename or "").lower().endswith(".pdf"):
        return pages_module.EMPTY
    raw = data.encode() if isinstance(data, str) else data
    try:
        texts = _pdf_pages(raw)
    except Exception:      # noqa: BLE001 — a page map is a nicety; the text is the product
        return pages_module.EMPTY
    if not texts:
        return pages_module.EMPTY
    joined = "\n".join(texts)
    lead = len(joined) - len(joined.lstrip())
    stripped_len = len(joined.strip())
    unshifted = pages_module.from_pages(texts)
    # Shift by the leading whitespace `_pdf_to_text` strips, drop pages that fall off the end of
    # the stripped text, and re-anchor the first entry at 0 — a map whose first offset is not 0
    # is not a map of the text anybody is holding.
    shifted = [max(0, o - lead) for o in unshifted.offsets if o - lead < stripped_len]
    if not shifted:
        return pages_module.EMPTY
    shifted[0] = 0
    return PageMap(offsets=tuple(shifted))


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
        if mime == _XLSX or name.endswith((".xlsx", ".xlsm")):
            return _xlsx_to_text(raw)
        # .xls is checked by extension first: browsers and Composio both label old workbooks
        # application/vnd.ms-excel, and so do some .xlsx files exported by older tooling.
        if name.endswith(".xls") or (mime == _XLS and not name.endswith((".xlsx", ".xlsm"))):
            return _xls_to_text(raw)
        if mime == _PPTX or name.endswith(".pptx"):
            return _pptx_to_text(raw)
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
    # The rasterized path is a per-page loop, so its map is exact and free. A page that OCR'd to
    # nothing is not in `texts` and so is not in the map either — which is honest: we have no
    # characters from it to cite, and numbering the ones we do have as if it were there would put
    # every later citation on the wrong page.
    return DocumentResult(text="\n".join(texts), native_parse_used=False, ocr_used=True,
                          ocr_engine=engine_name, ocr_pages=len(texts), confidence_bp=avg_bp,
                          status=outcome.status, detail=outcome.detail,
                          page_offsets=pages_module.from_pages(texts).offsets)


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
    result = route_document(doc, ocr=ocr, speech=speech)
    # L1.3.4-U5 · the page map, attached only when the text we are returning IS the text the map
    # describes. `route_document` may take the OCR branch, reject a short text layer, or return
    # an empty marked result, and a map from the native parse would then be offsets into a string
    # nobody is holding — a receipt pointing at the wrong page is worse than one with no page.
    if result.text and text and result.text == text and not result.ocr_used:
        page_map = native_page_map(mime=mime, data=data, filename=filename)
        if page_map:
            return _dc_replace(result, page_offsets=page_map.offsets)
    return result


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
