"""Google Docs known adapter — read-only thin pipe per g-i-1.

Filter Drive for application/vnd.google-apps.document, fetch doc content.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.memory.adapters import register_adapter
from core.memory.adapters.known._google_base import build_google_service
from core.memory.batch import RateLimited
from core.memory.interface import MemoryAdapter
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
SOURCE_TYPE = "gdocs"
DOC_MIME = "application/vnd.google-apps.document"


class DocsAdapter(MemoryAdapter):
    def __init__(self, session: Session, *, connection_id: str, org_id: str,
                 access_secret_ref: str, refresh_secret_ref: str, account_email: str) -> None:
        self.source_type = SOURCE_TYPE
        self.source_id = connection_id
        self._session = session
        self._connection_id = connection_id
        self._org_id = org_id
        self._access_ref = access_secret_ref
        self._refresh_ref = refresh_secret_ref
        self._account = account_email
        self._drive: Any | None = None
        self._docs: Any | None = None

    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        return ConnectionHandle(connection_id=self._connection_id, source_type=self.source_type,
                                source_id=self._account, granted_scopes=scopes)

    def health_check(self) -> HealthStatus:
        try:
            self._drive_svc().about().get(fields="user").execute()
            return HealthStatus(level=HealthStatusLevel.GREEN, last_sync_at=datetime.now(UTC),
                                items_pulled_count=0, scope_drops_count=0)
        except Exception as e:
            return HealthStatus(level=HealthStatusLevel.RED, last_sync_at=None, last_error=str(e)[:200])

    def disconnect(self) -> None:
        self._drive = None
        self._docs = None

    def list_changed_since(self, cursor: Cursor | None, limit: int) -> tuple[list[RawRecord], Cursor, bool]:
        drv = self._drive_svc()
        try:
            cur = cursor.value if cursor and cursor.value else ""
            q = f"mimeType = '{DOC_MIME}'"
            if cur:
                q += f" and modifiedTime > '{cur}'"
            resp = drv.files().list(
                q=q,
                orderBy="modifiedTime desc",
                pageSize=limit,
                fields="files(id,name,modifiedTime,owners,webViewLink)",
            ).execute()
            files = resp.get("files", [])
            max_ts = cur
            records: list[RawRecord] = []
            for f in files:
                ts = f.get("modifiedTime", "")
                if ts > max_ts:
                    max_ts = ts
                records.append(self._doc_to_raw(f))
            return records, Cursor(value=max_ts, strategy="updated_at"), False
        except HttpError as e:
            if e.resp.status == 429:
                retry_after = float(e.resp.get("retry-after", "1"))
                raise RateLimited(retry_after_seconds=retry_after) from e
            raise

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        drv = self._drive_svc()
        f = drv.files().get(fileId=ref.native_id, fields="id,name,modifiedTime,owners,webViewLink").execute()
        return self._doc_to_raw(f)

    def get_mapping(self) -> SourceMapping:
        return SourceMapping(
            source_type=SOURCE_TYPE,
            field_map={
                "content": FieldMapping(source_field="title_plus_body", confidence=1.0),
                "timestamp": FieldMapping(source_field="modifiedTime", confidence=1.0),
                "owner": FieldMapping(source_field="owner_email", confidence=1.0),
                "tags": FieldMapping(source_field="webViewLink", confidence=1.0),
            },
            confirmed_by="genios:hardcoded",
            confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )

    def _drive_svc(self) -> Any:
        if self._drive is None:
            self._drive = build_google_service(
                self._session, api_name="drive", api_version="v3",
                access_secret_ref=self._access_ref, refresh_secret_ref=self._refresh_ref,
            )
        return self._drive

    def _docs_svc(self) -> Any:
        if self._docs is None:
            self._docs = build_google_service(
                self._session, api_name="docs", api_version="v1",
                access_secret_ref=self._access_ref, refresh_secret_ref=self._refresh_ref,
            )
        return self._docs

    def _doc_to_raw(self, f: dict[str, Any]) -> RawRecord:
        body = ""
        try:
            doc = self._docs_svc().documents().get(documentId=f.get("id", "")).execute()
            body = _extract_doc_text(doc)
        except Exception as e:
            log.warning("gdocs_body_fetch_failed", file_id=f.get("id", ""), error=str(e)[:120])
        owners = f.get("owners", []) or []
        owner_email = (owners[0] if owners else {}).get("emailAddress", "")
        title_plus_body = f"{f.get('name', '')}\n\n{body[:4000]}".strip()
        return RawRecord(
            native_id=f.get("id", ""),
            fields={
                "title_plus_body": title_plus_body,
                "modifiedTime": f.get("modifiedTime", ""),
                "owner_email": owner_email,
                "webViewLink": f.get("webViewLink", ""),
            },
        )


def _extract_doc_text(doc: dict[str, Any]) -> str:
    out: list[str] = []
    for el in (doc.get("body", {}) or {}).get("content", []) or []:
        para = el.get("paragraph", {}) or {}
        for r in para.get("elements", []) or []:
            t = (r.get("textRun", {}) or {}).get("content", "")
            if t:
                out.append(t)
    return "".join(out)


def _factory(session: Session, *, connection_id: str, org_id: str,
             access_secret_ref: str, refresh_secret_ref: str, account_email: str) -> DocsAdapter:
    return DocsAdapter(session=session, connection_id=connection_id, org_id=org_id,
                       access_secret_ref=access_secret_ref, refresh_secret_ref=refresh_secret_ref,
                       account_email=account_email)


register_adapter(SOURCE_TYPE, _factory)


def register_v2_gdocs_connection(*, org_id: str, account_email: str, access_token: str,
                                  refresh_token: str, created_by: str) -> str:
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
            conn = Connection(org_id=org_id, source_type=SOURCE_TYPE, source_id=account_email,
                              status="active", health_status="green", created_by=created_by)
            session.add(conn)
            session.flush()
        else:
            conn = existing
            conn.status = "active"
            session.flush()
        put_secret(session, org_id=org_id, connection_id=conn.id,
                   secret_type="oauth_access",  # noqa: S106 — enum label
                   plaintext=access_token, actor_id=created_by)
        if refresh_token:
            put_secret(session, org_id=org_id, connection_id=conn.id,
                       secret_type="oauth_refresh",  # noqa: S106 — enum label
                       plaintext=refresh_token, actor_id=created_by)
        return conn.id
