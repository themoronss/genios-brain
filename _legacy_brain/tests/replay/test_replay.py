"""Tests for core.replay.replay_decision — deterministic symbolic reconstruction."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.foundations.db import Base
from core.reasoning.rule_loader import (
    Condition,
    Operator,
    Rule,
    RuleSet,
    ThenClause,
    WhenClause,
)
from core.replay import replay_decision


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _rs() -> RuleSet:
    return RuleSet(
        rules=[
            Rule(
                id="r1",
                module="sales",
                priority=10,
                when=WhenClause(all=[Condition(fact="x", op=Operator.GT, value=5)]),
                then=ThenClause(conclusion="x_big", reason="r"),
            )
        ]
    )


@pytest.mark.unit
def test_replay_symbolic_matches(session: Session) -> None:
    """Same facts + same rules -> same conclusion -> matched=True."""
    result = replay_decision(
        session,
        decision_id="dec_1",
        original_conclusion="x_big",
        original_path="symbolic",
        org_id="o",
        as_of_version=0,
        input_facts={"x": 10},
        ruleset=_rs(),
    )
    assert result.matched is True
    assert result.replayed_conclusion == "x_big"


@pytest.mark.unit
def test_replay_symbolic_differs(session: Session) -> None:
    """Original said X but replay says Y -> matched=False (signals data drift)."""
    result = replay_decision(
        session,
        decision_id="dec_1",
        original_conclusion="x_big",
        original_path="symbolic",
        org_id="o",
        as_of_version=0,
        input_facts={"x": 1},  # NOT > 5 -> rule won't fire
        ruleset=_rs(),
    )
    assert result.matched is False
    assert result.replayed_conclusion == ""


@pytest.mark.unit
def test_replay_neural_path_acknowledged_not_re_derived(session: Session) -> None:
    """Neural outputs are not deterministic — replay won't try to re-run the LLM."""
    result = replay_decision(
        session,
        decision_id="dec_1",
        original_conclusion="llm_said_x",
        original_path="neural",
        org_id="o",
        as_of_version=0,
        input_facts={},
        ruleset=_rs(),
    )
    assert result.matched is False
    assert "neural-only" in result.reason.lower()
