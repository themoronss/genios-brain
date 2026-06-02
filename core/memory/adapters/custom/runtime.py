"""Generic custom adapter — drives any source via a frozen SourceMapping.

Per g-i-1 custom integration path, step 6 READ:
The runtime knows nothing about the source's specific API; it relies entirely on:
- A frozen SourceMapping (from freezer.py)
- A pluggable Authenticator (from auth_factory.py)
- A pluggable DeltaStrategy (from delta_strategies.py)
- A `fetcher` callable supplied at construction (HTTP / SQL / etc.)

This lets us support ANY new custom source without writing a new adapter class —
just configure these pieces and register.

For source-specific adapters with quirky logic, write a dedicated subclass under
adapters/known/ instead.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.foundations.telemetry import get_logger
from core.memory.adapters import register_adapter
from core.memory.adapters.custom.freezer import load_active
from core.memory.delta_strategies import DeltaStrategy, UpdatedAtStrategy
from core.memory.interface import MemoryAdapter
from core.memory.types import (
    AuthConfig,
    ConnectionHandle,
    Cursor,
    HealthStatus,
    HealthStatusLevel,
    RawRecord,
    ReadScope,
    RecordRef,
    SourceMapping,
)

log = get_logger(__name__)

SOURCE_TYPE = "custom"

# Fetcher: takes (cursor_value, page_size, server_filter_hints) → (records, next_cursor_value, has_more)
# Implementations live with each customer's onboarding config. They wrap HTTP / SQL / SDK calls.
Fetcher = Callable[
    [str | None, int, dict[str, str]],
    tuple[list[RawRecord], str, bool],
]


class CustomRuntimeAdapter(MemoryAdapter):
    """The generic adapter that drives any custom source via a frozen mapping."""

    def __init__(
        self,
        session: Session,
        *,
        connection_id: str,
        org_id: str,
        source_subtype: str,  # e.g. "custom:acme-crm"
        fetcher: Fetcher,
        delta_strategy: DeltaStrategy | None = None,
    ) -> None:
        self.source_id = connection_id
        self.source_type = source_subtype  # override for per-customer namespacing
        self._session = session
        self._connection_id = connection_id
        self._org_id = org_id
        self._fetcher = fetcher
        self._delta = delta_strategy or UpdatedAtStrategy()
        self._mapping: SourceMapping | None = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    def connect(self, auth: AuthConfig, scopes: list[ReadScope]) -> ConnectionHandle:
        """The fetcher is already configured with auth at construction; nothing to do here."""
        self._mapping = load_active(self._session, self._connection_id, self.source_type)
        if self._mapping is None:
            raise RuntimeError(
                f"Custom adapter for {self._connection_id} has no frozen mapping. "
                f"Run propose -> confirm -> freeze first."
            )
        return ConnectionHandle(
            connection_id=self._connection_id,
            source_type=self.source_type,
            source_id=self._connection_id,
            granted_scopes=scopes,
        )

    def health_check(self) -> HealthStatus:
        """Light fetch of 1 record as liveness check."""
        try:
            records, _, _ = self._fetcher(None, 1, {})
            return HealthStatus(
                level=HealthStatusLevel.GREEN if records is not None else HealthStatusLevel.YELLOW,
                last_sync_at=datetime.now(UTC),
            )
        except Exception as e:
            return HealthStatus(
                level=HealthStatusLevel.RED,
                last_sync_at=None,
                last_error=str(e)[:200],
            )

    def disconnect(self) -> None:
        self._mapping = None

    # ── reading ────────────────────────────────────────────────────────────

    def list_changed_since(
        self,
        cursor: Cursor | None,
        limit: int,
    ) -> tuple[list[RawRecord], Cursor, bool]:
        """Delegate pulls to the fetcher; cursor strategy from configured DeltaStrategy."""
        server_hints = self._delta.server_filter(cursor)
        cursor_value = cursor.value if cursor else None
        records, next_value, has_more = self._fetcher(cursor_value, limit, server_hints)
        next_cursor = Cursor(value=next_value, strategy=self._delta.strategy_name)  # type: ignore[arg-type]
        return records, next_cursor, has_more

    def fetch_record(self, ref: RecordRef) -> RawRecord:
        """Single-record fetch by id (webhook flow). Most custom sources lack a fetch-one API,
        so the fetcher is asked to return [the one matching ref.native_id] in a 1-record page."""
        records, _, _ = self._fetcher(None, 1, {"native_id": ref.native_id})
        if not records:
            raise KeyError(f"native_id={ref.native_id} not found in source")
        return records[0]

    def get_mapping(self) -> SourceMapping:
        if self._mapping is None:
            raise RuntimeError("connect() must be called before get_mapping()")
        return self._mapping


def _factory(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    source_subtype: str,
    fetcher: Fetcher,
    delta_strategy: DeltaStrategy | None = None,
) -> CustomRuntimeAdapter:
    return CustomRuntimeAdapter(
        session=session,
        connection_id=connection_id,
        org_id=org_id,
        source_subtype=source_subtype,
        fetcher=fetcher,
        delta_strategy=delta_strategy,
    )


register_adapter(SOURCE_TYPE, _factory)
