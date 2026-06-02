"""Forward + backward chaining rule engine.

Per MD g-i-2 §2.1.2:
- Forward chaining (data-driven): start from facts, fire rules whose `when` matches,
  assert their `then` into working memory, loop until fixpoint (no new conclusions).
- Backward chaining (goal-driven): can we prove goal G? Find rules concluding G,
  recursively prove their premises.
- Conflict resolution (deterministic): priority -> specificity -> id (alphabetic for stability)
- Hard rules (`hard: true`) fire normally but their conclusions are marked so fusion
  (in g-i-2 neural layer) knows neural cannot override them.

The engine is PURE — it doesn't touch DB, doesn't call LLMs. Input: facts + ruleset.
Output: ChainResult with proof tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.foundations.telemetry import get_logger
from core.reasoning.derivation import DerivationStep, ProofTree
from core.reasoning.rule_loader import Rule, RuleSet

log = get_logger(__name__)


@dataclass(frozen=True)
class ChainResult:
    """Output of a forward / backward chain pass."""

    proof: ProofTree
    resolved: bool  # True if at least one rule fired (or goal proven)
    has_hard: bool  # True if any hard rule fired


# ─────────────────────────────────────────────────────────────────────────────
# Forward chaining
# ─────────────────────────────────────────────────────────────────────────────


class ForwardChainer:
    """Data-driven inference. Fire matching rules until fixpoint."""

    def __init__(self, ruleset: RuleSet, max_iterations: int = 100) -> None:
        self._ruleset = ruleset
        self._max_iterations = max_iterations

    def run(self, facts: dict[str, Any]) -> ChainResult:
        """Fire applicable rules in priority order until fixpoint or iteration cap."""
        working: dict[str, Any] = dict(facts)
        derived: dict[str, Any] = {}
        steps: list[DerivationStep] = []
        fired_ids: set[str] = set()
        has_hard = False

        for iteration in range(self._max_iterations):
            # Recompute agenda over current working memory; deterministic conflict resolution
            agenda = [
                r
                for r in self._ruleset.by_priority()
                if r.id not in fired_ids and r.when.matches(working)
            ]
            if not agenda:
                log.debug("forward_fixpoint_reached", iterations=iteration, fired=len(steps))
                break

            # Fire one per iteration so agenda re-evaluates after each conclusion
            rule = agenda[0]
            step = self._fire(rule, working)
            steps.append(step)
            fired_ids.add(rule.id)
            if rule.hard:
                has_hard = True

            # Assert conclusion into working memory as a fact named after the rule's conclusion
            # Convention: conclusion string becomes a boolean fact True; callers can read it.
            working[rule.then.conclusion] = True
            derived[rule.then.conclusion] = True
        else:
            log.warning(
                "forward_max_iterations_hit",
                cap=self._max_iterations,
                fired=len(steps),
            )

        final = steps[-1].conclusion if steps else ""
        return ChainResult(
            proof=ProofTree(
                final_conclusion=final,
                steps=steps,
                initial_facts=dict(facts),
                derived_facts=derived,
            ),
            resolved=bool(steps),
            has_hard=has_hard,
        )

    @staticmethod
    def _fire(rule: Rule, facts: dict[str, Any]) -> DerivationStep:
        """Build a DerivationStep with only the facts the rule's when-clause referenced."""
        referenced = _referenced_facts(rule)
        matched = {k: facts[k] for k in referenced if k in facts}
        return DerivationStep(
            rule_id=rule.id,
            rule_module=rule.module,
            rule_priority=rule.priority,
            matched_facts=matched,
            conclusion=rule.then.conclusion,
            recommend=rule.then.recommend,
            reason=rule.then.reason,
            hard=rule.hard,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Backward chaining
# ─────────────────────────────────────────────────────────────────────────────


class BackwardChainer:
    """Goal-driven inference. Can we prove `goal`?"""

    def __init__(self, ruleset: RuleSet, max_depth: int = 10) -> None:
        self._ruleset = ruleset
        self._max_depth = max_depth
        # Index rules by conclusion for quick lookup
        self._by_conclusion: dict[str, list[Rule]] = {}
        for r in ruleset.active():
            self._by_conclusion.setdefault(r.then.conclusion, []).append(r)

    def prove(self, goal: str, facts: dict[str, Any]) -> ChainResult:
        """Try to prove `goal` from `facts`. Returns ChainResult (resolved=True iff proven)."""
        steps: list[DerivationStep] = []
        proven, has_hard = self._prove_recursive(goal, dict(facts), steps, depth=0)
        return ChainResult(
            proof=ProofTree(
                final_conclusion=goal if proven else "",
                steps=steps,
                initial_facts=dict(facts),
                derived_facts={s.conclusion: True for s in steps},
            ),
            resolved=proven,
            has_hard=has_hard,
        )

    def _prove_recursive(
        self,
        goal: str,
        facts: dict[str, Any],
        steps: list[DerivationStep],
        depth: int,
    ) -> tuple[bool, bool]:
        """Returns (proven, has_hard_in_proof)."""
        if depth > self._max_depth:
            log.warning("backward_max_depth_hit", goal=goal)
            return False, False

        # Already a fact?
        if facts.get(goal) is True:
            return True, False

        # Try each rule that concludes `goal`, in priority order
        candidates = sorted(
            self._by_conclusion.get(goal, []),
            key=lambda r: (-r.priority, -r.when.specificity, r.id),
        )
        for rule in candidates:
            # First check: does this rule's when-clause hold with current facts?
            if not rule.when.matches(facts):
                # Try to prove missing premises recursively (when-clauses with `all`)
                if not self._try_prove_premises(rule, facts, steps, depth):
                    continue

            # Rule fires
            step = ForwardChainer._fire(rule, facts)
            steps.append(step)
            facts[rule.then.conclusion] = True
            has_hard = rule.hard
            return True, has_hard

        return False, False

    def _try_prove_premises(
        self, rule: Rule, facts: dict[str, Any], steps: list[DerivationStep], depth: int
    ) -> bool:
        """Recursively try to prove each missing premise of an `all`-clause rule."""
        if rule.when.all is None:
            # 'any' clause — backward chaining on disjunctions is more complex; skip in v1
            return False

        for cond in rule.when.all:
            if cond.evaluate(facts):
                continue
            # Try to prove the missing fact as a goal
            proven, _ = self._prove_recursive(cond.fact, facts, steps, depth + 1)
            if not proven:
                return False
        return rule.when.matches(facts)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _referenced_facts(rule: Rule) -> set[str]:
    """All fact names a rule's when-clause references."""
    out: set[str] = set()
    for cond in (rule.when.all or []) + (rule.when.any or []):
        out.add(cond.fact)
    return out
