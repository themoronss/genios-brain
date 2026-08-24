"""Tests for core.reflection — trigger + 80/20 routing + correction capture."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.reflection.human_flag import (
    DEFAULT_THETA_ACT,
    DEFAULT_THETA_FLAG,
    Route,
    capture_correction,
    route_decision,
)
from core.reflection.trigger import should_reflect
from core.worldmodel.store import CorrectionRow


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


# ── trigger ────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_reflection_fires_on_high_stakes_low_confidence() -> None:
    """stakes * (1 - confidence) > theta -> fires."""
    t = should_reflect(confidence=0.3, irreversibility=1.0, blast_radius=1.0, theta_reflect=0.5)
    assert t.fires is True
    assert t.score == pytest.approx(0.7)


@pytest.mark.unit
def test_reflection_skips_when_stakes_low() -> None:
    t = should_reflect(confidence=0.3, irreversibility=0.1, blast_radius=0.1, theta_reflect=0.5)
    assert t.fires is False


@pytest.mark.unit
def test_reflection_skips_when_confidence_high() -> None:
    t = should_reflect(confidence=0.95, irreversibility=1.0, blast_radius=1.0, theta_reflect=0.5)
    assert t.fires is False


@pytest.mark.unit
def test_reflection_rejects_out_of_range_input() -> None:
    with pytest.raises(ValueError):
        should_reflect(confidence=1.5, irreversibility=0.5, blast_radius=0.5, theta_reflect=0.5)


# ── 80/20 routing ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_high_confidence_reversible_routes_autonomous() -> None:
    d = route_decision(confidence=0.9, reversible=True)
    assert d.route == Route.AUTONOMOUS


@pytest.mark.unit
def test_high_confidence_irreversible_routes_notify() -> None:
    """Per MD: irreversible high-conf -> notify (NOT autonomous)."""
    d = route_decision(confidence=0.9, reversible=False)
    assert d.route == Route.NOTIFY


@pytest.mark.unit
def test_mid_confidence_reversible_routes_notify() -> None:
    d = route_decision(confidence=0.6, reversible=True)
    assert d.route == Route.NOTIFY


@pytest.mark.unit
def test_mid_confidence_irreversible_routes_flag() -> None:
    d = route_decision(confidence=0.6, reversible=False)
    assert d.route == Route.FLAG


@pytest.mark.unit
def test_low_confidence_always_flag() -> None:
    d_rev = route_decision(confidence=0.2, reversible=True)
    d_irrev = route_decision(confidence=0.2, reversible=False)
    assert d_rev.route == Route.FLAG
    assert d_irrev.route == Route.FLAG


@pytest.mark.unit
def test_user_redline_forces_flag_regardless_of_confidence() -> None:
    """Per MD g-i-9: persona redlines ALWAYS override confidence."""
    d = route_decision(
        confidence=0.99, reversible=True, user_redlines_hit=["never_email_cold_prospects"]
    )
    assert d.route == Route.FLAG
    assert d.redline_triggered is True


@pytest.mark.unit
def test_routing_thresholds_are_sensible() -> None:
    """Sanity check on default thresholds."""
    assert DEFAULT_THETA_FLAG < DEFAULT_THETA_ACT
    assert 0 < DEFAULT_THETA_FLAG < 1
    assert 0 < DEFAULT_THETA_ACT < 1


@pytest.mark.unit
def test_invalid_theta_combination_rejected() -> None:
    with pytest.raises(ValueError):
        route_decision(confidence=0.5, reversible=True, theta_act=0.3, theta_flag=0.5)


# ── correction capture ────────────────────────────────────────────────────


@pytest.mark.unit
def test_capture_correction_persists_with_diff(session: Session) -> None:
    row = capture_correction(
        session,
        org_id="o",
        decision_id="dec_1",
        input_context={"q": "is acme at risk?"},
        engine_decision={"verdict": "yes", "score": 0.7},
        human_decision={"verdict": "no", "score": 0.7},
        rule_ids=["churn_v1"],
        edge_ids=["e1"],
        actor="user:alice",
    )
    session.commit()

    assert row.actor == "user:alice"
    assert row.decision_id == "dec_1"
    # Diff only captures changed fields
    assert "verdict" in row.diff
    assert "score" not in row.diff  # score didn't change

    # Verify it's queryable
    queried = session.query(CorrectionRow).filter_by(decision_id="dec_1").one()
    assert queried.actor == "user:alice"
