"""Atlas Learning Validation and Governance — deterministic permission, not analysis.

Validation asks whether the evidence can support a claim. Governance asks whether the tenant is
allowed to retain or publish that otherwise-valid claim. Keeping those answers separate prevents
high confidence from silently overriding privacy, approval or retention policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from genios_engine.contracts.learning import BrainTarget, LearningObject, LearningState


@dataclass(frozen=True, slots=True)
class LearningPolicy:
    enabled: bool = True
    min_observations: int = 3
    min_distinct_days: int = 2
    min_confidence_bp: int = 6_500
    max_noise_bp: int = 2_500
    max_conflict_bp: int = 2_500
    min_business_value_bp: int = 1_000
    max_temporary_ttl_hours: int = 720
    require_human_targets: frozenset[BrainTarget] = frozenset({
        BrainTarget.KNOWLEDGE_SUGGESTION, BrainTarget.ORGANIZATION})
    blocked_subject_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    state: LearningState
    reason_code: str


def validate_learning(item: LearningObject, policy: LearningPolicy) -> ValidationResult:
    """Unit 11: evidence, repetition, noise, conflict, freshness and value checks."""
    evidence = item.evidence
    # An explicit leased memory is intentionally one-shot; permanence rules do not apply because
    # the value can only enter Runtime and must expire.
    if item.target is BrainTarget.RUNTIME:
        if item.expires_at is None:
            return ValidationResult(LearningState.REJECTED, "runtime_ttl_missing")
        ttl_hours = int((item.expires_at - item.observed_at).total_seconds() // 3600)
        if ttl_hours > policy.max_temporary_ttl_hours:
            return ValidationResult(LearningState.REJECTED, "runtime_ttl_exceeds_policy")
        if not bool(item.metadata.get("explicit")):
            return ValidationResult(LearningState.REJECTED, "runtime_memory_not_explicit")
        return ValidationResult(LearningState.VALIDATED, "explicit_temporary_memory")
    if evidence.observations < policy.min_observations:
        return ValidationResult(LearningState.OBSERVED, "repetition_pending")
    if evidence.distinct_days < policy.min_distinct_days:
        return ValidationResult(LearningState.CANDIDATE, "distinct_days_pending")
    if evidence.noise_bp > policy.max_noise_bp:
        return ValidationResult(LearningState.REJECTED, "noise_exceeds_policy")
    if evidence.conflict_bp > policy.max_conflict_bp:
        return ValidationResult(LearningState.REJECTED, "conflict_exceeds_policy")
    if evidence.confidence_bp < policy.min_confidence_bp:
        return ValidationResult(LearningState.CANDIDATE, "confidence_pending")
    if evidence.business_value_bp < policy.min_business_value_bp:
        return ValidationResult(LearningState.REJECTED, "business_value_below_policy")
    if evidence.freshness_bp == 0:
        return ValidationResult(LearningState.REJECTED, "evidence_stale")
    return ValidationResult(LearningState.VALIDATED, "evidence_validated")


def govern_learning(item: LearningObject, policy: LearningPolicy) -> ValidationResult:
    """Choose temporary, promoted or human-review after validation has passed."""
    if not policy.enabled:
        return ValidationResult(LearningState.REJECTED, "learning_disabled")
    if any(item.subject_key.startswith(prefix) for prefix in policy.blocked_subject_prefixes):
        return ValidationResult(LearningState.REJECTED, "subject_blocked_by_policy")
    if item.target is BrainTarget.RUNTIME:
        return ValidationResult(LearningState.TEMPORARY, "temporary_by_contract")
    if item.target in policy.require_human_targets:
        return ValidationResult(LearningState.HUMAN_REVIEW, "human_review_required")
    return ValidationResult(LearningState.PROMOTED, "automatic_promotion_allowed")


def lifecycle_path(item: LearningObject, policy: LearningPolicy) -> tuple[ValidationResult, ...]:
    """The complete legal path for a new immutable object, ready for an audit ledger."""
    validation = validate_learning(item, policy)
    if validation.state is LearningState.OBSERVED:
        return (validation,)
    if validation.state is LearningState.CANDIDATE:
        return (ValidationResult(LearningState.CANDIDATE, validation.reason_code),)
    if validation.state is LearningState.REJECTED:
        # Rejection from Observed is legal. When repetition was met, preserve the Candidate step.
        if item.evidence.observations >= policy.min_observations:
            return (ValidationResult(LearningState.CANDIDATE, "repetition_met"), validation)
        return (validation,)
    governed = govern_learning(item, policy)
    return (ValidationResult(LearningState.CANDIDATE, "repetition_met"), validation,
            ValidationResult(LearningState.GOVERNED, "governance_evaluated"), governed)


__all__ = ["LearningPolicy", "ValidationResult", "govern_learning", "lifecycle_path",
           "validate_learning"]
