"""Tests for core.reasoning.rule_engine — forward + backward chaining + conflict resolution."""

from __future__ import annotations

import pytest

from core.reasoning.rule_engine import BackwardChainer, ForwardChainer
from core.reasoning.rule_loader import Condition, Operator, Rule, RuleSet, ThenClause, WhenClause


def _rule(
    *,
    id: str,
    when: list[tuple[str, str, object]],
    conclusion: str,
    priority: int = 10,
    hard: bool = False,
    use_any: bool = False,
) -> Rule:
    conds = [Condition(fact=f, op=Operator(op), value=v) for f, op, v in when]
    when_clause = WhenClause(any=conds) if use_any else WhenClause(all=conds)
    return Rule(
        id=id,
        module="sales",
        priority=priority,
        when=when_clause,
        then=ThenClause(conclusion=conclusion, reason=f"rule {id} fired"),
        hard=hard,
    )


# ── Forward chaining ───────────────────────────────────────────────────────


@pytest.mark.unit
def test_forward_single_rule_fires() -> None:
    rs = RuleSet(rules=[_rule(id="r1", when=[("x", ">", 5)], conclusion="x_big")])
    result = ForwardChainer(rs).run({"x": 10})
    assert result.resolved
    assert result.proof.final_conclusion == "x_big"
    assert "x" in result.proof.steps[0].matched_facts
    assert result.proof.derived_facts["x_big"] is True


@pytest.mark.unit
def test_forward_no_match_returns_unresolved() -> None:
    rs = RuleSet(rules=[_rule(id="r1", when=[("x", ">", 100)], conclusion="big")])
    result = ForwardChainer(rs).run({"x": 5})
    assert not result.resolved
    assert result.proof.steps == []


@pytest.mark.unit
def test_forward_chains_to_fixpoint() -> None:
    """Rule 1 concludes 'A'; rule 2 fires when A is in working memory."""
    rs = RuleSet(
        rules=[
            _rule(id="r1", when=[("x", ">", 5)], conclusion="A"),
            _rule(id="r2", when=[("A", "==", True)], conclusion="B"),
        ]
    )
    result = ForwardChainer(rs).run({"x": 10})
    assert result.resolved
    assert len(result.proof.steps) == 2
    assert result.proof.derived_facts.get("A") is True
    assert result.proof.derived_facts.get("B") is True
    assert result.proof.final_conclusion == "B"


@pytest.mark.unit
def test_forward_priority_breaks_ties() -> None:
    """Highest priority rule fires first; lower-priority that also matches fires second."""
    rs = RuleSet(
        rules=[
            _rule(id="low", when=[("x", "==", 1)], conclusion="L", priority=10),
            _rule(id="high", when=[("x", "==", 1)], conclusion="H", priority=100),
        ]
    )
    result = ForwardChainer(rs).run({"x": 1})
    assert result.proof.rules_fired() == ["high", "low"]


@pytest.mark.unit
def test_forward_specificity_breaks_ties_when_priority_same() -> None:
    """When priority equal, more specific (more conditions) fires first."""
    rs = RuleSet(
        rules=[
            _rule(
                id="general",
                when=[("x", "==", 1)],
                conclusion="G",
                priority=10,
            ),
            _rule(
                id="specific",
                when=[("x", "==", 1), ("y", "==", 2)],
                conclusion="S",
                priority=10,
            ),
        ]
    )
    result = ForwardChainer(rs).run({"x": 1, "y": 2})
    assert result.proof.rules_fired() == ["specific", "general"]


@pytest.mark.unit
def test_forward_hard_rule_marked_in_proof() -> None:
    rs = RuleSet(
        rules=[
            _rule(id="r1", when=[("discount_pct", ">", 30)], conclusion="block", hard=True),
        ]
    )
    result = ForwardChainer(rs).run({"discount_pct": 50})
    assert result.has_hard
    assert result.proof.has_hard_constraint() is True


@pytest.mark.unit
def test_forward_real_sales_scenario_deal_stalled() -> None:
    """Real test case per MD: stage stall rule fires correctly."""
    rs = RuleSet(
        rules=[
            _rule(
                id="stage_stall",
                when=[
                    ("days_in_current_stage", ">", 21),
                    ("stage", "in", ["negotiation", "proposal"]),
                ],
                conclusion="deal_stalled",
                priority=60,
            )
        ]
    )
    result = ForwardChainer(rs).run({"days_in_current_stage": 22, "stage": "negotiation"})
    assert result.resolved
    assert result.proof.final_conclusion == "deal_stalled"


# ── Backward chaining ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_backward_proves_immediate_fact() -> None:
    rs = RuleSet(rules=[])
    result = BackwardChainer(rs).prove("x", {"x": True})
    assert result.resolved


@pytest.mark.unit
def test_backward_proves_via_rule() -> None:
    rs = RuleSet(rules=[_rule(id="r1", when=[("a", "==", 1)], conclusion="goal")])
    result = BackwardChainer(rs).prove("goal", {"a": 1})
    assert result.resolved
    assert result.proof.final_conclusion == "goal"


@pytest.mark.unit
def test_backward_proves_chained_rules() -> None:
    rs = RuleSet(
        rules=[
            _rule(id="r1", when=[("x", ">", 5)], conclusion="A"),
            _rule(id="r2", when=[("A", "==", True)], conclusion="goal"),
        ]
    )
    result = BackwardChainer(rs).prove("goal", {"x": 10})
    assert result.resolved


@pytest.mark.unit
def test_backward_returns_unresolved_when_unprovable() -> None:
    rs = RuleSet(rules=[_rule(id="r1", when=[("a", "==", 99)], conclusion="goal")])
    result = BackwardChainer(rs).prove("goal", {"a": 1})
    assert not result.resolved
