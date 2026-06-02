"""Tests for core.guardrails.grounding — claim -> source-fact verification."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.graph.store import FactRow
from core.guardrails.grounding import verify_grounding


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_fact(
    session: Session,
    *,
    org_id: str = "o",
    subject: str,
    predicate: str,
    object_: str,
) -> FactRow:
    f = FactRow(
        org_id=org_id,
        subject=subject,
        predicate=predicate,
        object=object_,
        source_item_id="mem_x",
        asserted_by_type="source",
        asserted_by_id="mem_x",
        confidence=1.0,
        created_at=datetime.now(UTC),
    )
    session.add(f)
    session.flush()
    return f


@pytest.mark.unit
def test_grounded_claim_returns_supporting_fact(session: Session) -> None:
    _seed_fact(session, subject="bob", predicate="emailed", object_="acme_corp_yesterday")
    result = verify_grounding(session, org_id="o", claims=["bob emailed acme_corp_yesterday"])
    assert result.grounded_count == 1
    assert result.grounding_score == 1.0
    assert result.claims[0].grounded is True
    assert result.claims[0].supporting_fact_id is not None


@pytest.mark.unit
def test_ungrounded_claim_flagged(session: Session) -> None:
    """Claim mentions facts NOT in the store -> ungrounded."""
    _seed_fact(session, subject="bob", predicate="emailed", object_="acme")
    result = verify_grounding(session, org_id="o", claims=["alice phoned globex about pricing"])
    assert result.grounded_count == 0
    assert result.grounding_score == 0.0
    assert result.claims[0].grounded is False


@pytest.mark.unit
def test_partial_grounding_score(session: Session) -> None:
    _seed_fact(session, subject="bob", predicate="emailed", object_="acme_corp")
    result = verify_grounding(
        session,
        org_id="o",
        claims=[
            "bob emailed acme_corp",  # grounded
            "alice phoned globex",  # ungrounded
        ],
    )
    assert result.grounded_count == 1
    assert result.total_count == 2
    assert result.grounding_score == 0.5


@pytest.mark.unit
def test_empty_claim_marked_ungrounded(session: Session) -> None:
    result = verify_grounding(session, org_id="o", claims=["", "   "])
    assert all(not c.grounded for c in result.claims)


@pytest.mark.unit
def test_stop_words_only_marked_ungrounded(session: Session) -> None:
    """A claim like 'the is a' has no significant tokens -> ungrounded."""
    result = verify_grounding(session, org_id="o", claims=["the is a"])
    assert result.claims[0].grounded is False
    assert "significant" in result.claims[0].reason.lower()


@pytest.mark.unit
def test_org_isolation(session: Session) -> None:
    """Fact in org A does NOT ground claim in org B."""
    _seed_fact(session, org_id="org_a", subject="bob", predicate="emailed", object_="acme")
    result = verify_grounding(session, org_id="org_b", claims=["bob emailed acme"])
    assert result.grounded_count == 0
