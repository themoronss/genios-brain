"""Metrics routes — the North Star + calibration + ROI + resolution-rate.

GET /v1/metrics/intervention_rate          per-day rollup + trend
GET /v1/metrics/intervention_rate/summary  per-module map for the dashboard header
POST /v1/metrics/intervention_rate/rollup  trigger a recompute (ops)
GET /v1/metrics/calibration                ECE/Brier per bucket for a window
POST /v1/metrics/calibration/compute       compute + persist a new window
GET /v1/metrics/roi                        value vs cost per day
GET /v1/metrics/resolution                 symbolic/neural/hybrid mix per day

All routes are org-scoped via require_org. No cross-org bleeds.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org
from core.foundations import intervention_rate as ir_svc
from core.foundations.calibration import compute_window, persist_window
from core.foundations.metrics_store import (
    CalibrationMetricRow,
    ResolutionMetricRow,
    RoiMetricRow,
)
from core.foundations.telemetry import get_logger

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])
log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Intervention rate (the North Star)
# ─────────────────────────────────────────────────────────────────────────────


class InterventionRateSeries(BaseModel):
    module_id: str
    days: list[date]
    rates: list[float]
    direction: str  # "down" | "up" | "flat"


class InterventionRollupRequest(BaseModel):
    module_ids: list[str] = Field(..., min_length=1)
    start_date: date | None = None
    end_date: date | None = None


@router.get("/intervention_rate", response_model=InterventionRateSeries)
def intervention_trend(
    module_id: str = Query(..., min_length=1),
    window_days: int = Query(default=14, ge=2, le=180),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> InterventionRateSeries:
    trend = ir_svc.trend(
        session, org_id=org_id, module_id=module_id, window_days=window_days
    )
    return InterventionRateSeries(
        module_id=trend.module_id,
        days=trend.days,
        rates=trend.rates,
        direction=trend.direction,
    )


@router.get("/intervention_rate/summary")
def intervention_summary(
    on_date: date | None = Query(default=None),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, float]:
    return ir_svc.org_summary(session, org_id=org_id, on_date=on_date)


@router.post("/intervention_rate/rollup")
def intervention_rollup(
    body: InterventionRollupRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, int]:
    today = datetime.now(UTC).date()
    start = body.start_date or today
    end = body.end_date or today
    n = ir_svc.rollup_range(
        session,
        org_id=org_id,
        module_ids=body.module_ids,
        start_date=start,
        end_date=end,
    )
    session.commit()
    return {"rollups_written": n}


# ─────────────────────────────────────────────────────────────────────────────
# Calibration (ECE / Brier)
# ─────────────────────────────────────────────────────────────────────────────


class CalibrationBucket(BaseModel):
    predicted_bucket: str
    bucket_lower: float
    bucket_upper: float
    sample_size: int
    mean_predicted_confidence: float
    actual_outcome_rate: float
    brier_score: float
    ece_contribution: float


class CalibrationReportOut(BaseModel):
    module_id: str
    window_start: date
    window_end: date
    sample_size: int
    ece: float
    brier: float
    buckets: list[CalibrationBucket]


@router.get("/calibration", response_model=CalibrationReportOut)
def calibration_window(
    module_id: str = Query(..., min_length=1),
    window_days: int = Query(default=7, ge=1, le=180),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> CalibrationReportOut:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=window_days - 1)
    rows = (
        session.execute(
            select(CalibrationMetricRow)
            .where(CalibrationMetricRow.org_id == org_id)
            .where(CalibrationMetricRow.module_id == module_id)
            .where(CalibrationMetricRow.window_start == start)
            .where(CalibrationMetricRow.window_end == end)
            .order_by(CalibrationMetricRow.bucket_lower.asc())
        )
        .scalars()
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"no persisted calibration for module={module_id} window={start}..{end} "
                "— call POST /v1/metrics/calibration/compute first"
            ),
        )
    sample = sum(r.sample_size for r in rows)
    ece = sum(r.ece_contribution for r in rows)
    brier = sum(r.brier_score * r.sample_size for r in rows) / max(1, sample)
    buckets = [
        CalibrationBucket(
            predicted_bucket=r.predicted_bucket,
            bucket_lower=r.bucket_lower,
            bucket_upper=r.bucket_upper,
            sample_size=r.sample_size,
            mean_predicted_confidence=r.mean_predicted_confidence,
            actual_outcome_rate=r.actual_outcome_rate,
            brier_score=r.brier_score,
            ece_contribution=r.ece_contribution,
        )
        for r in rows
    ]
    return CalibrationReportOut(
        module_id=module_id,
        window_start=start,
        window_end=end,
        sample_size=sample,
        ece=round(ece, 4),
        brier=round(brier, 4),
        buckets=buckets,
    )


class CalibrationComputeRequest(BaseModel):
    module_id: str = Field(..., min_length=1)
    window_days: int = Field(default=7, ge=1, le=180)


@router.post("/calibration/compute", response_model=CalibrationReportOut)
def calibration_compute(
    body: CalibrationComputeRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> CalibrationReportOut:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=body.window_days - 1)
    report = compute_window(
        session,
        org_id=org_id,
        module_id=body.module_id,
        window_start=start,
        window_end=end,
    )
    persist_window(session, report=report)
    session.commit()
    return CalibrationReportOut(
        module_id=body.module_id,
        window_start=start,
        window_end=end,
        sample_size=report.sample_size,
        ece=report.ece,
        brier=report.brier,
        buckets=[
            CalibrationBucket(
                predicted_bucket=b.label,
                bucket_lower=b.lower,
                bucket_upper=b.upper,
                sample_size=b.samples,
                mean_predicted_confidence=round(b.mean_predicted, 4),
                actual_outcome_rate=round(b.observed_rate, 4),
                brier_score=round(b.brier, 4),
                ece_contribution=round(
                    (b.samples / report.sample_size) * abs(b.mean_predicted - b.observed_rate)
                    if report.sample_size
                    else 0.0,
                    4,
                ),
            )
            for b in report.buckets
            if b.samples > 0
        ],
    )


# ─────────────────────────────────────────────────────────────────────────────
# ROI + resolution
# ─────────────────────────────────────────────────────────────────────────────


class RoiDailyPoint(BaseModel):
    date: date
    module_id: str
    autonomous_actions_count: int
    estimated_value_usd: float
    llm_cost_usd: float
    infra_cost_usd: float
    roi_ratio: float


@router.get("/roi", response_model=list[RoiDailyPoint])
def roi_series(
    module_id: str = Query(..., min_length=1),
    window_days: int = Query(default=14, ge=1, le=180),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> list[RoiDailyPoint]:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=window_days - 1)
    rows = (
        session.execute(
            select(RoiMetricRow)
            .where(RoiMetricRow.org_id == org_id)
            .where(RoiMetricRow.module_id == module_id)
            .where(RoiMetricRow.date >= start)
            .where(RoiMetricRow.date <= end)
            .order_by(RoiMetricRow.date.asc())
        )
        .scalars()
        .all()
    )
    return [
        RoiDailyPoint(
            date=r.date,
            module_id=r.module_id,
            autonomous_actions_count=r.autonomous_actions_count,
            estimated_value_usd=r.estimated_value_usd,
            llm_cost_usd=r.llm_cost_usd,
            infra_cost_usd=r.infra_cost_usd,
            roi_ratio=r.roi_ratio,
        )
        for r in rows
    ]


class ResolutionDailyPoint(BaseModel):
    date: date
    module_id: str
    symbolic_count: int
    neural_count: int
    hybrid_count: int
    symbolic_resolution_rate: float


@router.get("/resolution", response_model=list[ResolutionDailyPoint])
def resolution_series(
    module_id: str = Query(..., min_length=1),
    window_days: int = Query(default=14, ge=1, le=180),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> list[ResolutionDailyPoint]:
    end = datetime.now(UTC).date()
    start = end - timedelta(days=window_days - 1)
    rows = (
        session.execute(
            select(ResolutionMetricRow)
            .where(ResolutionMetricRow.org_id == org_id)
            .where(ResolutionMetricRow.module_id == module_id)
            .where(ResolutionMetricRow.date >= start)
            .where(ResolutionMetricRow.date <= end)
            .order_by(ResolutionMetricRow.date.asc())
        )
        .scalars()
        .all()
    )
    return [
        ResolutionDailyPoint(
            date=r.date,
            module_id=r.module_id,
            symbolic_count=r.symbolic_count,
            neural_count=r.neural_count,
            hybrid_count=r.hybrid_count,
            symbolic_resolution_rate=r.symbolic_resolution_rate,
        )
        for r in rows
    ]


@router.get("/headline")
def headline(
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    """One-call summary for the dashboard hero card.

    Returns: today's intervention_rate per module, latest ROI ratio per module,
    rolling symbolic resolution rate. Pulled from rollup tables (cheap).
    """
    today = datetime.now(UTC).date()
    intervention = ir_svc.org_summary(session, org_id=org_id, on_date=today)
    latest_roi: dict[str, float] = {}
    for roi_row in (
        session.execute(
            select(RoiMetricRow)
            .where(RoiMetricRow.org_id == org_id)
            .order_by(RoiMetricRow.date.desc())
            .limit(50)
        )
        .scalars()
        .all()
    ):
        latest_roi.setdefault(roi_row.module_id, roi_row.roi_ratio)
    resolution: dict[str, float] = {}
    for res_row in (
        session.execute(
            select(ResolutionMetricRow)
            .where(ResolutionMetricRow.org_id == org_id)
            .order_by(ResolutionMetricRow.date.desc())
            .limit(50)
        )
        .scalars()
        .all()
    ):
        resolution.setdefault(res_row.module_id, res_row.symbolic_resolution_rate)
    return {
        "date": today.isoformat(),
        "intervention_rate_by_module": intervention,
        "latest_roi_by_module": latest_roi,
        "latest_symbolic_resolution_rate_by_module": resolution,
    }
