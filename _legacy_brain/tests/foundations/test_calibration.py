"""Tests for confidence calibration tracker (ECE + Brier)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.delivery.store import FeedbackActionRow
from core.foundations.calibration import (
    compute_window,
    persist_window,
)
from core.foundations.db import Base
from core.foundations.metrics_store import CalibrationMetricRow
from core.worldmodel.store import CorrectionRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _add_decision(
    session: Session,
    *,
    confidence: float,
    org_id: str = "o",
    module_id: str = "sales",
    at: datetime | None = None,
) -> DecisionRow:
    row = DecisionRow(
        org_id=org_id,
        query_jsonb={},
        conclusion="x",
        derivation_chain_jsonb={},
        path="symbolic",
        confidence_score=confidence,
        confidence_breakdown_jsonb={},
        grounding_refs_jsonb=[],
        route="notify",
        as_of_version=1,
        triggered_by="query",
        module_id=module_id,
        created_at=at or (datetime.now(UTC) - timedelta(days=10)),
    )
    session.add(row)
    session.flush()
    return row


def _add_feedback(session: Session, *, decision_id: str, action: str, org_id: str = "o") -> None:
    session.add(
        FeedbackActionRow(
            org_id=org_id,
            user_id="u",
            decision_id=decision_id,
            action=action,
        )
    )
    session.flush()


@pytest.mark.unit
def test_empty_window_returns_zero(session: Session) -> None:
    today = datetime.now(UTC).date()
    report = compute_window(
        session,
        org_id="o",
        module_id="sales",
        window_start=today - timedelta(days=7),
        window_end=today,
    )
    assert report.sample_size == 0
    assert report.ece == 0.0
    assert report.brier == 0.0


@pytest.mark.unit
def test_perfectly_calibrated_low_ece(session: Session) -> None:
    """All confidence-0.9 decisions land in the 0.9-1.0 bucket with 90% positive."""
    older = datetime.now(UTC) - timedelta(days=20)
    decisions = [_add_decision(session, confidence=0.9, at=older) for _ in range(10)]
    # 9 positive (silence, past outcome window) + 1 explicit thumbs_down
    _add_feedback(session, decision_id=decisions[0].id, action="thumbs_down")

    today = datetime.now(UTC).date()
    report = compute_window(
        session,
        org_id="o",
        module_id="sales",
        window_start=today - timedelta(days=30),
        window_end=today,
    )
    assert report.sample_size == 10
    # 9/10 positive at predicted-mean 0.9 -> |0.9 - 0.9| ≈ 0 ECE
    assert report.ece < 0.05


@pytest.mark.unit
def test_overconfident_high_ece(session: Session) -> None:
    """All confidence-0.9 decisions but only 50% positive -> ECE around 0.4."""
    older = datetime.now(UTC) - timedelta(days=20)
    decisions = [_add_decision(session, confidence=0.9, at=older) for _ in range(10)]
    for d in decisions[:5]:
        _add_feedback(session, decision_id=d.id, action="thumbs_down")

    today = datetime.now(UTC).date()
    report = compute_window(
        session,
        org_id="o",
        module_id="sales",
        window_start=today - timedelta(days=30),
        window_end=today,
    )
    assert report.sample_size == 10
    assert report.ece > 0.3  # predicted 0.9 vs observed 0.5


@pytest.mark.unit
def test_correction_counts_as_outcome_zero(session: Session) -> None:
    older = datetime.now(UTC) - timedelta(days=20)
    decisions = [_add_decision(session, confidence=0.7, at=older) for _ in range(4)]
    session.add(
        CorrectionRow(
            org_id="o",
            decision_id=decisions[0].id,
            input_context={},
            engine_decision={},
            human_decision={},
            diff={},
            actor="u",
        )
    )
    session.flush()

    today = datetime.now(UTC).date()
    report = compute_window(
        session,
        org_id="o",
        module_id="sales",
        window_start=today - timedelta(days=30),
        window_end=today,
    )
    # 3 positives (silence past window) + 1 negative (correction) = 0.75 observed
    bucket = next(b for b in report.buckets if b.lower == 0.7)
    assert bucket.samples == 4
    assert bucket.observed_rate == 0.75


@pytest.mark.unit
def test_snooze_and_never_show_excluded(session: Session) -> None:
    """Snooze/never_show only -> within-window decisions excluded (no judgment)."""
    recent = datetime.now(UTC)  # inside outcome_window_days
    d = _add_decision(session, confidence=0.7, at=recent)
    _add_feedback(session, decision_id=d.id, action="snooze")

    today = datetime.now(UTC).date()
    report = compute_window(
        session,
        org_id="o",
        module_id="sales",
        window_start=today,
        window_end=today,
    )
    assert report.sample_size == 0


@pytest.mark.unit
def test_persist_window_writes_per_nonempty_bucket(session: Session) -> None:
    older = datetime.now(UTC) - timedelta(days=20)
    for _ in range(3):
        _add_decision(session, confidence=0.85, at=older)
    for _ in range(2):
        _add_decision(session, confidence=0.55, at=older)

    today = datetime.now(UTC).date()
    report = compute_window(
        session,
        org_id="o",
        module_id="sales",
        window_start=today - timedelta(days=30),
        window_end=today,
    )
    rows = persist_window(session, report=report)
    assert len(rows) == 2  # two non-empty buckets
    persisted = session.query(CalibrationMetricRow).all()
    assert len(persisted) == 2


@pytest.mark.unit
def test_persist_is_idempotent(session: Session) -> None:
    older = datetime.now(UTC) - timedelta(days=20)
    _add_decision(session, confidence=0.85, at=older)
    today = datetime.now(UTC).date()
    report = compute_window(
        session,
        org_id="o",
        module_id="sales",
        window_start=today - timedelta(days=30),
        window_end=today,
    )
    persist_window(session, report=report)
    persist_window(session, report=report)
    assert session.query(CalibrationMetricRow).count() == 1


@pytest.mark.unit
def test_window_validation(session: Session) -> None:
    today = datetime.now(UTC).date()
    with pytest.raises(ValueError):
        compute_window(
            session,
            org_id="o",
            module_id="sales",
            window_start=today,
            window_end=today - timedelta(days=1),
        )
