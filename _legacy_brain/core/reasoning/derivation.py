"""Proof tree — the engine's first-class output (per MD g-i-2 §2.1.2).

Every conclusion the engine emits comes with an ordered ProofTree showing
the (fact -> rule -> fact -> ...) chain that produced it. This is THE
differentiator over a black-box LLM and the input to g-i-6 narrator.

Design:
- Immutable, Pydantic types (frozen). Easy to ship as JSON to g-i-6 / g-i-7.
- Each DerivationStep captures: matched_facts, rule_id, rule_priority, conclusion.
- ProofTree is the ordered chain + the final conclusion + the originating facts.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DerivationStep(BaseModel):
    """One step in the proof chain — a rule firing on a set of facts."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: str
    rule_module: str
    rule_priority: int
    matched_facts: dict[str, Any] = Field(
        ...,
        description="Subset of facts that satisfied this rule's when-clause (keys -> values)",
    )
    conclusion: str
    recommend: str | None = None
    reason: str
    hard: bool = False


class ProofTree(BaseModel):
    """An ordered chain of DerivationSteps + the final conclusion.

    Steps are in firing order. The last step's conclusion is the final output
    (unless the rule_engine emitted a single-step conclusion).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    final_conclusion: str
    steps: list[DerivationStep] = Field(default_factory=list)
    initial_facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Facts present at the start of reasoning (before any rule fired)",
    )
    derived_facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Facts added during reasoning (conclusions of fired rules)",
    )

    def rules_fired(self) -> list[str]:
        """Convenience: ordered rule_ids fired."""
        return [s.rule_id for s in self.steps]

    def has_hard_constraint(self) -> bool:
        """True if any step came from a hard rule (informs fusion + routing)."""
        return any(s.hard for s in self.steps)


def empty_proof(initial_facts: dict[str, Any]) -> ProofTree:
    """Proof tree for the case where no rule fired (used by neural fallback)."""
    return ProofTree(
        final_conclusion="",
        steps=[],
        initial_facts=initial_facts,
        derived_facts={},
    )
