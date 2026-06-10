"""Confidence calibration tracker (g-i-8) — ECE + Brier per module per window.

Why this exists:
    The 80/20 autonomy rule (g-i-2) only holds if confidence is CALIBRATED.
    "0.85 confidence" must mean "right 85% of the time" — otherwise autonomous
    actions ship at the wrong rate. Per MD: track ECE/Brier, alert if drift.

Outcome signal:
    For each decision, "actual outcome" is derived from feedback:
        thumbs_up / no_feedback (within outcome_window_days) -> correct (1)
        thumbs_down / edit / correction                       -> incorrect (0)
    snooze / never_show signal absence-of-judgment → excluded.

Buckets: 10 fixed buckets, width 0.1 each.

Output:
    - Per-bucket: mean_predicted, observed_rate, sample_size, Brier
    - Per-window: ECE = Σ (n_i / N) · |predicted_i - observed_i|
    - Per-window: Brier = (1/N) Σ (predicted_i - outcome_i)²
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.delivery.store import FeedbackActionRow
from core.foundations.metrics_store import CalibrationMetricRow
from core.foundations.telemetry import get_logger
from core.worldmodel.store import CorrectionRow

log = get_logger(__name__)

BUCKET_WIDTH = 0.1
N_BUCKETS = 10
DEFAULT_OUTCOME_WINDOW_DAYS = 7


@dataclass
class BucketStats:
    """One confidence bucket's empirical stats over the window."""

    lower: float
    upper: float
    label: str
    samples: int = 0
    sum_predicted: float = 0.0
    sum_outcome: float = 0.0
    sum_sq_error: float = 0.0
    _outcomes: list[int] = field(default_factory=list)

    def add(self, predicted: float, outcome: int) -> None:
        self.samples += 1
        self.sum_predicted += predicted
        self.sum_outcome += outcome
        self.sum_sq_error += (predicted - outcome) ** 2
        self._outcomes.append(outcome)

    @property
    def mean_predicted(self) -> float:
        return self.sum_predicted / self.samples if self.samples else 0.0

    @property
    def observed_rate(self) -> float:
        return self.sum_outcome / self.samples if self.samples else 0.0

    @property
    def brier(self) -> float:
        return self.sum_sq_error / self.samples if self.samples else 0.0


@dataclass(frozen=True)
class CalibrationReport:
    """Outcome of `compute_window` — per-bucket plus aggregate ECE/Brier."""

    org_id: str
    module_id: str
    window_start: date
    window_end: date
    buckets: list[BucketStats]
    sample_size: int
    ece: float
    brier: float


def _bucket_for(confidence: float) -> int:
    """Return bucket index 0..N_BUCKETS-1 for a confidence in [0, 1].

    Add a tiny epsilon before flooring to dodge float artifacts like
    0.7 / 0.1 == 6.9999… → int(6) instead of 7.
    """
    if confidence < 0 or confidence > 1:
        raise ValueError(f"confidence out of [0,1]: {confidence}")
    idx = int(confidence / BUCKET_WIDTH + 1e-9)
    return min(idx, N_BUCKETS - 1)


def _empty_buckets() -> list[BucketStats]:
    out: list[BucketStats] = []
    for i in range(N_BUCKETS):
        lower = round(i * BUCKET_WIDTH, 2)
        upper = round((i + 1) * BUCKET_WIDTH, 2)
        out.append(BucketStats(lower=lower, upper=upper, label=f"{lower:.1f}-{upper:.1f}"))
    return out


