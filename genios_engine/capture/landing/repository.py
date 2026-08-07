from __future__ import annotations

from datetime import datetime
from typing import Protocol

from genios_engine.capture.lifecycle import ACTIVE, EXPIRED, NEW, is_expired
from genios_engine.contracts.source_event import SourceEvent


class SourceEventRepository(Protocol):
    """Storage seam. In-memory for dev/tests; a Postgres/Supabase impl replaces it
    behind the same interface (dedup uniqueness enforced by a DB unique index).
    `add` is called AFTER the gate with the decision outcome — this table is the
    dedup + decision ledger (metadata only); content is stored elsewhere, kept-only.
    route/triage_lane/domain_hints/linkage_hints persist the gate+triage decisions
    so L2 READS the seam instead of re-deriving it (heavy at ingestion, light at
    runtime)."""

    def exists(self, org_id: str, dedup_key: str) -> bool: ...
    def add(self, event: SourceEvent, outcome: str | None = None, *,
            route: str | None = None, triage_lane: str | None = None,
            domain_hints: list | None = None, linkage_hints: list | None = None) -> None: ...


class InMemorySourceEventRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], SourceEvent] = {}
        self._outcome: dict[tuple[str, str], str | None] = {}
        self._decision: dict[tuple[str, str], dict] = {}

    def exists(self, org_id: str, dedup_key: str) -> bool:
        return (org_id, dedup_key) in self._by_key

    def add(self, event: SourceEvent, outcome: str | None = None, *,
            route: str | None = None, triage_lane: str | None = None,
            domain_hints: list | None = None, linkage_hints: list | None = None) -> None:
        k = (event.org_id, event.dedup_key)
        self._by_key[k] = event
        self._outcome[k] = outcome
        self._decision[k] = {"route": route, "triage_lane": triage_lane,
                             "domain_hints": domain_hints, "linkage_hints": linkage_hints}

    def expire_due(self, now: datetime | None = None) -> int:
        """In-memory twin of the Postgres lifecycle sweep, so the rule is testable
        without a database. Same guard: a settled state is never re-opened."""
        moved = 0
        for event in self._by_key.values():
            if event.signal_state in (NEW, ACTIVE) and is_expired(event.expires_at, now):
                event.signal_state = EXPIRED
                moved += 1
        return moved

    def count(self) -> int:
        return len(self._by_key)
