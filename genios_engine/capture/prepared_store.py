"""PreparedContent persistence — the L1→L2 seam, stored.

L1 pays once (HTML strip, quote strip, PII mask, offset map) at ingestion; L2 and every
later re-extraction read the SAME prepared text instead of re-deriving it. The offset
map is what makes '[start,end] evidence → exact source sentence' possible downstream.

Retention: prepared text is the MASKED, replayable form — kept 180 days (longer than the
encrypted raw payload's 30) so an improved extractor can re-run history without re-paying
or re-fetching. Both clocks are enforced by purge jobs, and both stores erase by org for
account deletion."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import text

from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.platform.db import get_engine

PREPARED_TTL_DAYS = 180


class PreparedContentStore(Protocol):
    def put(self, *, org_id: str, prepared: PreparedContent,
            ttl_days: int = PREPARED_TTL_DAYS) -> None: ...
    def get_text(self, *, org_id: str, event_id: str) -> str | None: ...


class InMemoryPreparedContentStore:
    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}                 # event_id -> row

    def put(self, *, org_id, prepared: PreparedContent, ttl_days=PREPARED_TTL_DAYS):
        self.rows[prepared.event_id] = {"org_id": org_id, "prepared": prepared}

    def get_text(self, *, org_id, event_id) -> str | None:
        row = self.rows.get(event_id)
        if row is None or row["org_id"] != org_id:
            return None
        return row["prepared"].clean_text


class PostgresPreparedContentStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def put(self, *, org_id, prepared: PreparedContent, ttl_days=PREPARED_TTL_DAYS):
        expires = datetime.now(timezone.utc) + timedelta(days=ttl_days)
        with self._engine.begin() as c:
            c.execute(text(
                "insert into prepared_content (event_id, org_id, prepared_content_id, "
                "clean_text, language, masked_spans, protected_spans, offset_map, "
                "signature_hints, preprocessor_version, expires_at) "
                "values (:e, :o, :pid, :txt, :lang, cast(:ms as jsonb), cast(:ps as jsonb), "
                "cast(:om as jsonb), cast(:sh as jsonb), :pv, :exp) "
                "on conflict (event_id) do nothing"),
                {"e": prepared.event_id, "o": org_id,
                 "pid": prepared.prepared_content_id, "txt": prepared.clean_text,
                 "lang": prepared.language,
                 "ms": json.dumps([m.model_dump() for m in prepared.masked_spans]),
                 "ps": json.dumps([list(p) for p in prepared.protected_spans]),
                 "om": json.dumps([s.model_dump() for s in prepared.offset_map]),
                 "sh": json.dumps(prepared.signature_hints, default=str),
                 "pv": prepared.preprocessor_version, "exp": expires})

    def get_text(self, *, org_id, event_id) -> str | None:
        with self._engine.connect() as c:
            r = c.execute(text(
                "select clean_text from prepared_content "
                "where event_id=:e and org_id=:o"), {"e": event_id, "o": org_id}).first()
        return r.clean_text if r else None

    def purge_expired(self, *, eval_time=None) -> int:
        now = eval_time or datetime.now(timezone.utc)
        with self._engine.begin() as c:
            return c.execute(text(
                "delete from prepared_content where expires_at < :now"),
                {"now": now}).rowcount
