"""Unit tests for core.memory.scope — the safety-critical 2-layer enforcement."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.memory.scope import ScopeEnforcer
from core.memory.types import RawRecord, ReadScope, ScopeLevel


@pytest.mark.unit
def test_source_scope_allows_everything() -> None:
    """SOURCE level = no filter beyond connection itself."""
    enf = ScopeEnforcer(
        [ReadScope(level=ScopeLevel.SOURCE)],
        connection_id="c",
        org_id="o",
    )
    assert enf.is_allowed(RawRecord(native_id="x", fields={}))


@pytest.mark.unit
def test_container_include_filters() -> None:
    """CONTAINER include: only listed containers pass."""
    enf = ScopeEnforcer(
        [ReadScope(level=ScopeLevel.CONTAINER, include=["sales-folder"])],
        connection_id="c",
        org_id="o",
    )
    assert enf.is_allowed(RawRecord(native_id="a", fields={"container": "sales-folder"}))
    assert not enf.is_allowed(RawRecord(native_id="b", fields={"container": "private-folder"}))
    assert enf.drop_count == 1


@pytest.mark.unit
def test_attribute_exclude_wins() -> None:
    """ITEM_ATTRIBUTE exclude beats include — defense for sensitive tags."""
    enf = ScopeEnforcer(
        [
            ReadScope(
                level=ScopeLevel.ITEM_ATTRIBUTE,
                include=["shareable"],
                exclude=["pii", "private"],
            ),
        ],
        connection_id="c",
        org_id="o",
    )
    # has BOTH shareable AND pii -> exclude wins, dropped
    assert not enf.is_allowed(RawRecord(native_id="x", fields={"tags": ["shareable", "pii"]}))
    # only shareable -> allowed
    assert enf.is_allowed(RawRecord(native_id="y", fields={"tags": ["shareable"]}))


@pytest.mark.unit
def test_time_scope_drops_old_records() -> None:
    """TIME scope: anything older than since is dropped."""
    since = datetime(2026, 1, 1, tzinfo=UTC)
    enf = ScopeEnforcer(
        [ReadScope(level=ScopeLevel.TIME, since=since)],
        connection_id="c",
        org_id="o",
    )
    assert enf.is_allowed(RawRecord(native_id="new", fields={"timestamp": "2026-06-01T00:00:00Z"}))
    assert not enf.is_allowed(
        RawRecord(native_id="old", fields={"timestamp": "2025-12-01T00:00:00Z"})
    )


@pytest.mark.unit
def test_missing_timestamp_with_time_scope_drops() -> None:
    """Defensive: time-scoped record with no timestamp -> drop (never silent allow)."""
    enf = ScopeEnforcer(
        [ReadScope(level=ScopeLevel.TIME, since=datetime(2026, 1, 1, tzinfo=UTC))],
        connection_id="c",
        org_id="o",
    )
    assert not enf.is_allowed(RawRecord(native_id="x", fields={}))


@pytest.mark.unit
def test_server_side_hints() -> None:
    """Hints expose include/exclude lists adapters can push into source queries."""
    enf = ScopeEnforcer(
        [
            ReadScope(level=ScopeLevel.CONTAINER, include=["sales"]),
            ReadScope(level=ScopeLevel.ITEM_ATTRIBUTE, include=["urgent"], exclude=["pii"]),
        ],
        connection_id="c",
        org_id="o",
    )
    hints = enf.server_side_hints()
    assert "sales" in hints["containers"]
    assert "urgent" in hints["include_tags"]
    assert "pii" in hints["exclude_tags"]


@pytest.mark.unit
def test_filter_batch() -> None:
    """Convenience: filter drops out-of-scope records from a batch."""
    enf = ScopeEnforcer(
        [ReadScope(level=ScopeLevel.CONTAINER, include=["ok"])],
        connection_id="c",
        org_id="o",
    )
    records = [
        RawRecord(native_id="1", fields={"container": "ok"}),
        RawRecord(native_id="2", fields={"container": "drop"}),
        RawRecord(native_id="3", fields={"container": "ok"}),
    ]
    kept = enf.filter(records)
    assert [r.native_id for r in kept] == ["1", "3"]
    assert enf.drop_count == 1
