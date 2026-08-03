"""Tests for intervention_rate — THE North Star metric."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.foundations.db import Base
from core.foundations.intervention_rate import (
    compute_for_day,
    org_summary,
    rollup_day,
    rollup_range,
    trend,
)
from core.foundations.metrics_store import InterventionMetricRow
from core.worldmodel.store import CorrectionRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _make_decision(
    session: Session,
    *,
    org_id: str = "o",
    module_id: str = "sales",
    route: str = "notify",
    at: datetime | None = None,
    confidence: float = 0.8,
    path: str = "symbolic",
) -> DecisionRow:
    row = DecisionRow(
        org_id=org_id,
        query_jsonb={},
        conclusion="x",
        derivation_chain_jsonb={},
        path=path,
        confidence_score=confidence,
        confidence_breakdown_jsonb={},
        grounding_refs_jsonb=[],
        route=route,
        as_of_version=1,
        triggered_by="query",
        module_id=module_id,
        created_at=at or datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    return row


def _make_correction(session: Session, *, org_id: str, decision_id: str) -> None:
    session.add(
        CorrectionRow(
            org_id=org_id,
            decision_id=decision_id,
            input_context={},
            engine_decision={},
            human_decision={},
            diff={},
            actor="u",
        )
    )
    session.flush()


@pytest.mark.unit
def test_zero_decisions_zero_rate(session: Session) -> None:
    snap = compute_for_day(
        session, org_id="o", module_id="sales", on_date=datetime.now(UTC).date()
    )
    assert snap.total_decisions == 0
    assert snap.intervention_rate == 0.0


@pytest.mark.unit
def test_rate_is_overrides_over_decisions(session: Session) -> None:
    today = datetime.now(UTC).date()
    decs = [_make_decision(session) for _ in range(5)]
    _make_correction(session, org_id="o", decision_id=decs[0].id)
    _make_correction(session, org_id="o", decision_id=decs[1].id)
    session.flush()

    snap = compute_for_day(session, org_id="o", module_id="sales", on_date=today)
    assert snap.total_decisions == 5
    assert snap.human_overrides_count == 2
    assert snap.intervention_rate == 0.4


@pytest.mark.unit
def test_route_breakdown_counts(session: Session) -> None:
    today = datetime.now(UTC).date()
    _make_decision(session, route="autonomous")
    _make_decision(session, route="autonomous")
    _make_decision(session, route="notify")
    _make_decision(session, route="flag")
    snap = compute_for_day(session, org_id="o", module_id="sales", on_date=today)
    assert snap.autonomous_count == 2
    assert snap.notify_count == 1
    assert snap.flag_count == 1


@pytest.mark.unit
def test_org_isolation_strict(session: Session) -> None:
    """Other org's decisions + corrections never bleed into our rate."""
    today = datetime.now(UTC).date()
    _make_decision(session, org_id="o1")
    other = _make_decision(session, org_id="o2")
    _make_correction(session, org_id="o2", decision_id=other.id)
    snap = compute_for_day(session, org_id="o1", module_id="sales", on_date=today)
    assert snap.total_decisions == 1
    assert snap.human_overrides_count == 0


@pytest.mark.unit
def test_rollup_upsert_idempotent(session: Session) -> None:
    today = datetime.now(UTC).date()
    _make_decision(session)
    rollup_day(session, org_id="o", module_id="sales", on_date=today)
    rollup_day(session, org_id="o", module_id="sales", on_date=today)
    rows = session.query(InterventionMetricRow).all()
    assert len(rows) == 1
    assert rows[0].total_decisions == 1


@pytest.mark.unit
def test_rollup_range_writes_per_day_per_module(session: Session) -> None:
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    n = rollup_range(
        session,
        org_id="o",
        module_ids=["sales", "finance"],
        start_date=yesterday,
        end_date=today,
    )
    assert n == 4  # 2 days * 2 modules
    assert session.query(InterventionMetricRow).count() == 4


@pytest.mark.unit
def test_trend_classifies_direction(session: Session) -> None:
    end = datetime.now(UTC).date()
    # Window 4 days: first half rate 0.5, second half rate 0.1 -> down
    rates = [0.5, 0.5, 0.1, 0.1]
    for i, r in enumerate(rates):
        session.add(
            InterventionMetricRow(
                org_id="o",
                module_id="sales",
                date=end - timedelta(days=len(rates) - 1 - i),
                total_decisions=10,
                human_overrides_count=int(r * 10),
                intervention_rate=r,
            )
        )
    session.flush()
    t = trend(session, org_id="o", module_id="sales", window_days=4)
    assert t.direction == "down"
    assert len(t.days) == 4
    assert len(t.rates) == 4


@pytest.mark.unit
def test_org_summary_returns_per_module_map(session: Session) -> None:
    today = datetime.now(UTC).date()
    session.add_all(
        [
            InterventionMetricRow(
                org_id="o",
                module_id="sales",
                date=today,
                total_decisions=10,
                human_overrides_count=2,
                intervention_rate=0.2,
            ),
            InterventionMetricRow(
                org_id="o",
                module_id="finance",
                date=today,
                total_decisions=4,
                human_overrides_count=1,
                intervention_rate=0.25,
            ),
        ]
    )
    session.flush()
    out = org_summary(session, org_id="o", on_date=today)
    assert out["sales"] == 0.2
    assert out["finance"] == 0.25
