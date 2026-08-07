from __future__ import annotations

import base64
import binascii
import re
from datetime import datetime, timezone
from typing import Any

from genios_engine.capture.documents.native import process_document

from .base import RawObject, SourceBatch

# Composio sits BEHIND this interface — auth + Gmail data delivery only. Our contract,
# gate, graph, and acquisition orchestration stay ours; swappable for native.
#
# NOTE: the Gmail response field paths below are defensive and may need a small tweak
# against the real payload on the first live run (the "spike"). Only this mapping
# changes — nothing downstream.

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _b64url(s: Any) -> bytes:
    """Decode Gmail's URL-safe base64 body/attachment data. Tolerant of missing padding and
    of a standard-base64 fallback; never raises — returns b'' on anything unparseable."""
    if not isinstance(s, str) or not s:
        return b""
    pad = "=" * (-len(s) % 4)
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decoder(s + pad)
        except (binascii.Error, ValueError):
            continue
    return b""


# Attachment mimetypes worth DOWNLOADING (we can extract text from these). Everything else —
# calendar invites (invite.ics), vcards, signatures, images without OCR — is skipped BEFORE the
# per-file GMAIL_GET_ATTACHMENT network call. That call, not any LLM, is what made L1 slow: one
# round-trip per attachment, mostly for invite.ics that gets dropped anyway.
_EXTRACTABLE_ATTACHMENT_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",    # docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",           # xlsx
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",   # pptx
    "text/plain", "text/markdown",
}

# Headers that mark automated / bulk / mailing-list mail. Surfaced into raw["headers"] so the gate's
# N-01 (Auto-Submitted), N-02 (List-Unsubscribe) and N-04 (Precedence) rules can actually FIRE — the
# connector never built this dict, so those three rules were dead and bulk mail slipped L1 to L2,
# wasting an LLM call before being classified as noise. List-Id/List-Post/Feedback-ID = strong ESP markers.
_NOISE_HEADERS = ("Auto-Submitted", "Precedence", "List-Unsubscribe",
                  "List-Id", "List-Post", "Feedback-ID")

# First-ever backfill window on a fresh connect. Kept SHORT (1 month) so onboarding is fast — a
# Composio list page (~100 emails) is ~26s, so fewer days = fewer pages = quicker first sync.
# Steady-state incremental sync resumes from the watermark and only pulls new mail regardless.
_BACKFILL_WINDOW = "newer_than:30d"


def _extract_email(s: str | None) -> str | None:
    if not s:
        return None
    m = _EMAIL.search(s)
    return m.group(0).lower() if m else None


def _extract_emails(*sources: Any) -> list[str]:
    """ALL distinct emails across the given header values (To/Cc can list many, comma-separated,
    each possibly "Name <addr>"). Order-preserving dedup so L2 can build one edge per recipient."""
    seen: dict[str, None] = {}
    for s in sources:
        if not s:
            continue
        text_val = ", ".join(str(x) for x in s) if isinstance(s, (list, tuple)) else str(s)
        for m in _EMAIL.findall(text_val):
            seen.setdefault(m.lower(), None)
    return list(seen)


def _header(m: dict, name: str) -> str | None:
    for h in (m.get("payload") or {}).get("headers") or []:
        if str(h.get("name", "")).lower() == name.lower():
            return h.get("value")
    return None


def _parse_ts(m: dict) -> datetime:
    for k in ("internalDate", "messageTimestamp", "timestamp", "date"):
        v = m.get(k)
        if v is None:
            continue
        # epoch (ms or s), as int or digit-string
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            ms = int(v)
            return datetime.fromtimestamp(ms / 1000 if ms > 1e12 else ms, tz=timezone.utc)
        # ISO 8601, e.g. "2026-07-30T09:27:19Z"
        if isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
    # fallback: RFC-2822 Date header ("Thu, 30 Jul 2026 09:27:19 GMT")
    hdr = _header(m, "Date")
    if hdr:
        try:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(hdr)
            if dt:
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


