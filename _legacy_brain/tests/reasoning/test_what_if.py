"""Tests for core.reasoning.what_if — counterfactual + premortem."""

from __future__ import annotations

import pytest

from core.reasoning.rule_loader import (
    Condition,
    Operator,
    Rule,
    RuleSet,
    ThenClause,
    WhenClause,
)
from core.reasoning.what_if import DISCLAIMER, premortem, whatif


def _rule(
    id: str, when: list[tuple[str, str, object]], conclusion: str, priority: int = 10
) -> Rule:
    conds = [Condition(fact=f, op=Operator(op), value=v) for f, op, v in when]
    return Rule(
        id=id,
        module="sales",
        priority=priority,
        when=WhenClause(all=conds),
        then=ThenClause(conclusion=conclusion, reason="r"),
    )


@pytest.mark.unit
def test_whatif_intervention_changes_conclusion() -> None:
    rs = RuleSet(rules=[_rule("r1", [("x", ">", 50)], "high")])
    result = whatif(
        ruleset=rs,
        baseline_facts={"x": 20},
        intervention={"x": 80},
    )
    assert result.baseline_conclusion == ""  # didn't fire at x=20
    assert result.counterfactual_conclusion == "high"
    assert result.disclaimer == DISCLAIMER


@pytest.mark.unit
def test_whatif_no_change_when_intervention_irrelevant() -> None:
    rs = RuleSet(rules=[_rule("r1", [("x", ">", 50)], "high")])
    result = whatif(
        ruleset=rs,
        baseline_facts={"x": 80},
        intervention={"unrelated": "value"},
    )
    assert result.baseline_conclusion == "high"
    assert result.counterfactual_conclusion == "high"


@pytest.mark.unit
def test_premortem_identifies_failure_intervention() -> None:
    """Goal holds at baseline. One adverse intervention breaks it → identified."""
    rs = RuleSet(rules=[_rule("r1", [("usage", ">", 50)], "deal_safe")])
    facts = {"usage": 80}
    interventions = [
        {"usage": 30},  # this BREAKS the goal
        {"unrelated_field": "x"},  # this doesn't
    ]
    result = premortem(
        ruleset=rs,
        facts=facts,
        goal="deal_safe",
        candidate_interventions=interventions,
    )
    assert len(result.failure_interventions) == 1
    assert result.failure_interventions[0] == {"usage": 30}
    assert "usage" in result.load_bearing_assumptions


@pytest.mark.unit
def test_premortem_empty_when_no_intervention_breaks_goal() -> None:
    rs = RuleSet(rules=[_rule("r1", [("usage", ">", 50)], "deal_safe")])
    facts = {"usage": 80}
    result = premortem(
        ruleset=rs,
        facts=facts,
        goal="deal_safe",
        candidate_interventions=[{"unrelated": "v"}],
    )
    assert result.failure_interventions == []
    assert result.load_bearing_assumptions == []


@pytest.mark.unit
def test_whatif_disclaimer_always_present() -> None:
    """g-i-6 narrator cannot strip the disclaimer — it's part of the dataclass."""
    rs = RuleSet(rules=[_rule("r1", [("x", ">", 0)], "any")])
    result = whatif(ruleset=rs, baseline_facts={"x": 1}, intervention={"x": 2})
    assert "bounded by the asserted model" in result.disclaimer.lower()
