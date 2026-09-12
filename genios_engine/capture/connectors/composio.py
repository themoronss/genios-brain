from __future__ import annotations

import base64
import binascii
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Mapping

# Run the cheap deterministic junk rules (Gmail labels + automated senders) BEFORE the S2 LLM prime,
# so obvious junk never costs a model call. On by default; set false for a clean rollback to
# LLM-gates-everything behaviour.
_DET_JUNK_PREFILTER = os.environ.get("GENIOS_L1_DET_JUNK", "true").lower() != "false"

# Bounded concurrency for the per-message full-body fetch (the slow part: one Composio call per
# message). This is NETWORK-ONLY work — no DB touched here — so it never pressures the DB pool; the
# ceiling keeps us under Composio's rate limits and avoids a thread explosion inside a background
# backfill. DB writes stay in run_sync's own separate bounded pool.
# Per-page full-body fetches. These are Composio HTTP calls — pure network wait, no DB slot and
# no local CPU — so the only reason this was 6 is caution inherited from the DB budget next door.
_FETCH_WORKERS = int(os.environ.get("GENIOS_L1_FETCH_WORKERS", "12"))

from genios_engine.capture.documents.native import process_document
from genios_engine.capture.documents.router import has_pages
# The fetch decision and the gate decision key on the SAME threshold, or they drift — and this
# import is load-bearing at RUNTIME only (_skip_body), which is exactly how its absence shipped:
# the module imported cleanly, every test passed, and the first real fetch with a drop verdict
# raised NameError and took the whole gmail sync down.
from genios_engine.capture.gate.relevance import DROP_BELOW_RELEVANCE

from .backfill import DEFAULT_BACKFILL_DAYS, BackfillWindow
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
                  "List-Id", "List-Post", "Feedback-ID",
                  # vacation-responder markers → the N-05 availability marker (not a drop)
                  "X-Autoreply", "X-Autorespond")

# L1.2.4-U1 — the first-connect backfill window is NO LONGER a constant here. It was
# `_BACKFILL_WINDOW = "newer_than:60d"`, which handed every tenant the same two months of history
# with no way to change it short of a deploy. It is now a per-connection setting resolved by
# `connectors/backfill.py` and passed in at construction; see that module for why 540 days is the
# default and why existing connections keep 60 until an admin raises them.


def _extract_email(s: str | None) -> str | None:
    if not s:
        return None
    m = _EMAIL.search(s)
    return m.group(0).lower() if m else None


