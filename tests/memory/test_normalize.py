"""Unit tests for core.memory.normalize."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.memory.normalize import NormalizationError, normalize
from core.memory.types import FieldMapping, RawRecord, SourceMapping


def _mapping() -> SourceMapping:
    return SourceMapping(
        source_type="custom:test",
        field_map={
            "content": FieldMapping(source_field="body", confidence=0.9),
            "timestamp": FieldMapping(
                source_field="ts_ms",
                transform="epoch_ms_to_iso8601",
                confidence=0.95,
            ),
            "owner": FieldMapping(source_field="author", confidence=0.8),
            "tags": FieldMapping(source_field="labels", confidence=0.9),
        },
        confirmed_by="alice@org",
        confirmed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        version=1,
    )


@pytest.mark.unit
def test_normalize_happy_path() -> None:
    """Mapping applied, MemoryItem produced, stable id deterministic."""
    record = RawRecord(
        native_id="msg_123",
        fields={
            "body": "Hello world",
            "ts_ms": 1717200000000,
            "author": "bob@acme.com",
            "labels": ["urgent", "deal"],
        },
    )
    item = normalize(record, _mapping(), source_id="conn_abc")

    assert item.content == "Hello world"
    assert item.source_id == "conn_abc"
    assert item.source_type == "custom:test"
    assert item.metadata.owner == "bob@acme.com"
    assert item.metadata.tags == ["urgent", "deal"]
    # source_confidence = min across field confidences = 0.8 (owner)
    assert item.metadata.source_confidence == 0.8


@pytest.mark.unit
def test_normalize_stable_id() -> None:
    """Same (source_id, native_id) -> same item_id (idempotency)."""
    record = RawRecord(native_id="x", fields={"body": "a", "ts_ms": 1717200000000})
    m = SourceMapping(
        source_type="t",
        field_map={
            "content": FieldMapping(source_field="body", confidence=1.0),
            "timestamp": FieldMapping(source_field="ts_ms", transform="epoch_ms_to_iso8601", confidence=1.0),
        },
        confirmed_by="a",
        confirmed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        version=1,
    )
    a = normalize(record, m, source_id="conn")
    b = normalize(record, m, source_id="conn")
    assert a.item_id == b.item_id


@pytest.mark.unit
def test_normalize_missing_required_field_raises() -> None:
    """Missing 'content' source field -> NormalizationError (no silent defaults)."""
    record = RawRecord(native_id="x", fields={"ts_ms": 1717200000000})
    with pytest.raises(NormalizationError):
        normalize(record, _mapping(), source_id="conn")


@pytest.mark.unit
def test_normalize_handles_iso_string_timestamp() -> None:
    """ISO 8601 timestamp string with Z works."""
    m = SourceMapping(
        source_type="t",
        field_map={
            "content": FieldMapping(source_field="body", confidence=1.0),
            "timestamp": FieldMapping(source_field="iso_ts", confidence=1.0),
        },
        confirmed_by="a",
        confirmed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        version=1,
    )
    record = RawRecord(native_id="x", fields={"body": "hi", "iso_ts": "2026-06-01T12:00:00Z"})
    item = normalize(record, m, source_id="conn")
    assert item.metadata.timestamp.year == 2026
    assert item.metadata.timestamp.tzinfo is not None
