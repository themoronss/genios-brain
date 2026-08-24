"""Hard-constraint enforcement.

Per MD g-i-2 §2.3.1:
- Outputs violating domain hard rules are blocked outright
- These are the `hard: true` rules from §2.1.2
- Hard constraint violation → blocked output + audit log

Implementation: given a set of facts AND a candidate conclusion (typically from
neural output), check every hard rule. If a hard rule fires on the facts and
its conclusion CONFLICTS with the candidate, that's a violation.

The conflict notion is intentionally simple in v1: a candidate that asserts X
when a hard rule asserts NOT-X (or vice versa, modeled as different conclusion
strings on the same target topic) is a conflict. For richer policies, rule
authors can write explicit "block" conclusions and the engine treats them as
veto signals.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.reasoning.rule_engine import ForwardChainer
from core.reasoning.rule_loader import RuleSet

log = get_logger(__name__)


@dataclass(frozen=True)
class ConstraintViolation:
    """Detail of a single hard-rule violation."""

    rule_id: str
    rule_conclusion: str
    candidate_conclusion: str
    matched_facts: dict[str, Any]


@dataclass(frozen=True)
class ConstraintCheckResult:
    """Output of check_hard_constraints()."""

    ok: bool
    violations: list[ConstraintViolation]


def check_hard_constraints(
    *,
    org_id: str,
    ruleset: RuleSet,
    facts: dict[str, Any],
    candidate_conclusion: str,
    block_conclusions: Iterable[str] = ("block", "block_or_escalate", "veto"),
) -> ConstraintCheckResult:
    """Run hard rules over facts. Flag conflicts with the candidate.

    Conflict criteria (v1):
    1. A hard rule's conclusion is in `block_conclusions` — that's a veto, always blocks.
    2. A hard rule's conclusion is the negation of the candidate (string starts with "not_"
       or vice-versa) — interpreted as conflict.

    Any violation -> ok=False; audit-logged.
    """
    hard_rules = [r for r in ruleset.active() if r.hard]
    if not hard_rules:
        return ConstraintCheckResult(ok=True, violations=[])

    # Run forward chain restricted to hard rules to get matched_facts per fired rule
    hard_ruleset = RuleSet(rules=hard_rules)
    result = ForwardChainer(hard_ruleset).run(facts)

    violations: list[ConstraintViolation] = []
    for step in result.proof.steps:
        if _is_veto(step.conclusion, block_conclusions):
            violations.append(
                ConstraintViolation(
                    rule_id=step.rule_id,
                    rule_conclusion=step.conclusion,
                    candidate_conclusion=candidate_conclusion,
                    matched_facts=dict(step.matched_facts),
                )
            )
            continue
        if _is_negation(step.conclusion, candidate_conclusion):
            violations.append(
                ConstraintViolation(
                    rule_id=step.rule_id,
                    rule_conclusion=step.conclusion,
                    candidate_conclusion=candidate_conclusion,
                    matched_facts=dict(step.matched_facts),
                )
            )

    if violations:
        log.warning(
            "hard_constraint_violation",
            org_id=org_id,
            candidate=candidate_conclusion,
            violation_count=len(violations),
            rule_ids=[v.rule_id for v in violations],
        )
        audit.record(
            org_id=org_id,
            actor_type="system",
            actor_id="guardrails.constraints",
            action="config_changed",
            target_type="decision_candidate",
            target_id=candidate_conclusion[:64],
            metadata={
                "outcome": "blocked",
                "violated_rule_ids": [v.rule_id for v in violations],
                "violation_count": len(violations),
            },
        )

    return ConstraintCheckResult(ok=not violations, violations=violations)


# ─── helpers ────────────────────────────────────────────────────────────────


def _is_veto(rule_conclusion: str, block_set: Iterable[str]) -> bool:
    rc = rule_conclusion.strip().lower()
    return any(rc == b.lower() or rc.startswith(b.lower() + "_") for b in block_set)


def _is_negation(rule_conclusion: str, candidate: str) -> bool:
    rc = rule_conclusion.strip().lower()
    cd = candidate.strip().lower()
    if not rc or not cd:
        return False
    return rc == f"not_{cd}" or cd == f"not_{rc}"