def _extract_display_name(s: str | None) -> str | None:
    """The human name out of `"Deepthi Chandrashekhar" <deepthi@...>`, or None if there isn't one.

    Parsed with `email.utils.parseaddr`, which is the standard's own reader for this — hand-rolled
    quote stripping gets RFC 2047 encoded words and comma-in-quotes wrong, and both are ordinary in
    real mail.

    Returns None rather than a guess in the three cases where a source supplies something that is
    not a name: an empty display part, a display part that IS the address (many clients repeat it),
    and a bare local-part echo. Naming a person "ydvkhushi721" because that is what precedes the @
    would be a confident lie, where showing the address is merely ugly — so the fallback stays the
    address and this returns nothing.
    """
    if not s:
        return None
    from email.utils import parseaddr
    name, addr = parseaddr(str(s))
    name = (name or "").strip().strip('"').strip()
    if not name:
        return None
    if _EMAIL.search(name):
        return None                                  # the display part is just the address again
    if addr and name.lower() == addr.split("@", 1)[0].lower():
        return None                                  # ...or a bare local-part echo
    return name


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
                 connected_account_id: str | None = None, ocr=None, relevance=None,
                 backfill_days: int = DEFAULT_BACKFILL_DAYS) -> None:
        # How far back a FIRST sync reaches, per connection (L1.2.4-U1). Validated here rather
        # than at query time so a bad admin setting fails at construction, loudly, instead of
        # producing a silently narrow sync that still reports success.
        self.backfill_window = BackfillWindow(days=backfill_days)
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
        return self._to_batch(self._fetch(max_results=limit,
                                          query=self.backfill_window.gmail_query(),
                                          page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        # Resume from the stored watermark (date-granular → a natural overlap that the
        # dedup ledger de-dups) so nothing at the boundary is missed. No watermark yet
        # (first-ever connect+sync) → backfill this connection's configured window.
        query = (f"after:{since.strftime('%Y/%m/%d')}" if since
                 else self.backfill_window.gmail_query())
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

    def fetch_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """L1.3.8-U1 — download one attachment's bytes, and RAISE when that does not happen.

        The sibling `_attachment_bytes` swallows every error into ``b""``, which is right for a
        sync (one unreadable file must never abort a 2000-message batch) and useless for the
        refetch ladder: ``b""`` cannot say whether the message was DELETED — in which case no
        number of retries produces bytes and the park should be dead-lettered now — or whether
        Composio timed out, which is exactly what a backoff exists for. So the honest fetch is
        the method, and the swallowing one is a wrapper over it: one request path, two error
        policies, no chance of the two drifting.

        Satisfies `capture/parked/refetch.py::AttachmentFetcher`.
        """
        if not attachment_id:
            raise ValueError(
                f"no provider attachment id for message {message_id!r} — the parked reference "
                "carries only a filename, which Gmail cannot be asked for")
        r = self._execute("GMAIL_GET_ATTACHMENT",
                          {"message_id": message_id, "attachment_id": attachment_id})
        if isinstance(r, dict) and r.get("successful") is False:
            # Composio reports a tool failure in the envelope rather than by raising, so a
            # response that "arrived" can still be a 404. The message text is what
            # `refetch_policy.classify_fetch_error` reads to decide retry versus terminal.
            raise RuntimeError(f"gmail attachment fetch failed for "
                               f"{message_id}::{attachment_id}: {r.get('error') or 'no detail'}")
        d = r.get("data", r) if isinstance(r, dict) else {}
        data = _b64url(d.get("data") or d.get("attachmentData") or d.get("body") if isinstance(d, dict) else "")
        if not data:
            raise RuntimeError(f"gmail returned no attachment data for "
                               f"{message_id}::{attachment_id}")
        return data

    def _attachment_bytes(self, mid: str, attachment_id: str | None) -> bytes:
        """Download one attachment's bytes via Gmail's attachments.get. Defensive → b'' on any error."""
        try:
            return self.fetch_attachment(mid, attachment_id or "")
        except Exception:      # noqa: BLE001 — a sync never dies on one file; the refetch ladder
            return b""         # is the path that needs the reason, and it calls fetch_attachment

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
                             "ocr_engine": None, "ocr_pages": 0, "confidence_bp": None},
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
            from genios_engine.capture.gate.rules import availability_marker, light_junk
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
                    if not objs:
                        continue
                    # L1.3.8-U2 — attachment presence overrides junk confidence. A
                    # PROMOTIONS-labelled message carrying a signed contract is junk MAIL with a
                    # real document inside it, and dropping it here costs the document: the light
                    # pass never fetched the MIME payload, so `_walk` found no attachment parts
                    # and no attachment event was ever built. The email itself is still dropped —
                    # the pipeline gate applies the same N-06 rule to the full-fetched message —
                    # but the attachment reaches the gate as its own event and survives.
                    if attachment_overrides_junk(m, objs, ocr_enabled=self._ocr is not None):
                        continue
                    if light_junk(objs[0].raw.get("labelIds"), objs[0].actor_email,
                                  bool(objs[0].raw.get("has_attachment"))):
                        det_junk.add(id(m))
            # An availability notice (N-05) skips the LLM junk gate at the pipeline, so it must not
            # spend a prime call here either — nor be left as a body-less snippet by one.
            all_light = [o for m, objs in light if id(m) not in det_junk for o in objs
                         if not availability_marker(o.raw)]
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
            def _skip_body(m, objs) -> bool:
                if not objs or availability_marker(objs[0].raw):
                    return False
                # L1.3.8-U2 — the same override, against the LLM's confident drop. This is the
                # case the spec names: "a junk-classified email with a real contract attached
                # loses the contract". Confidence about the PROSE says nothing about the file.
                if attachment_overrides_junk(m, objs, ocr_enabled=self._ocr is not None):
                    return False
                v = rel.verdict_for(objs[0].source_object_id)
                if not v or v.disposition != "drop":
                    return False
                # Unconfident drop → the gate will PARK it, and a park needs a body to be worth
                # anything. Only confident junk is cheap enough to leave unfetched.
                return not (v.relevance is not None and v.relevance >= DROP_BELOW_RELEVANCE)

            keepers = [m for m, objs in light
                       if id(m) not in det_junk and not _skip_body(m, objs)]
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

    def webhook_objects(self, payload: Mapping[str, Any]) -> tuple[RawObject, ...]:
        """L1.2.5-U1 — one pushed Gmail trigger → exactly what a poll of that message emits.

        It funnels into `_to_objects`, the SAME parser the sweep uses, so the two doors cannot
        drift: the attachment events, the header-derived noise fields and the recipient tuple all
        exist on the webhook path because there is only one place that builds them.
        """
        message = payload.get("message") or payload.get("email") or payload
        if not isinstance(message, Mapping):
            return ()
        return tuple(self._to_objects(dict(message)))

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
            occurred_at=occurred, actor_email=sender_email,
            actor_name=_extract_display_name(sender), actor_type="external_contact",
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
                # W-04, WIRED. `gate/rules.whitelist` has read `raw["important_attachment"]` since
                # the gate was written and NOTHING in the engine ever set it, so the rung named
                # "a contract/invoice is attached, do not blanket-drop this" could not fire — a
                # documented rule that is unreachable is the same as an absent one, and harder to
                # notice. It matters for exactly one class: N-06/N-07 drop on Gmail's own
                # PROMOTIONS/SOCIAL guess REGARDLESS of attachments (unlike N-02/03/04, which
                # already exempt them), so a renewal notice with the countersigned PDF attached,
                # from a sender we have not met yet, lost its covering email and every date and
                # amount stated in it. The FILE always survived — `attachment_overrides_junk`
                # forces the full fetch and the attachment lands as its own event with no labels
                # on it — but a contract with no covering message is a document with no context.
                #
                # Deliberately narrow: only a part we could actually READ (`_is_extractable_part`
                # over the real MIME/extension table), never an `invite.ics` or a signature image,
                # because the whitelist skips EVERY N-code and a wider rule would readmit the
                # newsletter volume the prefilter exists to refuse.
                "important_attachment": any(
                    _is_extractable_part(a.get("mime"), a.get("filename"),
                                         ocr_enabled=self._ocr is not None)
                    for a in atts),
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
                # pixels (image001.png, gifs) are true noise → skip; a .csv / .zip / a screenshot
                # invoice lands as a stub that PARKS (reviewable). Store-don't-delete.
                fn = (a.get("filename") or "").lower()
                if mime == "image/gif" or re.match(r"image\d{3}\.\w+$", fn):
                    continue
                # WHICH park code, and why the distinction is the whole point. `unsupported`
                # (DOC-02) says *nothing can ever read this* — a .zip, a firmware blob — and it
                # is terminal: `parked/drain.py` will not requeue it. A screenshot invoice or a
                # scanned PO is the opposite: readable in principle, unread only because no OCR
                # engine is wired on this host, which is `ocr_unavailable` (DOC-06) and is fixed
                # by one config line plus a redeploy. `documents/router.py` already draws this
                # line for the files we DO download ("`unsupported` shrank"); the pre-download
                # skip above never learned it, so every scanned attachment in production was
                # filed as permanently unreadable and the OCR gap it actually reported was
                # invisible. `has_pages` is imported from the router rather than restated here,
                # so the two doors cannot drift about what "has pages" means.
                status = "ocr_unavailable" if has_pages(mime, fn) else "unsupported"
                objs.append(self._attachment_stub(
                    mid=mid, att=a, idx=i, occurred=occurred, sender_email=sender_email,
                    to_emails=to_emails, cc_emails=cc_emails, status=status))
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
                    # `page_offsets` is L1.3.4-U5's map: where each page of this file begins in
                    # the text above. Carried on the event because it exists for one moment
                    # inside the extractor and is unrecoverable afterwards — it is what lets an
                    # evidence span say "page 4" instead of "character 4,812".
                    "document": {"native_parse_used": r.native_parse_used, "ocr_used": r.ocr_used,
                                 "ocr_engine": r.ocr_engine, "ocr_pages": r.ocr_pages,
                                 "confidence_bp": r.confidence_bp, "status": r.status,
                                 "page_offsets": list(r.page_offsets), "first_page": 1},
                    "to": to_emails, "cc": cc_emails,
                },
            ))
        return objs