def _decision_outcomes(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    window_start: date,
    window_end: date,
    outcome_window_days: int,
) -> Iterable[tuple[float, int]]:
    """Yield (predicted_confidence, outcome_0_or_1) per decision in the window.

    Outcome derivation (per module spec):
    - Has matching CorrectionRow OR thumbs_down/edit FeedbackActionRow → 0
    - thumbs_up FeedbackActionRow                                     → 1
    - No feedback within outcome_window_days AND decision is at least
      outcome_window_days old → treated as 1 (silence = acceptance)
    - Still within outcome_window_days and no feedback              → skipped
    - snooze / never_show feedback only                              → skipped
    """
    start = datetime.combine(window_start, datetime.min.time(), tzinfo=UTC)
    end = datetime.combine(window_end, datetime.max.time(), tzinfo=UTC)
    decisions = list(
        session.execute(
            select(DecisionRow)
            .where(DecisionRow.org_id == org_id)
            .where(DecisionRow.module_id == module_id)
            .where(DecisionRow.created_at >= start)
            .where(DecisionRow.created_at <= end)
        )
        .scalars()
        .all()
    )
    if not decisions:
        return

    dec_ids = [d.id for d in decisions]
    corrections = (
        session.execute(
            select(CorrectionRow.decision_id)
            .where(CorrectionRow.org_id == org_id)
            .where(CorrectionRow.decision_id.in_(dec_ids))
        )
        .scalars()
        .all()
    )
    corrected_ids = set(corrections)

    feedbacks = list(
        session.execute(
            select(FeedbackActionRow)
            .where(FeedbackActionRow.org_id == org_id)
            .where(FeedbackActionRow.decision_id.in_(dec_ids))
        )
        .scalars()
        .all()
    )
    fb_by_decision: dict[str, list[FeedbackActionRow]] = {}
    for fb in feedbacks:
        if fb.decision_id is None:
            continue
        fb_by_decision.setdefault(fb.decision_id, []).append(fb)

    cutoff = datetime.now(UTC) - timedelta(days=outcome_window_days)
    for d in decisions:
        if d.id in corrected_ids:
            yield (d.confidence_score, 0)
            continue
        fbs = fb_by_decision.get(d.id, [])
        actions = {fb.action for fb in fbs}
        if "thumbs_down" in actions or "edit" in actions:
            yield (d.confidence_score, 0)
            continue
        if "thumbs_up" in actions:
            yield (d.confidence_score, 1)
            continue
        # No judgmental feedback: only count as positive if outcome window elapsed.
        # SQLite stores datetimes as naive — normalize before comparing.
        created = d.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if created <= cutoff:
            yield (d.confidence_score, 1)


def compute_window(
    session: Session,
    *,
    org_id: str,
    module_id: str,
    window_start: date,
    window_end: date,
    outcome_window_days: int = DEFAULT_OUTCOME_WINDOW_DAYS,
) -> CalibrationReport:
    """Build the calibration report for one (org, module) window. Pure read."""
    if window_start > window_end:
        raise ValueError("window_start must be <= window_end")

    buckets = _empty_buckets()
    samples = 0
    sum_sq_error = 0.0
    for predicted, outcome in _decision_outcomes(
        session,
        org_id=org_id,
        module_id=module_id,
        window_start=window_start,
        window_end=window_end,
        outcome_window_days=outcome_window_days,
    ):
        buckets[_bucket_for(predicted)].add(predicted, outcome)
        samples += 1
        sum_sq_error += (predicted - outcome) ** 2

    ece = 0.0
    if samples:
        for b in buckets:
            if b.samples == 0:
                continue
            weight = b.samples / samples
            ece += weight * abs(b.mean_predicted - b.observed_rate)

    brier = sum_sq_error / samples if samples else 0.0
    return CalibrationReport(
        org_id=org_id,
        module_id=module_id,
        window_start=window_start,
        window_end=window_end,
        buckets=buckets,
        sample_size=samples,
        ece=round(ece, 4),
        brier=round(brier, 4),
    )


def persist_window(
    session: Session,
    *,
    report: CalibrationReport,
) -> list[CalibrationMetricRow]:
    """Write one CalibrationMetricRow per non-empty bucket. Idempotent (deletes + inserts)."""
    # Wipe prior rows for the same window so re-runs don't double-count
    existing = (
        session.execute(
            select(CalibrationMetricRow)
            .where(CalibrationMetricRow.org_id == report.org_id)
            .where(CalibrationMetricRow.module_id == report.module_id)
            .where(CalibrationMetricRow.window_start == report.window_start)
            .where(CalibrationMetricRow.window_end == report.window_end)
        )
        .scalars()
        .all()
    )
    for r in existing:
        session.delete(r)

    rows: list[CalibrationMetricRow] = []
    for b in report.buckets:
        if b.samples == 0:
            continue
        contribution = (b.samples / report.sample_size) * abs(
            b.mean_predicted - b.observed_rate
        ) if report.sample_size else 0.0
        row = CalibrationMetricRow(
            org_id=report.org_id,
            module_id=report.module_id,
            window_start=report.window_start,
            window_end=report.window_end,
            predicted_bucket=b.label,
            bucket_lower=b.lower,
            bucket_upper=b.upper,
            sample_size=b.samples,
            mean_predicted_confidence=round(b.mean_predicted, 4),
            actual_outcome_rate=round(b.observed_rate, 4),
            brier_score=round(b.brier, 4),
            ece_contribution=round(contribution, 4),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    log.info(
        "calibration_persisted",
        org_id=report.org_id,
        module_id=report.module_id,
        window_start=report.window_start.isoformat(),
        window_end=report.window_end.isoformat(),
        ece=report.ece,
        brier=report.brier,
        sample_size=report.sample_size,
    )
    return rows
