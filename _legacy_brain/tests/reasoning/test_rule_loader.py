"""Tests for core.reasoning.rule_loader — YAML schema + load + validate."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.reasoning.rule_loader import (
    Condition,
    Operator,
    Rule,
    RuleLoadError,
    RuleSet,
    ThenClause,
    WhenClause,
    load_rules,
)


def _write_yaml(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


# ── Condition evaluation ───────────────────────────────────────────────────


@pytest.mark.unit
def test_condition_eq() -> None:
    c = Condition(fact="x", op=Operator.EQ, value=5)
    assert c.evaluate({"x": 5}) is True
    assert c.evaluate({"x": 6}) is False


@pytest.mark.unit
def test_condition_gt_numeric() -> None:
    c = Condition(fact="usage_drop_pct", op=Operator.GT, value=40)
    assert c.evaluate({"usage_drop_pct": 65}) is True
    assert c.evaluate({"usage_drop_pct": 40}) is False


@pytest.mark.unit
def test_condition_in() -> None:
    c = Condition(fact="stage", op=Operator.IN, value=["negotiation", "proposal"])
    assert c.evaluate({"stage": "negotiation"}) is True
    assert c.evaluate({"stage": "closed"}) is False


@pytest.mark.unit
def test_condition_contains_list() -> None:
    c = Condition(fact="tags", op=Operator.CONTAINS, value="urgent")
    assert c.evaluate({"tags": ["urgent", "deal"]}) is True
    assert c.evaluate({"tags": ["normal"]}) is False


@pytest.mark.unit
def test_condition_missing_fact_returns_false() -> None:
    c = Condition(fact="x", op=Operator.EQ, value=5)
    assert c.evaluate({}) is False


# ── WhenClause ─────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_when_all_requires_all_match() -> None:
    w = WhenClause(
        all=[
            Condition(fact="a", op=Operator.EQ, value=1),
            Condition(fact="b", op=Operator.EQ, value=2),
        ]
    )
    assert w.matches({"a": 1, "b": 2}) is True
    assert w.matches({"a": 1, "b": 3}) is False


@pytest.mark.unit
def test_when_any_requires_any_match() -> None:
    w = WhenClause(
        any=[
            Condition(fact="a", op=Operator.EQ, value=1),
            Condition(fact="b", op=Operator.EQ, value=2),
        ]
    )
    assert w.matches({"a": 1, "b": 99}) is True
    assert w.matches({"a": 99, "b": 99}) is False


@pytest.mark.unit
def test_when_rejects_empty_list() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        WhenClause(all=[])


@pytest.mark.unit
def test_specificity_orders_by_condition_count() -> None:
    w1 = WhenClause(all=[Condition(fact="a", op=Operator.EQ, value=1)])
    w2 = WhenClause(
        all=[
            Condition(fact="a", op=Operator.EQ, value=1),
            Condition(fact="b", op=Operator.EQ, value=2),
        ]
    )
    assert w2.specificity > w1.specificity


# ── RuleSet ordering ────────────────────────────────────────────────────────


@pytest.mark.unit
def test_ruleset_by_priority_desc_then_specificity_then_id() -> None:
    high = Rule(
        id="z_high",
        module="sales",
        priority=100,
        when=WhenClause(all=[Condition(fact="x", op=Operator.EQ, value=1)]),
        then=ThenClause(conclusion="c", reason="r"),
    )
    low = Rule(
        id="a_low",
        module="sales",
        priority=10,
        when=WhenClause(all=[Condition(fact="y", op=Operator.EQ, value=1)]),
        then=ThenClause(conclusion="c2", reason="r"),
    )
    rs = RuleSet(rules=[low, high])
    ordered = rs.by_priority()
    assert ordered[0].id == "z_high"
    assert ordered[1].id == "a_low"


@pytest.mark.unit
def test_inactive_rules_excluded() -> None:
    active_rule = Rule(
        id="active",
        module="sales",
        priority=10,
        when=WhenClause(all=[Condition(fact="x", op=Operator.EQ, value=1)]),
        then=ThenClause(conclusion="c", reason="r"),
        active=True,
    )
    inactive = Rule(
        id="inactive",
        module="sales",
        priority=10,
        when=WhenClause(all=[Condition(fact="x", op=Operator.EQ, value=1)]),
        then=ThenClause(conclusion="c", reason="r"),
        active=False,
    )
    rs = RuleSet(rules=[active_rule, inactive])
    assert len(rs.active()) == 1
    assert rs.active()[0].id == "active"


# ── load_rules (YAML) ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_load_rules_valid_yaml(tmp_path: Path) -> None:
    p = _write_yaml(
        tmp_path,
        "churn.yaml",
        """
- id: churn_usage_silence
  module: sales
  priority: 80
  when:
    all:
      - fact: usage_drop_pct_30d
        op: ">"
        value: 40
      - fact: days_since_last_contact
        op: ">"
        value: 14
  then:
    conclusion: churn_risk_high
    recommend: trigger_reengagement_sequence
    reason: Usage down >40% in 30d AND no contact in 14d
  hard: false
""",
    )
    rs = load_rules([p])
    assert len(rs.rules) == 1
    rule = rs.rules[0]
    assert rule.id == "churn_usage_silence"
    assert rule.when.matches({"usage_drop_pct_30d": 65, "days_since_last_contact": 18}) is True


@pytest.mark.unit
def test_load_rules_duplicate_id_rejected(tmp_path: Path) -> None:
    p1 = _write_yaml(
        tmp_path,
        "a.yaml",
        """
- id: dup
  module: sales
  priority: 10
  when: {all: [{fact: x, op: "==", value: 1}]}
  then: {conclusion: c, reason: r}
""",
    )
    p2 = _write_yaml(
        tmp_path,
        "b.yaml",
        """
- id: dup
  module: sales
  priority: 10
  when: {all: [{fact: x, op: "==", value: 2}]}
  then: {conclusion: c, reason: r}
""",
    )
    with pytest.raises(RuleLoadError) as ei:
        load_rules([p1, p2])
    assert "duplicate" in str(ei.value).lower()


@pytest.mark.unit
def test_load_rules_invalid_schema_rejected(tmp_path: Path) -> None:
    p = _write_yaml(
        tmp_path,
        "bad.yaml",
        """
- id: bad
  module: sales
  # missing when + then
""",
    )
    with pytest.raises(RuleLoadError):
        load_rules([p])


@pytest.mark.unit
def test_load_rules_unknown_field_rejected(tmp_path: Path) -> None:
    """Pydantic extra='forbid' catches typos in YAML."""
    p = _write_yaml(
        tmp_path,
        "typo.yaml",
        """
- id: typo
  module: sales
  priority: 10
  when: {all: [{fact: x, op: "==", value: 1}]}
  then: {conclusion: c, reason: r}
  hardcoded: true
""",
    )
    with pytest.raises(RuleLoadError):
        load_rules([p])
