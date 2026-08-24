"""HubSpot known adapter — read-only thin pipe per g-i-1.

Pulls contacts + companies from HubSpot CRM v3 API.
- OAuth bearer + refresh tokens
- Cursor: last-modified timestamp (updated_at strategy)
- Mapping hardcoded — source_confidence = 1.0
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

SOURCE_TYPE = "hubspot"
HUBSPOT_API = "https://api.hubapi.com"


class HubSpotAdapter(MemoryAdapter):
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
        self._portal = account_email

    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        return ConnectionHandle(
            connection_id=self._connection_id,
            source_type=self.source_type,
            source_id=self._portal,
            granted_scopes=scopes,
        )

    def health_check(self) -> HealthStatus:
        try:
            self._get("/crm/v3/objects/contacts?limit=1")
            return HealthStatus(
                level=HealthStatusLevel.GREEN,
                last_sync_at=datetime.now(UTC),
                items_pulled_count=0,
                scope_drops_count=0,
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
        # Pull contacts modified since cursor (HubSpot ISO timestamp)
        params: dict[str, Any] = {
            "limit": limit,
            "properties": "email,firstname,lastname,company,phone,jobtitle,lifecyclestage,notes_last_contacted",
        }
        if cursor and cursor.value:
            # HubSpot search API supports lastmodifieddate filter
            body = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "lastmodifieddate",
                                "operator": "GT",
                                "value": cursor.value,
                            }
                        ]
                    }
                ],
                "properties": params["properties"].split(","),
                "limit": limit,
                "sorts": [{"propertyName": "lastmodifieddate", "direction": "DESCENDING"}],
            }
            data = self._post("/crm/v3/objects/contacts/search", body)
        else:
            data = self._get(f"/crm/v3/objects/contacts?limit={limit}&properties={params['properties']}")

        results = data.get("results", [])
        max_ts = cursor.value if cursor else ""
        records: list[RawRecord] = []
        for c in results:
            ts = c.get("updatedAt", "")
            if ts > max_ts:
                max_ts = ts
            records.append(_contact_to_raw(c))

        return records, Cursor(value=max_ts, strategy="updated_at"), False

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        data = self._get(f"/crm/v3/objects/contacts/{ref.native_id}")
        return _contact_to_raw(data)

    def get_mapping(self) -> SourceMapping:
        return SourceMapping(
            source_type=SOURCE_TYPE,
            field_map={
                "content": FieldMapping(source_field="summary", confidence=1.0),
                "timestamp": FieldMapping(source_field="updatedAt", confidence=1.0),
                "owner": FieldMapping(source_field="email", confidence=1.0),
                "tags": FieldMapping(source_field="lifecyclestage", confidence=1.0),
            },
            confirmed_by="genios:hardcoded",
            confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _get(self, path: str) -> dict[str, Any]:
        return self._call("GET", path, None)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self._call("POST", path, body)

    def _call(self, method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        token = get_secret(self._session, self._access_ref)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = requests.request(
            method, f"{HUBSPOT_API}{path}", headers=headers, json=body, timeout=20
        )
        if resp.status_code == 401:
            # Refresh + retry once
            self._refresh_access_token()
            token = get_secret(self._session, self._access_ref)
            headers["Authorization"] = f"Bearer {token}"
            resp = requests.request(
                method, f"{HUBSPOT_API}{path}", headers=headers, json=body, timeout=20
            )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", "1"))
            raise RateLimited(retry_after_seconds=retry_after)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data

    def _refresh_access_token(self) -> None:
        client_id = os.getenv("HUBSPOT_CLIENT_ID", "")
        client_secret = os.getenv("HUBSPOT_CLIENT_SECRET", "")
        refresh = get_secret(self._session, self._refresh_ref)
        resp = requests.post(
            "https://api.hubapi.com/oauth/v1/token",
            data={
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh,
            },
            timeout=20,
        )
        resp.raise_for_status()
        body = resp.json()
        new_access = body.get("access_token", "")
        if new_access:
            rotate_secret(self._session, self._access_ref, new_access)


def _contact_to_raw(c: dict[str, Any]) -> RawRecord:
    props = c.get("properties", {}) or {}
    summary_parts: list[str] = []
    name = " ".join(filter(None, [props.get("firstname", ""), props.get("lastname", "")])).strip()
    if name:
        summary_parts.append(name)
    if props.get("email"):
        summary_parts.append(f"<{props['email']}>")
    if props.get("company"):
        summary_parts.append(f"at {props['company']}")
    if props.get("jobtitle"):
        summary_parts.append(f"— {props['jobtitle']}")
    summary = " ".join(summary_parts)
    return RawRecord(
        native_id=str(c.get("id", "")),
        fields={
            "summary": summary,
            "email": props.get("email", ""),
            "updatedAt": c.get("updatedAt", ""),
            "lifecyclestage": props.get("lifecyclestage", ""),
            "company": props.get("company", ""),
        },
    )


def _factory(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    access_secret_ref: str,
    refresh_secret_ref: str,
    account_email: str,
) -> HubSpotAdapter:
    return HubSpotAdapter(
        session=session,
        connection_id=connection_id,
        org_id=org_id,
        access_secret_ref=access_secret_ref,
        refresh_secret_ref=refresh_secret_ref,
        account_email=account_email,
    )


register_adapter(SOURCE_TYPE, _factory)


def register_v2_hubspot_connection(
    *, org_id: str, portal_id: str, access_token: str, refresh_token: str, created_by: str
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
            .where(Connection.source_id == portal_id)
            .limit(1)
        ).scalar_one_or_none()
        if existing is None:
            conn = Connection(
                org_id=org_id,
                source_type=SOURCE_TYPE,
                source_id=portal_id,
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
