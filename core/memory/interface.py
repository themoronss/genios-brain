"""MemoryAdapter — the contract every source implements.

HARD INVARIANT (per g-i-1 §1.1.1):
- NO WRITE METHODS. Adapters cannot mutate source data.
- This invariant is enforced by construction (interface omits them).
- For providers that only issue read+write tokens, an outer guard layer (auth_factory)
  refuses non-read operations.

Two construction paths share this same interface:
- KnownAdapter — mapping hardcoded by us. sourceConfidence = 1.0.
- CustomAdapter — mapping resolved at setup via LLM-propose + human-confirm + freeze.

This file defines the contract only. Concrete implementations live in adapters/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.memory.types import (
        AuthConfig,
        ConnectionHandle,
        Cursor,
        HealthStatus,
        RawRecord,
        ReadScope,
        RecordRef,
        SourceMapping,
        WebhookRegistration,
    )


class MemoryAdapter(ABC):
    """The contract. All read-only. No write paths.

    Subclasses MUST set:
        sourceType: str  # 'gmail' | 'notion' | 'custom:<id>'

    Subclasses MUST implement:
        connect, health_check, disconnect, list_changed_since, fetch_record, get_mapping

    Subclasses MAY implement (webhook-capable sources):
        register_webhook, parse_webhook
    """

    source_type: str
    source_id: str

    # ── lifecycle ──────────────────────────────────────────────────────────

    @abstractmethod
    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        """Authenticate + register scope grants. Returns a handle."""

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Liveness + last-sync info for the customer health page."""

    @abstractmethod
    def disconnect(self) -> None:
        """Tear down (revoke tokens if provider supports it, drop in-memory state)."""

    # ── reading (READ-ONLY) ────────────────────────────────────────────────

    @abstractmethod
    def list_changed_since(
        self,
        cursor: Cursor | None,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        """Pull changed records since the cursor.

        Returns (records, next_cursor, has_more). `has_more=True` means
        more pages are available immediately.
        """

    @abstractmethod
    def fetch_record(self, ref: RecordRef) -> RawRecord:
        """Fetch a single record by reference (used by webhook -> fetch flow)."""

    # ── mapping ────────────────────────────────────────────────────────────

    @abstractmethod
    def get_mapping(self) -> SourceMapping:
        """Return the source mapping (hardcoded for known, frozen artifact for custom)."""

    # ── realtime (optional — None if source has no webhooks) ──────────────

    def register_webhook(self, scopes: list[ReadScope]) -> WebhookRegistration | None:
        """Optionally register a webhook with the source. Default: None (no webhook)."""
        return None

    def parse_webhook(self, payload: object) -> list[RecordRef]:
        """Optionally parse an inbound webhook payload into record refs. Default: empty."""
        return []
