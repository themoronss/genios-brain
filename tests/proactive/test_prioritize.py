"""Tests for core.proactive.prioritize — multiplicative scoring + VoI gate + suppression."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.proactive.feedback_store import FeedbackStore
from core.proactive.prioritize import prioritize_insight
from core.proactive.types import Insight, InsightType


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _insight(*, org_id: str = "o", entity: str = "acme") -> Insight:
    return Insight(
        id="ins_1",
        org_id=org_id,
        type=InsightType.RISK,
        primary_entity=entity,
        root_cause_edge="e1",
        derivation_chain=[{"rule_id": "r1", "conclusion": "churn_risk_high"}],
        grounding_refs=[],
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )


# ── multiplicative property (the critical MD requirement) ──────────────────


@pytest.mark.unit
def test_any_near_zero_factor_kills_priority() -> None:
    """Per MD: priority = impact * urgency * relevance * novelty * confidence.
    Multiplicative — ANY near-zero factor kills the insight.
    """
    high_priority = prioritize_insight(
        _insight(), impact=0.9, urgency=0.9, relevance=0.9, confidence=0.9
    )
    # Now zero out relevance — entire priority should collapse
    low_relevance = prioritize_insight(
        _insight(), impact=0.9, urgency=0.9, relevance=0.01, confidence=0.9
    )
    assert low_relevance.priority < high_priority.priority * 0.05


@pytest.mark.unit
def test_full_signal_above_threshold() -> None:
    s = prioritize_insight(_insight(), impact=0.9, urgency=0.9, relevance=0.9, confidence=0.9)
    assert s.above_threshold is True
    assert s.priority > 0.5


# ── VoI gate ───────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_voi_gate_blocks_low_expected_value() -> None:
    """EV(info) <= attention_cost -> push blocked."""
    s = prioritize_insight(
        _insight(),
        impact=0.2,
        urgency=0.2,
        relevance=0.2,
        confidence=0.2,
        attention_cost=0.5,  # high
        estimated_value_if_acted=1.0,
    )
    assert s.voi_passed is False
    assert s.above_threshold is False


@pytest.mark.unit
def test_voi_gate_passes_high_value() -> None:
    s = prioritize_insight(
        _insight(),
        impact=0.9,
        urgency=0.9,
        relevance=0.9,
        confidence=0.9,
        attention_cost=0.1,
        estimated_value_if_acted=10.0,
    )
    assert s.voi_passed is True


# ── KL-novelty ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_no_baseline_means_full_novelty() -> None:
    """No recent baseline -> novelty = 1.0 (treat as novel)."""
    s = prioritize_insight(_insight(), impact=0.5, urgency=0.5, relevance=0.5, confidence=0.5)
    assert s.breakdown["novelty"] == 1.0


@pytest.mark.unit
def test_similar_to_baseline_low_novelty() -> None:
    """When current signal matches baseline mean closely -> novelty near 0."""
    s = prioritize_insight(
        _insight(),
        impact=0.5,
        urgency=0.5,
        relevance=0.5,
        confidence=0.5,
        recent_baseline=[0.5, 0.5, 0.5, 0.5, 0.5],
    )
    assert s.breakdown["novelty"] < 0.1


# ── suppression from feedback ──────────────────────────────────────────────


@pytest.mark.unit
def test_never_show_hard_mutes(session: Session) -> None:
    """never_show feedback -> suppression_factor 0 -> priority 0."""
    store = FeedbackStore(session)
    ins = _insight()
    store.record(org_id="o", user_id="u", signature_hash=ins.signature.hash(), action="never_show")
    session.commit()

    s = prioritize_insight(
        ins,
        impact=0.9,
        urgency=0.9,
        relevance=0.9,
        confidence=0.9,
        user_id="u",
        feedback_store=store,
    )
    assert s.suppression_factor == 0.0
    assert s.priority == 0.0


@pytest.mark.unit
def test_repeat_dismissals_halve_priority(session: Session) -> None:
    """Each dismissal halves priority (capped at 0.1x)."""
    store = FeedbackStore(session)
    ins = _insight()
    sig = ins.signature.hash()
    for _ in range(3):
        store.record(org_id="o", user_id="u", signature_hash=sig, action="dismissed")
    session.commit()

    s = prioritize_insight(
        ins,
        impact=0.9,
        urgency=0.9,
        relevance=0.9,
        confidence=0.9,
        user_id="u",
        feedback_store=store,
    )
    # 0.5^3 = 0.125 (above 0.1 cap)
    assert 0.1 <= s.suppression_factor <= 0.2


# ── input validation ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_rejects_out_of_range_factor() -> None:
    with pytest.raises(ValueError):
        prioritize_insight(_insight(), impact=1.5, urgency=0.5, relevance=0.5, confidence=0.5)
