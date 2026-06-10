"""Workflow-level drift detection.

Per MD update §1.1.3 (founder-added section):
    workflow drift = customer's channel/cadence/topic mix shifting over time
    (e.g. Q1 mostly email, Q2 mostly Slack). Prioritizer baselines go stale ->
    pushed insights become wrong. Need to detect and recalibrate.

Implementation:
- rolling baseline per org per dimension (channel_mix | cadence | topic_mix)
- on each check, compare current window vs baseline
- shift > WORKFLOW_DRIFT_THRESHOLD -> emit DriftReport + flag for recalibration

Drift score = total variation distance between distributions, normalized to [0,1].
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.foundations.config import WORKFLOW_DRIFT_THRESHOLD
from core.foundations.telemetry import get_logger
from core.proactive.store import WorkflowBaselineRow

log = get_logger(__name__)


DriftDim = Literal["channel_mix", "cadence", "topic_mix"]


@dataclass(frozen=True)
class DriftReport:
    """Outcome of a workflow drift check."""

    org_id: str
    dim: DriftDim
    drift_score: float  # in [0, 1]; higher = more shift
    drift_detected: bool
    baseline: dict[str, float]
    current: dict[str, float]
    window_days: int


def check_workflow_drift(
    session: Session,
    *,
    org_id: str,
    dim: DriftDim,
    current_distribution: Mapping[str, float],
    threshold: float = WORKFLOW_DRIFT_THRESHOLD,
    window_days: int = 30,
) -> DriftReport:
    """Compare current distribution against the most recent baseline.

    `current_distribution` is the caller's measurement over the recent window
    (e.g. {"email": 0.3, "slack": 0.6, "calendar": 0.1}).

    First call for an org -> baseline created, drift_score=0 (nothing to compare).
    Subsequent calls -> total variation distance vs baseline.
    """
    baseline_row = _latest_baseline(session, org_id=org_id, dim=dim)
    current_norm = _normalize(current_distribution)

    if baseline_row is None:
        # First measurement — seed the baseline + report zero drift
        _persist_baseline(
            session, org_id=org_id, dim=dim, distribution=current_norm, window_days=window_days
        )
        return DriftReport(
            org_id=org_id,
            dim=dim,
            drift_score=0.0,
            drift_detected=False,
            baseline=current_norm,
            current=current_norm,
            window_days=window_days,
        )

    baseline = dict(baseline_row.baseline_jsonb)
    score = _total_variation_distance(baseline, current_norm)
    detected = score >= threshold

    if detected:
        log.warning(
            "workflow_drift_detected",
            org_id=org_id,
            dim=dim,
            drift_score=round(score, 3),
            threshold=threshold,
        )
        # Update the baseline so we don't keep alerting on the same drift
        _persist_baseline(
            session,
            org_id=org_id,
            dim=dim,
            distribution=current_norm,
            window_days=window_days,
        )

    return DriftReport(
        org_id=org_id,
        dim=dim,
        drift_score=score,
        drift_detected=detected,
        baseline=baseline,
        current=current_norm,
        window_days=window_days,
    )


# ─── internals ─────────────────────────────────────────────────────────────


def _normalize(d: Mapping[str, float]) -> dict[str, float]:
    """Normalize a distribution to sum to 1 (ignoring negatives)."""
    total = sum(max(0.0, v) for v in d.values())
    if total <= 0:
        return {k: 0.0 for k in d}
    return {k: max(0.0, v) / total for k, v in d.items()}


def _total_variation_distance(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    """TVD(a, b) = (1/2) * sum_k |a_k - b_k|. Normalized to [0, 1]."""
    keys = set(a) | set(b)
    diff = sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)
    return min(1.0, max(0.0, diff / 2.0))


def _latest_baseline(session: Session, *, org_id: str, dim: DriftDim) -> WorkflowBaselineRow | None:
    return session.execute(
        select(WorkflowBaselineRow)
        .where(WorkflowBaselineRow.org_id == org_id)
        .where(WorkflowBaselineRow.dim == dim)
        .order_by(WorkflowBaselineRow.window_end.desc())
        .limit(1)
    ).scalar_one_or_none()


def _persist_baseline(
    session: Session,
    *,
    org_id: str,
    dim: DriftDim,
    distribution: dict[str, float],
    window_days: int,
) -> WorkflowBaselineRow:
    now = datetime.now(UTC)
    row = WorkflowBaselineRow(
        org_id=org_id,
        dim=dim,
        baseline_jsonb=distribution,
        window_start=now - timedelta(days=window_days),
        window_end=now,
    )
    session.add(row)
    session.flush()
    return row
