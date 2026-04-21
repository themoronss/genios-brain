"""Brain activity — a dashboard view of what the brain is doing right now.

Currently the dashboard has NO visibility into detector fires, recommendation
push rate, feedback arrivals. Founder on a demo can't see the brain thinking.

This endpoint surfaces:
 - Detector fire counters (last 24h, per insight_type) from Redis
 - Recommendation push rate (hourly buckets) from `recommendations`
 - Feedback arrival counts (acted / dismissed / ignored) from outcomes
 - Rolling 7-day AAR trend (daily points)

All queries are cheap (indexed) and org-scoped. Intended to be polled every
5-10s from the dashboard `brain/` page.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _detector_counter_key(org_id: str, insight_type: str, bucket_hour: str) -> str:
    return f"brain:detector_fires:{org_id}:{insight_type}:{bucket_hour}"


@router.get("/v1/admin/brain/activity")
def brain_activity(
    hours: int = 24,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Live snapshot of brain activity for the dashboard."""
    hours = max(1, min(168, int(hours)))  # cap 7 days
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # ── Recommendations pushed, by hour ──────────────────────────────────────
    pushed_rows = db.execute(
        text("""
            SELECT
                DATE_TRUNC('hour', created_at) AS hour,
                COUNT(*) AS n,
                COUNT(*) FILTER (WHERE outcome = 'acted')     AS acted,
                COUNT(*) FILTER (WHERE outcome = 'dismissed') AS dismissed,
                COUNT(*) FILTER (WHERE outcome = 'ignored')   AS ignored
            FROM recommendations
            WHERE org_id = :oid AND created_at >= :since
            GROUP BY DATE_TRUNC('hour', created_at)
            ORDER BY hour ASC
        """),
        {"oid": org_id, "since": since},
    ).fetchall()

    by_hour = [
        {
            "hour": r.hour.isoformat() if r.hour else None,
            "pushed": int(r.n or 0),
            "acted": int(r.acted or 0),
            "dismissed": int(r.dismissed or 0),
            "ignored": int(r.ignored or 0),
        }
        for r in pushed_rows
    ]

    # ── Aggregates (window totals) ──────────────────────────────────────────
    totals = db.execute(
        text("""
            SELECT
                COUNT(*)                                       AS total_pushed,
                COUNT(*) FILTER (WHERE outcome = 'acted')     AS total_acted,
                COUNT(*) FILTER (WHERE outcome = 'dismissed') AS total_dismissed,
                COUNT(*) FILTER (WHERE outcome = 'ignored')   AS total_ignored,
                COUNT(*) FILTER (WHERE outcome IS NULL)       AS total_pending,
                COUNT(DISTINCT insight_type)                  AS distinct_detectors,
                COUNT(DISTINCT subject_entity_id)             AS distinct_contacts
            FROM recommendations
            WHERE org_id = :oid AND created_at >= :since
        """),
        {"oid": org_id, "since": since},
    ).fetchone()

    # Rolling 7-day AAR trend (daily points over window, regardless of `hours`)
    aar_trend_rows = db.execute(
        text("""
            SELECT
                DATE_TRUNC('day', created_at) AS day,
                COUNT(*) FILTER (WHERE outcome = 'acted')                                 AS acted,
                COUNT(*) FILTER (WHERE outcome IN ('acted', 'dismissed', 'ignored'))       AS labelled
            FROM recommendations
            WHERE org_id = :oid AND created_at >= NOW() - INTERVAL '7 days'
            GROUP BY DATE_TRUNC('day', created_at)
            ORDER BY day ASC
        """),
        {"oid": org_id},
    ).fetchall()
    aar_trend = [
        {
            "day": r.day.date().isoformat() if r.day else None,
            "aar": round(float(r.acted) / float(r.labelled), 4) if r.labelled else 0.0,
            "n": int(r.labelled or 0),
        }
        for r in aar_trend_rows
    ]

    # Top insight types by volume in window
    top_detectors = db.execute(
        text("""
            SELECT insight_type, COUNT(*) AS n,
                   COUNT(*) FILTER (WHERE outcome = 'acted') AS acted,
                   COUNT(*) FILTER (WHERE outcome IS NULL)   AS pending
            FROM recommendations
            WHERE org_id = :oid AND created_at >= :since
            GROUP BY insight_type
            ORDER BY n DESC
            LIMIT 10
        """),
        {"oid": org_id, "since": since},
    ).fetchall()
    detectors = [
        {
            "insight_type": r.insight_type,
            "fires": int(r.n or 0),
            "acted": int(r.acted or 0),
            "pending": int(r.pending or 0),
        }
        for r in top_detectors
    ]

    # Live signals
    live_signals = {}
    try:
        # Incremented by brain/router.py when it consumes events
        last_tick = redis_client.get(f"brain:router:last_tick:{org_id}")
        last_tick_count = redis_client.get(f"brain:router:last_consumed:{org_id}")
        live_signals = {
            "last_router_tick_at": last_tick,
            "last_tick_consumed": int(last_tick_count) if last_tick_count else 0,
        }
    except Exception:
        pass

    return {
        "org_id": org_id,
        "window_hours": hours,
        "totals": {
            "pushed": int(totals.total_pushed or 0),
            "acted": int(totals.total_acted or 0),
            "dismissed": int(totals.total_dismissed or 0),
            "ignored": int(totals.total_ignored or 0),
            "pending": int(totals.total_pending or 0),
            "distinct_detectors": int(totals.distinct_detectors or 0),
            "distinct_contacts": int(totals.distinct_contacts or 0),
        },
        "by_hour": by_hour,
        "aar_trend_7d": aar_trend,
        "top_detectors": detectors,
        "live": live_signals,
    }
