"""Tests for core.neural.gateway — symbolic-first routing.

Real LLM calls are NOT exercised here (require ANTHROPIC_API_KEY + Redis).
We test the routing logic by injecting fakes for LLMClient + CostGuard.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from core.neural.client import LLMCall, LLMResponse
from core.neural.cost_guard import BudgetExceededError
from core.neural.gateway import (
    Gateway,
    GatewayValidationError,
    RoutingChoice,
)
from core.reasoning.derivation import DerivationStep, ProofTree
from core.reasoning.rule_engine import ChainResult

# ── Fakes ──────────────────────────────────────────────────────────────────


class _FakeLLM:
    def __init__(self, text: str) -> None:
        self._text = text
        self.calls: list[LLMCall] = []

    def call(self, call: LLMCall) -> LLMResponse:
        self.calls.append(call)
        return LLMResponse(
            text=self._text,
            input_tokens=10,
            output_tokens=5,
            cost_usd=0.0001,
            model_id="claude-haiku-test",
            latency_ms=10,
        )


class _OkCostGuard:
    def __init__(self) -> None:
        self.charges: list[float] = []

    def require_capacity(self, org_id: str) -> None:
        return None

    def charge(self, org_id: str, cost_usd: float) -> object:
        self.charges.append(cost_usd)
        return None


class _HaltedCostGuard:
    def require_capacity(self, org_id: str) -> None:
        raise BudgetExceededError("test halt")

    def charge(self, org_id: str, cost_usd: float) -> object:
        return None


# ── Schema for parsed output ───────────────────────────────────────────────


class _Output(BaseModel):
    decision: str
    confidence: float


# ── Helpers ────────────────────────────────────────────────────────────────


def _sym(*, resolved: bool, conclusion: str = "", has_hard: bool = False) -> ChainResult:
    steps = (
        [
            DerivationStep(
                rule_id="r1",
                rule_module="sales",
                rule_priority=10,
                matched_facts={},
                conclusion=conclusion,
                reason="r",
                hard=has_hard,
            )
        ]
        if resolved
        else []
    )
    return ChainResult(
        proof=ProofTree(
            final_conclusion=conclusion if resolved else "",
            steps=steps,
            initial_facts={},
            derived_facts={conclusion: True} if resolved else {},
        ),
        resolved=resolved,
        has_hard=has_hard,
    )


# ── Routing tests ──────────────────────────────────────────────────────────


@pytest.mark.unit
def test_symbolic_hard_skips_llm() -> None:
    llm = _FakeLLM('{"decision": "x", "confidence": 1}')
    g = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]
    d = g.route(
        org_id="o",
        symbolic_result=_sym(resolved=True, conclusion="ok", has_hard=True),
    )
    assert d.route == RoutingChoice.SYMBOLIC
    assert llm.calls == []  # NO LLM call


@pytest.mark.unit
def test_symbolic_resolved_soft_skips_llm() -> None:
    llm = _FakeLLM('{"decision": "x", "confidence": 1}')
    g = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]
    d = g.route(
        org_id="o",
        symbolic_result=_sym(resolved=True, conclusion="ok"),
    )
    assert d.route == RoutingChoice.SYMBOLIC
    assert llm.calls == []


@pytest.mark.unit
def test_no_neural_wiring_returns_symbolic_default() -> None:
    llm = _FakeLLM('{"decision": "x", "confidence": 1}')
    g = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]
    d = g.route(
        org_id="o",
        symbolic_result=_sym(resolved=False),
        # no gap_description / system_prompt / output_schema -> stays symbolic
    )
    assert d.route == RoutingChoice.SYMBOLIC
    assert llm.calls == []


@pytest.mark.unit
def test_neural_gap_fill_when_unresolved() -> None:
    """Unresolved symbolic + neural wiring -> LLM call -> parsed output returned."""
    llm = _FakeLLM('{"decision": "escalate", "confidence": 0.8}')
    cost = _OkCostGuard()
    g = Gateway(llm, cost)  # type: ignore[arg-type]
    d = g.route(
        org_id="o",
        symbolic_result=_sym(resolved=False),
        gap_description="suggest action",
        gap_facts={"deal_value": 50000},
        system_prompt="You are a sales assistant.",
        output_schema=_Output,
    )
    assert d.route == RoutingChoice.NEURAL_GAP_FILL
    assert len(llm.calls) == 1
    assert d.parsed_output is not None
    assert d.parsed_output.decision == "escalate"  # type: ignore[attr-defined]
    assert cost.charges == [0.0001]  # cost guard charged


@pytest.mark.unit
def test_cost_guard_halt_blocks_call() -> None:
    llm = _FakeLLM('{"decision": "x", "confidence": 1}')
    g = Gateway(llm, _HaltedCostGuard())  # type: ignore[arg-type]
    d = g.route(
        org_id="o",
        symbolic_result=_sym(resolved=False),
        gap_description="x",
        system_prompt="y",
        output_schema=_Output,
    )
    assert d.route == RoutingChoice.HALTED
    assert llm.calls == []


@pytest.mark.unit
def test_unparseable_llm_output_rejected() -> None:
    llm = _FakeLLM("this is not json")
    g = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]
    with pytest.raises(GatewayValidationError):
        g.route(
            org_id="o",
            symbolic_result=_sym(resolved=False),
            gap_description="x",
            system_prompt="y",
            output_schema=_Output,
        )


@pytest.mark.unit
def test_invalid_schema_rejected() -> None:
    """JSON parses but missing required field -> rejected."""
    llm = _FakeLLM('{"foo": "bar"}')
    g = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]
    with pytest.raises(GatewayValidationError):
        g.route(
            org_id="o",
            symbolic_result=_sym(resolved=False),
            gap_description="x",
            system_prompt="y",
            output_schema=_Output,
        )


@pytest.mark.unit
def test_validate_fn_can_reject_otherwise_valid_output() -> None:
    """Caller-supplied constraint validator runs AFTER schema check."""
    llm = _FakeLLM('{"decision": "x", "confidence": 0.5}')
    g = Gateway(llm, _OkCostGuard())  # type: ignore[arg-type]

    def reject_all(_: Any) -> tuple[bool, str]:
        return False, "policy says no"

    with pytest.raises(GatewayValidationError) as ei:
        g.route(
            org_id="o",
            symbolic_result=_sym(resolved=False),
            gap_description="x",
            system_prompt="y",
            output_schema=_Output,
            validate_fn=reject_all,
        )
    assert "policy says no" in str(ei.value)
