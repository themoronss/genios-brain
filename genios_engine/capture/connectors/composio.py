from __future__ import annotations

import base64
import binascii
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

# Run the cheap deterministic junk rules (Gmail labels + automated senders) BEFORE the S2 LLM prime,
# so obvious junk never costs a model call. On by default; set false for a clean rollback to
# LLM-gates-everything behaviour.
_DET_JUNK_PREFILTER = os.environ.get("GENIOS_L1_DET_JUNK", "true").lower() != "false"

# Bounded concurrency for the per-message full-body fetch (the slow part: one Composio call per
# message). This is NETWORK-ONLY work — no DB touched here — so it never pressures the DB pool; the
# ceiling keeps us under Composio's rate limits and avoids a thread explosion inside a background
# backfill. DB writes stay in run_sync's own separate bounded pool.
_FETCH_WORKERS = 6

from genios_engine.capture.documents.native import process_document
# The fetch decision and the gate decision key on the SAME threshold, or they drift — and this
# import is load-bearing at RUNTIME only (_skip_body), which is exactly how its absence shipped:
# the module imported cleanly, every test passed, and the first real fetch with a drop verdict
# raised NameError and took the whole gmail sync down.
from genios_engine.capture.gate.relevance import DROP_BELOW_RELEVANCE

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
_BACKFILL_WINDOW = "newer_than:60d"     # first-connect backfill: last 2 months of email history


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
                 connected_account_id: str | None = None, ocr=None, relevance=None) -> None:
        self._api_key = api_key
        self._user_id = user_id
        self._account = connected_account_id or None
        self._client: Any = None
        self._ocr = ocr          # OcrEngine | None — for scanned-PDF attachments (native-only if None)
        # Optional S2 classifier. When it can batch-gate on the cheap LIST snippet, we skip the slow
        # per-message full-body fetch for confident DROPS — full-fetch runs ONLY for keepers. The
        # SAME instance is handed to the pipeline, so its primed verdict is reused (no re-call).
        self._relevance = relevance

    def _client_(self) -> Any:
        if self._client is None:
            from composio import Composio          # lazy: only needed on real runs
            # Explicit timeout — see composio_base.ComposioExec._c() for why omitting it leaves the
            # underlying httpx client with NO bound at all, which can wedge the single-threaded
            # scheduler forever on one stalled Gmail call. This connector has no ThreadPoolExecutor
            # deadline wrapper (unlike ComposioExec), so this is its ONLY defense against a hang.
            self._client = Composio(api_key=self._api_key, timeout=60)
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
            # An attachment belongs to the same conversation as its message, so it carries the
            # same participant set — otherwise a deck arrives with no idea who it was sent to.
            recipients=tuple(to_emails) + tuple(cc_emails),
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
        messages = [m for m in (data.get("messages") or data.get("emails")
                    or data.get("response_data") or []) if isinstance(m, dict)]
        cursor = data.get("nextPageToken") or data.get("next_page_token")
        if not messages:
            return SourceBatch(objects=[], next_cursor=cursor)

        # FAST PATH: gate on the cheap LIST snippet first, then full-fetch ONLY the keepers. On a
        # newsletter-heavy inbox this skips ~95% of the slow per-message calls. Needs a classifier
        # that can batch-prime (prime()) and answer verdict_for(id). Bias is KEEP: anything not a
        # confident DROP is full-fetched, so recall (and L2's full body) is preserved.
        rel = self._relevance
        if rel is not None and hasattr(rel, "prime") and hasattr(rel, "verdict_for"):
            from genios_engine.capture.gate.rules import light_junk
            light: list[tuple[dict, list[RawObject]]] = [(m, self._to_objects(m, fetch_full=False))
                                                         for m in messages]
            # DETERMINISTIC PRE-FILTER — the cheap rules run BEFORE the LLM, not after. Gmail's own
            # PROMOTIONS/SOCIAL/SPAM labels and clearly-automated senders are high-confidence junk we
            # can drop from the LIST fields alone, so they never cost an S2 gate call. On a real inbox
            # this is most of the volume. Header-only bulk signals (List-Unsubscribe) still need the
            # full body → they stay on the LLM path. Flag-guarded (GENIOS_L1_DET_JUNK) for rollback.
            det_junk: set[int] = set()
            if _DET_JUNK_PREFILTER:
                for m, objs in light:
                    if objs and light_junk(objs[0].raw.get("labelIds"), objs[0].actor_email,
                                           bool(objs[0].raw.get("has_attachment"))):
                        det_junk.add(id(m))
            all_light = [o for m, objs in light if id(m) not in det_junk for o in objs]
            try:
                rel.prime(all_light)                          # LLM only on what the rules couldn't settle
            except Exception:      # noqa: BLE001 — gate failure → treat all as keepers (full-fetch)
                pass
            # A "drop" verdict is NOT sufficient to skip the body fetch.
            #
            # The gate only DELETES on a drop the model was confident about; below
            # DROP_BELOW_RELEVANCE it parks instead, and its own comment promises the park
            # "keeps a payload and can be re-adjudicated when the gate improves". That promise
            # was empty on this path: the fetch decision here ran FIRST and keyed on
            # `disposition == "drop"` alone, so every message the gate later parked had already
            # been reduced to a list snippet — the same snippet the model had just judged. Worse,
            # with no MIME payload `_walk` yields no attachment parts either, so a deck or
            # contract on a message the model called junk became no event at all.
            #
            # Same threshold, same constant, so the two surfaces cannot drift apart again.
            def _skip_body(objs) -> bool:
                if not objs:
                    return False
                v = rel.verdict_for(objs[0].source_object_id)
                if not v or v.disposition != "drop":
                    return False
                # Unconfident drop → the gate will PARK it, and a park needs a body to be worth
                # anything. Only confident junk is cheap enough to leave unfetched.
                return not (v.relevance is not None and v.relevance >= DROP_BELOW_RELEVANCE)

            keepers = [m for m, objs in light
                       if id(m) not in det_junk and not _skip_body(objs)]
            drops = {id(m) for m, _ in light} - {id(m) for m in keepers}
            # full-fetch keepers concurrently; CONFIDENT junk keeps its light (snippet) object —
            # the pipeline gate re-reads the SAME primed verdict and drops it without another
            # call. Unconfident drops are fetched in full so the park they become is recoverable.
            fetched: dict[int, list[RawObject]] = {}
            if keepers:
                workers = min(_FETCH_WORKERS, len(keepers))
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    for m, sub in zip(keepers, ex.map(lambda mm: self._to_objects(mm, fetch_full=True),
                                                      keepers)):
                        fetched[id(m)] = sub
            objs: list[RawObject] = []
            for m, light_objs in light:
                objs.extend(light_objs if id(m) in drops else fetched.get(id(m), light_objs))
            return SourceBatch(objects=objs, next_cursor=cursor)

        # LEGACY PATH (no priming classifier): full-fetch every message concurrently.
        workers = min(_FETCH_WORKERS, len(messages))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            per_message = list(ex.map(self._to_objects, messages))
        objs = [o for sub in per_message for o in sub]
        return SourceBatch(objects=objs, next_cursor=cursor)

    def _to_raw(self, m: dict) -> RawObject | None:
        """The email object only (attachments come from _to_objects). Kept for callers/tests."""
        objs = self._to_objects(m)
        return objs[0] if objs else None

    def _to_objects(self, m: dict, fetch_full: bool | None = None) -> list[RawObject]:
        """One Gmail message → [email_message] + one [email_attachment] per file. The email carries
        the FULL body (walked from MIME parts, snippet only as fallback); each attachment is text-
        extracted (native/OCR) exactly like a Drive file so its content reaches the graph too.

        fetch_full: None → decide by need_full (legacy); True → always full-fetch (keepers); False →
        LIGHT (list snippet only, NO per-message call) — used to gate cheaply before deciding."""
        mid = m.get("messageId") or m.get("id") or m.get("message_id")
        if not mid:
            return []
        mid = str(mid)

        # Full-fetch policy. For keepers we pull the FULL MIME message (a signal can sit anywhere in
        # the body); for a LIGHT pass (fetch_full=False) we use only the cheap list snippet so the
        # gate can drop obvious junk WITHOUT paying ~2000 per-message fetches. Legacy (None) keeps the
        # old need_full behaviour so nothing else changes.
        list_body = m.get("messageText") or m.get("body") or ""
        list_body = list_body if isinstance(list_body, str) else ""
        list_payload = m.get("payload") if isinstance(m.get("payload"), dict) else None
        if fetch_full is False:
            need_full = False
        elif fetch_full is True:
            need_full = True
        else:
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
            # Typed, so the participant set survives past the payload TTL — the raw dict
            # is encrypted and expires; this column does not.
            recipients=tuple(to_emails) + tuple(cc_emails),
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
                recipients=tuple(to_emails) + tuple(cc_emails),
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
