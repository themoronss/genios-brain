"""Layer 5.2 · Phase 5 — the Rate Limiter (section 5.6).

PostgreSQL conditionally reserves the final attention slot, so two workers cannot both spend it.
The reservation is a single atomic statement: increment ``used`` only while it is below ``budget``.
A definite non-delivery releases the slot; an ambiguous outcome retains it, because the person may
already have been interrupted. Slack/Teams share one tenant-wide rolling hour; the local-day budget
stays per recipient (so mixed timezones are respected). ``budget = None`` means unbounded.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

#: Channel families that share one tenant-wide rolling-hour attention stream, keyed by this sentinel
#: rather than by an individual seat — a customer feels "how loud is Slack right now?" tenant-wide.
_SHARED_HOUR_FAMILIES = {"slack": "chat_stream", "teams": "chat_stream"}


def hour_recipient_key(channel: str, recipient: str | None) -> str:
    """The rolling-hour bucket key: a shared stream for chat families, else the seat."""
    return _SHARED_HOUR_FAMILIES.get(channel, recipient or "org_wide")


def reserve_slot(conn, *, org_id: str, recipient: str, window_kind: str, window_start: datetime,
                 budget: int | None, at: datetime) -> bool:
    """Atomically reserve one attention slot. True if reserved, False if the window is full.

    Unbounded budgets always reserve. A bounded window increments ``used`` only while it is strictly
    below ``budget``; the ``where`` on the conflict update is what makes two concurrent workers
    unable to both take the last slot — the loser's update matches no row and returns nothing.
    """
    if budget is None:
        # Still record the impression for analytics/fatigue, but never refuse.
        conn.execute(text(
            "insert into delivery_rate_windows (org_id, recipient, window_kind, window_start, used, budget) "
            "values (:o, :r, :k, :w, 1, null) "
            "on conflict (org_id, recipient, window_kind, window_start) "
            "do update set used = delivery_rate_windows.used + 1, updated_at = :at"),
            {"o": org_id, "r": recipient, "k": window_kind, "w": window_start, "at": at})
        return True

    reserved = conn.execute(text(
        "insert into delivery_rate_windows (org_id, recipient, window_kind, window_start, used, budget) "
        "values (:o, :r, :k, :w, 1, :b) "
        "on conflict (org_id, recipient, window_kind, window_start) "
        "do update set used = delivery_rate_windows.used + 1, updated_at = :at "
        "  where delivery_rate_windows.used < delivery_rate_windows.budget "
        "returning used"),
        {"o": org_id, "r": recipient, "k": window_kind, "w": window_start, "b": budget, "at": at}
    ).first()
    return reserved is not None


def release_slot(conn, *, org_id: str, recipient: str, window_kind: str,
                 window_start: datetime, at: datetime) -> None:
    """Give a reserved slot back — only on a DEFINITE non-delivery. Never below zero."""
    conn.execute(text(
        "update delivery_rate_windows set used = greatest(0, used - 1), updated_at = :at "
        "where org_id = :o and recipient = :r and window_kind = :k and window_start = :w"),
        {"o": org_id, "r": recipient, "k": window_kind, "w": window_start, "at": at})


__all__ = ["hour_recipient_key", "release_slot", "reserve_slot"]
