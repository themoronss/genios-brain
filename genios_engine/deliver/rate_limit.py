"""Atomic Postgres attention reservations for multi-worker Layer 5.2 drains."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text


def window_start(now: datetime, *, seconds: int = 3_600) -> datetime:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    utc = now.astimezone(timezone.utc)
    epoch = int(utc.timestamp())
    return datetime.fromtimestamp(epoch - epoch % seconds, tz=timezone.utc)


def _rolling_lock(conn, *, org_id: str, recipient: str | None,
                  channel_class: str, seconds: int) -> None:
    """Serialize one tenant/recipient rolling counter across database workers."""
    key = f"l52-rate:{org_id}:{recipient or '*'}:{channel_class}:{seconds}"
    conn.execute(text(
        "select pg_advisory_xact_lock(hashtextextended(cast(:key as text),0))"),
        {"key": key})


def reserve(conn, *, org_id: str, recipient: str | None, channel_class: str,
            limit: int, now: datetime | None = None, seconds: int = 3_600,
            start: datetime | None = None, rolling: bool = False) -> bool:
    """Atomically reserve one attention slot; false means the window is full.

    Fixed windows use one conditional UPSERT (the daily local-time budget). Rolling windows use
    a transaction-scoped advisory lock and sum every still-live reservation, including provider
    calls that have started but have not yet produced a delivered row. This closes the top-of-hour
    boundary where two fixed buckets could otherwise admit nearly twice the hourly allowance.
    """
    if limit <= 0:
        return False
    at = now or datetime.now(timezone.utc)
    if start is not None and start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    if rolling:
        _rolling_lock(conn, org_id=org_id, recipient=recipient,
                      channel_class=channel_class, seconds=seconds)
        cutoff = at.astimezone(timezone.utc) - timedelta(seconds=seconds)
        row = conn.execute(text(
            "select coalesce(sum(used),0) as used from delivery_rate_windows "
            "where org_id=:o and recipient=:r and channel_class=:c "
            "and window_seconds=:seconds and window_start>:cutoff and used>0"),
            {"o": org_id, "r": recipient or "*", "c": channel_class,
             "seconds": seconds, "cutoff": cutoff}).first()
        used = int((row.used if hasattr(row, "used") else row[0]) if row is not None else 0)
        if used >= int(limit):
            return False
        begins = at.astimezone(timezone.utc)
    else:
        begins = (start.astimezone(timezone.utc) if start is not None
                  else window_start(at, seconds=seconds))
    row = conn.execute(text(
        "insert into delivery_rate_windows "
        "(org_id,recipient,channel_class,window_start,window_seconds,used) "
        "values (:o,:r,:c,:w,:seconds,1) "
        "on conflict (org_id,recipient,channel_class,window_start) do update set "
        "used=delivery_rate_windows.used+1,updated_at=now() "
        "where delivery_rate_windows.used<:limit returning used"),
        {"o": org_id, "r": recipient or "*", "c": channel_class,
         "w": begins, "seconds": seconds, "limit": int(limit)}).first()
    return row is not None


def release(conn, *, org_id: str, recipient: str | None, channel_class: str,
            now: datetime | None = None, seconds: int = 3_600,
            start: datetime | None = None, rolling: bool = False) -> bool:
    """Return a reservation after a definite non-delivery.

    Unknown acknowledgements deliberately keep the slot: the provider may have produced the
    interruption. The conditional decrement makes duplicate cleanup harmless.
    """
    at = now or datetime.now(timezone.utc)
    if start is not None and start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    if rolling:
        if start is None:
            raise ValueError("rolling release requires the original reservation start")
        _rolling_lock(conn, org_id=org_id, recipient=recipient,
                      channel_class=channel_class, seconds=seconds)
    begins = start.astimezone(timezone.utc) if start is not None else window_start(at, seconds=seconds)
    row = conn.execute(text(
        "update delivery_rate_windows set used=used-1,updated_at=now() "
        "where org_id=:o and recipient=:r and channel_class=:c and window_start=:w "
        "and used>0 returning used"),
        {"o": org_id, "r": recipient or "*", "c": channel_class, "w": begins}).first()
    return row is not None


def next_window(now: datetime, *, seconds: int = 3_600) -> datetime:
    return window_start(now, seconds=seconds) + timedelta(seconds=seconds)


def next_available(conn, *, org_id: str, recipient: str | None, channel_class: str,
                   now: datetime | None = None, seconds: int = 3_600) -> datetime:
    """Earliest expiry among positive reservations in an exact rolling window."""
    at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = at - timedelta(seconds=seconds)
    row = conn.execute(text(
        "select min(window_start + (:seconds * interval '1 second')) as available_at "
        "from delivery_rate_windows where org_id=:o and recipient=:r and channel_class=:c "
        "and window_seconds=:seconds and window_start>:cutoff and used>0"),
        {"o": org_id, "r": recipient or "*", "c": channel_class,
         "seconds": seconds, "cutoff": cutoff}).first()
    value = (row.available_at if row is not None and hasattr(row, "available_at")
             else row[0] if row is not None else None)
    return max(value or (at + timedelta(seconds=seconds)), at + timedelta(seconds=1))


__all__ = ["next_available", "next_window", "release", "reserve", "window_start"]
