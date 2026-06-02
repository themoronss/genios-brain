"""Admin endpoints — GDPR delete + beta tenant AAR (Phase 6.4).

Auth: re-uses the normal API-key check; caller must be the org owner.
Any cross-tenant leak is impossible — `org_id` comes from the authenticated
principal, not the request body.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from scripts.gdpr_delete import run as gdpr_run

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Phase 4.11 — GDPR delete ───────────────────────────────────────────────

class DeleteRequest(BaseModel):
    entity_id: str       # contact_id
    dry_run: bool = True


@router.post("/v1/admin/delete", status_code=200)
def admin_delete(
    req: DeleteRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """GDPR deletion cascade. Dry-run by default."""
    if not req.entity_id or len(req.entity_id) < 10:
        raise HTTPException(status_code=400, detail="entity_id required (contact UUID)")
    try:
        result = gdpr_run(org_id, req.entity_id, dry_run=req.dry_run)
    except Exception as e:
        logger.exception("gdpr delete failed")
        raise HTTPException(status_code=500, detail=f"delete failed: {e}")
    return result


# ── Phase 6.4 — AAR (Autonomous Act-on Rate) per tenant ────────────────────

def _compute_aar(db: Session, org_id: str, days: int) -> dict:
    """AAR = acted / (acted + dismissed + ignored). `pending` excluded.

    Also returns `by_insight_type` — same metric grouped by `insight_type` so
    calibration can tune per-detector thresholds and operators can see which
    detector types are working vs. noisy.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Aggregate
    row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE outcome = 'acted')     AS acted,
                COUNT(*) FILTER (WHERE outcome = 'dismissed') AS dismissed,
                COUNT(*) FILTER (WHERE outcome = 'ignored')   AS ignored,
                COUNT(*) FILTER (WHERE outcome IS NULL)       AS pending,
                COUNT(*)                                       AS total
            FROM recommendations
            WHERE org_id = :oid AND created_at >= :since
        """),
        {"oid": org_id, "since": since},
    ).fetchone()
    acted = int(row.acted or 0)
    dismissed = int(row.dismissed or 0)
    ignored = int(row.ignored or 0)
    labelled = acted + dismissed + ignored
    aar = round(acted / labelled, 4) if labelled else 0.0

    # Per-insight_type breakdown
    detector_rows = db.execute(
        text("""
            SELECT
                COALESCE(insight_type, 'unknown') AS insight_type,
                COUNT(*) FILTER (WHERE outcome = 'acted')     AS acted,
                COUNT(*) FILTER (WHERE outcome = 'dismissed') AS dismissed,
                COUNT(*) FILTER (WHERE outcome = 'ignored')   AS ignored,
                COUNT(*) FILTER (WHERE outcome IS NULL)       AS pending,
                COUNT(*)                                       AS total
            FROM recommendations
            WHERE org_id = :oid AND created_at >= :since
            GROUP BY COALESCE(insight_type, 'unknown')
            ORDER BY total DESC
        """),
        {"oid": org_id, "since": since},
    ).fetchall()

    by_insight_type = []
    for r in detector_rows:
        a = int(r.acted or 0)
        d = int(r.dismissed or 0)
        i = int(r.ignored or 0)
        lbl = a + d + i
        by_insight_type.append({
            "insight_type": r.insight_type,
            "aar": round(a / lbl, 4) if lbl else 0.0,
            "acted": a,
            "dismissed": d,
            "ignored": i,
            "pending": int(r.pending or 0),
            "total": int(r.total or 0),
            # False-positive rate = (dismissed + ignored) / labelled. Feeds
            # directly into calibration threshold tuning for Item 4.
            "false_positive_rate": round((d + i) / lbl, 4) if lbl else 0.0,
        })

    return {
        "org_id": org_id,
        "window_days": days,
        "aar": aar,
        "acted": acted,
        "dismissed": dismissed,
        "ignored": ignored,
        "pending": int(row.pending or 0),
        "total": int(row.total or 0),
        "by_insight_type": by_insight_type,
    }


@router.get("/v1/admin/aar")
def admin_aar(
    days: int = 30,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Autonomous Act-on Rate over the last `days` days."""
    days = max(1, min(90, int(days)))
    return _compute_aar(db, org_id, days)


@router.get("/v1/admin/aar/by_detector")
def admin_aar_by_detector(
    days: int = 30,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Per-detector AAR breakdown. Identical data to `by_insight_type` in the
    main AAR endpoint; exposed as its own endpoint so calibration + ops
    dashboards can consume it without re-computing the top-level aggregates."""
    days = max(1, min(90, int(days)))
    aggregate = _compute_aar(db, org_id, days)
    return {
        "org_id": org_id,
        "window_days": days,
        "by_insight_type": aggregate["by_insight_type"],
    }


@router.get("/v1/admin/aar.csv")
def admin_aar_csv(
    days: int = 30,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Per-recommendation CSV export for beta check-ins."""
    days = max(1, min(90, int(days)))
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = db.execute(
        text("""
            SELECT id, insight_type, category, priority, confidence,
                   title, reason, action, outcome, outcome_at,
                   created_at, delivered_at
            FROM recommendations
            WHERE org_id = :oid AND created_at >= :since
            ORDER BY created_at ASC
        """),
        {"oid": org_id, "since": since},
    ).fetchall()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "id", "insight_type", "category", "priority", "confidence",
        "title", "reason", "action", "outcome", "outcome_at",
        "created_at", "delivered_at",
    ])
    for r in rows:
        w.writerow([
            str(r.id), r.insight_type, r.category,
            float(r.priority or 0), float(r.confidence or 0),
            r.title, r.reason, r.action, r.outcome,
            r.outcome_at.isoformat() if r.outcome_at else "",
            r.created_at.isoformat() if r.created_at else "",
            r.delivered_at.isoformat() if r.delivered_at else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="aar_{days}d.csv"'},
    )
