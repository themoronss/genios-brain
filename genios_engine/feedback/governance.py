"""Atlas Learning Validation and Governance — deterministic permission, not analysis.

Validation asks whether the evidence can support a claim. Governance asks whether the tenant is
allowed to retain or publish that otherwise-valid claim. Keeping those answers separate prevents
high confidence from silently overriding privacy, approval or retention policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from genios_engine.contracts.learning import LearningObject, LearningState, LearningTarget
from genios_engine.contracts.visibility import ORG, PUBLIC, Visibility


@dataclass(frozen=True, slots=True)
class LearningPolicy:
    revision: int = 0
    enabled: bool = True
    min_observations: int = 3
    min_distinct_days: int = 2
    min_confidence_bp: int = 6_500
    max_noise_bp: int = 2_500
    max_conflict_bp: int = 2_500
    min_business_value_bp: int = 1_000
    max_temporary_ttl_hours: int = 720
    require_human_targets: frozenset[LearningTarget] = frozenset({
        LearningTarget.KNOWLEDGE_SUGGESTION, LearningTarget.ORGANIZATION})
    blocked_targets: frozenset[LearningTarget] = frozenset()
    blocked_subject_prefixes: tuple[str, ...] = ()
    require_review_for_constrained_visibility: bool = True


@dataclass(frozen=True, slots=True)
class ValidationResult:
    state: LearningState
    reason_code: str


def preflight_learning(item: LearningObject, policy: LearningPolicy) -> ValidationResult | None:
    """Apply consent and retention gates before a proposal payload may be persisted."""
    if not policy.enabled:
        return ValidationResult(LearningState.REJECTED, "learning_disabled")
    if item.target in policy.blocked_targets:
        return ValidationResult(LearningState.REJECTED, "target_blocked_by_policy")
    if (item.target is LearningTarget.RUNTIME
            and LearningTarget.RUNTIME in policy.require_human_targets):
        return ValidationResult(LearningState.REJECTED,
                                "runtime_review_policy_unsupported")
    if any(item.subject_key.startswith(prefix) for prefix in policy.blocked_subject_prefixes):
        return ValidationResult(LearningState.REJECTED, "subject_blocked_by_policy")
    if not item.lineage_complete or not item.evidence.source_refs:
        return ValidationResult(LearningState.REJECTED, "evidence_lineage_incomplete")
    visibility = Visibility.model_validate(dict(item.visibility))
    if visibility.scope not in {PUBLIC, ORG} and not visibility.principals:
        return ValidationResult(LearningState.REJECTED, "constrained_visibility_has_no_audience")
    if (item.target is LearningTarget.ORGANIZATION
            and visibility.scope not in {PUBLIC, ORG}):
        return ValidationResult(LearningState.REJECTED,
                                "organization_learning_requires_org_visible_evidence")
    personal_subject = item.subject_key.startswith(
        ("preference:user:", "behavior:user:", "adaptive:user:"))
    if (personal_subject and (item.subject_principal is None
                             or not visibility.can_view(
                                 item.subject_principal, org_member=True))):
        return ValidationResult(LearningState.REJECTED,
                                "learned_subject_not_visible_in_evidence")
    # Retention is a consent boundary, so leased values are rejected before their payload can be
    # persisted. Validation repeats no value-bearing work after this gate.
    if item.target is LearningTarget.RUNTIME:
        if item.expires_at is None:
            return ValidationResult(LearningState.REJECTED, "runtime_ttl_missing")
        ttl_seconds = (item.expires_at - item.observed_at).total_seconds()
        if ttl_seconds > policy.max_temporary_ttl_hours * 3_600:
            return ValidationResult(LearningState.REJECTED, "runtime_ttl_exceeds_policy")
        if not bool(item.metadata.get("explicit")):
            return ValidationResult(LearningState.REJECTED, "runtime_memory_not_explicit")
    return None


def _current_freshness(item: LearningObject, eval_time: datetime | None) -> int:
    if eval_time is None:
        return item.evidence.freshness_bp
    age_seconds = max(0, int((eval_time - item.last_seen_at).total_seconds()))
    window_seconds = 28 * 24 * 60 * 60
    return min(item.evidence.freshness_bp,
               max(0, 10_000 - age_seconds * 10_000 // window_seconds))


def validate_learning(item: LearningObject, policy: LearningPolicy,
                      *, eval_time: datetime | None = None) -> ValidationResult:
    """Unit 11: evidence, repetition, noise, conflict, freshness and value checks."""
    preflight = preflight_learning(item, policy)
    if preflight is not None:
        return preflight
    evidence = item.evidence
    # An explicit leased memory is intentionally one-shot; permanence rules do not apply because
    # the value can only enter Runtime and must expire.
    if item.target is LearningTarget.RUNTIME:
        return ValidationResult(LearningState.VALIDATED, "explicit_temporary_memory")
    if evidence.independent_observations < policy.min_observations:
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
    if _current_freshness(item, eval_time) == 0:
        return ValidationResult(LearningState.REJECTED, "evidence_stale")
    return ValidationResult(LearningState.VALIDATED, "evidence_validated")


def govern_learning(item: LearningObject, policy: LearningPolicy) -> ValidationResult:
    """Choose temporary, promoted or human-review after validation has passed."""
    preflight = preflight_learning(item, policy)
    if preflight is not None:
        return preflight
    if item.target is LearningTarget.RUNTIME:
        return ValidationResult(LearningState.TEMPORARY, "temporary_by_contract")
    if item.target in policy.require_human_targets:
        return ValidationResult(LearningState.HUMAN_REVIEW, "human_review_required")
    visibility = Visibility.model_validate(dict(item.visibility))
    if (policy.require_review_for_constrained_visibility
            and visibility.scope not in {PUBLIC, ORG}
            and item.target not in {LearningTarget.METRICS,
                                    LearningTarget.KNOWLEDGE_SUGGESTION}):
        return ValidationResult(LearningState.HUMAN_REVIEW,
                                "constrained_visibility_review_required")
    return ValidationResult(LearningState.PROMOTED, "automatic_promotion_allowed")


def lifecycle_path(item: LearningObject, policy: LearningPolicy, *,
                   eval_time: datetime | None = None) -> tuple[ValidationResult, ...]:
    """The complete legal path for a new immutable object, ready for an audit ledger."""
    validation = validate_learning(item, policy, eval_time=eval_time)
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
           "preflight_learning", "validate_learning"]