class ComposioGmailConnector:
    source = "gmail"

    def __init__(self, *, api_key: str, user_id: str,
                 connected_account_id: str | None = None, ocr=None) -> None:
        self._api_key = api_key
        self._user_id = user_id
        self._account = connected_account_id or None
        self._client: Any = None
        self._ocr = ocr          # OcrEngine | None — for scanned-PDF attachments (native-only if None)

    def _client_(self) -> Any:
        if self._client is None:
            from composio import Composio          # lazy: only needed on real runs
            self._client = Composio(api_key=self._api_key)
        return self._client

    def _execute(self, slug: str, arguments: dict[str, Any]) -> Any:
        # Composio 0.18 requires an explicit toolkit version for manual execution.
        # Trial: skip (uses latest). TODO(prod): pin toolkit_versions={"gmail": "<ver>"}.
        return self._client_().tools.execute(
            slug, user_id=self._user_id, arguments=arguments,
            dangerously_skip_version_check=True,
        )

    def _fetch(self, *, max_results: int, query: str | None = None,
               page_token: str | None = None) -> Any:
        args: dict[str, Any] = {"max_results": max_results}
        if query:
            args["query"] = query
        if page_token:
            args["page_token"] = page_token
        if self._account:
            args["connected_account_id"] = self._account
        return self._execute("GMAIL_FETCH_EMAILS", args)

    def validate_connection(self) -> bool:
        self._fetch(max_results=1)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._fetch(max_results=limit, query=_BACKFILL_WINDOW,
                                          page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        # Resume from the stored watermark (date-granular → a natural overlap that the
        # dedup ledger de-dups) so nothing at the boundary is missed. No watermark yet
        # (first-ever connect+sync) → backfill the last month (see _BACKFILL_WINDOW) so onboarding
        # is quick. Subsequent syncs use the watermark and pull only new mail.
        query = f"after:{since.strftime('%Y/%m/%d')}" if since else _BACKFILL_WINDOW
        return self._to_batch(self._fetch(max_results=limit, query=query, page_token=cursor))

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return self._execute("GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID", {"message_id": object_ref})

    # -- full-message + attachment retrieval ---------------------------------------
    def _full_message(self, mid: str) -> dict:
        """Fetch the FULL MIME message (payload.parts + full body). Defensive: any failure
        (not connected, API error, unknown shape) → {} and we fall back to the list message."""
        try:
            r = self.fetch_content(mid)
        except Exception:      # noqa: BLE001 — never let one message abort the batch
            return {}
        d = r.get("data", r) if isinstance(r, dict) else {}
        return d if isinstance(d, dict) else {}

    def _attachment_bytes(self, mid: str, attachment_id: str | None) -> bytes:
        """Download one attachment's bytes via Gmail's attachments.get. Defensive → b'' on any error."""
        if not attachment_id:
            return b""
        try:
            r = self._execute("GMAIL_GET_ATTACHMENT",
                              {"message_id": mid, "attachment_id": attachment_id})
        except Exception:      # noqa: BLE001
            return b""
        d = r.get("data", r) if isinstance(r, dict) else {}
        return _b64url(d.get("data") or d.get("attachmentData") or d.get("body") if isinstance(d, dict) else "")

    def _attachment_stub(self, *, mid: str, att: dict, idx: int, occurred, sender_email,
                         to_emails, cc_emails, status: str) -> RawObject:
        """A NAMED attachment we could not extract — an unsupported type, or a failed download.
        Emit it anyway with an empty body + a document status so the gate PARKS it (DOC-02
        unsupported / DOC-05 fetch_failed — reviewable, and a failed download is retryable),
        instead of silently dropping a real file. has_attachment=True keeps it out of the
        N-10 empty-drop. Store-don't-delete."""
        return RawObject(
            source="gmail", object_type="email_attachment",
            source_object_id=f"{mid}::{att.get('attachmentId') or att.get('filename') or idx}",
            occurred_at=occurred, actor_email=sender_email, actor_type="external_contact",
            parent_object_id=mid,
            raw={
                "subject": att.get("filename") or "attachment",
                "body": "",
                "mime": att.get("mime"),
                "has_attachment": True,
                "document": {"status": status, "native_parse_used": False, "ocr_used": False,
                             "ocr_engine": None, "ocr_pages": 0, "avg_confidence": 0.0},
                "to": to_emails, "cc": cc_emails,
            },
        )

    @staticmethod
    def _walk(payload: Any, texts: list, atts: list) -> None:
        """Recursively collect (mime, bytes) text bodies and attachment part-refs from a Gmail
        MIME payload — so the FULL body (not a 280-char snippet) and every PDF/file are captured."""
        if not isinstance(payload, dict):
            return
        for p in (payload.get("parts") or []):
            ComposioGmailConnector._walk(p, texts, atts)
        mime = payload.get("mimeType") or ""
        filename = payload.get("filename") or ""
        body = payload.get("body") or {}
        data = body.get("data") if isinstance(body, dict) else None
        att_id = body.get("attachmentId") if isinstance(body, dict) else None
        if filename and (att_id or data):                       # an attachment part
            atts.append({"filename": filename, "mime": mime, "attachmentId": att_id, "data": data})
        elif mime in ("text/plain", "text/html") and data:       # a body text part
            texts.append((mime, _b64url(data)))

    # -- response mapping (adjust field paths on first live run) --------------------
    def _to_batch(self, result: Any) -> SourceBatch:
        data = result.get("data", result) if isinstance(result, dict) else {}
        messages = (data.get("messages") or data.get("emails")
                    or data.get("response_data") or [])
        objs: list[RawObject] = []
        for m in messages:
            if isinstance(m, dict):
                objs.extend(self._to_objects(m))       # email + its attachments
        cursor = data.get("nextPageToken") or data.get("next_page_token")
        return SourceBatch(objects=objs, next_cursor=cursor)

    def _to_raw(self, m: dict) -> RawObject | None:
        """The email object only (attachments come from _to_objects). Kept for callers/tests."""
        objs = self._to_objects(m)
        return objs[0] if objs else None

    def _to_objects(self, m: dict) -> list[RawObject]:
        """One Gmail message → [email_message] + one [email_attachment] per file. The email carries
        the FULL body (walked from MIME parts, snippet only as fallback); each attachment is text-
        extracted (native/OCR) exactly like a Drive file so its content reaches the graph too."""
        mid = m.get("messageId") or m.get("id") or m.get("message_id")
        if not mid:
            return []
        mid = str(mid)

        # Pull the FULL MIME message UNLESS the list row already carries a complete MIME structure
        # (payload.parts, walked below). A flat body string of ANY length may be Gmail's clipped
        # preview — and for deep extraction a signal (competitor, pricing, legal, budget) can sit
        # anywhere in the body, so we never feed the LLM a possibly-truncated body. Full-fetch is one
        # extra call for exactly the at-risk emails; if it fails we fall back to the list row (safe).
        # (Was: only fetched full when body < 400 chars → a 500-char clip of a 2,000-char email slipped
        #  through truncated → the LLM missed everything past the clip.)
        list_body = m.get("messageText") or m.get("body") or ""
        list_body = list_body if isinstance(list_body, str) else ""
        list_payload = m.get("payload") if isinstance(m.get("payload"), dict) else None
        need_full = not (list_payload and list_payload.get("parts"))
        full = self._full_message(mid) if need_full else {}
        src = full or m                                  # prefer the full message for every field
        payload = (src.get("payload") if isinstance(src.get("payload"), dict) else list_payload)

        def pick(*keys):
            for k in keys:
                v = src.get(k) if isinstance(src, dict) else None
                if v:
                    return v
            for k in keys:
                v = m.get(k)
                if v:
                    return v
            return None

        sender = pick("sender", "from") or _header(src, "From") or _header(m, "From")
        sender_email = _extract_email(sender)
        to_emails = _extract_emails(m.get("to"), m.get("toRecipients"),
                                    _header(src, "To"), _header(m, "To"))
        cc_emails = _extract_emails(m.get("cc"), m.get("ccRecipients"),
                                    _header(src, "Cc"), _header(m, "Cc"))
        occurred = _parse_ts(src if isinstance(src, dict) and src else m)
        subject = pick("subject") or _header(src, "Subject") or _header(m, "Subject")
        thread = pick("threadId", "thread_id")
        labels = pick("labelIds", "labels") or []
        # noise-relevant headers → without this dict the gate's N-01/N-02/N-04 rules never fired on
        # real Gmail, so bulk/automated mail wasted an L2 LLM call before being dropped as noise.
        headers = {h: v for h in _NOISE_HEADERS if (v := (_header(src, h) or _header(m, h)))}

        # walk MIME → full body text + attachment refs
        texts: list = []
        atts: list = []
        self._walk(payload, texts, atts)
        plain = next((t for mm, t in texts if mm == "text/plain"), b"")
        html = next((t for mm, t in texts if mm == "text/html"), b"")
        body_bytes = plain or html
        body = body_bytes.decode("utf-8", "replace") if body_bytes else list_body
        preview = pick("preview", "snippet") or ""
        preview = preview if isinstance(preview, str) else ""
        snippet = preview if len(preview.strip()) >= 20 else body[:280]

        objs = [RawObject(
            source="gmail", object_type="email_message", source_object_id=mid,
            occurred_at=occurred, actor_email=sender_email, actor_type="external_contact",
            parent_object_id=thread,
            raw={
                "subject": subject,
                "body": body,                 # FULL text now → preprocess → L2
                "snippet": snippet,
                "labelIds": labels,
                "headers": headers,            # revives the header-based noise rules (N-01/02/04)
                "to": to_emails, "cc": cc_emails,
                "has_attachment": bool(atts),  # keeps attachment-only emails out of the N-10 drop
            },
        )]

        # each attachment → its own DOCUMENT event (mirrors the Drive connector): download bytes,
        # extract text natively/OCR, gate + L2 it. "PDF me file hai usse bhi banke aana chahiye."
        for i, a in enumerate(atts):
            mime = (a.get("mime") or "").lower()
            # skip non-extractable files BEFORE the expensive per-file download (this is the L1
            # speed fix): only PDFs/Office/txt, or images when OCR is on, are worth fetching.
            worth = mime in _EXTRACTABLE_ATTACHMENT_MIMES or (self._ocr and mime.startswith("image/"))
            if not worth:
                # Don't SILENTLY vanish a real named file. Inline signature images / tracking
                # pixels (image001.png, gifs) are true noise → skip; a .csv / .zip / screenshot
                # invoice lands as a stub that PARKS (DOC-02, reviewable). Store-don't-delete.
                fn = (a.get("filename") or "").lower()
                if mime == "image/gif" or re.match(r"image\d{3}\.\w+$", fn):
                    continue
                objs.append(self._attachment_stub(
                    mid=mid, att=a, idx=i, occurred=occurred, sender_email=sender_email,
                    to_emails=to_emails, cc_emails=cc_emails, status="unsupported"))
                continue
            raw_bytes = _b64url(a.get("data")) if a.get("data") else \
                self._attachment_bytes(mid, a.get("attachmentId"))
            if not raw_bytes:
                # a file we WANTED (pdf/docx/…) whose download failed → park + retry, never lose it
                objs.append(self._attachment_stub(
                    mid=mid, att=a, idx=i, occurred=occurred, sender_email=sender_email,
                    to_emails=to_emails, cc_emails=cc_emails, status="fetch_failed"))
                continue
            r = process_document(mime=a.get("mime") or "", data=raw_bytes,
                                 filename=a.get("filename") or "", ocr=self._ocr)
            objs.append(RawObject(
                source="gmail", object_type="email_attachment",
                source_object_id=f"{mid}::{a.get('attachmentId') or a.get('filename') or i}",
                occurred_at=occurred, actor_email=sender_email, actor_type="external_contact",
                parent_object_id=mid,          # links the file back to its email
                raw={
                    "subject": a.get("filename") or "attachment",
                    "body": r.text,            # extracted document text → L2 facts
                    "mime": a.get("mime"),
                    "has_attachment": bool(r.text),
                    "document": {"native_parse_used": r.native_parse_used, "ocr_used": r.ocr_used,
                                 "ocr_engine": r.ocr_engine, "ocr_pages": r.ocr_pages,
                                 "avg_confidence": r.avg_confidence, "status": r.status},
                    "to": to_emails, "cc": cc_emails,
                },
            ))
        return objs