# ── L1.3.8-U2 · Gmail fast-path attachment recovery ──────────────────────────────────────────
#
# The fast path exists because full-fetching every message costs one Composio round-trip each and
# ~95% of a real inbox is newsletters. It gates on the cheap LIST fields and full-fetches only the
# keepers. The bug is what "keeper" was allowed to mean: a message the gate was CONFIDENT was junk
# was never fetched, and a Gmail list entry carries no MIME payload — so `_walk` found no
# attachment parts, no `email_attachment` event was built, and the PDF invoice on that message
# stopped existing. Not parked. Not dropped with a trace. It was never an object.
#
# The rule the spec states is absolute and it is the right one: **attachment presence overrides
# junk confidence.** Note what it does NOT do — it does not keep the email. The message still
# meets the pipeline gate with the same verdict and is still dropped; all this buys is the FETCH,
# which is what turns the attachment into its own event that can be judged on its own merits.
#
# The extractable-mime qualifier is load-bearing in the other direction. Overriding on ANY named
# part would mean every promotional mail with an `invite.ics` or a vcard defeats the deterministic
# prefilter, and the prefilter is the thing that keeps a 2000-message backfill affordable. So:
#   * a part we can read (PDF/Office/text, or an image when OCR is wired) overrides;
#   * a part we cannot read does not — it would only ever have become a DOC-02 review stub;
#   * an OPAQUE signal ("this message has an attachment", with no type) overrides, because the
#     only way to learn the type is to fetch, and guessing "probably junk" is how the contract
#     was lost the first time.

