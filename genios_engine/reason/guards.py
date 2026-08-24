"""Contract guards shared by the reasoning kernel and its persistence verifier.

These predicates answer one question: *may this reasoner output be trusted as a decision input?*
They are deliberately public and dependency-free.  The orchestrator applies them the moment a
reasoner returns, and `reason.store` re-applies the identical functions when it re-derives a
persisted run — two independent callers proving the same law, so a forged or drifted audit row
cannot pass verification by satisfying a weaker copy of the rule.

They must stay pure and total: given the same result and request they always reach the same
verdict, with no clock, database, or configuration lookup.
"""

from __future__ import annotations

from typing import Any

from genios_engine.contracts.reasoning import ReasonerResult

# The only score components a reasoner may move, and the only pipeline stages a check may claim.
# Both are closed sets: an unknown component or stage is a deployment fault, never a silent no-op.
CANDIDATE_COMPONENTS: frozenset[str] = frozenset({
    "impact", "success", "urgency", "effort", "risk"})
CHECK_STAGES: frozenset[str] = frozenset({
    "precondition", "constraint", "policy", "permission", "safety", "cost_benefit", "ranking"})


def required_missing(request: Any, required: tuple[str, ...]) -> tuple[str, ...]:
    """Return the declared fields this context cannot honestly supply.

    A field counts as missing when it is absent *or* when Layer 2 explicitly published it as
    missing — an unknown fact and a known-absent fact must both stop reasoning rather than be
    silently treated as a default value.  `neighbor:` scopes the lookup to the neighbourhood facts.
    """
    missing = set()
    declared_missing = set(request.context.missing_fields)
    for field in required:
        if field.startswith("neighbor:"):
            name = field.split(":", 1)[1]
            absent = name not in request.context.neighbor_facts
        else:
            absent = field not in request.context.facts
        if absent or field in declared_missing:
            missing.add(field)
    return tuple(sorted(missing))


def validate_candidate_effects(result: ReasonerResult, play_ids: set[str]) -> None:
    """Reject decision effects that reference anything the capability never declared."""
    for name, value in result.metrics.items():
        if name.endswith("_bp") and (isinstance(value, bool) or not isinstance(value, int)
                                      or not 0 <= value <= 10_000):
            raise ValueError(f"reasoner metric {name} must be integer basis points")
    for adjustment in result.adjustments:
        if adjustment.play_id not in play_ids:
            raise ValueError(f"adjustment references unknown play: {adjustment.play_id}")
        if adjustment.component not in CANDIDATE_COMPONENTS:
            raise ValueError(f"adjustment references unknown component: {adjustment.component}")
    for check in result.checks:
        if check.play_id not in play_ids:
            raise ValueError(f"check references unknown play: {check.play_id}")
        if check.stage not in CHECK_STAGES:
            raise ValueError(f"check references unsupported stage: {check.stage}")


def validate_evidence_references(result: ReasonerResult, request: Any) -> None:
    """Every citation must resolve inside the frozen context snapshot.

    This is what makes evidence replayable: a reasoner cannot cite a row it fetched itself, only
    what the selector already froze into the snapshot the decision was hashed against.
    """
    available = {item.evidence_id for item in request.context.evidence}
    referenced = set(result.evidence_ids)
    referenced.update(evidence_id for finding in result.findings
                      for evidence_id in finding.evidence_ids)
    referenced.update(evidence_id for adjustment in result.adjustments
                      for evidence_id in adjustment.evidence_ids)
    unknown = sorted(referenced - available)
    if unknown:
        raise ValueError("reasoner references evidence outside the context snapshot: "
                         + ", ".join(unknown))


__all__ = ["CANDIDATE_COMPONENTS", "CHECK_STAGES", "required_missing",
           "validate_candidate_effects", "validate_evidence_references"]
