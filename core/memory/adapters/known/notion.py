"""Notion known adapter — read-only thin pipe per g-i-1.

Notion uses internal-integration / OAuth bearer tokens — no refresh dance.
- Cursor strategy: `last_edited_time` filter on search/database queries
- Content: page title + plaintext block extract
- Mapping hardcoded — source_confidence = 1.0
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests
from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.memory.adapters import register_adapter
from core.memory.batch import RateLimited
from core.memory.interface import MemoryAdapter
from core.memory.secrets import get_secret
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

SOURCE_TYPE = "notion"
NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionAdapter(MemoryAdapter):
    """Notion read-only adapter — search for pages updated since cursor."""

    def __init__(
        self,
        session: Session,
        *,
        connection_id: str,
        org_id: str,
        access_secret_ref: str,
        refresh_secret_ref: str | None = None,
        account_email: str,
    ) -> None:
        self.source_type = SOURCE_TYPE
        self.source_id = connection_id
        self._session = session
        self._connection_id = connection_id
        self._org_id = org_id
        self._access_ref = access_secret_ref
        self._workspace_ref = account_email

    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        return ConnectionHandle(
            connection_id=self._connection_id,
            source_type=self.source_type,
            source_id=self._workspace_ref,
            granted_scopes=scopes,
        )

    def health_check(self) -> HealthStatus:
        try:
            resp = self._call("GET", "/users/me", {})
            if resp.get("object") == "user":
                return HealthStatus(
                    level=HealthStatusLevel.GREEN,
                    last_sync_at=datetime.now(UTC),
                    items_pulled_count=0,
                    scope_drops_count=0,
                )
            return HealthStatus(
                level=HealthStatusLevel.RED, last_sync_at=None, last_error="users/me unexpected"
            )
        except Exception as e:
            return HealthStatus(
                level=HealthStatusLevel.RED, last_sync_at=None, last_error=str(e)[:200]
            )

    def disconnect(self) -> None:
        pass

    def list_changed_since(
        self,
        cursor: Cursor | None,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        # Notion's search supports sort by last_edited_time
        body: dict[str, Any] = {
            "page_size": limit,
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
            "filter": {"value": "page", "property": "object"},
        }
        resp = self._call("POST", "/search", body)
        results = resp.get("results", [])

        # Apply cursor: only keep pages strictly newer than last cursor (ISO timestamp)
        cur_ts = cursor.value if cursor and cursor.value else ""
        records: list[RawRecord] = []
        max_ts = cur_ts
        for page in results:
            ts = page.get("last_edited_time", "")
            if cur_ts and ts <= cur_ts:
                continue
            records.append(self._page_to_raw(page))
            if ts > max_ts:
                max_ts = ts

        return records, Cursor(value=max_ts, strategy="updated_at"), False

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        page = self._call("GET", f"/pages/{ref.native_id}", {})
        return self._page_to_raw(page)

    def get_mapping(self) -> SourceMapping:
        return SourceMapping(
            source_type=SOURCE_TYPE,
            field_map={
                "content": FieldMapping(source_field="title_plus_blocks", confidence=1.0),
                "timestamp": FieldMapping(source_field="last_edited_time", confidence=1.0),
                "owner": FieldMapping(source_field="created_by", confidence=1.0),
                "tags": FieldMapping(source_field="parent_type", confidence=1.0),
            },
            confirmed_by="genios:hardcoded",
            confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _call(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        token = get_secret(self._session, self._access_ref)
        headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        if method == "GET":
            resp = requests.get(f"{NOTION_API}{path}", headers=headers, timeout=20)
        else:
            resp = requests.request(method, f"{NOTION_API}{path}", headers=headers, json=body, timeout=20)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", "1"))
            raise RateLimited(retry_after_seconds=retry_after)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def _page_to_raw(self, page: dict[str, Any]) -> RawRecord:
        page_id = page.get("id", "")
        title = _extract_page_title(page)
        # Pull first ~10 blocks for content snippet
        snippet = self._extract_block_text(page_id, limit=10)
        body = f"{title}\n\n{snippet}".strip()
        return RawRecord(
            native_id=page_id,
            fields={
                "title_plus_blocks": body,
                "last_edited_time": page.get("last_edited_time", ""),
                "created_by": (page.get("created_by", {}) or {}).get("id", ""),
                "parent_type": (page.get("parent", {}) or {}).get("type", ""),
                "url": page.get("url", ""),
            },
        )

    def _extract_block_text(self, page_id: str, *, limit: int) -> str:
        try:
            resp = self._call("GET", f"/blocks/{page_id}/children?page_size={limit}", {})
        except Exception:
            return ""
        parts: list[str] = []
        for block in resp.get("results", []):
            btype = block.get("type", "")
            inner = block.get(btype, {}) if btype else {}
            for rt in inner.get("rich_text", []) or []:
                t = rt.get("plain_text", "")
                if t:
                    parts.append(t)
        return " ".join(parts)


def _extract_page_title(page: dict[str, Any]) -> str:
    props = page.get("properties", {}) or {}
    for prop in props.values():
        if prop.get("type") == "title":
            title_rt = prop.get("title", [])
            return " ".join(rt.get("plain_text", "") for rt in title_rt).strip()
    return ""


def _factory(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    access_secret_ref: str,
    refresh_secret_ref: str | None = None,
    account_email: str,
) -> NotionAdapter:
    return NotionAdapter(
        session=session,
        connection_id=connection_id,
        org_id=org_id,
        access_secret_ref=access_secret_ref,
        refresh_secret_ref=refresh_secret_ref,
        account_email=account_email,
    )


register_adapter(SOURCE_TYPE, _factory)


def register_v2_notion_connection(
    *, org_id: str, workspace_id: str, access_token: str, created_by: str
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
            .where(Connection.source_id == workspace_id)
            .limit(1)
        ).scalar_one_or_none()
        if existing is None:
            conn = Connection(
                org_id=org_id,
                source_type=SOURCE_TYPE,
                source_id=workspace_id,
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
        return conn.id
