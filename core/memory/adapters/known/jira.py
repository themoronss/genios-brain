"""Jira Cloud known adapter — read-only thin pipe per g-i-1.

Pulls issues updated since cursor via Jira REST v3 search.
- OAuth 2.0 (3LO) — access + refresh tokens
- Cursor: max(updated) ISO timestamp
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import requests
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
SOURCE_TYPE = "jira"


class JiraAdapter(MemoryAdapter):
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
        # account_email holds cloud_id for Jira (format: "<cloud_id>")
        self._cloud_id = account_email

    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        return ConnectionHandle(
            connection_id=self._connection_id,
            source_type=self.source_type,
            source_id=self._cloud_id,
            granted_scopes=scopes,
        )

    def health_check(self) -> HealthStatus:
        try:
            self._get("/myself")
            return HealthStatus(
                level=HealthStatusLevel.GREEN,
                last_sync_at=datetime.now(UTC),
                items_pulled_count=0,
                scope_drops_count=0,
            )
        except Exception as e:
            return HealthStatus(level=HealthStatusLevel.RED, last_sync_at=None, last_error=str(e)[:200])

    def disconnect(self) -> None:
        pass

    def list_changed_since(
        self,
        cursor: Cursor | None,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        cur = cursor.value if cursor and cursor.value else ""
        jql = f'updated > "{cur}"' if cur else "updated >= -1d"
        body = {"jql": jql, "maxResults": limit, "fields": ["summary", "description", "status", "assignee", "updated"]}
        data = self._post("/search", body)
        issues = data.get("issues", [])
        max_ts = cur
        records: list[RawRecord] = []
        for iss in issues:
            f = iss.get("fields", {}) or {}
            ts = f.get("updated", "")
            if ts > max_ts:
                max_ts = ts
            records.append(_issue_to_raw(iss))
        return records, Cursor(value=max_ts, strategy="updated_at"), False

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        data = self._get(f"/issue/{ref.native_id}")
        return _issue_to_raw(data)

    def get_mapping(self) -> SourceMapping:
        return SourceMapping(
            source_type=SOURCE_TYPE,
            field_map={
                "content": FieldMapping(source_field="summary_plus_desc", confidence=1.0),
                "timestamp": FieldMapping(source_field="updated", confidence=1.0),
                "owner": FieldMapping(source_field="assignee", confidence=1.0),
                "tags": FieldMapping(source_field="status", confidence=1.0),
            },
            confirmed_by="genios:hardcoded",
            confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )

    def _base_url(self) -> str:
        return f"https://api.atlassian.com/ex/jira/{self._cloud_id}/rest/api/3"

    def _get(self, path: str) -> dict[str, Any]:
        return self._call("GET", path, None)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._call("POST", path, body)

    def _call(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        token = get_secret(self._session, self._access_ref)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}
        url = f"{self._base_url()}{path}"
        resp = requests.request(method, url, headers=headers, json=body, timeout=20)
        if resp.status_code == 401:
            self._refresh_access_token()
            token = get_secret(self._session, self._access_ref)
            headers["Authorization"] = f"Bearer {token}"
            resp = requests.request(method, url, headers=headers, json=body, timeout=20)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", "1"))
            raise RateLimited(retry_after_seconds=retry_after)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def _refresh_access_token(self) -> None:
        refresh = get_secret(self._session, self._refresh_ref)
        resp = requests.post(
            "https://auth.atlassian.com/oauth/token",
            json={
                "grant_type": "refresh_token",
                "client_id": os.getenv("JIRA_CLIENT_ID", ""),
                "client_secret": os.getenv("JIRA_CLIENT_SECRET", ""),
                "refresh_token": refresh,
            },
            timeout=20,
        )
        resp.raise_for_status()
        new = resp.json().get("access_token", "")
        if new:
            rotate_secret(self._session, self._access_ref, new)


def _issue_to_raw(iss: dict[str, Any]) -> RawRecord:
    f = iss.get("fields", {}) or {}
    summary = f.get("summary", "") or ""
    desc = f.get("description", {}) or {}
    if isinstance(desc, dict):
        desc = _extract_adf_text(desc)
    body = f"{summary}\n\n{desc}".strip()
    assignee = (f.get("assignee", {}) or {}).get("emailAddress", "") or (f.get("assignee", {}) or {}).get("displayName", "")
    status = (f.get("status", {}) or {}).get("name", "")
    return RawRecord(
        native_id=iss.get("key", ""),
        fields={
            "summary_plus_desc": body,
            "updated": f.get("updated", ""),
            "assignee": assignee,
            "status": status,
        },
    )


def _extract_adf_text(doc: Any) -> str:
    """Flatten ADF (Atlassian Document Format) tree → plaintext."""
    out: list[str] = []
    if isinstance(doc, dict):
        if doc.get("type") == "text" and "text" in doc:
            out.append(doc["text"])
        for c in doc.get("content", []) or []:
            out.append(_extract_adf_text(c))
    elif isinstance(doc, list):
        for c in doc:
            out.append(_extract_adf_text(c))
    return " ".join(filter(None, out))


def _factory(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    access_secret_ref: str,
    refresh_secret_ref: str,
    account_email: str,
) -> JiraAdapter:
    return JiraAdapter(
        session=session,
        connection_id=connection_id,
        org_id=org_id,
        access_secret_ref=access_secret_ref,
        refresh_secret_ref=refresh_secret_ref,
        account_email=account_email,
    )


register_adapter(SOURCE_TYPE, _factory)


def register_v2_jira_connection(
    *, org_id: str, cloud_id: str, access_token: str, refresh_token: str, created_by: str
) -> str:
    from sqlalchemy import select

    from core.foundations.db import get_session
    from core.memory.secrets import put_secret
    from core.memory.store import Connection

    with get_session() as session:
        existing = session.execute(
            select(Connection)
            .where(Connection.org_id == org_id)
            .where(Connection.source_type == SOURCE_TYPE)
            .where(Connection.source_id == cloud_id)
            .limit(1)
        ).scalar_one_or_none()
        if existing is None:
            conn = Connection(
                org_id=org_id,
                source_type=SOURCE_TYPE,
                source_id=cloud_id,
                status="active",
                health_status="green",
                created_by=created_by,
            )
            session.add(conn)
            session.flush()
        else:
            conn = existing
            conn.status = "active"
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
