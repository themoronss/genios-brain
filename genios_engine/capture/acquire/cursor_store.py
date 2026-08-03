from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import text

from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id


@dataclass
class Cursor:
    cursor: str | None = None            # provider pagination token
    watermark: datetime | None = None    # latest occurred_at seen — resume point
    last_object_id: str | None = None


class CursorStore(Protocol):
    """Per-connection sync position. Combined with a small overlap + the dedup ledger,
    this is the no-miss backbone: next run resumes from the watermark, re-scans the
    boundary, and duplicates are dropped by dedup — nothing slips through the gap."""

    def get(self, org_id: str, connection_id: str, source: str) -> Cursor | None: ...
    def save(self, org_id: str, connection_id: str, source: str, *,
             cursor: str | None = None, watermark: datetime | None = None,
             last_object_id: str | None = None) -> None: ...


class InMemoryCursorStore:
    def __init__(self) -> None:
        self._d: dict[tuple[str, str, str], Cursor] = {}

    def get(self, org_id, connection_id, source):
        return self._d.get((org_id, connection_id, source))

    def save(self, org_id, connection_id, source, *, cursor=None, watermark=None,
             last_object_id=None):
        self._d[(org_id, connection_id, source)] = Cursor(cursor, watermark, last_object_id)


class PostgresCursorStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def get(self, org_id, connection_id, source):
        with self._engine.connect() as c:
            r = c.execute(text(
                "select cursor, watermark, last_object_id from sync_cursors "
                "where org_id=:o and connection_id=:c and source=:s"),
                {"o": org_id, "c": connection_id, "s": source}).first()
        return Cursor(r.cursor, r.watermark, r.last_object_id) if r else None

    def save(self, org_id, connection_id, source, *, cursor=None, watermark=None,
             last_object_id=None):
        with self._engine.begin() as c:
            row = c.execute(text("select id from sync_cursors where org_id=:o "
                                 "and connection_id=:c and source=:s"),
                            {"o": org_id, "c": connection_id, "s": source}).first()
            if row:
                c.execute(text("update sync_cursors set cursor=:cur, watermark=:wm, "
                               "last_object_id=:lo, updated_at=now() where id=:id"),
                          {"cur": cursor, "wm": watermark, "lo": last_object_id, "id": row.id})
            else:
                c.execute(text("insert into sync_cursors "
                               "(id, org_id, connection_id, source, cursor, watermark, last_object_id) "
                               "values (:id,:o,:c,:s,:cur,:wm,:lo)"),
                          {"id": new_id("cur"), "o": org_id, "c": connection_id, "s": source,
                           "cur": cursor, "wm": watermark, "lo": last_object_id})
