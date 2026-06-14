"""Integration tests for core.decision.decide() — the full 11-step engine pipeline.

These tests wire up real ForwardChainer + ConfidenceScorer + (fake) Gateway and
verify the orchestration logic end-to-end against a SQLite session.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.decision import DecideRequest, decide
from core.decision_store import DecisionRow
from core.foundations.db import Base
from core.graph.store import FactRow
from core.neural.client import LLMCall, LLMResponse
from core.neural.cost_guard import BudgetExceededError
from core.neural.gateway import Gateway
from core.reasoning.rule_loader import (
    Condition,
    Operator,
    Rule,
    RuleSet,
    ThenClause,
    WhenClause,
)
from core.reflection.human_flag import Route

# ── fakes ──────────────────────────────────────────────────────────────────


class _FakeLLM:
    def __init__(self, text: str | None = None) -> None:
        self._text = text or '{"conclusion": "neural_says_proceed"}'
        self.calls: list[LLMCall] = []

    def call(self, call: LLMCall) -> LLMResponse:
        self.calls.append(call)
        return LLMResponse(
            text=self._text,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0001,
            model_id="test",
            latency_ms=5,
        )


class _OkCostGuard:
    def require_capacity(self, org_id: str) -> None:
        return None

    def charge(self, org_id: str, cost_usd: float) -> object:
        return None


class _HaltedCostGuard:
    def require_capacity(self, org_id: str) -> None:
        raise BudgetExceededError("test halt")

    def charge(self, org_id: str, cost_usd: float) -> object:
        return None


class _NeuralOutput(BaseModel):
    conclusion: str


# ── fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _rule(
    *,
    id: str,
    when: list[tuple[str, str, Any]],
    conclusion: str,
    priority: int = 10,
    hard: bool = False,
) -> Rule:
    conds = [Condition(fact=f, op=Operator(op), value=v) for f, op, v in when]
    return Rule(
        id=id,
        module="sales",
        priority=priority,
        when=WhenClause(all=conds),
        then=ThenClause(conclusion=conclusion, reason="r"),
        hard=hard,
    )


def _seed_grounding_fact(session: Session) -> None:
    """Seed a fact so the grounding check has something to match."""
    f = FactRow(
        org_id="o",
        subject="deal",
        predicate="stalled",
        object="negotiation",
        source_item_id="mem_x",
        asserted_by_type="rule",
        asserted_by_id="r1",
        confidence=1.0,
        created_at=datetime.now(UTC),
    )
    session.add(f)
    session.flush()


# ── tests ──────────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_pipeline_symbolic_resolved_path(session: Session) -> None:
    """Symbolic rule fires; no neural call; route based on confidence."""
    _seed_grounding_fact(session)
    rs = RuleSet(
        rules=[
            _rule(
                id="r1",
                when=[("days_in_stage", ">", 21)],
                conclusion="deal_stalled_negotiation",
            )
        ]
    )
    llm = _FakeLLM()
    gateway = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]

    result = decide(
        session,
        gateway=gateway,
        request=DecideRequest(
            org_id="o",
            query={"q": "is this deal stalled?"},
            facts={"days_in_stage": 22},
            ruleset=rs,
            reversible=True,
        ),
    )
    session.commit()

    assert result.path == "symbolic"
    assert result.conclusion == "deal_stalled_negotiation"
    assert llm.calls == []  # symbolic-first: no LLM call
    assert result.decision_id

    # Decision was persisted
    row = session.get(DecisionRow, result.decision_id)
    assert row is not None
    assert row.path == "symbolic"
    assert row.route == result.route.value


@pytest.mark.unit
def test_pipeline_hard_constraint_blocks_neural(session: Session) -> None:
    """Hard rule fires + LLM proposed something conflicting -> fusion rejects neural."""
    rs = RuleSet(
        rules=[
            _rule(
                id="hard_block",
                when=[("discount_pct", ">", 20), ("margin_pct", "<", 40)],
                conclusion="block_or_escalate",
                hard=True,
            )
        ]
    )
    llm = _FakeLLM('{"conclusion": "approve_discount"}')
    gateway = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]

    result = decide(
        session,
        gateway=gateway,
        request=DecideRequest(
            org_id="o",
            query={"q": "approve?"},
            facts={"discount_pct": 30, "margin_pct": 35},
            ruleset=rs,
            reversible=False,
            gap_description="suggest action",
            neural_system_prompt="you are sales",
            neural_output_schema=_NeuralOutput,
        ),
    )
    session.commit()

    # Hard rule fires -> symbolic wins. Confidence is 0 (constraint_pass=False because
    # candidate 'block_or_escalate' is itself the violation conclusion). Routes FLAG.
    # The IMPORTANT property: neural's 'approve_discount' MUST NOT be the conclusion.
    assert result.conclusion != "approve_discount"
    # The hard rule's veto conclusion must be the final
    assert "block" in result.conclusion.lower() or result.conclusion == "block_or_escalate"


@pytest.mark.unit
def test_pipeline_neural_validated_routes_notify(session: Session) -> None:
    """Symbolic silent + neural produces a SCHEMA-VALID non-empty answer.

    Under the path-aware confidence weights (NEURAL_PATH_WEIGHTS), a valid
    LLM gap-fill that passes hard constraints earns enough llm_validation
    credit to clear theta_flag (0.45). On a reversible action this lands
    at NOTIFY, not FLAG — that's the intended 80/20 router behavior so
    customers don't see every neural answer flagged for human review.
    """
    rs = RuleSet(rules=[])  # nothing fires symbolically
    llm = _FakeLLM('{"conclusion": "do_something_random"}')
    gateway = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]

    result = decide(
        session,
        gateway=gateway,
        request=DecideRequest(
            org_id="o",
            query={"q": "what should I do?"},
            facts={},
            ruleset=rs,
            reversible=True,
            gap_description="anything",
            neural_system_prompt="you are an agent",
            neural_output_schema=_NeuralOutput,
        ),
    )
    session.commit()

    # Valid LLM output + reversible -> NOTIFY (between theta_flag 0.45 and theta_act 0.75)
    assert result.route == Route.NOTIFY
    assert result.path in {"neural", "hybrid"}
    # Confidence should land in the NOTIFY band — proves llm_validation weight kicked in
    assert 0.45 <= result.confidence < 0.75


@pytest.mark.unit
def test_pipeline_neural_empty_output_routes_flag(session: Session) -> None:
    """Symbolic silent + neural returns empty -> llm_validation=0 -> FLAG.

    Guarantees the path-aware weights still flag the case the original test
    cared about: when the LLM refuses to answer (empty conclusion) we must
    NOT promote the response — flag for human review.
    """
    rs = RuleSet(rules=[])
    llm = _FakeLLM('{"conclusion": ""}')
    gateway = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]

    result = decide(
        session,
        gateway=gateway,
        request=DecideRequest(
            org_id="o",
            query={"q": "what should I do?"},
            facts={},
            ruleset=rs,
            reversible=True,
            gap_description="anything",
            neural_system_prompt="you are an agent",
            neural_output_schema=_NeuralOutput,
        ),
    )
    session.commit()

    assert result.route == Route.FLAG
    assert result.confidence < 0.45


@pytest.mark.unit
def test_pipeline_persona_redline_forces_flag(session: Session) -> None:
    """User redline overrides high confidence -> FLAG."""
    _seed_grounding_fact(session)
    rs = RuleSet(
        rules=[_rule(id="r1", when=[("x", "==", 1)], conclusion="deal_stalled_negotiation")]
    )
    gateway = Gateway(_FakeLLM(), _OkCostGuard())  # type: ignore[arg-type]

    result = decide(
        session,
        gateway=gateway,
        request=DecideRequest(
            org_id="o",
            query={"q": "?"},
            facts={"x": 1},
            ruleset=rs,
            reversible=True,
            user_redlines_hit=["never_auto_close"],
        ),
    )
    session.commit()
    assert result.route == Route.FLAG
    assert result.routing.redline_triggered is True


@pytest.mark.unit
def test_pipeline_cost_guard_halt_records_halted(session: Session) -> None:
    """Budget exhausted -> gateway halts -> decision still emitted with halted=True."""
    rs = RuleSet(rules=[])
    gateway = Gateway(_FakeLLM(), _HaltedCostGuard())  # type: ignore[arg-type]

    result = decide(
        session,
        gateway=gateway,
        request=DecideRequest(
            org_id="o",
            query={"q": "?"},
            facts={},
            ruleset=rs,
            gap_description="anything",
            neural_system_prompt="x",
            neural_output_schema=_NeuralOutput,
        ),
    )
    session.commit()
    assert result.halted_by_cost_guard is True


@pytest.mark.unit
def test_pipeline_high_stakes_low_confidence_reflects_and_flags(session: Session) -> None:
    """High stakes + low confidence -> reflection fires -> promoted to FLAG."""
    rs = RuleSet(rules=[])
    gateway = Gateway(_FakeLLM(), _OkCostGuard())  # type: ignore[arg-type]

    result = decide(
        session,
        gateway=gateway,
        request=DecideRequest(
            org_id="o",
            query={"q": "?"},
            facts={},
            ruleset=rs,
            reversible=True,
            irreversibility=1.0,
            blast_radius=1.0,
        ),
    )
    session.commit()
    # No symbolic + no neural wiring -> conclusion empty -> low confidence -> reflection fires
    assert result.reflected is True
    assert result.route == Route.FLAG
