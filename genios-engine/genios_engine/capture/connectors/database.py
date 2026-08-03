from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.platform.db import get_engine

from .base import RawObject, SourceBatch

# Read-only pull from a CLIENT's OWN database. Rows are STRUCTURED → they short-circuit
# the gate (no LLM). We never copy the DB — we read changed rows via a watermark column
# and emit only the mapped signal. The LLM never gets DB/SQL access. Table/column names are
# interpolated into SQL, so they are STRICTLY validated as identifiers (defense against a
# hostile /connections config being used for SQL injection).

# schema.table or bare table; letters/digits/underscore only, one optional dotted qualifier
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


def _safe_ident(name: str, what: str) -> str:
    if not isinstance(name, str) or not _IDENT.match(name):
        raise ValueError(f"unsafe {what} identifier: {name!r}")
    return name


class ClientDatabaseConnector:
    def __init__(self, *, database_url: str, table: str, identity_field: str,
                 watermark_col: str = "updated_at", source: str = "postgres") -> None:
        self._engine = get_engine(database_url)
        self.source = source
        self._table = _safe_ident(table, "table")            # e.g. "public.customer_accounts"
        self._id = _safe_ident(identity_field, "identity_field")
        self._wm = _safe_ident(watermark_col, "watermark_col")

    def _rows(self, *, since: datetime | None, limit: int) -> list[dict]:
        q = f"select * from {self._table}"    # table = trusted config, not user input
        params: dict[str, Any] = {"lim": limit}
        if since is not None:
            q += f" where {self._wm} > :since"
            params["since"] = since
        q += f" order by {self._wm} limit :lim"
        with self._engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(text(q), params)]

    def _to_raw(self, row: dict) -> RawObject | None:
        rid = row.get(self._id)
        if rid is None:
            return None
        wm = row.get(self._wm)
        occurred = wm if isinstance(wm, datetime) else datetime.now(timezone.utc)
        return RawObject(source=self.source, object_type=self._table,
                         source_object_id=str(rid), occurred_at=occurred,
                         # the watermark value IS the row's content version — a CRM deal that
                         # moves proposal→won gets a new updated_at → re-lands → deal.stage updates.
                         content_version=str(wm) if wm is not None else None,
                         actor_type="system", raw=dict(row))

    def _to_batch(self, rows: list[dict]) -> SourceBatch:
        objs = [self._to_raw(r) for r in rows]
        return SourceBatch(objects=[o for o in objs if o], next_cursor=None)

    def validate_connection(self) -> bool:
        with self._engine.connect() as c:
            c.execute(text(f"select 1 from {self._table} limit 1"))
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._rows(since=None, limit=limit))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        return self._to_batch(self._rows(since=since, limit=limit))

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        with self._engine.connect() as c:
            r = c.execute(text(f"select * from {self._table} where {self._id} = :id limit 1"),
                          {"id": object_ref}).first()
        return dict(r._mapping) if r else {}