#: Filename extensions that imply an extractable mime when the list entry gives us no mimeType.
#: Gmail's list payloads are inconsistent about `mimeType` on attachment parts, and a part named
#: `MSA-countersigned.pdf` with a blank mime is not an unknown format — it is a PDF.
_EXTRACTABLE_ATTACHMENT_EXTS = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "md": "text/markdown",
}

#: Message-level fields that mean "there is an attachment" without saying what it is. Different
#: Composio/Gmail list shapes use different spellings; all of them are opaque in the same way.
_OPAQUE_ATTACHMENT_FIELDS = ("hasAttachment", "has_attachment", "hasAttachments",
                             "attachments", "attachmentIds", "attachment_ids")


def _effective_mime(mime: str | None, filename: str | None) -> str:
    """The part's mime, falling back to what its extension says. Lowercased, never None."""
    declared = (mime or "").strip().lower()
    if declared:
        return declared
    ext = (filename or "").rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""
    return _EXTRACTABLE_ATTACHMENT_EXTS.get(ext, "")


def _is_extractable_part(mime: str | None, filename: str | None, *, ocr_enabled: bool) -> bool:
    """Whether this part is one we could read if we fetched it — the SAME test `_to_objects`
    applies before paying for the download, so the fast path and the slow path cannot disagree
    about which files are worth the round-trip."""
    effective = _effective_mime(mime, filename)
    if not effective:
        return False
    return (effective in _EXTRACTABLE_ATTACHMENT_MIMES
            or (ocr_enabled and effective.startswith("image/")))


def _typed_attachment_parts(message: dict, light_objects) -> list[tuple[str | None, str | None]]:
    """Every attachment part we can put a (mime, filename) to from LIST-time data alone.

    Two sources, because the light pass sees the list entry in two shapes: the raw Gmail payload
    when the list response carried MIME parts, and the `email_attachment` objects `_to_objects`
    already built from it. Reading only one of them makes the override depend on which shape the
    provider happened to send.
    """
    parts: list[tuple[str | None, str | None]] = []
    payload = message.get("payload") if isinstance(message.get("payload"), dict) else None
    if payload is not None:
        texts: list = []
        atts: list = []
        ComposioGmailConnector._walk(payload, texts, atts)
        parts.extend((a.get("mime"), a.get("filename")) for a in atts)
    for obj in light_objects or ():
        if getattr(obj, "object_type", None) == "email_attachment":
            raw = getattr(obj, "raw", None) or {}
            parts.append((raw.get("mime"), raw.get("subject")))
    return parts


def _has_opaque_attachment_flag(message: dict) -> bool:
    """A list entry that says "there is an attachment" without saying what it is."""
    for field in _OPAQUE_ATTACHMENT_FIELDS:
        value = message.get(field)
        if isinstance(value, (list, tuple, set)):
            if len(value) > 0:
                return True
        elif isinstance(value, bool):
            if value:
                return True
        elif isinstance(value, str):
            if value.strip().lower() in ("true", "yes", "1"):
                return True
        elif value:
            return True
    return False


def attachment_overrides_junk(message: dict, light_objects, *,
                              ocr_enabled: bool = False) -> bool:
    """L1.3.8-U2 — must this message be full-fetched despite a confident junk verdict?

    True when the LIST fields show a readable attachment, or show an attachment whose type they
    do not disclose. False for a message with no attachment signal at all, and false for one whose
    only attachments are formats we could not read even after downloading them — those would have
    become review stubs at best, and buying a network round-trip per newsletter to create review
    stubs is how a recall fix turns into a cost regression.
    """
    if not isinstance(message, dict):
        return False
    parts = _typed_attachment_parts(message, light_objects)
    if parts:
        return any(_is_extractable_part(mime, filename, ocr_enabled=ocr_enabled)
                   for mime, filename in parts)
    return _has_opaque_attachment_flag(message)
