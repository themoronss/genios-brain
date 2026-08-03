from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    versions: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1
