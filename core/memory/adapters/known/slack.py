"""Slack known adapter — read-only thin pipe per g-i-1.

Slack uses bot/user tokens (no OAuth2 refresh dance like Google).
- Access token stored in secrets_ref (encrypted)
- Cursor: per-channel `oldest` timestamp (Slack's native filter)
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

SOURCE_TYPE = "slack"
SLACK_API = "https://slack.com/api"


class SlackAdapter(MemoryAdapter):
    """Slack read-only adapter — pulls from conversations.history across joined channels."""

    def __init__(
        self,
        session: Session,
        *,
        connection_id: str,
        org_id: str,
        access_secret_ref: str,
        refresh_secret_ref: str | None,  # Slack doesn't issue refresh tokens (rotating tokens optional)
        account_email: str,  # workspace identifier (e.g. team_id)
    ) -> None:
        self.source_type = SOURCE_TYPE
        self.source_id = connection_id
        self._session = session
        self._connection_id = connection_id
        self._org_id = org_id
        self._access_ref = access_secret_ref
        self._workspace_ref = account_email

    # ── lifecycle ──────────────────────────────────────────────────────────

    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        return ConnectionHandle(
            connection_id=self._connection_id,
            source_type=self.source_type,
            source_id=self._workspace_ref,
            granted_scopes=scopes,
        )

    def health_check(self) -> HealthStatus:
        try:
            resp = self._call("auth.test", {})
            if resp.get("ok"):
                return HealthStatus(
                    level=HealthStatusLevel.GREEN,
                    last_sync_at=datetime.now(UTC),
                    items_pulled_count=0,
                    scope_drops_count=0,
                )
            return HealthStatus(
                level=HealthStatusLevel.RED,
                last_sync_at=None,
                last_error=resp.get("error", "auth.test failed"),
            )
        except Exception as e:
            return HealthStatus(
                level=HealthStatusLevel.RED, last_sync_at=None, last_error=str(e)[:200]
            )

    def disconnect(self) -> None:
        pass  # Stateless — token revocation handled at route layer

    # ── reading (READ-ONLY) ────────────────────────────────────────────────

    def list_changed_since(
        self,
        cursor: Cursor | None,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        """Pull messages from all member channels.

        Cursor format: "<oldest_ts>" — fetch messages with ts > oldest_ts.
        First run: pulls last 24h.
        """
        oldest = (cursor.value if cursor and cursor.value else "")
        if not oldest:
            # Last 24h
            oldest = str(int((datetime.now(UTC).timestamp()) - 86400))

        # List channels the bot/user is in
        ch_resp = self._call(
            "conversations.list",
            {"types": "public_channel,private_channel", "limit": 100},
        )
        channels = ch_resp.get("channels", [])

        records: list[RawRecord] = []
        max_ts = oldest
        for ch in channels[:20]:  # cap channels per pull
            ch_id = ch.get("id")
            if not ch_id:
                continue
            try:
                hist = self._call(
                    "conversations.history",
                    {"channel": ch_id, "oldest": oldest, "limit": limit},
                )
                for msg in hist.get("messages", []):
                    records.append(_message_to_raw(msg, channel_id=ch_id))
                    ts = msg.get("ts", "")
                    if ts > max_ts:
                        max_ts = ts
                    if len(records) >= limit:
                        break
            except Exception as e:
                log.warning("slack_channel_pull_failed", channel=ch_id, error=str(e))
            if len(records) >= limit:
                break

        return records, Cursor(value=max_ts, strategy="native"), False

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        # ref.native_id encodes "channel:ts"
        ch, ts = ref.native_id.split(":", 1) if ":" in ref.native_id else (ref.native_id, "")
        resp = self._call(
            "conversations.history",
            {"channel": ch, "latest": ts, "inclusive": True, "limit": 1},
        )
        msgs = resp.get("messages", [])
        if not msgs:
            raise ValueError(f"slack message not found: {ref.native_id}")
        return _message_to_raw(msgs[0], channel_id=ch)

    def get_mapping(self) -> SourceMapping:
        return SourceMapping(
            source_type=SOURCE_TYPE,
            field_map={
                "content": FieldMapping(source_field="text", confidence=1.0),
                "timestamp": FieldMapping(
                    source_field="ts",
                    transform="slack_ts_to_iso8601",
                    confidence=1.0,
                ),
                "owner": FieldMapping(source_field="user_id", confidence=1.0),
                "tags": FieldMapping(source_field="channel_id", confidence=1.0),
            },
            confirmed_by="genios:hardcoded",
            confirmed_at=datetime(2026, 1, 1, tzinfo=UTC),
            version=1,
        )

    # ── helpers ────────────────────────────────────────────────────────────

    def _call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        token = get_secret(self._session, self._access_ref)
        resp = requests.post(
            f"{SLACK_API}/{method}",
            headers={"Authorization": f"Bearer {token}"},
            data=params,
            timeout=20,
        )
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("retry-after", "1"))
            raise RateLimited(retry_after_seconds=retry_after)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data


def _message_to_raw(msg: dict[str, Any], *, channel_id: str) -> RawRecord:
    """Slack message → RawRecord. Plaintext only."""
    return RawRecord(
        native_id=f"{channel_id}:{msg.get('ts', '')}",
        fields={
            "text": msg.get("text", "") or "",
            "ts": msg.get("ts", ""),
            "user_id": msg.get("user", "") or msg.get("bot_id", ""),
            "channel_id": channel_id,
            "thread_ts": msg.get("thread_ts", ""),
            "subtype": msg.get("subtype", ""),
        },
    )


# Registry
def _factory(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    access_secret_ref: str,
    refresh_secret_ref: str | None = None,
    account_email: str,
) -> SlackAdapter:
    return SlackAdapter(
        session=session,
        connection_id=connection_id,
        org_id=org_id,
        access_secret_ref=access_secret_ref,
        refresh_secret_ref=refresh_secret_ref,
        account_email=account_email,
    )


register_adapter(SOURCE_TYPE, _factory)


# Migration helper
def register_v2_slack_connection(
    *,
    org_id: str,
    workspace_id: str,
    access_token: str,
    created_by: str,
) -> str:
    """Slack has no refresh token by default — single bot/user token suffices."""
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
            secret_type="api_key",  # noqa: S106 — enum label
            plaintext=access_token,
            actor_id=created_by,
        )
        # Reuse same key as "oauth_access" so sync_runner finds it
        put_secret(
            session,
            org_id=org_id,
            connection_id=conn.id,
            secret_type="oauth_access",  # noqa: S106 — enum label
            plaintext=access_token,
            actor_id=created_by,
        )
        return conn.id
