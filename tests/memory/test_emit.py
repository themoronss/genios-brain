"""Tests for core.memory.emit — multi-subscriber pub/sub with failure isolation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.memory.emit import InProcessBus
from core.memory.types import MemoryItem, MemoryItemMetadata


def _item(item_id: str = "abc") -> MemoryItem:
    return MemoryItem(
        item_id=item_id,
        source_id="conn",
        source_type="gmail",
        content="hi",
        metadata=MemoryItemMetadata(timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)),
    )


@pytest.mark.unit
def test_fan_out_to_all_subscribers() -> None:
    bus = InProcessBus()
    received: dict[str, list[str]] = {"a": [], "b": [], "c": []}

    bus.subscribe("a", lambda i: received["a"].append(i.item_id))
    bus.subscribe("b", lambda i: received["b"].append(i.item_id))
    bus.subscribe("c", lambda i: received["c"].append(i.item_id))

    bus.emit(_item("x"), org_id="o")
    assert received == {"a": ["x"], "b": ["x"], "c": ["x"]}


@pytest.mark.unit
def test_one_failing_subscriber_does_not_break_others() -> None:
    """Critical isolation property — per emission contract."""
    bus = InProcessBus()
    received: list[str] = []

    def boom(_: MemoryItem) -> None:
        raise RuntimeError("subscriber explodes")

    bus.subscribe("boom", boom)
    bus.subscribe("good", lambda i: received.append(i.item_id))

    # Must not raise, must deliver to "good"
    bus.emit(_item("x"), org_id="o")
    assert received == ["x"]


@pytest.mark.unit
def test_replacing_subscriber() -> None:
    bus = InProcessBus()
    seen: list[str] = []
    bus.subscribe("only", lambda i: seen.append("first:" + i.item_id))
    bus.subscribe("only", lambda i: seen.append("second:" + i.item_id))
    bus.emit(_item("y"), org_id="o")
    assert seen == ["second:y"]


@pytest.mark.unit
def test_clear_removes_all() -> None:
    bus = InProcessBus()
    seen: list[str] = []
    bus.subscribe("a", lambda i: seen.append(i.item_id))
    bus.clear()
    bus.emit(_item("x"), org_id="o")
    assert seen == []
