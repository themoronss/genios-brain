from __future__ import annotations

from typing import Protocol

from genios_engine.contracts.source_event import SourceEvent


class SourceEventRepository(Protocol):
    """Storage seam. In-memory for dev/tests; a Postgres/Supabase impl replaces it
    behind the same interface (dedup uniqueness enforced by a DB unique index).
    `add` is called AFTER the gate with the decision outcome — this table is the
    dedup + decision ledger (metadata only); content is stored elsewhere, kept-only."""

    def exists(self, org_id: str, dedup_key: str) -> bool: ...
    def add(self, event: SourceEvent, outcome: str | None = None) -> None: ...


class InMemorySourceEventRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], SourceEvent] = {}
        self._outcome: dict[tuple[str, str], str | None] = {}

    def exists(self, org_id: str, dedup_key: str) -> bool:
        return (org_id, dedup_key) in self._by_key

    def add(self, event: SourceEvent, outcome: str | None = None) -> None:
        self._by_key[(event.org_id, event.dedup_key)] = event
        self._outcome[(event.org_id, event.dedup_key)] = outcome

    def count(self) -> int:
        return len(self._by_key)
