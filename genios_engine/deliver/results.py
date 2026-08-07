"""Typed projections of the durable outbox — Layer 5.2's public output.

The outbox remains the single source of truth.  This module does not create a second delivery
ledger; it translates implementation states into the stable ``DeliveryObject`` and
``DeliveryResult`` contracts that APIs, analytics and Layer 6 may consume.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.delivery import (
    DeliveryObject,
    DeliveryResult,
    DeliveryResultStatus,
)
from genios_engine.contracts.execution import ChannelClass
from genios_engine.deliver.outbox import BACKOFF_MINUTES


_STATUS = {
    "queued": DeliveryResultStatus.QUEUED,
    "delivered": DeliveryResultStatus.DELIVERED,
    "suppressed": DeliveryResultStatus.SUPPRESSED,
    "cancelled": DeliveryResultStatus.CANCELLED,
    "failed_terminal": DeliveryResultStatus.FAILED,
}


def _mapping(row: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    raw = getattr(row, "_mapping", None)
    return dict(raw) if raw is not None else dict(vars(row))


def _payload(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def delivery_object_from_row(row: Mapping[str, Any] | Any) -> DeliveryObject:
    """Project one outbox row into the immutable Atlas delivery object."""
    item = _mapping(row)
    raw_class = str(item.get("channel_class") or ChannelClass.IN_APP.value)
    try:
        channel_class = ChannelClass(raw_class)
    except ValueError:
        channel_class = ChannelClass.IN_APP
    return DeliveryObject(
        delivery_id=str(item["id"]),
        org_id=str(item["org_id"]),
        subject_id=str(item["card_id"]),
        recipient=str(item["recipient"]) if item.get("recipient") else None,
        channel=str(item["channel"]),
        channel_class=channel_class,
        band=str(item.get("band") or "standard"),
        interrupt=bool(item.get("interrupt")),
        payload=_payload(item.get("payload")),
        retry_minutes=BACKOFF_MINUTES,
        created_at=item.get("created_at"),
    )


def delivery_result_from_row(row: Mapping[str, Any] | Any) -> DeliveryResult:
    """Project one outbox row into the stable Layer 5.2 result vocabulary."""
    item = _mapping(row)
    raw_status = str(item.get("status") or "queued")
    deferrals = max(0, int(item.get("defer_count") or 0))
    status = (_STATUS.get(raw_status, DeliveryResultStatus.FAILED)
              if not (raw_status == "queued" and deferrals)
              else DeliveryResultStatus.DEFERRED)
    created = item.get("created_at")
    delivered = item.get("delivered_at")
    latency_ms = None
    if isinstance(created, datetime) and isinstance(delivered, datetime):
        latency_ms = max(0, int((delivered - created).total_seconds() * 1000))
    metrics = {
        "transport_attempts": max(0, int(item.get("attempts") or 0)),
        "deferrals": deferrals,
    }
    if latency_ms is not None:
        metrics["delivery_latency_ms"] = latency_ms
    reason = item.get("gate_reason")
    if not reason and raw_status in {"failed_terminal", "cancelled"}:
        reason = "transport_failed" if raw_status == "failed_terminal" else "authority_revoked"
    return DeliveryResult(
        delivery_id=str(item["id"]),
        org_id=str(item["org_id"]),
        subject_id=str(item["card_id"]),
        recipient=str(item["recipient"]) if item.get("recipient") else None,
        channel=str(item["channel"]),
        status=status,
        attempts=max(0, int(item.get("attempts") or 0)),
        deferrals=deferrals,
        delivered_at=delivered,
        reason_code=str(reason) if reason else None,
        metrics=metrics,
        metadata={"outbox_status": raw_status,
                  "gate_unit": item.get("gate_unit"),
                  "last_error": item.get("last_error")},
    )


_RESULT_COLUMNS = (
    "id, org_id, card_id, channel, payload, status, attempts, recipient, band, "
    "channel_class, interrupt, defer_count, gate_unit, gate_reason, last_error, "
    "created_at, delivered_at"
)


def load_results(conn, org_id: str, *, limit: int = 100,
                 channel: str | None = None) -> list[DeliveryResult]:
    """Read recent typed results for one tenant. Tenant scope is mandatory in the SQL."""
    params: dict[str, Any] = {"o": org_id, "l": max(1, min(int(limit), 500))}
    channel_sql = ""
    if channel:
        channel_sql = " and channel=:ch"
        params["ch"] = channel
    rows = conn.execute(text(
        f"select {_RESULT_COLUMNS} from delivery_outbox where org_id=:o{channel_sql} "
        "order by created_at desc limit :l"), params).mappings().all()
    return [delivery_result_from_row(row) for row in rows]


def load_delivery(conn, org_id: str, delivery_id: str) \
        -> tuple[DeliveryObject, DeliveryResult] | None:
    row = conn.execute(text(
        f"select {_RESULT_COLUMNS} from delivery_outbox where org_id=:o and id=:i"),
        {"o": org_id, "i": delivery_id}).mappings().first()
    if row is None:
        return None
    return delivery_object_from_row(row), delivery_result_from_row(row)


def load_inbox(conn, org_id: str, *, channel: str, recipient: str | None = None,
               limit: int = 100) -> list[tuple[DeliveryObject, DeliveryResult]]:
    """Read deliveries materialised on a pull surface such as app, API or extension."""
    params: dict[str, Any] = {
        "o": org_id, "ch": channel, "l": max(1, min(int(limit), 500))}
    recipient_sql = ""
    if recipient:
        recipient_sql = " and (recipient=:r or recipient is null)"
        params["r"] = recipient
    rows = conn.execute(text(
        f"select {_RESULT_COLUMNS} from delivery_outbox "
        "where org_id=:o and channel=:ch and status='delivered'"
        f"{recipient_sql} order by delivered_at desc limit :l"), params).mappings().all()
    return [(delivery_object_from_row(row), delivery_result_from_row(row)) for row in rows]


__all__ = ["delivery_object_from_row", "delivery_result_from_row", "load_delivery",
           "load_inbox", "load_results"]
