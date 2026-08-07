from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from genios_engine.contracts.visibility import Visibility


class DomainHint(BaseModel):
    domain: str
    source: str                              # scope | keyword | history


class GatedEvent(BaseModel):
    """L1's output to L2. Deterministic only — no LLM classification here. Carries the
    routing decision (structured values vs needs-extraction) plus cheap hints; L2's
    single combined call produces relevance + typed facts."""

    event_id: str
    org_id: str
    source: str
    object_type: str
    occurred_at: datetime
    payload_ref: str | None = None
    prepared_content_ref: str | None = None

    route: str                               # "structured" | "needs_extraction"
    structured_fields: dict[str, Any] = Field(default_factory=dict)   # for structured route

    domain_hints: list[DomainHint] = Field(default_factory=list)
    deadline_at: datetime | None = None
    linkage_hints: list[dict[str, Any]] = Field(default_factory=list)
    triage_lane: str = "P2"
    coverage_ready: bool | None = None
    # Company canon (capture.internal_knowledge.INTERNAL_KINDS) — the authority this
    # event carries into the graph. None = observed traffic, ordinary rank.
    internal_kind: str | None = None
    # The audience of the evidence, carried from the source ACL (contracts.visibility).
    # Every layer above must narrow to this, never widen past it — L1 is the last place
    # that still knows who the original recipients were.
    visibility: Visibility = Field(default_factory=Visibility)
    # Signal lifecycle (capture.lifecycle): when this stops being current, and its state.
    # L1 emits `new`; `active`/`satisfied` are L2+'s to write, `expired` is the sweep's.
    expires_at: datetime | None = None
    signal_state: str = "new"
    versions: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 3                  # v3: + visibility, expires_at, signal_state
