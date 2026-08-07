"""Durable Layer 5.2 transport/engagement lifecycle.

The outbox transport state and the public engagement state are deliberately separate. Provider
retries cannot turn a human's `accepted` action back into `queued`, and a human ignore is not
misreported as a transport failure. Every move appends an idempotent event in the same transaction.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping

from sqlalchemy import text

from genios_engine.platform.ids import new_id


class DeliveryState(str, Enum):
    QUEUED = "queued"
    DEFERRED = "deferred"
    DELIVERED = "delivered"
    VIEWED = "viewed"
    IGNORED = "ignored"
    ACCEPTED = "accepted"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"
    SUPPRESSED = "suppressed"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: Mapping[DeliveryState, frozenset[DeliveryState]] = {
    DeliveryState.QUEUED: frozenset({
        DeliveryState.DEFERRED, DeliveryState.DELIVERED, DeliveryState.FAILED,
        DeliveryState.EXPIRED, DeliveryState.SUPPRESSED, DeliveryState.CANCELLED}),
    DeliveryState.DEFERRED: frozenset({
        DeliveryState.QUEUED, DeliveryState.DELIVERED, DeliveryState.FAILED,
        DeliveryState.EXPIRED, DeliveryState.SUPPRESSED, DeliveryState.CANCELLED}),
    DeliveryState.DELIVERED: frozenset({
        DeliveryState.VIEWED, DeliveryState.IGNORED, DeliveryState.ACCEPTED,
        DeliveryState.EXECUTED, DeliveryState.EXPIRED}),
    DeliveryState.VIEWED: frozenset({
        DeliveryState.IGNORED, DeliveryState.ACCEPTED, DeliveryState.EXECUTED,
        DeliveryState.EXPIRED}),
    DeliveryState.ACCEPTED: frozenset({
        DeliveryState.EXECUTED, DeliveryState.FAILED, DeliveryState.EXPIRED}),
    DeliveryState.IGNORED: frozenset(),
    DeliveryState.EXECUTED: frozenset(),
    DeliveryState.FAILED: frozenset({DeliveryState.QUEUED}),  # explicit owner replay only
    DeliveryState.EXPIRED: frozenset(),
    DeliveryState.SUPPRESSED: frozenset(),
    DeliveryState.CANCELLED: frozenset(),
}

_TIMESTAMP_COLUMN = {
    DeliveryState.VIEWED: "viewed_at",
    DeliveryState.IGNORED: "ignored_at",
    DeliveryState.ACCEPTED: "accepted_at",
    DeliveryState.EXECUTED: "executed_at",
    DeliveryState.EXPIRED: "expired_at",
}


class DeliveryTransitionError(ValueError):
    pass


def can_transition(current: DeliveryState | str, target: DeliveryState | str) -> bool:
    source = current if isinstance(current, DeliveryState) else DeliveryState(current)
    destination = target if isinstance(target, DeliveryState) else DeliveryState(target)
    return destination in ALLOWED_TRANSITIONS[source]


def append_event(conn, *, org_id: str, delivery_id: str,
                 target: DeliveryState | str, reason_code: str, actor_id: str,
                 idempotency_key: str, occurred_at: datetime | None = None,
                 metadata: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Move one delivery under a row lock and append its evidence exactly once."""
    state = target if isinstance(target, DeliveryState) else DeliveryState(target)
    at = occurred_at or datetime.now(timezone.utc)
    if at.tzinfo is None:
        raise DeliveryTransitionError("occurred_at must be timezone-aware")
    if not idempotency_key.strip():
        raise DeliveryTransitionError("idempotency_key is required")
    row = conn.execute(text(
        "select lifecycle_status,created_at,delivered_at,viewed_at,ignored_at,accepted_at,"
        "executed_at,expired_at from delivery_outbox where org_id=:o and id=:d for update"),
        {"o": org_id, "d": delivery_id}).mappings().first()
    if row is None:
        raise DeliveryTransitionError("delivery not found")
    current = DeliveryState(str(row["lifecycle_status"]))
    existing = conn.execute(text(
        "select event_id,event_type from delivery_events where org_id=:o and delivery_id=:d "
        "and idempotency_key=:k"),
        {"o": org_id, "d": delivery_id, "k": idempotency_key}).mappings().first()
    if existing is not None:
        # Check the receipt identity before applying today's lifecycle/clock constraints. A retry
        # of a historical `viewed` receipt must remain a no-op after the row advances to accepted.
        return {"changed": False, "duplicate": True, "state": current.value,
                "event_id": str(existing["event_id"]),
                "event_type": str(existing["event_type"])}
    if actor_id != "delivery" and at > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise DeliveryTransitionError("occurred_at is too far in the future")
    floors = [row.get("created_at")]
    if state in {DeliveryState.DELIVERED, DeliveryState.VIEWED, DeliveryState.IGNORED,
                 DeliveryState.ACCEPTED, DeliveryState.EXECUTED}:
        floors.append(row.get("delivered_at"))
    if current is DeliveryState.DELIVERED:
        floors.append(row.get("delivered_at"))
    current_timestamp = _TIMESTAMP_COLUMN.get(current)
    if current_timestamp:
        floors.append(row.get(current_timestamp))
    if any(isinstance(floor, datetime) and at < floor for floor in floors):
        raise DeliveryTransitionError("occurred_at precedes the delivery lifecycle")
    if current is state:
        # Repeated deferrals and repeated observations are evidence, not illegal transitions. The
        # caller-supplied idempotency key still ensures a retried receipt is recorded only once.
        event_id = new_id("dev")
        inserted = conn.execute(text(
            "insert into delivery_events (event_id,org_id,delivery_id,event_type,reason_code,"
            "actor_id,idempotency_key,metadata,occurred_at) values "
            "(:e,:o,:d,:t,:r,:a,:k,cast(:m as jsonb),:at) "
            "on conflict (org_id,delivery_id,idempotency_key) do nothing returning event_id"),
            {"e": event_id, "o": org_id, "d": delivery_id, "t": state.value,
             "r": reason_code, "a": actor_id, "k": idempotency_key,
             "m": json.dumps(dict(metadata or {}), default=str), "at": at}).first()
        return {"changed": False, "duplicate": inserted is None, "state": state.value,
                "event_id": event_id if inserted is not None else None}
    if not can_transition(current, state):
        raise DeliveryTransitionError(
            f"illegal delivery transition {current.value} -> {state.value}")

    event_id = new_id("dev")
    inserted = conn.execute(text(
        "insert into delivery_events (event_id,org_id,delivery_id,event_type,reason_code,"
        "actor_id,idempotency_key,metadata,occurred_at) values "
        "(:e,:o,:d,:t,:r,:a,:k,cast(:m as jsonb),:at) "
        "on conflict (org_id,delivery_id,idempotency_key) do nothing returning event_id"),
        {"e": event_id, "o": org_id, "d": delivery_id, "t": state.value,
         "r": reason_code, "a": actor_id, "k": idempotency_key,
         "m": json.dumps(dict(metadata or {}), default=str), "at": at}).first()
    if inserted is None:
        return {"changed": False, "duplicate": True, "state": current.value}

    sets = ["lifecycle_status=:state", "updated_at=:at"]
    timestamp = _TIMESTAMP_COLUMN.get(state)
    if timestamp:
        sets.append(f"{timestamp}=coalesce({timestamp},:at)")
    conn.execute(text(
        f"update delivery_outbox set {', '.join(sets)} where org_id=:o and id=:d"),
        {"state": state.value, "at": at, "o": org_id, "d": delivery_id})
    return {"changed": True, "duplicate": False, "from": current.value,
            "state": state.value, "event_id": event_id}


