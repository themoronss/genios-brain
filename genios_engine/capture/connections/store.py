from __future__ import annotations

import json
from typing import Protocol

from sqlalchemy import text

from genios_engine.contracts.connection import Connection
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt, encrypt
from genios_engine.platform.db import get_engine

# Secret fields inside a connection's config (client DB password, OAuth tokens) are ENCRYPTED at
# rest with the engine's Fernet key — a leaked connections table / backup no longer exposes every
# client's production DB password in clear. "enc:" prefix marks a sealed value; unsealed legacy
# values pass through and get sealed on the next write (backward-compatible).
_SECRET_FIELDS = ("db_url", "token", "password", "api_key", "secret")


def _seal_config(config: dict) -> dict:
    key = get_settings().crypto_key
    if not key or not config:
        return config
    out = dict(config)
    for f in _SECRET_FIELDS:
        v = out.get(f)
        if isinstance(v, str) and v and not v.startswith("enc:"):
            out[f] = "enc:" + encrypt(v, key).decode("ascii")
    return out


def _open_config(config: dict) -> dict:
    key = get_settings().crypto_key
    if not key or not config:
        return config
    out = dict(config)
    for f in _SECRET_FIELDS:
        v = out.get(f)
        if isinstance(v, str) and v.startswith("enc:"):
            try:
                out[f] = decrypt(v[4:].encode("ascii"), key)
            except Exception:      # noqa: BLE001 — leave sealed rather than crash on a bad token
                pass
    return out


class ConnectionStore(Protocol):
    def add(self, c: Connection) -> None: ...
    def list_active(self, source_type: str | None = None) -> list[Connection]: ...
    def get(self, connection_id: str) -> Connection | None: ...
    def set_status(self, connection_id: str, status: str) -> None: ...


class InMemoryConnectionStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Connection] = {}

    def add(self, c: Connection) -> None:
        self._by_id[c.connection_id] = c

    def list_active(self, source_type: str | None = None) -> list[Connection]:
        return [c for c in self._by_id.values()
                if c.status == "connected"
                and (source_type is None or c.source_type == source_type)]

    def get(self, connection_id: str) -> Connection | None:
        return self._by_id.get(connection_id)

    def set_status(self, connection_id: str, status: str) -> None:
        if connection_id in self._by_id:
            self._by_id[connection_id].status = status


_UPSERT = text(
    """
    insert into connections
      (connection_id, org_id, provider, source_type, composio_user_id, capture_scope,
       status, created_at)
    values
      (:connection_id, :org_id, :provider, :source_type, :composio_user_id,
       cast(:config as jsonb), :status, :created_at)
    on conflict (connection_id) do update set
      composio_user_id = excluded.composio_user_id,
      capture_scope = excluded.capture_scope, status = excluded.status
    """
)
_COLS = ("connection_id, org_id, provider, source_type, composio_user_id, "
         "capture_scope, status, created_at")


def _to_conn(row) -> Connection:
    cfg = row.capture_scope
    if isinstance(cfg, str):
        cfg = json.loads(cfg) if cfg else {}
    return Connection(connection_id=row.connection_id, org_id=row.org_id,
                      provider=row.provider, source_type=row.source_type,
                      composio_user_id=row.composio_user_id, config=_open_config(cfg or {}),
                      status=row.status, created_at=row.created_at)


class PostgresConnectionStore:
    """Per-org connections in Supabase — the multi-tenant identity table. 30 startups
    = 30 rows; each carries its own composio_user_id (never in .env)."""

    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def add(self, c: Connection) -> None:
        with self._engine.begin() as conn:
            conn.execute(_UPSERT, {
                "connection_id": c.connection_id, "org_id": c.org_id, "provider": c.provider,
                "source_type": c.source_type, "composio_user_id": c.composio_user_id,
                "config": json.dumps(_seal_config(c.config), default=str), "status": c.status,
                "created_at": c.created_at,
            })

    def list_active(self, source_type: str | None = None) -> list[Connection]:
        q = f"select {_COLS} from connections where status='connected'"
        params: dict = {}
        if source_type is not None:
            q += " and source_type=:st"
            params["st"] = source_type
        with self._engine.connect() as conn:
            return [_to_conn(r) for r in conn.execute(text(q), params)]

    def get(self, connection_id: str) -> Connection | None:
        with self._engine.connect() as conn:
            r = conn.execute(text(f"select {_COLS} from connections where connection_id=:c"),
                             {"c": connection_id}).first()
        return _to_conn(r) if r else None

    def set_status(self, connection_id: str, status: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("update connections set status=:s where connection_id=:c"),
                         {"s": status, "c": connection_id})
