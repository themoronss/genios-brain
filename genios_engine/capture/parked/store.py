from __future__ import annotations

import json
from typing import Protocol

from sqlalchemy import text

from genios_engine.contracts.parked import ParkedEvent
from genios_engine.contracts.trace import EventTrace
from genios_engine.platform.db import get_engine


class ParkedStore(Protocol):
    def add(self, p: ParkedEvent) -> None: ...
    def list(self, org_id: str, reason_code: str | None = None) -> list[ParkedEvent]: ...
    def get(self, event_id: str) -> ParkedEvent | None: ...
    def set_status(self, event_id: str, status: str) -> None: ...


class InMemoryParkedStore:
    def __init__(self) -> None:
        self._by_id: dict[str, ParkedEvent] = {}

    def add(self, p: ParkedEvent) -> None:
        self._by_id[p.event_id] = p

    def list(self, org_id: str, reason_code: str | None = None) -> list[ParkedEvent]:
        return [p for p in self._by_id.values()
                if p.org_id == org_id and (reason_code is None or p.reason_code == reason_code)]

    def get(self, event_id: str) -> ParkedEvent | None:
        return self._by_id.get(event_id)

    def set_status(self, event_id: str, status: str) -> None:
        if event_id in self._by_id:
            self._by_id[event_id].status = status


_P_COLS = "event_id, org_id, source, reason_code, stage, trace, status, created_at"


def _to_parked(row) -> ParkedEvent:
    tr = row.trace if isinstance(row.trace, list) else json.loads(row.trace or "[]")
    return ParkedEvent(event_id=row.event_id, org_id=row.org_id, source=row.source,
                       reason_code=row.reason_code, stage=row.stage, trace=tr,
                       status=row.status, created_at=row.created_at)


class PostgresParkedStore:
    def __init__(self, database_url: str) -> None:
        self._engine = get_engine(database_url)

    def add(self, p: ParkedEvent) -> None:
        with self._engine.begin() as conn:
            conn.execute(text(
                """insert into parked_events
                   (event_id, org_id, source, reason_code, stage, trace, status, created_at)
                   values (:event_id, :org_id, :source, :reason_code, :stage,
                           cast(:trace as jsonb), :status, :created_at)
                   on conflict (event_id) do nothing"""),
                {"event_id": p.event_id, "org_id": p.org_id, "source": p.source,
                 "reason_code": p.reason_code, "stage": p.stage,
                 "trace": json.dumps(p.trace, default=str), "status": p.status,
                 "created_at": p.created_at})

    def list(self, org_id: str, reason_code: str | None = None) -> list[ParkedEvent]:
        q = f"select {_P_COLS} from parked_events where org_id=:o"
        params: dict = {"o": org_id}
        if reason_code is not None:
            q += " and reason_code=:r"
            params["r"] = reason_code
        with self._engine.connect() as conn:
            return [_to_parked(r) for r in conn.execute(text(q + " order by created_at desc"),
                                                        params)]

    def get(self, event_id: str) -> ParkedEvent | None:
        with self._engine.connect() as conn:
            r = conn.execute(text(f"select {_P_COLS} from parked_events where event_id=:e"),
                             {"e": event_id}).first()
        return _to_parked(r) if r else None

    def set_status(self, event_id: str, status: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(text("update parked_events set status=:s where event_id=:e"),
                         {"s": status, "e": event_id})


def parked_from_trace(org_id: str, event_id: str, source: str, reason_code: str,
                      trace: EventTrace) -> ParkedEvent:
    last = trace.records[-1] if trace.records else None
    return ParkedEvent(
        event_id=event_id, org_id=org_id, source=source, reason_code=reason_code,
        stage=last.stage if last else "unknown",
        trace=[{"stage": r.stage, "action": r.action.value, "reason": r.reason_code}
               for r in trace.records],
    )
