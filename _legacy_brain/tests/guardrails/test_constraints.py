"""Tests for core.guardrails.constraints — hard-rule violation detection."""

from __future__ import annotations

import pytest

from core.guardrails.constraints import check_hard_constraints
from core.reasoning.rule_loader import (
    Condition,
    Operator,
    Rule,
    RuleSet,
    ThenClause,
    WhenClause,
)


def _hard_rule(
    *, id: str, when: list[tuple[str, str, object]], conclusion: str, priority: int = 100
) -> Rule:
    conds = [Condition(fact=f, op=Operator(op), value=v) for f, op, v in when]
    return Rule(
        id=id,
        module="sales",
        priority=priority,
        when=WhenClause(all=conds),
        then=ThenClause(conclusion=conclusion, reason="hard veto"),
        hard=True,
    )


@pytest.mark.unit
def test_veto_conclusion_blocks_candidate() -> None:
    """Real MD test case: discount > 20% with margin < 40% -> block_or_escalate."""
    rs = RuleSet(
        rules=[
            _hard_rule(
                id="pricing_discount_margin_guard",
                when=[("discount_pct", ">", 20), ("gross_margin_pct", "<", 40)],
                conclusion="block_or_escalate",
            )
        ]
    )
    result = check_hard_constraints(
        org_id="o",
        ruleset=rs,
        facts={"discount_pct": 30, "gross_margin_pct": 35},
        candidate_conclusion="approve_discount",
    )
    assert result.ok is False
    assert len(result.violations) == 1
    assert result.violations[0].rule_id == "pricing_discount_margin_guard"


@pytest.mark.unit
def test_no_violation_when_hard_rule_does_not_fire() -> None:
    """Hard rule exists but conditions don't match -> ok=True."""
    rs = RuleSet(
        rules=[
            _hard_rule(
                id="veto",
                when=[("discount_pct", ">", 50)],
                conclusion="block_or_escalate",
            )
        ]
    )
    result = check_hard_constraints(
        org_id="o",
        ruleset=rs,
        facts={"discount_pct": 10},
        candidate_conclusion="approve",
    )
    assert result.ok is True
    assert result.violations == []


@pytest.mark.unit
def test_negation_conclusion_detected() -> None:
    """If a hard rule concludes 'not_X' and candidate is 'X', that's a conflict."""
    rs = RuleSet(
        rules=[
            _hard_rule(
                id="not_safe",
                when=[("trust_score", "<", 30)],
                conclusion="not_approve",
            )
        ]
    )
    result = check_hard_constraints(
        org_id="o",
        ruleset=rs,
        facts={"trust_score": 10},
        candidate_conclusion="approve",
    )
    assert result.ok is False


@pytest.mark.unit
def test_soft_rules_excluded() -> None:
    """Non-hard rules are NEVER violations even if they conflict."""
    soft = Rule(
        id="soft_block",
        module="sales",
        priority=10,
        when=WhenClause(all=[Condition(fact="x", op=Operator.GT, value=0)]),
        then=ThenClause(conclusion="block_or_escalate", reason="soft"),
        hard=False,
    )
    rs = RuleSet(rules=[soft])
    result = check_hard_constraints(
        org_id="o", ruleset=rs, facts={"x": 5}, candidate_conclusion="approve"
    )
    assert result.ok is True


@pytest.mark.unit
def test_no_hard_rules_returns_ok() -> None:
    rs = RuleSet(rules=[])
    result = check_hard_constraints(
        org_id="o", ruleset=rs, facts={}, candidate_conclusion="anything"
    )
    assert result.ok is True
