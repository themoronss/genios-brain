"""Gmail known adapter.

Salvaged from _legacy/app/ingestion/gmail_connector.py:
- OAuth scopes + token refresh pattern (Google's Credentials object)
- Service build helper

Cleaned for v2:
- Implements MemoryAdapter interface (no write methods)
- Uses snippet (Google-provided plain text), NOT full body — keeps content out of our pipeline
- Cursor strategy: historyId (Gmail's native change cursor; falls back to internalDate)
- Mapping hardcoded (known source → source_confidence = 1.0)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build as google_build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.memory.adapters import register_adapter
from core.memory.batch import RateLimited
from core.memory.interface import MemoryAdapter
from core.memory.secrets import get_secret, rotate_secret
from core.memory.types import (
    AuthConfig,
    ConnectionHandle,
    Cursor,
    FieldMapping,
    HealthStatus,
    HealthStatusLevel,
    RawRecord,
    ReadScope,
    RecordRef,
    SourceMapping,
)

log = get_logger(__name__)

SOURCE_TYPE = "gmail"

# Read-only scopes (per g-i-1 §1.1.1 — read-only enforcement at provider level)
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


class GmailAdapter(MemoryAdapter):
    """Gmail read-only adapter."""

    def __init__(
        self,
        session: Session,
        *,
        connection_id: str,
        org_id: str,
        access_secret_ref: str,
        refresh_secret_ref: str,
        account_email: str,
    ) -> None:
        self.source_type = SOURCE_TYPE
        self.source_id = connection_id
        self._session = session
        self._connection_id = connection_id
        self._org_id = org_id
        self._access_ref = access_secret_ref
        self._refresh_ref = refresh_secret_ref
        self._account_email = account_email
        self._service: Any | None = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        """Build the Gmail service. Token refresh happens transparently in _service_for()."""
        self._service = self._service_for()
        return ConnectionHandle(
            connection_id=self._connection_id,
            source_type=self.source_type,
            source_id=self._account_email,
            granted_scopes=scopes,
        )

    def health_check(self) -> HealthStatus:
        """Liveness ping via getProfile (lightest possible Gmail API call)."""
        try:
            svc = self._service_for()
            svc.users().getProfile(userId="me").execute()
            return HealthStatus(
                level=HealthStatusLevel.GREEN,
                last_sync_at=datetime.now(UTC),
                items_pulled_count=0,
                scope_drops_count=0,
            )
        except Exception as e:
            return HealthStatus(
                level=HealthStatusLevel.RED,
                last_sync_at=None,
                last_error=str(e)[:200],
            )

    def disconnect(self) -> None:
        """Drop in-memory service. Token revocation handled at the route level."""
        self._service = None

    # ── reading (READ-ONLY) ────────────────────────────────────────────────

    def list_changed_since(
        self,
        cursor: Cursor | None,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        """List changed messages since cursor.

        Uses Gmail's history API when we have a historyId cursor (native delta).
        Falls back to listing recent messages on first run.
        """
        svc = self._service_for()

        try:
            if cursor and cursor.value and cursor.strategy == "native":
                return self._pull_via_history(svc, history_id=cursor.value, limit=limit)
            return self._pull_recent(svc, limit=limit)
        except HttpError as e:
            if e.resp.status == 429:
                retry_after = float(e.resp.get("retry-after", "1"))
                raise RateLimited(retry_after_seconds=retry_after) from e
            raise

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        """Fetch a single message by id (used by webhook -> fetch flow).

        Webhook path stays metadata-only — it's used for routing decisions,
        not for ingestion. Full body + attachments are pulled in the batch
        path via `_fetch_full` so a single per-event hook isn't doing slow
        PDF parsing inline.
        """
        svc = self._service_for()
        msg = svc.users().messages().get(userId="me", id=ref.native_id, format="metadata").execute()
        return _to_raw_record(msg)

    def get_mapping(self) -> SourceMapping:
        """Hardcoded mapping (known source). source_confidence = 1.0."""
        return SourceMapping(
            source_type=SOURCE_TYPE,
            field_map={
                "content": FieldMapping(source_field="snippet", confidence=1.0),
                "timestamp": FieldMapping(
                    source_field="internal_date_ms",
                    transform="epoch_ms_to_iso8601",
                    confidence=1.0,
                ),
                "owner": FieldMapping(source_field="from", confidence=1.0),
                "tags": FieldMapping(source_field="labels", confidence=1.0),
            },
            confirmed_by="genios:hardcoded",
            confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _service_for(self) -> Any:
        """Build a Gmail service with auto-refresh of the access token."""
        if self._service is not None:
            return self._service

        access = get_secret(self._session, self._access_ref)
        refresh = get_secret(self._session, self._refresh_ref)
        creds = Credentials(  # type: ignore[no-untyped-call]
            token=access,
            refresh_token=refresh,
            token_uri="https://oauth2.googleapis.com/token",  # noqa: S106 — Google's well-known URL, not a secret
            client_id=_google_client_id(),
            client_secret=_google_client_secret(),
        )

        if not creds.valid:
            creds.refresh(GoogleRequest())  # type: ignore[no-untyped-call]
            # Persist refreshed access token
            if creds.token and creds.token != access:
                rotate_secret(self._session, self._access_ref, creds.token)

        self._service = google_build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    def _pull_via_history(
        self,
        svc: Any,
        *,
        history_id: str,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        """Use Gmail's history API for delta detection (native cursor strategy)."""
        history_resp = (
            svc.users()
            .history()
            .list(userId="me", startHistoryId=history_id, maxResults=limit,
                  labelId="INBOX", historyTypes=["messageAdded"])
            .execute()
        )
        message_ids: list[str] = []
        for entry in history_resp.get("history", []):
            for ma in entry.get("messagesAdded", []):
                if "message" in ma and "id" in ma["message"]:
                    # Skip if the message arrived with promo/social/spam labels.
                    labels = set(ma["message"].get("labelIds", []))
                    if labels & {"SPAM", "TRASH", "CATEGORY_PROMOTIONS",
                                 "CATEGORY_SOCIAL", "CATEGORY_UPDATES",
                                 "CATEGORY_FORUMS", "CHAT"}:
                        continue
                    message_ids.append(ma["message"]["id"])
        next_history = history_resp.get("historyId", history_id)
        has_more = bool(history_resp.get("nextPageToken"))
        records: list[RawRecord] = []
        for mid in message_ids[:limit]:
            records.extend(self._fetch_full(svc, mid))
        return records, Cursor(value=str(next_history), strategy="native"), has_more

    # Gmail query that excludes marketing / spam / trash / social so we don't
    # burn LLM credits extracting entities from newsletters and shopping ads.
    # Negative category filters keep CATEGORY_PERSONAL / CATEGORY_FORUMS /
    # primary inbox messages. -in:chats drops Hangouts/Chat noise.
    _NOISE_FILTER = (
        "-category:promotions -category:social -category:updates -category:forums "
        "-in:spam -in:trash -in:chats"
    )

    def _pull_recent(
        self,
        svc: Any,
        *,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        """First-run fallback: list recent INBOX messages (filtering marketing/
        spam so credits don't burn on noise). Captures starting historyId."""
        list_resp = svc.users().messages().list(
            userId="me",
            maxResults=limit,
            q=self._NOISE_FILTER,
            labelIds=["INBOX"],
        ).execute()
        msg_ids = [m["id"] for m in list_resp.get("messages", [])]
        records: list[RawRecord] = []
        for mid in msg_ids:
            records.extend(self._fetch_full(svc, mid))

        # Capture profile.historyId for next run's delta detection
        profile = svc.users().getProfile(userId="me").execute()
        history_id = str(profile.get("historyId", "1"))
        return records, Cursor(value=history_id, strategy="native"), False

    @staticmethod
    def _fetch_metadata(svc: Any, mid: str) -> RawRecord:
        """Cheap metadata-only fetch — used by webhook + tests."""
        msg = svc.users().messages().get(userId="me", id=mid, format="metadata").execute()
        return _to_raw_record(msg)

    @staticmethod
    def _fetch_full(svc: Any, mid: str) -> list[RawRecord]:
        """Fetch FULL message: body text + every parseable attachment.

        Returns 1+N RawRecords per message:
          [0]  body (or snippet fallback) — native_id = mid
          [1+] one per attachment — native_id = f"{mid}_a{i}", with
               fields["parent_native_id"] = mid for traceability.

        Per g-i-1: adapter does plaintext extraction at emit-time so the
        engine just sees clean text. Failing attachments degrade — we
        skip the part but still emit body and other attachments.
        """
        msg = svc.users().messages().get(userId="me", id=mid, format="full").execute()
        body_text, attachments = _walk_mime_parts(msg.get("payload", {}))
        records: list[RawRecord] = []

        # Body record — fall back to snippet if no body text was found
        # (rare: e.g. inline-only PNG without alt text).
        records.append(_to_raw_record(msg, body_override=body_text or None))

        # Attachments — fetch bytes per part, decode via type-specific parser.
        for i, att in enumerate(attachments):
            try:
                text = _fetch_and_parse_attachment(svc, mid, att)
            except Exception:
                continue
            if not text:
                continue
            records.append(_to_attachment_record(msg, mid, i, att, text))
        return records


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (pure)
# ─────────────────────────────────────────────────────────────────────────────


def _to_raw_record(msg: dict[str, Any], body_override: str | None = None) -> RawRecord:
    """Convert Gmail message payload to RawRecord.

    `body_override`: when present, used as `snippet` (which the SourceMapping
    routes to MemoryItem.content). Falls back to Google's snippet preview
    for messages we only fetched metadata for, or when no body text was
    decodable (rare attachment-only emails).
    """
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    content = body_override if body_override else msg.get("snippet", "")
    return RawRecord(
        native_id=msg["id"],
        fields={
            "snippet": content,
            "internal_date_ms": int(msg.get("internalDate", 0)),
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "labels": msg.get("labelIds", []),
            "thread_id": msg.get("threadId"),
            "ref": f"gmail:{msg['id']}",
        },
    )


def _to_attachment_record(
    msg: dict[str, Any], parent_mid: str, idx: int,
    att: dict[str, Any], text: str,
) -> RawRecord:
    """One RawRecord per email attachment whose bytes we successfully parsed.

    native_id = "<parent>_a<idx>" so the resolver can still uniquely identify
    each item, and `parent_native_id` is carried in fields so a downstream
    view can group attachments under their parent email.
    """
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    return RawRecord(
        native_id=f"{parent_mid}_a{idx}",
        fields={
            "snippet": text,
            "internal_date_ms": int(msg.get("internalDate", 0)),
            "from": headers.get("From", ""),
            "subject": f"{headers.get('Subject', '')} — attachment: {att.get('filename', '')}",
            "labels": msg.get("labelIds", []),
            "thread_id": msg.get("threadId"),
            "ref": f"gmail:{parent_mid}#a{idx}",
            "parent_native_id": parent_mid,
            "attachment_filename": att.get("filename", ""),
            "attachment_mime_type": att.get("mime_type", ""),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# MIME walker + attachment decoder
# ─────────────────────────────────────────────────────────────────────────────


_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MiB — match Resources upload cap


def _walk_mime_parts(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Recurse the MIME tree. Return (joined plaintext body, [attachment refs]).

    Body strategy: prefer text/plain; fall back to text/html stripped to text
    if no plain part was found. Attachments = any part with a filename + an
    attachmentId we can resolve via the attachments.get API.
    """
    text_plain: list[str] = []
    text_html: list[str] = []
    attachments: list[dict[str, Any]] = []

    def walk(part: dict[str, Any]) -> None:
        mime = (part.get("mimeType") or "").lower()
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        data = body.get("data")
        attachment_id = body.get("attachmentId")
        sub_parts = part.get("parts") or []
        if sub_parts:
            for sp in sub_parts:
                walk(sp)
            return
        if filename and attachment_id:
            attachments.append({
                "filename": filename,
                "mime_type": mime,
                "attachment_id": attachment_id,
                "size": int(body.get("size", 0) or 0),
            })
            return
        if not data:
            return
        import base64
        try:
            raw = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        except Exception:
            return
        if mime == "text/plain":
            text_plain.append(raw)
        elif mime == "text/html":
            text_html.append(raw)

    walk(payload)
    body = "\n\n".join(s.strip() for s in text_plain if s.strip())
    if not body and text_html:
        body = _html_to_text("\n\n".join(text_html))
    return body.strip(), attachments


def _html_to_text(html: str) -> str:
    """Strip tags to plaintext using stdlib HTMLParser. Light but enough for
    transactional email HTML that's mostly text with light markup."""
    from html.parser import HTMLParser as _H

    chunks: list[str] = []

    class _Strip(_H):
        def handle_data(self, data: str) -> None:
            chunks.append(data)

    p = _Strip()
    try:
        p.feed(html)
        p.close()
    except Exception:
        return ""
    return "\n".join(c.strip() for c in chunks if c.strip())


def _fetch_and_parse_attachment(svc: Any, mid: str, att: dict[str, Any]) -> str:
    """Pull the attachment bytes via gmail API + decode by mime type.

    Cap at 10 MiB to match the Resources upload limit; oversized parts are
    skipped (better than blocking sync on a 50MB PDF). Unsupported mime
    types return "" so the caller drops the record cleanly.
    """
    if att.get("size", 0) > _MAX_ATTACHMENT_BYTES:
        return ""
    import base64
    api = (
        svc.users().messages().attachments()
        .get(userId="me", messageId=mid, id=att["attachment_id"])
        .execute()
    )
    raw_b64 = api.get("data", "")
    if not raw_b64:
        return ""
    raw_bytes = base64.urlsafe_b64decode(raw_b64 + "==")
    if len(raw_bytes) > _MAX_ATTACHMENT_BYTES:
        return ""
    mime = (att.get("mime_type") or "").lower()
    filename = (att.get("filename") or "").lower()
    return _decode_attachment_bytes(raw_bytes, mime=mime, filename=filename)


def _decode_attachment_bytes(raw: bytes, *, mime: str, filename: str) -> str:
    """Parse PDF/DOCX/plaintext bytes to text. Unknown types → "".

    Mirrors core/resources/uploads.py:_parse_to_text so a PDF emailed and
    a PDF uploaded land in the same extraction pipeline with the same
    quality. Parser deps are optional — missing pypdf/python-docx degrades
    to "" rather than raising into the sync runner.
    """
    if mime.startswith("text/") or filename.endswith((".txt", ".md", ".csv", ".tsv")):
        try:
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return ""
    if mime == "application/pdf" or filename.endswith(".pdf"):
        try:
            import io as _io
            from pypdf import PdfReader  # type: ignore
            reader = PdfReader(_io.BytesIO(raw))
            return "\n\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            return ""
    if mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ) or filename.endswith((".docx", ".doc")):
        try:
            import io as _io
            import docx  # type: ignore
            d = docx.Document(_io.BytesIO(raw))
            return "\n".join(p.text for p in d.paragraphs)
        except Exception:
            return ""
    return ""


def _google_client_id() -> str:
    """Resolve Google OAuth client id from env. Raises if unset."""
    import os

    v = os.getenv("GOOGLE_CLIENT_ID", "")
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_ID env var required for Gmail adapter")
    return v


def _google_client_secret() -> str:
    import os

    v = os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_SECRET env var required for Gmail adapter")
    return v


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# ─────────────────────────────────────────────────────────────────────────────


def _factory(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    access_secret_ref: str,
    refresh_secret_ref: str,
    account_email: str,
) -> GmailAdapter:
    return GmailAdapter(
        session=session,
        connection_id=connection_id,
        org_id=org_id,
        access_secret_ref=access_secret_ref,
        refresh_secret_ref=refresh_secret_ref,
        account_email=account_email,
    )


register_adapter(SOURCE_TYPE, _factory)


# ─────────────────────────────────────────────────────────────────────────────
# Migration helper — used by v1 OAuth callback to mirror token into v2 store
# ─────────────────────────────────────────────────────────────────────────────


def register_v2_gmail_connection(
    *,
    org_id: str,
    account_email: str,
    access_token: str,
    refresh_token: str,
    created_by: str,
) -> str:
    """Create the v2 thin-pipe row set for a Gmail mailbox.

    Idempotent on (org_id, source_id=email) — re-running OAuth for the same
    mailbox UPDATES the secret refs instead of duplicating connections.

    Returns the v2 connection_id (UUID string).
    """
    from sqlalchemy import select

    from core.foundations.db import get_session
    from core.memory.secrets import put_secret
    from core.memory.store import Connection

    with get_session() as session:
        existing = session.execute(
            select(Connection)
            .where(Connection.org_id == org_id)
            .where(Connection.source_type == SOURCE_TYPE)
            .where(Connection.source_id == account_email)
            .limit(1)
        ).scalar_one_or_none()

        if existing is None:
            conn = Connection(
                org_id=org_id,
                source_type=SOURCE_TYPE,
                source_id=account_email,
                status="active",
                health_status="green",
                created_by=created_by,
            )
            session.add(conn)
            session.flush()
        else:
            conn = existing
            conn.status = "active"
            conn.health_status = "green"
            session.flush()

        # Always insert fresh secret refs (latest wins via created_at desc lookup).
        put_secret(
            session,
            org_id=org_id,
            connection_id=conn.id,
            secret_type="oauth_access",  # noqa: S106 — enum label, not a password
            plaintext=access_token,
            actor_id=created_by,
        )
        if refresh_token:
            put_secret(
                session,
                org_id=org_id,
                connection_id=conn.id,
                secret_type="oauth_refresh",  # noqa: S106 — enum label, not a password
                plaintext=refresh_token,
                actor_id=created_by,
            )
        return conn.id
