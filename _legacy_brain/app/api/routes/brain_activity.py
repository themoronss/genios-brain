"""Brain activity — v2 view derived from decisions + corrections + facts.

Per g-i-1 plan: no more reads from v1 `recommendations` / `insights` tables.
Surface what the v2 engine is actually doing right now: decisions emitted,
which rules fired, feedback (corrections), proactive insights, and the
intervention_rate (g-i-8 North Star).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/v1/admin/brain/activity")
def brain_activity(
    request: Request,
    response: Response,
    hours: int = 24,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
) -> dict[str, Any]:
    """v2-native live snapshot of brain activity for the dashboard.

    Counts come from `decisions` (emit + route + path), `corrections`
    (👎/edit), `proactive_insights` (g-i-4 generated), and rolling
    `intervention_metrics` for the 7-day trend.
    """
    hours = max(1, min(168, int(hours)))
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    # ── Decisions emitted (the "push" stream in v2) ─────────────────────────
    by_hour_rows = db.execute(
        text(
            """
            SELECT
                DATE_TRUNC('hour', created_at) AS hour,
                COUNT(*) AS n,
                COUNT(*) FILTER (WHERE route = 'autonomous') AS acted,
                COUNT(*) FILTER (WHERE route = 'flag')       AS dismissed,
                COUNT(*) FILTER (WHERE route = 'notify')     AS ignored
            FROM decisions
            WHERE org_id = :oid AND created_at >= :since
            GROUP BY DATE_TRUNC('hour', created_at)
            ORDER BY hour ASC
            """
        ),
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
        for r in by_hour_rows
    ]

    # ── Window totals ───────────────────────────────────────────────────────
    totals_row = db.execute(
        text(
            """
            SELECT
                COUNT(*)                                       AS total_pushed,
                COUNT(*) FILTER (WHERE route = 'autonomous')  AS total_acted,
                COUNT(*) FILTER (WHERE route = 'flag')        AS total_dismissed,
                COUNT(*) FILTER (WHERE route = 'notify')      AS total_ignored,
                COUNT(*) FILTER (WHERE confidence_score < 0.6) AS total_low_conf,
                COUNT(DISTINCT module_id)                      AS distinct_modules,
                COUNT(DISTINCT user_id)                        AS distinct_users
            FROM decisions
            WHERE org_id = :oid AND created_at >= :since
            """
        ),
        {"oid": org_id, "since": since},
    ).fetchone()

    n_corrections = db.execute(
        text(
            "SELECT COUNT(*) FROM corrections WHERE org_id = :oid AND timestamp >= :since"
        ),
        {"oid": org_id, "since": since},
    ).scalar() or 0

    totals = {
        "pushed": int(totals_row.total_pushed or 0),
        "acted": int(totals_row.total_acted or 0),
        "dismissed": int(totals_row.total_dismissed or 0),
        "ignored": int(totals_row.total_ignored or 0),
        "pending": int(totals_row.total_low_conf or 0),
        "corrections": int(n_corrections),
        "distinct_detectors": int(totals_row.distinct_modules or 0),
        "distinct_contacts": int(totals_row.distinct_users or 0),
    }

    # ── 7-day intervention-rate trend (replaces v1 AAR) ─────────────────────
    aar_trend_rows = db.execute(
        text(
            """
            SELECT date, intervention_rate, total_decisions
            FROM intervention_metrics
            WHERE org_id = :oid AND date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY date ASC
            """
        ),
        {"oid": org_id},
    ).fetchall()
    aar_trend = [
        {
            "day": r.date.isoformat() if hasattr(r.date, "isoformat") else str(r.date),
            "aar": 1.0 - float(r.intervention_rate or 0),  # AAR inverse of intervention
            "n": int(r.total_decisions or 0),
        }
        for r in aar_trend_rows
    ]

    # ── Top "detectors" = which rules fire most ─────────────────────────────
    detectors_rows = db.execute(
        text(
            """
            SELECT module_id AS insight_type,
                   COUNT(*) AS fires,
                   COUNT(*) FILTER (WHERE route = 'autonomous') AS acted,
                   COUNT(*) FILTER (WHERE confidence_score < 0.6) AS pending
            FROM decisions
            WHERE org_id = :oid AND created_at >= :since AND module_id IS NOT NULL
            GROUP BY module_id
            ORDER BY fires DESC
            LIMIT 10
            """
        ),
        {"oid": org_id, "since": since},
    ).fetchall()
    detectors = [
        {
            "insight_type": r.insight_type or "?",
            "fires": int(r.fires or 0),
            "acted": int(r.acted or 0),
            "pending": int(r.pending or 0),
        }
        for r in detectors_rows
    ]

    return {
        "org_id": org_id,
        "window_hours": hours,
        "totals": totals,
        "by_hour": by_hour,
        "aar_trend_7d": aar_trend,
        "top_detectors": detectors,
        "live": {"router_last_tick": None, "consumed_in_window": totals["pushed"]},
    }


@router.get("/api/org/{org_id}/brain/activity")
def org_brain_activity(
    org_id: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Per-org brain activity for graph header — v2 view, no API key required."""
    fifteen = datetime.now(timezone.utc) - timedelta(minutes=15)
    reactive = db.execute(
        select(func.count())
        .select_from(text("decisions"))
        .where(text("org_id = :oid AND created_at > :ago"))
        .params(oid=org_id, ago=fifteen)
    ).scalar() or 0

    proactive = db.execute(
        text(
            "SELECT COUNT(*) FROM proactive_insights "
            "WHERE org_id = :oid AND created_at > CURRENT_DATE"
        ),
        {"oid": org_id},
    ).scalar() or 0

    total_nodes = db.execute(
        text("SELECT COUNT(*) FROM graph_nodes WHERE org_id = :oid"),
        {"oid": org_id},
    ).scalar() or 0

    total_facts = db.execute(
        text("SELECT COUNT(*) FROM facts WHERE org_id = :oid"),
        {"oid": org_id},
    ).scalar() or 0

    last_sync = db.execute(
        text(
            "SELECT MAX(last_sync_at) FROM cursors "
            "WHERE connection_id IN (SELECT id FROM connections WHERE org_id = :oid)"
        ),
        {"oid": org_id},
    ).scalar()

    return {
        "reactive_signal_count": int(reactive),
        "proactive_insight_count": int(proactive),
        "predictive_alert_count": 0,
        "graph_status": "live" if last_sync else "syncing",
        "total_contacts": int(total_nodes),
        "total_interactions": int(total_facts),
    }
