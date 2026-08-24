"""Multi-subscriber MemoryItem emission.

In-process pub/sub for v1 — abstract behind interface so a RabbitMQ / Redis Streams
swap is trivial later. Subscribers (per g-i-1 emission contract):
- g-i-3: persists Facts/entities into the graph
- g-i-4: triggers proactive analysis via diff detection
- observability: increments per-source counters

Failure isolation: one subscriber's exception does NOT break delivery to others.
Each subscriber is called in try/except; failures are logged + audited; processing
continues. This matches the MD requirement: "a single source failing must not take
down others" extended to subscribers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.memory.types import MemoryItem

log = get_logger(__name__)

Subscriber = Callable[[MemoryItem], None]


class EmissionBus(Protocol):
    """Interface so the implementation can be swapped without caller changes."""

    def subscribe(self, name: str, handler: Subscriber) -> None: ...
    def emit(self, item: MemoryItem, *, org_id: str) -> None: ...
    def clear(self) -> None: ...  # tests + shutdown


class InProcessBus:
    """In-process pub/sub. Synchronous fan-out with per-subscriber isolation."""

    def __init__(self) -> None:
        self._subs: dict[str, Subscriber] = {}

    def subscribe(self, name: str, handler: Subscriber) -> None:
        """Register a named subscriber. Re-registering replaces the prior handler."""
        if name in self._subs:
            log.warning("subscriber_replaced", name=name)
        self._subs[name] = handler

    def emit(self, item: MemoryItem, *, org_id: str) -> None:
        """Fan out to all subscribers. One failing subscriber does NOT block others.

        Per g-i-1 emission contract: subscribers include g-i-3 persist, g-i-4 trigger,
        observability counters. All called; all failures captured independently.
        """
        for name, handler in list(self._subs.items()):
            try:
                handler(item)
            except Exception as e:
                log.error(
                    "subscriber_failed",
                    subscriber=name,
                    item_id=item.item_id,
                    source_type=item.source_type,
                    error=str(e),
                )
                audit.record(
                    org_id=org_id,
                    actor_type="system",
                    actor_id="emit",
                    action="data_accessed",
                    target_type="memory_item",
                    target_id=item.item_id,
                    metadata={
                        "subscriber": name,
                        "outcome": "subscriber_error",
                        "source_type": item.source_type,
                    },
                )

    def clear(self) -> None:
        """Remove all subscribers (used by tests + shutdown)."""
        self._subs.clear()


# Module-level singleton (swap implementation by reassigning if ever needed)
_bus: EmissionBus = InProcessBus()


def get_bus() -> EmissionBus:
    """Return the active bus. Modules import this rather than the implementation."""
    return _bus


def emit(item: MemoryItem, *, org_id: str) -> None:
    """Convenience wrapper for the default bus."""
    _bus.emit(item, org_id=org_id)


def subscribe(name: str, handler: Subscriber) -> None:
    """Convenience wrapper for the default bus."""
    _bus.subscribe(name, handler)
