"""
Attachment text extraction — Phase 2 Task 2.1.

Pulls text out of PDF, DOCX, and plain-text attachments arriving via Gmail
so the LLM extraction pipeline can see what was inside the file. Investor
term sheets, pitch decks, and shared documents were previously invisible
to the brain.

Fail-soft: any attachment that fails to fetch or parse is logged and
skipped. The main extraction flow never blocks on attachment errors.
"""
from __future__ import annotations

import base64
import io
import logging

logger = logging.getLogger(__name__)

# Caps to keep cost and memory bounded.
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024   # 10 MB per attachment
MAX_PDF_PAGES = 20                         # ignore tail of huge decks
MAX_TEXT_PER_ATTACHMENT = 5000             # truncate per file before LLM


def extract_attachment_text(service, message_id: str, payload: dict) -> str:
    """
    Walk the Gmail message payload, fetch supported attachments, and return
    concatenated extracted text. Each attachment's text is prefixed with a
    `[ATTACHMENT: <filename>]` marker so downstream extraction knows the
    source.

    Returns empty string if there are no supported attachments or all
    extractions fail.
    """
    parts = payload.get("parts", [])
    if not parts:
        return ""

    chunks: list[str] = []
    _walk(service, message_id, parts, chunks)
    return "\n\n".join(chunks)


def _walk(service, message_id, parts, results: list[str]) -> None:
    for part in parts:
        if "parts" in part:
            _walk(service, message_id, part["parts"], results)
            continue

        filename = (part.get("filename") or "").strip()
        mime_type = part.get("mimeType") or ""
        body = part.get("body") or {}
        size = body.get("size", 0)
        attachment_id = body.get("attachmentId")

        if not attachment_id or not filename:
            continue
        if size and size > MAX_ATTACHMENT_BYTES:
            logger.info(f"skipping oversized attachment: {filename} ({size} bytes)")
            continue

        text = _extract_one(service, message_id, attachment_id, filename, mime_type)
        if text:
            trimmed = text[:MAX_TEXT_PER_ATTACHMENT].strip()
            if trimmed:
                results.append(f"[ATTACHMENT: {filename}]\n{trimmed}")


def _extract_one(service, message_id, attachment_id, filename, mime_type) -> str:
    fname = filename.lower()
    try:
        if mime_type == "application/pdf" or fname.endswith(".pdf"):
            return _extract_pdf(service, message_id, attachment_id)
        if (
            mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or fname.endswith(".docx")
        ):
            return _extract_docx(service, message_id, attachment_id)
        if mime_type == "text/plain" or fname.endswith((".txt", ".md")):
            return _extract_plain(service, message_id, attachment_id)
    except Exception as e:
        logger.warning(f"attachment extraction failed: {filename} ({mime_type}): {e}")
    return ""


def _fetch_bytes(service, message_id, attachment_id) -> bytes:
    """Fetch raw attachment bytes via Gmail attachments.get endpoint."""
    att = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    data = att.get("data", "")
    if not data:
        return b""
    return base64.urlsafe_b64decode(data.encode("ASCII"))


def _extract_pdf(service, message_id, attachment_id) -> str:
    try:
        import fitz  # PyMuPDF — already in requirements.txt
    except ImportError:
        logger.warning("PyMuPDF not installed — PDF attachment skipped")
        return ""

    raw = _fetch_bytes(service, message_id, attachment_id)
    if not raw:
        return ""
    doc = fitz.open(stream=raw, filetype="pdf")
    try:
        page_count = min(doc.page_count, MAX_PDF_PAGES)
        return "\n".join(doc[i].get_text() for i in range(page_count))
    finally:
        doc.close()


def _extract_docx(service, message_id, attachment_id) -> str:
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx not installed — DOCX attachment skipped")
        return ""

    raw = _fetch_bytes(service, message_id, attachment_id)
    if not raw:
        return ""
    doc = Document(io.BytesIO(raw))
    return "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())


def _extract_plain(service, message_id, attachment_id) -> str:
    raw = _fetch_bytes(service, message_id, attachment_id)
    if not raw:
        return ""
    return raw.decode("utf-8", errors="ignore")
