from __future__ import annotations

from typing import Protocol

from genios_engine.capture.attention import ATTENTIONS
from genios_engine.contracts.source_event import SourceEvent


class SourceEventRepository(Protocol):
    """Storage seam. In-memory for dev/tests; a Postgres/Supabase impl replaces it
    behind the same interface (dedup uniqueness enforced by a DB unique index).
    `add` is called AFTER the gate with the decision outcome — this table is the
    dedup + decision ledger (metadata only); content is stored elsewhere, kept-only.
    route/triage_lane/domain_hints/linkage_hints persist the gate+triage decisions
    so L2 READS the seam instead of re-deriving it (heavy at ingestion, light at
    runtime). attention/attention_reason are the mail's tier and why (STEP-03,
    `capture/attention.attention_for`) — None from a caller that names none."""

    def exists(self, org_id: str, dedup_key: str) -> bool: ...
    def add(self, event: SourceEvent, outcome: str | None = None, *,
            route: str | None = None, triage_lane: str | None = None,
            domain_hints: list | None = None, linkage_hints: list | None = None,
            attention: str | None = None, attention_reason: str | None = None) -> None: ...


class InMemorySourceEventRepository:
    def __init__(self) -> None:
        self._by_key: dict[tuple[str, str], SourceEvent] = {}
        self._outcome: dict[tuple[str, str], str | None] = {}
        self._decision: dict[tuple[str, str], dict] = {}

    def exists(self, org_id: str, dedup_key: str) -> bool:
        return (org_id, dedup_key) in self._by_key

    def add(self, event: SourceEvent, outcome: str | None = None, *,
            route: str | None = None, triage_lane: str | None = None,
            domain_hints: list | None = None, linkage_hints: list | None = None,
            attention: str | None = None, attention_reason: str | None = None) -> None:
        # Migration 0192's check, mirrored: a tier outside the vocabulary is refused here exactly
        # where Postgres refuses it, so a test on this store fails where production would.
        if attention is not None and attention not in ATTENTIONS:
            raise ValueError(f"attention {attention!r} is not one of {ATTENTIONS}")
        k = (event.org_id, event.dedup_key)
        self._by_key[k] = event
        self._outcome[k] = outcome
        self._decision[k] = {"route": route, "triage_lane": triage_lane,
                             "domain_hints": domain_hints, "linkage_hints": linkage_hints,
                             "attention": attention, "attention_reason": attention_reason}

    def count(self) -> int:
        return len(self._by_key)
