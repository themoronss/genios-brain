"""Layer 5.2 · Phase 4 — the Delivery Tracker (section 5.2).

Separates raw transport state from the public engagement lifecycle and moves a delivery through it
legally: ``queued → deferred → delivered → viewed → ignored`` and ``delivered → accepted →
executed | failed``. Every move appends a ``delivery_events`` row in the same transaction as the
state change. Client idempotency keys make a repeated tap/retry a no-op; chronology validation
rejects a receipt dated before the delivery existed or more than five minutes in the future.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text

from genios_engine.contracts.delivery import DeliveryLifecycle, delivery_can_transition
from genios_engine.deliver.spine import log_delivery_event

#: A receipt more than this far in the future is a clock error or a spoof, not a real engagement.
FUTURE_SKEW = timedelta(minutes=5)

#: Lifecycle states that stamp a dedicated engagement clock on the row (for analytics + Layer 6).
_STATE_CLOCK: dict[str, str] = {
    DeliveryLifecycle.DELIVERED.value: "delivered_at",
    DeliveryLifecycle.VIEWED.value: "viewed_at",
    DeliveryLifecycle.IGNORED.value: "ignored_at",
    DeliveryLifecycle.ACCEPTED.value: "accepted_at",
    DeliveryLifecycle.EXECUTED.value: "executed_at",
}


class ChronologyError(ValueError):
    """A receipt whose timestamp cannot be true relative to the delivery's own clock."""


class IllegalTransition(ValueError):
    """A lifecycle move that the state machine forbids from the current state."""


def validate_chronology(*, receipt_at: datetime, created_at: datetime, now: datetime) -> None:
    """A receipt must not predate the delivery, nor sit more than five minutes in the future."""
    if receipt_at < created_at:
        raise ChronologyError("receipt predates the delivery's creation")
    if receipt_at > now + FUTURE_SKEW:
        raise ChronologyError("receipt is implausibly far in the future")


def record_transition(conn, *, org_id: str, delivery_id: str, target: DeliveryLifecycle,
                      at: datetime, now: datetime, actor: str | None = None,
                      idempotency_key: str | None = None, detail: dict | None = None) -> bool:
    """Move one delivery to ``target`` legally, atomically, idempotently.

    Returns True if this call performed the move, False if it was a no-op (an idempotent replay of
    a receipt already recorded, or the delivery already in ``target``). Raises ``IllegalTransition``
    for a forbidden move and ``ChronologyError`` for an impossible receipt time.
    """
    row = conn.execute(text(
        "select lifecycle, created_at from delivery_outbox "
        "where org_id = :o and delivery_id = :d for update"),
        {"o": org_id, "d": delivery_id}).mappings().first()
    if row is None:
        raise IllegalTransition(f"no delivery {delivery_id!r} to transition")

    validate_chronology(receipt_at=at, created_at=row["created_at"], now=now)

    current = DeliveryLifecycle(row["lifecycle"])
    if current is target:
        return False                                   # already there — idempotent no-op
    if not delivery_can_transition(current, target):
        raise IllegalTransition(f"{current.value} → {target.value} is not a legal move")

    # A keyed receipt that was already recorded makes the whole transition a no-op: the event
    # insert is guarded by the partial unique index, and we only advance state on a fresh event.
    if idempotency_key is not None:
        seen = conn.execute(text(
            "select 1 from delivery_events where org_id = :o and delivery_id = :d "
            "and idempotency_key = :k"), {"o": org_id, "d": delivery_id, "k": idempotency_key}
        ).first()
        if seen is not None:
            return False

    clock = _STATE_CLOCK.get(target.value)
    set_clock = f", {clock} = coalesce({clock}, :at)" if clock else ""
    conn.execute(text(
        f"update delivery_outbox set lifecycle = :t{set_clock} "
        "where org_id = :o and delivery_id = :d"),
        {"t": target.value, "at": at, "o": org_id, "d": delivery_id})
    log_delivery_event(conn, org_id=org_id, delivery_id=delivery_id, kind=target.value,
                       at=at, actor=actor, idempotency_key=idempotency_key, detail=detail)
    return True


__all__ = ["FUTURE_SKEW", "ChronologyError", "IllegalTransition", "record_transition",
           "validate_chronology"]
