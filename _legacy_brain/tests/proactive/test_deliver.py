"""Tests for core.proactive.deliver — 80/20 routing + per-user push budget."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.proactive.deliver import deliver_insight
from core.proactive.store import PushBudgetRow
from core.proactive.types import DeliveryRoute, Insight, InsightType


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _insight() -> Insight:
    return Insight(
        id="ins_1",
        org_id="o",
        type=InsightType.RISK,
        primary_entity="acme",
        derivation_chain=[],
        grounding_refs=[],
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )


@pytest.mark.unit
def test_high_confidence_reversible_routes_autonomous(session: Session) -> None:
    d = deliver_insight(
        session, insight=_insight(), user_id="u", confidence=0.9, reversible=True, urgent=False
    )
    assert d.route == DeliveryRoute.AUTONOMOUS
    assert d.channel == "autonomous_action"
    assert d.budget_consumed is False


@pytest.mark.unit
def test_high_confidence_irreversible_urgent_consumes_budget(session: Session) -> None:
    d = deliver_insight(
        session, insight=_insight(), user_id="u", confidence=0.9, reversible=False, urgent=True
    )
    assert d.route == DeliveryRoute.NOTIFY
    assert d.channel == "interrupt"
    assert d.budget_consumed is True


@pytest.mark.unit
def test_high_confidence_irreversible_non_urgent_digests(session: Session) -> None:
    d = deliver_insight(
        session, insight=_insight(), user_id="u", confidence=0.9, reversible=False, urgent=False
    )
    assert d.route == DeliveryRoute.NOTIFY
    assert d.channel == "digest"
    assert d.budget_consumed is False


@pytest.mark.unit
def test_low_confidence_always_flag(session: Session) -> None:
    for rev in (True, False):
        d = deliver_insight(
            session, insight=_insight(), user_id="u", confidence=0.2, reversible=rev, urgent=True
        )
        assert d.route == DeliveryRoute.FLAG
        assert d.channel == "flag_queue"


@pytest.mark.unit
def test_mid_confidence_irreversible_flags(session: Session) -> None:
    d = deliver_insight(
        session, insight=_insight(), user_id="u", confidence=0.55, reversible=False, urgent=True
    )
    assert d.route == DeliveryRoute.FLAG


@pytest.mark.unit
def test_push_budget_blocks_excess_interrupts(session: Session) -> None:
    """Per MD: per-user budget cap; overflow -> digest, not dropped."""
    # Consume budget up to limit (default 5)
    for i in range(5):
        d = deliver_insight(
            session,
            insight=_insight(),
            user_id="u",
            confidence=0.9,
            reversible=False,
            urgent=True,
        )
        assert d.channel == "interrupt", f"call {i} should interrupt"
    session.commit()

    # 6th call should fall back to digest
    overflow = deliver_insight(
        session, insight=_insight(), user_id="u", confidence=0.9, reversible=False, urgent=True
    )
    session.commit()
    assert overflow.channel == "digest"
    assert overflow.budget_consumed is False


@pytest.mark.unit
def test_per_user_budget_isolation(session: Session) -> None:
    """User A's budget consumption does NOT affect User B."""
    # Burn through user A's budget
    for _ in range(5):
        deliver_insight(
            session,
            insight=_insight(),
            user_id="user_a",
            confidence=0.9,
            reversible=False,
            urgent=True,
        )
    session.commit()

    # User B should still have full budget
    d = deliver_insight(
        session,
        insight=_insight(),
        user_id="user_b",
        confidence=0.9,
        reversible=False,
        urgent=True,
    )
    assert d.channel == "interrupt"


@pytest.mark.unit
def test_budget_row_persists_correctly(session: Session) -> None:
    deliver_insight(
        session,
        insight=_insight(),
        user_id="u",
        confidence=0.9,
        reversible=False,
        urgent=True,
        today="2026-06-02",
    )
    session.commit()

    row = session.execute(select(PushBudgetRow).where(PushBudgetRow.user_id == "u")).scalar_one()
    assert row.interrupts_used == 1
    assert row.date == "2026-06-02"
