"""Apply a SourceMapping to a RawRecord -> MemoryItem.

Pure function. No I/O. No persistence. In-flight transform only.

Stable item_id discipline (per g-i-1 idempotency requirement):
    item_id = sha256(source_id + ':' + native_id)[:24]

This means the same source record always produces the same item_id, so
downstream dedupe (g-i-3 grounding) is safe across retries / re-runs.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from core.memory.types import (
    FieldMapping,
    MemoryItem,
    MemoryItemMetadata,
    RawRecord,
    SourceMapping,
)


class NormalizationError(Exception):
    """Raised when a required field is missing or untransformable."""


def normalize(record: RawRecord, mapping: SourceMapping, source_id: str) -> MemoryItem:
    """Apply mapping to a raw record. Returns a MemoryItem ready for emission."""
    fields = record.fields

    content = _apply(fields, mapping.field_map["content"])
    timestamp_raw = _apply(fields, mapping.field_map["timestamp"])
    timestamp = _coerce_datetime(timestamp_raw, mapping.field_map["timestamp"].transform)

    owner = _apply_optional(fields, mapping.field_map.get("owner"))
    tags = _apply_tags(fields, mapping.field_map.get("tags"))

    item_id = _stable_id(source_id, record.native_id)

    return MemoryItem(
        item_id=item_id,
        source_id=source_id,
        source_type=mapping.source_type,
        content=str(content) if content is not None else "",
        content_ref=str(fields.get("ref")) if "ref" in fields else None,
        metadata=MemoryItemMetadata(
            timestamp=timestamp,
            owner=str(owner) if owner is not None else None,
            source_confidence=mapping.overall_confidence,
            tags=tags,
            native_id=record.native_id,
        ),
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _apply(fields: dict[str, Any], fm: FieldMapping) -> Any:
    if fm.source_field not in fields:
        raise NormalizationError(f"Required source field missing: {fm.source_field!r}")
    return fields[fm.source_field]


def _apply_optional(fields: dict[str, Any], fm: FieldMapping | None) -> Any:
    if fm is None or fm.source_field not in fields:
        return None
    return fields[fm.source_field]


def _apply_tags(fields: dict[str, Any], fm: FieldMapping | None) -> list[str]:
    if fm is None:
        return []
    v = fields.get(fm.source_field)
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]


def _coerce_datetime(v: Any, transform: str | None) -> datetime:
    """Coerce raw timestamp value to UTC datetime.

    Supported transforms:
        None             -> ISO 8601 string or datetime
        'epoch_ms_to_iso8601'  -> int/float milliseconds since epoch
        'epoch_s_to_iso8601'   -> int/float seconds since epoch
    """
    if transform == "epoch_ms_to_iso8601":
        return datetime.fromtimestamp(float(v) / 1000, tz=UTC)
    if transform == "epoch_s_to_iso8601":
        return datetime.fromtimestamp(float(v), tz=UTC)

    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=UTC)
    if isinstance(v, (int, float)):
        # Heuristic: > 1e12 -> ms, else seconds
        return datetime.fromtimestamp(float(v) / 1000 if v > 1e12 else float(v), tz=UTC)
    if isinstance(v, str):
        try:
            dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError as e:
            raise NormalizationError(f"Cannot parse timestamp string: {v!r}") from e
    raise NormalizationError(f"Unsupported timestamp value type: {type(v).__name__}")


def _stable_id(source_id: str, native_id: str) -> str:
    """Deterministic, collision-safe item id."""
    h = hashlib.sha256(f"{source_id}:{native_id}".encode()).hexdigest()
    return h[:24]
