"""Google Calendar known adapter — read-only thin pipe per g-i-1.

Mirrors Gmail adapter pattern:
- OAuth credentials decrypted from secrets_ref on every service build
- Token refresh persists rotated access token via rotate_secret
- Cursor strategy: Google's incremental syncToken (native delta)
- Mapping hardcoded — source_confidence = 1.0
- Plaintext-only `content` field (event summary + description in-flight; never stored beyond MemoryItem)
"""

from __future__ import annotations

import os
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

SOURCE_TYPE = "gcal"

CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


class CalendarAdapter(MemoryAdapter):
    """Google Calendar read-only adapter."""

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
        self._service = self._service_for()
        return ConnectionHandle(
            connection_id=self._connection_id,
            source_type=self.source_type,
            source_id=self._account_email,
            granted_scopes=scopes,
        )

    def health_check(self) -> HealthStatus:
        try:
            svc = self._service_for()
            svc.calendarList().get(calendarId="primary").execute()
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
        self._service = None

    # ── reading (READ-ONLY) ────────────────────────────────────────────────

    def list_changed_since(
        self,
        cursor: Cursor | None,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        svc = self._service_for()
        try:
            params: dict[str, Any] = {"calendarId": "primary", "maxResults": limit}
            if cursor and cursor.value and cursor.strategy == "native":
                params["syncToken"] = cursor.value
            else:
                # First run: pull a bounded PAST window — the old timeMin=now was
                # future-only, so users whose meetings are in the past saw zero
                # events synced ("connected but nothing shows up"). Expand
                # recurring events and sort by start time.
                from datetime import timedelta
                params["timeMin"] = (
                    datetime.now(UTC) - timedelta(days=90)
                ).isoformat().replace("+00:00", "Z")
                params["singleEvents"] = True
                params["orderBy"] = "startTime"
                params["showDeleted"] = False

            resp = svc.events().list(**params).execute()
            items = resp.get("items", [])
            records = [_event_to_raw(ev) for ev in items if ev.get("status") != "cancelled"]
            # Precedence: without the parens, `A or B or cursor.value if cursor`
            # parsed as `(A or B or cursor.value) if cursor else ""`, discarding
            # the token on the first run (cursor is None) — so no cursor ever
            # persisted and every sync restarted as a full first run.
            next_token = resp.get("nextSyncToken") or resp.get("nextPageToken") or (cursor.value if cursor else "")
            return (
                records,
                Cursor(value=str(next_token or ""), strategy="native"),
                bool(resp.get("nextPageToken")),
            )
        except HttpError as e:
            if e.resp.status == 410:
                # syncToken expired — wipe cursor; next run does a full re-pull window
                log.warning("calendar_sync_token_expired", connection=self._connection_id)
                return [], Cursor(value="", strategy="native"), False
            if e.resp.status == 429:
                retry_after = float(e.resp.get("retry-after", "1"))
                raise RateLimited(retry_after_seconds=retry_after) from e
            raise

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        svc = self._service_for()
        ev = svc.events().get(calendarId="primary", eventId=ref.native_id).execute()
        return _event_to_raw(ev)

    def get_mapping(self) -> SourceMapping:
        return SourceMapping(
            source_type=SOURCE_TYPE,
            field_map={
                "content": FieldMapping(source_field="summary", confidence=1.0),
                "timestamp": FieldMapping(source_field="start_iso", confidence=1.0),
                "owner": FieldMapping(source_field="organizer_email", confidence=1.0),
                "tags": FieldMapping(source_field="attendee_emails", confidence=1.0),
            },
            confirmed_by="genios:hardcoded",
            confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _service_for(self) -> Any:
        if self._service is not None:
            return self._service

        access = get_secret(self._session, self._access_ref)
        refresh = get_secret(self._session, self._refresh_ref)
        creds = Credentials(  # type: ignore[no-untyped-call]
            token=access,
            refresh_token=refresh,
            token_uri="https://oauth2.googleapis.com/token",  # noqa: S106 — Google's well-known endpoint
            client_id=_google_client_id(),
            client_secret=_google_client_secret(),
        )
        if not creds.valid:
            creds.refresh(GoogleRequest())  # type: ignore[no-untyped-call]
            if creds.token and creds.token != access:
                rotate_secret(self._session, self._access_ref, creds.token)

        self._service = google_build("calendar", "v3", credentials=creds, cache_discovery=False)
        return self._service


# ─────────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────────


def _event_to_raw(ev: dict[str, Any]) -> RawRecord:
    """Calendar event → RawRecord. Summary + description in plaintext."""
    summary = ev.get("summary", "") or ""
    description = ev.get("description", "") or ""
    # Strip HTML-ish content if any (Calendar usually plaintext but defensive)
    import re
    description = re.sub(r"<[^>]+>", " ", description).strip()
    body = f"{summary}\n\n{description}".strip()

    start = ev.get("start", {})
    start_iso = start.get("dateTime") or start.get("date") or ""
    organizer_email = (ev.get("organizer", {}) or {}).get("email", "")
    attendees = [a.get("email", "") for a in (ev.get("attendees", []) or []) if a.get("email")]

    return RawRecord(
        native_id=ev["id"],
        fields={
            "summary": body,
            "start_iso": start_iso,
            "organizer_email": organizer_email,
            "attendee_emails": attendees,
            "location": ev.get("location", "") or "",
            "html_link": ev.get("htmlLink", ""),
        },
    )


def _google_client_id() -> str:
    v = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_ID env var required for Calendar adapter")
    return v


def _google_client_secret() -> str:
    v = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not v:
        raise RuntimeError("GOOGLE_CLIENT_SECRET env var required for Calendar adapter")
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
) -> CalendarAdapter:
    return CalendarAdapter(
        session=session,
        connection_id=connection_id,
        org_id=org_id,
        access_secret_ref=access_secret_ref,
        refresh_secret_ref=refresh_secret_ref,
        account_email=account_email,
    )


register_adapter(SOURCE_TYPE, _factory)


# ─────────────────────────────────────────────────────────────────────────────
# Migration helper — used by v1 OAuth callback to write into v2 store
# ─────────────────────────────────────────────────────────────────────────────


def register_v2_calendar_connection(
    *,
    org_id: str,
    account_email: str,
    access_token: str,
    refresh_token: str,
    created_by: str,
) -> str:
    """Create v2 thin-pipe rows for a Calendar mailbox. Returns connection_id."""
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

        put_secret(
            session,
            org_id=org_id,
            connection_id=conn.id,
            secret_type="oauth_access",  # noqa: S106 — enum label
            plaintext=access_token,
            actor_id=created_by,
        )
        if refresh_token:
            put_secret(
                session,
                org_id=org_id,
                connection_id=conn.id,
                secret_type="oauth_refresh",  # noqa: S106 — enum label
                plaintext=refresh_token,
                actor_id=created_by,
            )
        return conn.id
