"""Tests for core.neural.fusion — symbolic-wins policy."""

from __future__ import annotations

import pytest

from core.neural.fusion import FusionConflict, fuse
from core.reasoning.derivation import DerivationStep, ProofTree
from core.reasoning.rule_engine import ChainResult


def _result(*, resolved: bool, conclusion: str = "", has_hard: bool = False) -> ChainResult:
    steps = (
        [
            DerivationStep(
                rule_id="r1",
                rule_module="sales",
                rule_priority=10,
                matched_facts={},
                conclusion=conclusion,
                reason="test",
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


@pytest.mark.unit
def test_symbolic_resolved_wins_over_neural() -> None:
    """Per MD: symbolic always wins when it has a conclusion."""
    sym = _result(resolved=True, conclusion="churn_risk_high")
    result = fuse(symbolic=sym, neural_conclusion="something_else")
    assert result.winner == "symbolic"
    assert result.chosen_conclusion == "churn_risk_high"
    assert result.rejected_neural is True


@pytest.mark.unit
def test_neural_violating_hard_constraint_rejected() -> None:
    """Per MD: neural that violates hard constraint -> REJECTED regardless."""
    sym = _result(resolved=False)
    conflict = FusionConflict(
        rule_id="r_hard",
        rule_conclusion="block_or_escalate",
        neural_value="approve",
    )
    result = fuse(
        symbolic=sym,
        neural_conclusion="approve",
        neural_violates_hard=True,
        hard_conflicts=[conflict],
    )
    assert result.rejected_neural is True
    assert result.winner == "neither"
    assert len(result.conflicts) == 1


@pytest.mark.unit
def test_neural_fills_silent_gap() -> None:
    """Symbolic silent + neural produced something + no hard violation -> neural accepted."""
    sym = _result(resolved=False)
    result = fuse(symbolic=sym, neural_conclusion="suggest_followup")
    assert result.winner == "neural"
    assert result.chosen_conclusion == "suggest_followup"
    assert not result.rejected_neural


@pytest.mark.unit
def test_both_silent_yields_neither() -> None:
    sym = _result(resolved=False)
    result = fuse(symbolic=sym, neural_conclusion=None)
    assert result.winner == "neither"
    assert result.chosen_conclusion == ""


@pytest.mark.unit
def test_symbolic_hard_resolved_wins_even_over_valid_neural() -> None:
    """Per MD fusion priority: hard symbolic conclusion is authoritative."""
    sym = _result(resolved=True, conclusion="hard_block", has_hard=True)
    result = fuse(symbolic=sym, neural_conclusion="proceed")
    assert result.winner == "symbolic"
    assert result.chosen_conclusion == "hard_block"
