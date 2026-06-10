"""Symbolic what-if simulation.

Per MD g-i-2 §2.1.2:
- Apply a hypothetical change to a COPY of facts/graph
- Re-run forward chaining
- Report the delta + its derivation
- Validity is bounded by the asserted model — every output carries a disclaimer

Per MD g-i-4 (premortem mode):
- Failure-mode what-if: "what would have to be true for this goal to FAIL?"
- Propagate adverse interventions over the asserted graph
- Output: failure paths + which assumptions they hinge on

This module provides both modes. The disclaimer is included in the return value
so g-i-6 narrator can never strip it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.reasoning.derivation import ProofTree
from core.reasoning.rule_engine import ChainResult, ForwardChainer
from core.reasoning.rule_loader import RuleSet

DISCLAIMER = (
    "Counterfactual results are bounded by the asserted model; they are not "
    "predictions of reality. Treat as exploration of the rule system, not ground truth."
)


@dataclass(frozen=True)
class WhatIfResult:
    """Output of a what-if intervention."""

    baseline_conclusion: str
    intervention: dict[str, Any]
    counterfactual_conclusion: str
    delta: dict[str, Any]
    counterfactual_proof: ProofTree
    disclaimer: str = DISCLAIMER


def whatif(
    *,
    ruleset: RuleSet,
    baseline_facts: dict[str, Any],
    intervention: dict[str, Any],
) -> WhatIfResult:
    """Apply intervention on a copy of facts; re-run engine; report delta."""
    chainer = ForwardChainer(ruleset)
    baseline: ChainResult = chainer.run(baseline_facts)

    new_facts = dict(baseline_facts)
    new_facts.update(intervention)
    cf: ChainResult = chainer.run(new_facts)

    delta = _diff(baseline.proof.derived_facts, cf.proof.derived_facts)
    return WhatIfResult(
        baseline_conclusion=baseline.proof.final_conclusion,
        intervention=intervention,
        counterfactual_conclusion=cf.proof.final_conclusion,
        delta=delta,
        counterfactual_proof=cf.proof,
    )


@dataclass(frozen=True)
class PremortemResult:
    """Output of premortem analysis: what would have to break for `goal` to fail?"""

    goal: str
    failure_interventions: list[dict[str, Any]]
    failure_paths: list[ProofTree]
    load_bearing_assumptions: list[str]
    disclaimer: str = DISCLAIMER


def premortem(
    *,
    ruleset: RuleSet,
    facts: dict[str, Any],
    goal: str,
    candidate_interventions: list[dict[str, Any]],
) -> PremortemResult:
    """For each candidate adverse intervention, check if it breaks the goal.

    `candidate_interventions` are domain-specific: caller supplies (e.g. for a
    deal-close goal: "discount_pct=50", "deal_age_days=120", "champion_left=True").

    Returns the interventions that DO cause failure + the proofs showing how.
    The fact names referenced in failed interventions are the "load-bearing
    assumptions" — the things that, if they changed, would break the goal.
    """
    chainer = ForwardChainer(ruleset)
    baseline = chainer.run(facts)
    baseline_holds = baseline.proof.derived_facts.get(goal, False)

    failures: list[dict[str, Any]] = []
    paths: list[ProofTree] = []
    assumptions: set[str] = set()

    for intervention in candidate_interventions:
        cf_facts = dict(facts)
        cf_facts.update(intervention)
        cf = chainer.run(cf_facts)
        cf_holds = cf.proof.derived_facts.get(goal, False)
        # Failure = goal held before, does NOT hold after
        if baseline_holds and not cf_holds:
            failures.append(intervention)
            paths.append(cf.proof)
            assumptions.update(intervention.keys())

    return PremortemResult(
        goal=goal,
        failure_interventions=failures,
        failure_paths=paths,
        load_bearing_assumptions=sorted(assumptions),
    )


# ─── helpers ────────────────────────────────────────────────────────────────


def _diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Return entries in b that differ from a (or are new)."""
    out: dict[str, Any] = {}
    for k, v in b.items():
        if a.get(k) != v:
            out[k] = v
    for k in a:
        if k not in b:
            out[k] = None  # removed
    return out
