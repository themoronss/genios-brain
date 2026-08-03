from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import text

from genios_engine.platform.crypto import encrypt
from genios_engine.platform.db import get_engine


class RawPayloadStore(Protocol):
    """Raw content lives here — encrypted, with a short TTL — and ONLY for KEPT
    (emitted) events, so L2 can read the body. Dropped noise is never stored: this
    is what keeps L1 a filter, not a data warehouse."""

    def put(self, *, payload_id: str, org_id: str, event_id: str, content: str,
            content_type: str = "application/json", ttl_days: int = 7) -> None: ...


class InMemoryRawPayloadStore:
    def __init__(self) -> None:
        self.payloads: dict[str, dict] = {}

    def put(self, *, payload_id, org_id, event_id, content,
            content_type="application/json", ttl_days=7):
        self.payloads[payload_id] = {"org_id": org_id, "event_id": event_id,
                                     "content": content, "content_type": content_type}


_INSERT = text(
    """
    insert into raw_payloads (id, org_id, event_id, content_type, enc_content, expires_at)
    values (:id, :org_id, :event_id, :content_type, :enc_content, :expires_at)
    on conflict (id) do nothing
    """
)


class PostgresRawPayloadStore:
    def __init__(self, database_url: str, crypto_key: str) -> None:
        self._engine = get_engine(database_url)
        self._key = crypto_key

    def put(self, *, payload_id, org_id, event_id, content,
            content_type="application/json", ttl_days=7):
        expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        with self._engine.begin() as conn:
            conn.execute(_INSERT, {
                "id": payload_id, "org_id": org_id, "event_id": event_id,
                "content_type": content_type,
                "enc_content": encrypt(content, self._key),
                "expires_at": expires,
            })

    def purge_expired(self, *, org_id: str | None = None, eval_time=None) -> int:
        """Enforce the raw-content TTL (DB Law 2). Deletes encrypted raw bodies past expires_at
        and returns the count (a deletion-certificate primitive). Was NEVER run → raw PII grew
        unbounded and the 'short TTL' / deletion promise was unmet. In-process cron, no Celery."""
        now = eval_time or datetime.now(timezone.utc)
        q = "delete from raw_payloads where expires_at < :now"
        params = {"now": now}
        if org_id is not None:
            q += " and org_id = :o"
            params["o"] = org_id
        with self._engine.begin() as conn:
            return conn.execute(text(q), params).rowcount
