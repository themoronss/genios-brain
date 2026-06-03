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
        """Fetch a single message by id (used by webhook -> fetch flow)."""
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
            .list(userId="me", startHistoryId=history_id, maxResults=limit)
            .execute()
        )
        message_ids: list[str] = []
        for entry in history_resp.get("history", []):
            for ma in entry.get("messagesAdded", []):
                if "message" in ma and "id" in ma["message"]:
                    message_ids.append(ma["message"]["id"])
        next_history = history_resp.get("historyId", history_id)
        has_more = bool(history_resp.get("nextPageToken"))
        records = [self._fetch_metadata(svc, mid) for mid in message_ids[:limit]]
        return records, Cursor(value=str(next_history), strategy="native"), has_more

    def _pull_recent(
        self,
        svc: Any,
        *,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        """First-run fallback: list recent messages, capture starting historyId."""
        list_resp = svc.users().messages().list(userId="me", maxResults=limit).execute()
        msg_ids = [m["id"] for m in list_resp.get("messages", [])]
        records = [self._fetch_metadata(svc, mid) for mid in msg_ids]

        # Capture profile.historyId for next run's delta detection
        profile = svc.users().getProfile(userId="me").execute()
        history_id = str(profile.get("historyId", "1"))
        return records, Cursor(value=history_id, strategy="native"), False

    @staticmethod
    def _fetch_metadata(svc: Any, mid: str) -> RawRecord:
        msg = svc.users().messages().get(userId="me", id=mid, format="metadata").execute()
        return _to_raw_record(msg)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (pure)
# ─────────────────────────────────────────────────────────────────────────────


def _to_raw_record(msg: dict[str, Any]) -> RawRecord:
    """Convert Gmail message payload to RawRecord. Snippet only (no full body)."""
    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
    return RawRecord(
        native_id=msg["id"],
        fields={
            "snippet": msg.get("snippet", ""),
            "internal_date_ms": int(msg.get("internalDate", 0)),
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "labels": msg.get("labelIds", []),
            "thread_id": msg.get("threadId"),
            "ref": f"gmail:{msg['id']}",
        },
    )


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
