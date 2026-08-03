from __future__ import annotations

import json
from typing import Protocol

from sqlalchemy import text

from genios_engine.contracts.trace import EventTrace
from genios_engine.platform.db import get_engine


class TraceRepository(Protocol):
    """Persists the per-event decision trace. One row per stage in event_trace so any
    event's full path (what came in, which stage filtered it, why) is queryable."""

    def save(self, trace: EventTrace) -> None: ...


class InMemoryTraceRepository:
    def __init__(self) -> None:
        self.traces: list[EventTrace] = []

    def save(self, trace: EventTrace) -> None:
        self.traces.append(trace)


_INSERT = text(
    """
    insert into event_trace
      (org_id, event_id, dedup_key, source, stage, action, reason_code, detail)
    values
      (:org_id, :event_id, :dedup_key, :source, :stage, :action, :reason_code,
       cast(:detail as jsonb))
    """
)


class PostgresTraceRepository:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def save(self, trace: EventTrace) -> None:
        rows = [{
            "org_id": trace.org_id, "event_id": trace.event_id,
            "dedup_key": trace.dedup_key, "source": trace.source,
            "stage": r.stage, "action": r.action.value, "reason_code": r.reason_code,
            "detail": json.dumps(r.detail, default=str),
        } for r in trace.records]
        if not rows:
            return
        with self._engine.begin() as conn:
            conn.execute(_INSERT, rows)
