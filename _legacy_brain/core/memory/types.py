"""Type contracts for the memory layer.

THIN canonical shape per g-i-1 §1.2.2 — deep enrichment is Part 2/3's job, not here.

Design rules enforced here:
- MemoryItem.content is plain text (g-i-3 will SPO-parse it)
- Stable itemId enables downstream dedupe (idempotency requirement)
- sourceConfidence carries mapping confidence forward so reasoning can weight it
- No fields that would imply we store more than this snapshot
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ─────────────────────────────────────────────────────────────────────────────
# Core item shape (engine input)
# ─────────────────────────────────────────────────────────────────────────────


class StructuredFactsHint(BaseModel):
    """Hint that this MemoryItem already carries deterministic structured
    facts and the LLM-extraction subscriber should skip the Haiku call.

    Used by row-shaped adapters (CSV upload, custom-mapping connections,
    direct API sync of well-typed records) where:
      * Column→fact mapping is already resolved (no need to re-discover via
        LLM) — so emit cost-free.
      * Predicate names are guaranteed to match what module rules consume —
        so engine reasoning stays deterministic.
      * Derived facts the LLM cannot reliably compute (days_past_due,
        client_late_count_90d) are pre-baked here.

    Wire contract: when this is present on `MemoryItemMetadata`, the
    `g-i-3` ingest subscriber MUST persist the entities+facts directly
    (no extract call). When absent, the existing LLM-extract path runs
    unchanged. Single bus, two ingestion modes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    entity_name: str = Field(..., min_length=1, description="Primary entity (e.g. Client) — becomes canonical_name on a graph node")
    entity_type: str = Field(default="client", description="Graph node type for the primary entity")
    secondary_entity_id: str | None = Field(
        default=None,
        description="External id of a secondary entity emitted alongside (e.g. invoice_id) — also persisted as a graph node",
    )
    secondary_entity_type: str = Field(default="invoice", description="Type of the secondary entity")
    entity_attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Attributes stored on the primary entity node (email, phone, etc.)",
    )
    facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Predicate -> value map. Each entry becomes one FactRow on the secondary entity (or primary if secondary absent).",
    )
    edge_predicate: str | None = Field(
        default="issued_to",
        description="Predicate of the edge linking secondary -> primary entity",
    )


class MemoryItemMetadata(BaseModel):
    """Metadata for a MemoryItem — every field optional except timestamp."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime = Field(..., description="When the item was created/updated at source")
    owner: str | None = Field(default=None, description="Who it belongs to at source, if known")
    source_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="1.0 for known adapters; lower for LLM-mapped custom sources",
    )
    tags: list[str] = Field(default_factory=list, description="Source-native labels passed through")
    native_id: str | None = Field(
        default=None,
        description="Raw provider record id (pre-hash). Lets the zero-signal sync "
        "refund key back to the exact deduct row, whose idempotency_key ends in "
        "the raw native_id — item_id (the hash) would never match.",
    )
    structured_facts: StructuredFactsHint | None = Field(
        default=None,
        description="Optional — present when the adapter already resolved column->fact mapping. Tells g-i-3 ingest subscriber to skip LLM extraction and persist directly. See StructuredFactsHint docstring for the invariant.",
    )


class MemoryItem(BaseModel):
    """The canonical engine input. Thin by design."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: str = Field(
        ...,
        min_length=1,
        description="Stable, deterministic id (sourceId + native record id, hashed) — enables dedupe",
    )
    source_id: str = Field(..., min_length=1, description="Connected source instance id")
    source_type: str = Field(
        ...,
        min_length=1,
        description="e.g. 'gmail' | 'notion' | 'custom:acme-db'",
    )
    content: str = Field(
        ...,
        description="Plaintext, source-stripped. Adapter responsible for clean extraction.",
    )
    content_ref: str | None = Field(
        default=None,
        description="Optional pointer back to source record (URL/id) — NOT a stored copy",
    )
    metadata: MemoryItemMetadata


# ─────────────────────────────────────────────────────────────────────────────
# Raw source record (in-flight only — never persisted)
# ─────────────────────────────────────────────────────────────────────────────


class RawRecord(BaseModel):
    """What an adapter returns from a source. Used in-flight only."""

    model_config = ConfigDict(extra="allow")

    native_id: str = Field(..., description="Source's native record id")
    fields: dict[str, Any] = Field(..., description="Raw source fields (used for normalization)")


class RecordRef(BaseModel):
    """A pointer to a source record (for webhook -> fetch flow)."""

    model_config = ConfigDict(frozen=True)

    source_id: str
    native_id: str


