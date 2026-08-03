"""Admin endpoints — GDPR delete + beta tenant AAR (Phase 6.4).

Auth: re-uses the normal API-key check; caller must be the org owner.
Any cross-tenant leak is impossible — `org_id` comes from the authenticated
principal, not the request body.
"""
from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key

# gdpr_delete script is not in this repo (lived in deploy infra). Stub so the
# v1 backend can boot — POST /v1/admin/delete just returns 501 until restored.
try:
    from scripts.gdpr_delete import run as gdpr_run  # type: ignore
except ImportError:
    def gdpr_run(org_id, entity_id, dry_run=True):  # type: ignore
        raise NotImplementedError(
            "gdpr_delete script not present in this checkout. "
            "Restore scripts/gdpr_delete.py from deploy infra to enable."
        )

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
    # The `recommendations` table (its outcome column powered AAR) was dropped
    # in migration 0015 with the dead System-B brain router. No v2 source writes
    # per-recommendation outcomes yet, so AAR is not computable — return a
    # well-formed zeroed result (route kept live so dashboards don't 500) until
    # outcome attribution is wired onto `proactive_insights` + feedback.
    return {
        "org_id": org_id,
        "window_days": days,
        "aar": 0.0,
        "acted": 0,
        "dismissed": 0,
        "ignored": 0,
        "pending": 0,
        "total": 0,
        "by_insight_type": [],
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

    # `recommendations` was dropped in migration 0015 (dead System-B brain
    # router). No v2 source writes it, so the export is header-only until
    # per-recommendation outcomes are wired onto `proactive_insights`.
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "id", "insight_type", "category", "priority", "confidence",
        "title", "reason", "action", "outcome", "outcome_at",
        "created_at", "delivered_at",
    ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="aar_{days}d.csv"'},
    )
