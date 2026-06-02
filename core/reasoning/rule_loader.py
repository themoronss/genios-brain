"""Load + validate YAML rules from module data.

Per MD g-i-2 §2.1.2 rule schema (LOCKED, hard to migrate):

    - id: <unique_rule_id>
      module: <module_id>
      priority: <int>
      when:
        all:
          - fact: <name>
            op: ==|!=|>|<|>=|<=|in|not_in|contains
            value: <literal>
        # OR
        any:
          - fact: <name>
            op: ...
      then:
        conclusion: <string>
        recommend: <string|null>
        reason: <string>
      hard: true|false
      active: true|false

Validation here is strict (Pydantic): unknown fields rejected, missing required rejected.
This is the contract the rule_engine consumes.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator


class Operator(StrEnum):
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GTE = ">="
    LTE = "<="
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"


class Condition(BaseModel):
    """One predicate over a fact value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    fact: str
    op: Operator
    value: Any  # comparator literal — type-flexible

    def evaluate(self, facts: dict[str, Any]) -> bool:
        if self.fact not in facts:
            return False
        actual = facts[self.fact]
        match self.op:
            case Operator.EQ:
                return bool(actual == self.value)
            case Operator.NE:
                return bool(actual != self.value)
            case Operator.GT:
                return _gt(actual, self.value)
            case Operator.LT:
                return _lt(actual, self.value)
            case Operator.GTE:
                return _gte(actual, self.value)
            case Operator.LTE:
                return _lte(actual, self.value)
            case Operator.IN:
                return _in(actual, self.value)
            case Operator.NOT_IN:
                return not _in(actual, self.value)
            case Operator.CONTAINS:
                return _contains(actual, self.value)


class WhenClause(BaseModel):
    """Predicate group. Exactly one of `all` / `any` must be set."""

    model_config = ConfigDict(extra="forbid")

    all: list[Condition] | None = None
    any: list[Condition] | None = None

    @field_validator("all", "any")
    @classmethod
    def _non_empty(cls, v: list[Condition] | None) -> list[Condition] | None:
        if v is not None and len(v) == 0:
            raise ValueError("when.all / when.any must have at least one condition")
        return v

    def matches(self, facts: dict[str, Any]) -> bool:
        if self.all is not None and self.any is not None:
            raise ValueError("when clause cannot have both 'all' and 'any'")
        if self.all is not None:
            return all(c.evaluate(facts) for c in self.all)
        if self.any is not None:
            return any(c.evaluate(facts) for c in self.any)
        return False

    @property
    def specificity(self) -> int:
        """Used for conflict resolution: more conditions = more specific = wins."""
        return len(self.all or []) + len(self.any or [])


class ThenClause(BaseModel):
    """Conclusion produced when `when` matches."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    conclusion: str
    recommend: str | None = None
    reason: str


class Rule(BaseModel):
    """A YAML rule loaded from a module's rules/*.yaml file."""

    model_config = ConfigDict(extra="forbid")

    id: str
    module: str
    priority: int = 0
    when: WhenClause
    then: ThenClause
    hard: bool = False
    active: bool = True


class RuleSet(BaseModel):
    """A loaded set of rules from one or more YAML files."""

    model_config = ConfigDict(extra="forbid")

    rules: list[Rule]

    def active(self) -> list[Rule]:
        return [r for r in self.rules if r.active]

    def by_priority(self) -> list[Rule]:
        """Sort by (priority DESC, specificity DESC, id ASC) for deterministic conflict resolution."""
        return sorted(
            self.active(),
            key=lambda r: (-r.priority, -r.when.specificity, r.id),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Loader
# ─────────────────────────────────────────────────────────────────────────────


class RuleLoadError(Exception):
    """YAML parse error, schema error, or duplicate rule id."""


def load_rules(paths: Sequence[Path | str]) -> RuleSet:
    """Load + validate rules from a list of YAML files.

    Each file must contain a list of rule dicts at the top level. Duplicate
    rule ids across files are rejected (loud error — modules must namespace).
    """
    all_rules: list[Rule] = []
    seen_ids: set[str] = set()

    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise RuleLoadError(f"Rule file not found: {path}")
        try:
            data = yaml.safe_load(path.read_text("utf-8"))
        except yaml.YAMLError as e:
            raise RuleLoadError(f"YAML parse error in {path}: {e}") from e

        if not isinstance(data, list):
            raise RuleLoadError(f"Rule file {path} must contain a top-level list")

        for idx, raw_rule in enumerate(data):
            try:
                rule = Rule.model_validate(raw_rule)
            except Exception as e:  # Pydantic ValidationError
                raise RuleLoadError(f"Invalid rule in {path}[{idx}]: {e}") from e

            if rule.id in seen_ids:
                raise RuleLoadError(
                    f"Duplicate rule id '{rule.id}' in {path}. Rule ids must be unique."
                )
            seen_ids.add(rule.id)
            all_rules.append(rule)

    return RuleSet(rules=all_rules)


# ─────────────────────────────────────────────────────────────────────────────
# Operator helpers (type-tolerant)
# ─────────────────────────────────────────────────────────────────────────────


def _coerce_numeric(v: Any) -> float | None:
    if isinstance(v, bool):
        return None  # don't coerce bool to numeric
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _gt(a: Any, b: Any) -> bool:
    na, nb = _coerce_numeric(a), _coerce_numeric(b)
    if na is None or nb is None:
        return bool(a > b) if type(a) is type(b) else False
    return na > nb


def _lt(a: Any, b: Any) -> bool:
    na, nb = _coerce_numeric(a), _coerce_numeric(b)
    if na is None or nb is None:
        return bool(a < b) if type(a) is type(b) else False
    return na < nb


def _gte(a: Any, b: Any) -> bool:
    return _gt(a, b) or a == b


def _lte(a: Any, b: Any) -> bool:
    return _lt(a, b) or a == b


def _in(actual: Any, container: Any) -> bool:
    if not isinstance(container, (list, tuple, set, dict, str)):
        return False
    return actual in container


def _contains(actual: Any, needle: Any) -> bool:
    if isinstance(actual, (list, tuple, set, str)):
        return needle in actual
    return False


# Hint for downstream — used by codebases that want to check the literal pattern
WhenKind = Literal["all", "any"]