# ─────────────────────────────────────────────────────────────────────────────
# Cursor (delta detection state)
# ─────────────────────────────────────────────────────────────────────────────


class Cursor(BaseModel):
    """Opaque per-source position marker. Strategy varies per adapter."""

    model_config = ConfigDict(frozen=True)

    value: str = Field(..., description="Opaque cursor value (sync token / timestamp / hash)")
    strategy: Literal["native", "updated_at", "content_hash", "backfill"] = Field(
        ...,
        description="Which delta-detection strategy produced this cursor. "
        "'backfill' = paginating existing items on first connect (Drive), "
        "switched to the native delta token once the backfill is exhausted.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Source mapping (frozen artifact for custom adapters)
# ─────────────────────────────────────────────────────────────────────────────


class FieldMapping(BaseModel):
    """One source field -> canonical field."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_field: str
    transform: str | None = Field(
        default=None,
        description="Optional transform identifier, e.g. 'epoch_ms_to_iso8601'",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


class SourceMapping(BaseModel):
    """The frozen mapping artifact. Drives all reads from a custom source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: str
    field_map: dict[Literal["content", "timestamp", "owner", "tags"], FieldMapping]
    confirmed_by: str = Field(..., description="Human who approved the mapping")
    confirmed_at: datetime
    version: int = Field(..., ge=1, description="Bumps on re-confirmation after drift")

    @property
    def overall_confidence(self) -> float:
        """Min confidence across mapped fields — propagated to MemoryItem.metadata."""
        if not self.field_map:
            return 0.0
        return min(fm.confidence for fm in self.field_map.values())


# ─────────────────────────────────────────────────────────────────────────────
# Scope (4 granularity levels per g-i-1 §1.2.1)
# ─────────────────────────────────────────────────────────────────────────────


class ScopeLevel(StrEnum):
    """Granularity of a read scope. Defense-in-depth: server-side filter + post-fetch gate."""

    SOURCE = "source"  # entire source instance (the workspace)
    CONTAINER = "container"  # folder / label / database / collection
    ITEM_ATTRIBUTE = "item_attribute"  # tag-based filter (include/exclude)
    TIME = "time"  # only items newer than X


class ReadScope(BaseModel):
    """A scope grant. Multiple per connection are AND-combined."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: ScopeLevel
    include: list[str] = Field(default_factory=list, description="Inclusive matchers")
    exclude: list[str] = Field(
        default_factory=list, description="Exclusive matchers (override include)"
    )
    since: datetime | None = Field(default=None, description="For TIME level — only items >= this")

    @field_validator("include", "exclude")
    @classmethod
    def _not_empty_strings(cls, v: list[str]) -> list[str]:
        return [s for s in v if s.strip()]


# ─────────────────────────────────────────────────────────────────────────────
# Auth (pluggable schemes for custom sources)
# ─────────────────────────────────────────────────────────────────────────────


class AuthScheme(StrEnum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    SERVICE_ACCOUNT = "service_account"
    BASIC = "basic"
    MTLS = "mtls"
    JWT = "jwt"
    SIGNED_HEADER = "signed_header"


class AuthConfig(BaseModel):
    """Auth configuration for a connection.

    Actual credentials live in the encrypted secrets store, referenced by `secrets_ref_id`.
    Never carry plaintext credentials through this object.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    scheme: AuthScheme
    secrets_ref_id: str = Field(..., description="Pointer into secrets store (encrypted)")
    extra: dict[str, str] = Field(
        default_factory=dict,
        description="Non-secret auth params (e.g. token_url, scope strings)",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Runtime handles (connect() output, webhook registration)
# ─────────────────────────────────────────────────────────────────────────────


class ConnectionHandle(BaseModel):
    """Returned by MemoryAdapter.connect(). Carries connection-level runtime state."""

    model_config = ConfigDict(frozen=True)

    connection_id: str
    source_type: str
    source_id: str
    granted_scopes: list[ReadScope]


class WebhookRegistration(BaseModel):
    """Returned by MemoryAdapter.registerWebhook(). Carries source-issued ids."""

    model_config = ConfigDict(frozen=True)

    webhook_id: str = Field(..., description="Source-assigned id for the registration")
    secret: str = Field(..., description="Secret used to verify inbound webhook signatures")
    callback_url: str = Field(..., description="Public URL the source will POST to")


class HealthStatusLevel(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class HealthStatus(BaseModel):
    """Returned by MemoryAdapter.healthCheck(). Customer-facing status."""

    model_config = ConfigDict(frozen=True)

    level: HealthStatusLevel
    last_sync_at: datetime | None
    items_pulled_count: int = 0
    scope_drops_count: int = 0
    last_error: str | None = None
