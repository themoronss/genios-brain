from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from genios_engine.contracts.visibility import Visibility


class DomainHint(BaseModel):
    domain: str
    source: str                              # scope | keyword | history


class GatedEvent(BaseModel):
    """L1's output to L2 — the QualifiedEnterpriseSignal boundary object (RC-1 / B-01).

    Deterministic only — no LLM classification here. Carries the routing decision (structured
    values vs needs-extraction) plus cheap hints; L2's single combined call produces relevance
    + typed facts.

    The audit's RC-1 named this object as "does not exist"; it existed under this name and was
    missing its qualifying half. Now carried: the full participant set (`recipients`), the
    source-stamped audience (`visibility`), the domain candidates (`domain_hints`), the scoped
    coverage verdict (`coverage_ready`), the authority class (`internal_kind`), and every
    version that produced it. Still deliberately absent, by design not omission:
    `importance_bp` (importance is a REASONING output — L1 stamping it would be the priority/
    importance conflation the spec forbids) and typed role candidates (roles need the
    extraction the envelope feeds; L2's b3-3 prompt owns them).
    """

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
    #: Whether the tenant's sources are complete enough for a NEGATIVE inference about this
    #: event's domain ("they did not reply", "no meeting was booked").
    #:
    #: Declared here and never assigned by `_build_gated_event`, the only constructor — so it
    #: was permanently None while `coverage/model.py` computed the real answer and threw it
    #: away. A dead field on a contract is worse than a missing one: it invites a consumer to
    #: trust a seam that carries nothing, and None reads as "unknown" exactly where a caller
    #: most wants a yes.
    coverage_ready: bool | None = None
    # Company canon (capture.internal_knowledge.INTERNAL_KINDS) — the authority this
    # event carries into the graph. None = observed traffic, ordinary rank.
    internal_kind: str | None = None
    #: The full participant set — who else was on this. Without it L2 cannot tell a
    #: conversation from a broadcast, or an introducer from a counterparty.
    recipients: tuple[str, ...] = ()
    #: Who could see the original (source-stamped at the normalize seam, gate-enforced).
    #: None only for pre-visibility rows; a freshly gated event always carries one — the gate
    #: parks `visibility_unknown` rather than publishing without it.
    visibility: Visibility | None = None
    versions: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 2                  # v2: + internal_kind (additive only)
