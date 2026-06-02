"""Tests for ROI tracker + resolution-rate (engine health)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.decision_store import DecisionRow
from core.delivery.store import AgentCallRow
from core.foundations.db import Base
from core.foundations.metrics_store import ResolutionMetricRow, RoiMetricRow
from core.foundations.roi import (
    compute_resolution,
    compute_roi,
    persist_resolution,
    persist_roi,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _add_decision(
    session: Session,
    *,
    org_id: str = "o",
    module_id: str = "sales",
    route: str = "autonomous",
    path: str = "symbolic",
    at: datetime | None = None,
) -> DecisionRow:
    row = DecisionRow(
        org_id=org_id,
        query_jsonb={},
        conclusion="x",
        derivation_chain_jsonb={},
        path=path,
        confidence_score=0.9,
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


def _add_agent_call(session: Session, *, cost: float, at: datetime | None = None) -> None:
    session.add(
        AgentCallRow(
            org_id="o",
            agent_id="ag",
            endpoint="x",
            request_jsonb={},
            cost_usd=cost,
            outcome="ok",
            timestamp=at or datetime.now(UTC),
        )
    )
    session.flush()


@pytest.mark.unit
def test_roi_basic(session: Session) -> None:
    today = datetime.now(UTC).date()
    for _ in range(3):
        _add_decision(session, route="autonomous")
    _add_agent_call(session, cost=0.5)
    _add_agent_call(session, cost=1.5)

    snap = compute_roi(
        session,
        org_id="o",
        module_id="sales",
        on_date=today,
        value_heuristic=lambda _: 10.0,
        infra_cost_usd=1.0,
    )
    assert snap.autonomous_actions_count == 3
    assert snap.estimated_value_usd == 30.0
    assert snap.llm_cost_usd == 2.0
    assert snap.infra_cost_usd == 1.0
    assert snap.roi_ratio == 10.0  # 30 / (2+1)


@pytest.mark.unit
def test_roi_only_autonomous_counted(session: Session) -> None:
    today = datetime.now(UTC).date()
    _add_decision(session, route="autonomous")
    _add_decision(session, route="notify")
    _add_decision(session, route="flag")
    snap = compute_roi(
        session,
        org_id="o",
        module_id="sales",
        on_date=today,
        value_heuristic=lambda _: 5.0,
    )
    assert snap.autonomous_actions_count == 1
    assert snap.estimated_value_usd == 5.0


@pytest.mark.unit
def test_roi_zero_cost_infinite_ratio(session: Session) -> None:
    today = datetime.now(UTC).date()
    _add_decision(session, route="autonomous")
    snap = compute_roi(
        session,
        org_id="o",
        module_id="sales",
        on_date=today,
        value_heuristic=lambda _: 1.0,
    )
    assert snap.roi_ratio == float("inf")


@pytest.mark.unit
def test_roi_persist_clamps_inf(session: Session) -> None:
    today = datetime.now(UTC).date()
    _add_decision(session, route="autonomous")
    snap = compute_roi(
        session,
        org_id="o",
        module_id="sales",
        on_date=today,
        value_heuristic=lambda _: 1.0,
    )
    row = persist_roi(session, snap=snap)
    assert row.roi_ratio == 9999.0


@pytest.mark.unit
def test_roi_persist_upserts(session: Session) -> None:
    today = datetime.now(UTC).date()
    _add_decision(session, route="autonomous")
    snap = compute_roi(
        session,
        org_id="o",
        module_id="sales",
        on_date=today,
        value_heuristic=lambda _: 1.0,
        infra_cost_usd=0.5,
    )
    persist_roi(session, snap=snap)
    persist_roi(session, snap=snap)
    assert session.query(RoiMetricRow).count() == 1


@pytest.mark.unit
def test_resolution_rate_pure_symbolic(session: Session) -> None:
    today = datetime.now(UTC).date()
    for _ in range(4):
        _add_decision(session, path="symbolic")
    _add_decision(session, path="hybrid")
    snap = compute_resolution(session, org_id="o", module_id="sales", on_date=today)
    assert snap.symbolic_count == 4
    assert snap.hybrid_count == 1
    assert snap.neural_count == 0
    assert snap.symbolic_resolution_rate == 0.8


@pytest.mark.unit
def test_resolution_persist_idempotent(session: Session) -> None:
    today = datetime.now(UTC).date()
    _add_decision(session)
    snap = compute_resolution(session, org_id="o", module_id="sales", on_date=today)
    persist_resolution(session, snap=snap)
    persist_resolution(session, snap=snap)
    assert session.query(ResolutionMetricRow).count() == 1


@pytest.mark.unit
def test_roi_org_isolation(session: Session) -> None:
    """Different org's agent_calls + decisions never bleed in."""
    today = datetime.now(UTC).date()
    _add_decision(session, org_id="o1", route="autonomous")
    _add_decision(session, org_id="o2", route="autonomous")
    snap = compute_roi(
        session,
        org_id="o1",
        module_id="sales",
        on_date=today,
        value_heuristic=lambda _: 5.0,
    )
    assert snap.autonomous_actions_count == 1
