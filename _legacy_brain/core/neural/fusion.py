"""Fusion policy: symbolic always wins; neural fills only silent gaps.

Per MD g-i-2 §2.2.2:
    if neural_output violates a HARD symbolic constraint:
        reject neural_output                  # symbolic ALWAYS wins
    elif symbolic is silent on this sub-question:
        accept neural_output (as gap-fill) IF it passed validation + grounding
    else:
        prefer symbolic

No "blending". Symbolic is authoritative; neural is a gap-filler.

Pure functional. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.reasoning.rule_engine import ChainResult


@dataclass(frozen=True)
class FusionConflict:
    """Detail of a hard-constraint vs neural conflict (logged for audit)."""

    rule_id: str
    rule_conclusion: str
    neural_value: Any


@dataclass(frozen=True)
class FusionResult:
    """Output of fuse(). winner indicates which source the engine should emit."""

    winner: str  # "symbolic" | "neural" | "neither"
    chosen_conclusion: str
    rejected_neural: bool
    conflicts: list[FusionConflict]
    reason: str


def fuse(
    *,
    symbolic: ChainResult,
    neural_conclusion: str | None,
    neural_violates_hard: bool = False,
    hard_conflicts: list[FusionConflict] | None = None,
) -> FusionResult:
    """Apply the symbolic-wins fusion policy.

    Args:
        symbolic: ForwardChainer/BackwardChainer result
        neural_conclusion: what the LLM produced (None if no neural call was made)
        neural_violates_hard: True if neural output failed a hard constraint check
                              (typically computed by guardrails.constraints before fusion)
        hard_conflicts: optional list of which hard rules the neural output violated

    Returns:
        FusionResult with winner = "symbolic" | "neural" | "neither"
    """
    conflicts = list(hard_conflicts or [])

    # Case 1: neural violates hard constraint -> reject neural, prefer symbolic (or empty)
    if neural_violates_hard:
        return FusionResult(
            winner="symbolic" if symbolic.resolved else "neither",
            chosen_conclusion=symbolic.proof.final_conclusion if symbolic.resolved else "",
            rejected_neural=True,
            conflicts=conflicts,
            reason="neural output violated hard symbolic constraint; rejected per fusion policy",
        )

    # Case 2: symbolic resolved -> symbolic wins (regardless of neural)
    if symbolic.resolved:
        return FusionResult(
            winner="symbolic",
            chosen_conclusion=symbolic.proof.final_conclusion,
            rejected_neural=neural_conclusion is not None,
            conflicts=conflicts,
            reason="symbolic resolved; neural deferred to symbolic per policy",
        )

    # Case 3: symbolic silent + neural produced something -> accept neural as gap-fill
    if neural_conclusion is not None:
        return FusionResult(
            winner="neural",
            chosen_conclusion=neural_conclusion,
            rejected_neural=False,
            conflicts=conflicts,
            reason="symbolic silent; neural gap-fill accepted",
        )

    # Case 4: both silent
    return FusionResult(
        winner="neither",
        chosen_conclusion="",
        rejected_neural=False,
        conflicts=conflicts,
        reason="symbolic silent + no neural output; no conclusion",
    )
