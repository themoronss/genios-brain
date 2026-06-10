"""Tests for core.proactive.foresight + drift."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.proactive.drift import check_workflow_drift
from core.proactive.foresight import (
    ForesightMode,
    compute_premortem,
    estimate_likelihood,
)
from core.reasoning.rule_loader import (
    Condition,
    Operator,
    Rule,
    RuleSet,
    ThenClause,
    WhenClause,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


# ── foresight: base-rate vs qualitative ────────────────────────────────────


@pytest.mark.unit
def test_below_n_min_falls_back_to_qualitative() -> None:
    """Per MD: if n < N_min -> Mode B (qualitative). No invented numbers."""
    result = estimate_likelihood(historical_outcomes=[True, False, True], n_min=20)
    assert result.mode == ForesightMode.QUALITATIVE
    assert result.value in {"high", "medium", "low"}


@pytest.mark.unit
def test_above_n_min_returns_base_rate() -> None:
    """Per MD: n >= N_min -> Mode A (base-rate, Laplace-smoothed) + report n."""
    outcomes = [True] * 15 + [False] * 5  # 15/20 positive
    result = estimate_likelihood(historical_outcomes=outcomes, n_min=10)
    assert result.mode == ForesightMode.BASE_RATE
    assert isinstance(result.value, float)
    assert 0.0 < result.value < 1.0
    assert result.sample_size == 20


@pytest.mark.unit
def test_empty_history_qualitative() -> None:
    result = estimate_likelihood(historical_outcomes=None)
    assert result.mode == ForesightMode.QUALITATIVE


@pytest.mark.unit
def test_disclaimer_always_present() -> None:
    """Disclaimer is embedded in dataclass — narrator cannot strip."""
    base = estimate_likelihood(historical_outcomes=[True] * 30, n_min=20)
    qual = estimate_likelihood(historical_outcomes=[True], n_min=20)
    assert "bounded by the asserted model" in base.disclaimer.lower()
    assert "qualitative" in qual.disclaimer.lower()


# ── foresight: premortem ───────────────────────────────────────────────────


@pytest.mark.unit
def test_premortem_identifies_failure_intervention() -> None:
    """Goal holds; intervention that breaks it gets flagged."""
    rule = Rule(
        id="r1",
        module="sales",
        priority=10,
        when=WhenClause(all=[Condition(fact="usage", op=Operator.GT, value=50)]),
        then=ThenClause(conclusion="deal_safe", reason="r"),
    )
    rs = RuleSet(rules=[rule])
    result = compute_premortem(
        ruleset=rs,
        facts={"usage": 80},
        goal="deal_safe",
        candidate_interventions=[{"usage": 30}, {"unrelated": "x"}],
    )
    assert len(result.failure_interventions) == 1
    assert "usage" in result.load_bearing_assumptions


# ── workflow drift ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_first_baseline_zero_drift(session: Session) -> None:
    """First measurement -> baseline seeded, no drift to report yet."""
    report = check_workflow_drift(
        session,
        org_id="o",
        dim="channel_mix",
        current_distribution={"email": 0.7, "slack": 0.3},
    )
    assert report.drift_score == 0.0
    assert report.drift_detected is False


@pytest.mark.unit
def test_no_drift_on_stable_distribution(session: Session) -> None:
    """Same distribution measured twice -> no drift."""
    check_workflow_drift(
        session,
        org_id="o",
        dim="channel_mix",
        current_distribution={"email": 0.7, "slack": 0.3},
    )
    session.commit()
    report = check_workflow_drift(
        session,
        org_id="o",
        dim="channel_mix",
        current_distribution={"email": 0.7, "slack": 0.3},
    )
    assert report.drift_score == 0.0


@pytest.mark.unit
def test_drift_detected_on_workflow_shift(session: Session) -> None:
    """Per MD §1.1.3: customer shifts from email-dominant to Slack-dominant -> drift."""
    # Q1: email-heavy
    check_workflow_drift(
        session,
        org_id="o",
        dim="channel_mix",
        current_distribution={"email": 0.8, "slack": 0.1, "calendar": 0.1},
    )
    session.commit()

    # Q2: Slack-heavy (workflow shifted)
    report = check_workflow_drift(
        session,
        org_id="o",
        dim="channel_mix",
        current_distribution={"email": 0.1, "slack": 0.8, "calendar": 0.1},
        threshold=0.3,
    )
    assert report.drift_detected is True
    assert report.drift_score > 0.3


@pytest.mark.unit
def test_drift_per_org_isolation(session: Session) -> None:
    """Org A baseline doesn't influence Org B's drift detection."""
    check_workflow_drift(
        session,
        org_id="org_a",
        dim="channel_mix",
        current_distribution={"email": 0.9, "slack": 0.1},
    )
    session.commit()

    # Org B's first measurement should be zero drift, NOT compared to Org A
    report = check_workflow_drift(
        session,
        org_id="org_b",
        dim="channel_mix",
        current_distribution={"email": 0.1, "slack": 0.9},
    )
    assert report.drift_detected is False  # first baseline for org_b
