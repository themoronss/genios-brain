"""Delta detection — fallback chain per g-i-1 §1.1.2.

Preference order (adapters pick highest available):
1. NATIVE      — provider's change cursor / sync token (best: Drive changes API)
2. UPDATED_AT  — `updated_at > last_checkpoint` server-side filter
3. CONTENT_HASH — last resort: store hashes (NOT content) to detect change

Each strategy returns the next cursor + a `since`/filter the adapter can push to source.
After successful processing, the adapter calls `advance_cursor()` to persist the
new position ATOMICALLY (so a crash re-processes rather than skips).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from core.memory.store import CursorRow
from core.memory.types import Cursor, RawRecord


class DeltaStrategy(Protocol):
    """Adapter picks one of these for its source."""

    strategy_name: str  # 'native' | 'updated_at' | 'content_hash'

    def initial_cursor(self) -> Cursor: ...
    def server_filter(self, cursor: Cursor | None) -> dict[str, str]:
        """Hints the adapter can push into source query (e.g. {'updated_since': '...'})."""

    def next_cursor(self, records: list[RawRecord], current: Cursor | None) -> Cursor:
        """Compute the cursor to persist after processing `records`."""


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1: NATIVE (provider gives a cursor; we just pass it back)
# ─────────────────────────────────────────────────────────────────────────────


class NativeCursorStrategy:
    """Provider returns its own cursor (e.g. Google Drive changes pageToken)."""

    strategy_name = "native"

    def initial_cursor(self) -> Cursor:
        return Cursor(value="", strategy="native")

    def server_filter(self, cursor: Cursor | None) -> dict[str, str]:
        return {"pageToken": cursor.value} if cursor and cursor.value else {}

    def next_cursor(self, records: list[RawRecord], current: Cursor | None) -> Cursor:
        # Adapter must extract the new pageToken from the response and pass it
        # via this object's `provider_token` attribute before calling next_cursor.
        # Cleaner pattern: adapter calls Cursor(value=token, strategy="native") directly.
        # Default fallback: keep current.
        return current or Cursor(value="", strategy="native")


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2: UPDATED_AT (timestamp filter)
# ─────────────────────────────────────────────────────────────────────────────


class UpdatedAtStrategy:
    """Use server-side `updated_at > X` filter; cursor = ISO timestamp of last seen."""

    strategy_name = "updated_at"

    def __init__(self, updated_field: str = "updated_at") -> None:
        self._field = updated_field

    def initial_cursor(self) -> Cursor:
        return Cursor(value="1970-01-01T00:00:00+00:00", strategy="updated_at")

    def server_filter(self, cursor: Cursor | None) -> dict[str, str]:
        if cursor is None or not cursor.value:
            return {}
        return {f"{self._field}_gte": cursor.value}

    def next_cursor(self, records: list[RawRecord], current: Cursor | None) -> Cursor:
        max_ts: datetime | None = None
        for r in records:
            v = r.fields.get(self._field)
            ts = _coerce_iso(v)
            if ts is not None and (max_ts is None or ts > max_ts):
                max_ts = ts
        if max_ts is None:
            return current or self.initial_cursor()
        return Cursor(value=max_ts.isoformat(), strategy="updated_at")


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3: CONTENT_HASH (last resort — store ONLY hashes, not content)
# ─────────────────────────────────────────────────────────────────────────────


class ContentHashStrategy:
    """Store rolling sha256 of (native_id + content_hash) pairs as a delimited blob.

    Used when source has neither cursor nor updated_at. We never store the content
    itself — only its hash, scoped to native_id. On each batch we compare hashes
    to detect changed records.

    The cursor is a single sha256 over the sorted (native_id, content_hash) entries;
    we keep the actual map in a SEPARATE table when this strategy is used
    (`content_hash_state`, deferred to when first adapter needs it — most won't).

    For most realistic sources at least UPDATED_AT exists, so this is rarely picked.
    """

    strategy_name = "content_hash"

    def initial_cursor(self) -> Cursor:
        return Cursor(value="", strategy="content_hash")

    def server_filter(self, cursor: Cursor | None) -> dict[str, str]:
        # Content-hash strategy can't filter server-side; full scan + diff client-side
        return {}

    def next_cursor(self, records: list[RawRecord], current: Cursor | None) -> Cursor:
        entries = sorted((r.native_id, _hash_content(r)) for r in records)
        rolled = hashlib.sha256(repr(entries).encode("utf-8")).hexdigest()
        return Cursor(value=rolled, strategy="content_hash")


# ─────────────────────────────────────────────────────────────────────────────
# Cursor persistence (atomic)
# ─────────────────────────────────────────────────────────────────────────────


def load_cursor(session: Session, connection_id: str) -> Cursor | None:
    row = session.get(CursorRow, connection_id)
    if row is None:
        return None
    return Cursor(value=row.cursor_value, strategy=row.strategy)  # type: ignore[arg-type]


def advance_cursor(
    session: Session,
    *,
    connection_id: str,
    org_id: str,
    new_cursor: Cursor,
    items_pulled_delta: int,
) -> None:
    """Persist the new cursor + bump items_pulled counter.

    Atomicity: caller wraps in a session transaction. Cursor advances ONLY
    after items have been emitted to the bus — so a crash before this point
    causes re-processing (downstream dedupes via stable item_id).
    """
    row = session.get(CursorRow, connection_id)
    if row is None:
        row = CursorRow(
            connection_id=connection_id,
            org_id=org_id,
            cursor_value=new_cursor.value,
            strategy=new_cursor.strategy,
            items_pulled_count=items_pulled_delta,
        )
        session.add(row)
    else:
        row.cursor_value = new_cursor.value
        row.strategy = new_cursor.strategy
        row.last_sync_at = datetime.now(UTC)
        row.items_pulled_count = (row.items_pulled_count or 0) + items_pulled_delta


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _coerce_iso(v: object) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            return None
    return None


def _hash_content(r: RawRecord) -> str:
    """Stable hash of a record's fields (not the content itself — just its fingerprint)."""
    payload = repr(sorted(r.fields.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
