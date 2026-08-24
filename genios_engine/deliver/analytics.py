"""Layer 5.2 · Phase 5 — Delivery Analytics (section 5.7).

Counted cohorts over real impressions only — a delivery that never reached a person is not a
denominator. Read-only; every number is arithmetic over ``delivery_outbox`` / ``delivery_events``,
never an estimate. Earlier engagement clocks survive a later expiry (a viewed-then-expired delivery
still counts as viewed), because ``delivered_at``/``viewed_at`` are stamped once and never cleared.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text


def delivery_analytics(conn, *, org_id: str, since: datetime) -> dict:
    """Status/channel cohorts + engagement rates for one tenant since ``since``.

    Rates use real impressions (``delivered_at is not null``) as the denominator, so an un-delivered
    queued row can never dilute a view rate.
    """
    by_status = {r["lifecycle"]: r["n"] for r in conn.execute(text(
        "select lifecycle, count(*) as n from delivery_outbox "
        "where org_id = :o and created_at >= :s group by lifecycle"),
        {"o": org_id, "s": since}).mappings()}

    by_channel = {r["channel"]: r["n"] for r in conn.execute(text(
        "select channel, count(*) as n from delivery_outbox "
        "where org_id = :o and created_at >= :s group by channel"),
        {"o": org_id, "s": since}).mappings()}

    counts = conn.execute(text(
        "select "
        " count(*) filter (where delivered_at is not null) as delivered, "
        " count(*) filter (where viewed_at is not null) as viewed, "
        " count(*) filter (where accepted_at is not null) as accepted, "
        " count(*) filter (where executed_at is not null) as executed, "
        " count(*) filter (where ignored_at is not null) as ignored, "
        " count(*) filter (where status = 'failed' or lifecycle = 'failed') as failed "
        "from delivery_outbox where org_id = :o and created_at >= :s"),
        {"o": org_id, "s": since}).mappings().first()

    delivered = counts["delivered"] or 0

    def rate(n: int) -> float:
        return round((n or 0) / delivered, 4) if delivered else 0.0

    return {
        "by_status": by_status,
        "by_channel": by_channel,
        "impressions": delivered,
        "transport": {"delivered": delivered, "failed": counts["failed"] or 0},
        "engagement": {
            "viewed": counts["viewed"] or 0, "accepted": counts["accepted"] or 0,
            "executed": counts["executed"] or 0, "ignored": counts["ignored"] or 0},
        "rates": {
            "view": rate(counts["viewed"]), "accept": rate(counts["accepted"]),
            "execute": rate(counts["executed"]), "ignore": rate(counts["ignored"])},
    }


def recipient_fatigue(conn, *, org_id: str, since: datetime) -> list[dict]:
    """Intrusive impressions per recipient — the input to fatigue-aware suppression later."""
    return [dict(r) for r in conn.execute(text(
        "select recipient, count(*) as intrusive_impressions from delivery_outbox "
        "where org_id = :o and delivered_at >= :s and channel_class = 'chat' "
        "  and recipient is not null "
        "group by recipient order by intrusive_impressions desc"),
        {"o": org_id, "s": since}).mappings()]


__all__ = ["delivery_analytics", "recipient_fatigue"]
