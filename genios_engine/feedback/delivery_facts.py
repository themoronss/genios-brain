"""Layer 5.2 → Layer 6 handoff — the DeliveryFact seam (section 8).

Layer 6 Learning reads the *same durable outbox*, by tenant and bounded window, through this typed
seam — it never reaches into Layer 5.2's internals and never infers engagement. If a client has not
emitted an authenticated receipt, the field stays null; a view that happened before a later expiry
survives as evidence (the engagement clocks are stamped once and never cleared). This module is the
producer side; Layer 6's Selector consumes ``DeliveryFact`` and turns it into learning evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import text


@dataclass(frozen=True, slots=True)
class DeliveryFact:
    """One delivery as Layer 6 sees it — transport + real, receipt-backed engagement only."""

    delivery_id: str
    execution_id: str | None
    channel: str
    priority: str
    lifecycle: str
    delivered_at: datetime | None
    viewed_at: datetime | None
    ignored_at: datetime | None
    accepted_at: datetime | None
    executed_at: datetime | None
    attempts: int
    failed: bool

    @property
    def is_impression(self) -> bool:
        """A real impression = it actually reached a surface. The only honest denominator."""
        return self.delivered_at is not None

    @property
    def engaged(self) -> bool:
        """Did a human do something with it — a receipt exists, not an inference."""
        return any((self.viewed_at, self.accepted_at, self.executed_at))

    @property
    def pre_delivery_failure(self) -> bool:
        """Only a failure BEFORE first delivery is transport-negative (section 2 / Unit 9).

        A failure after delivery is the execution's/business's problem, not the transport's.
        """
        return self.failed and self.delivered_at is None


def load_delivery_facts(conn, *, org_id: str, since: datetime,
                        limit: int = 5000) -> list[DeliveryFact]:
    """The bounded-window read Layer 6 consumes. Includes rows created in-window or with in-window
    lifecycle activity; no engagement is fabricated for a row without a receipt clock."""
    rows = conn.execute(text(
        "select delivery_id, execution_id, channel, priority, lifecycle, attempts, status, "
        "       delivered_at, viewed_at, ignored_at, accepted_at, executed_at "
        "from delivery_outbox "
        "where org_id = :o and delivery_id is not null "
        "  and (created_at >= :s or delivered_at >= :s or viewed_at >= :s "
        "       or accepted_at >= :s or executed_at >= :s) "
        "order by created_at desc limit :l"),
        {"o": org_id, "s": since, "l": limit}).mappings().all()
    return [DeliveryFact(
        delivery_id=r["delivery_id"], execution_id=r["execution_id"], channel=r["channel"],
        priority=r["priority"] or "medium", lifecycle=r["lifecycle"] or "queued",
        delivered_at=r["delivered_at"], viewed_at=r["viewed_at"], ignored_at=r["ignored_at"],
        accepted_at=r["accepted_at"], executed_at=r["executed_at"],
        attempts=int(r["attempts"] or 0),
        failed=(r["status"] == "failed" or r["lifecycle"] == "failed")) for r in rows]


__all__ = ["DeliveryFact", "load_delivery_facts"]