def expire_due(conn, *, now: datetime | None = None, limit: int = 500) -> int:
    """Expire undelivered/unfinished execution deliveries after their authority window."""
    at = now or datetime.now(timezone.utc)
    rows = conn.execute(text(
        "select id,org_id from delivery_outbox where authority_expires_at is not null "
        "and authority_expires_at<=:now and lifecycle_status in "
        "('queued','deferred','delivered','viewed','accepted') "
        "order by authority_expires_at,id limit :l for update skip locked"),
        {"now": at, "l": max(1, min(int(limit), 2_000))}).fetchall()
    changed = 0
    for row in rows:
        delivery_id = row.id if hasattr(row, "id") else row[0]
        org_id = row.org_id if hasattr(row, "org_id") else row[1]
        result = append_event(
            conn, org_id=str(org_id), delivery_id=delivery_id,
            target=DeliveryState.EXPIRED, reason_code="authority_window_elapsed",
            actor_id="delivery", idempotency_key="system:expiry", occurred_at=at)
        if result["changed"]:
            # Stop future claims in the same transaction. A provider call already outside the
            # database may still acknowledge late; its physical attempt remains auditable while
            # the public lifecycle correctly stays terminal `expired`.
            conn.execute(text(
                "update delivery_outbox set status=case when status in ('queued','in_flight') "
                "then 'cancelled' else status end,claim_token=null,claimed_at=null,"
                "claimed_until=null,updated_at=:at where org_id=:o and id=:d"),
                {"at": at, "o": str(org_id), "d": delivery_id})
        changed += int(result["changed"])
    return changed


__all__ = ["ALLOWED_TRANSITIONS", "DeliveryState", "DeliveryTransitionError",
           "append_event", "can_transition", "expire_due"]
