"""Layer 6 · Phase 4 — Preflight + Governance (Part 6).

Two questions, asked in order. **Validation** (Unit 11, in ``units.py``) already asked *"does the
evidence support this proposal?"*. **Preflight** asks *"may this tenant even retain it?"* and runs
BEFORE any proposal is persisted — consent, blocked target/subject, lineage, ACL authority, Runtime
TTL. **Governance** then decides the lifecycle path, and it can always narrow or refuse a
high-confidence proposal but never loosen one: Organization and Knowledge and constrained-visibility
proposals go to human review; a valid Runtime lease publishes immediately as Temporary; a metric is
a measurement, not a claim to be reviewed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from genios_engine.contracts.learning import (
    LearningObject,
    LearningPolicy,
    LearningState,
    LearningTarget,
    VisibilityScope,
)


@dataclass(frozen=True, slots=True)
class PreflightResult:
    ok: bool
    reason_code: str


def preflight(obj: LearningObject, policy: LearningPolicy, *, now: datetime) -> PreflightResult:
    """The pre-persistence gate. A refusal here means the proposal is never stored."""
    if not policy.learning_enabled:
        return PreflightResult(False, "consent_disabled")

    if obj.target.value in policy.blocked_targets:
        return PreflightResult(False, "target_blocked")

    for prefix in policy.blocked_subject_prefixes:
        if obj.subject.startswith(prefix):
            return PreflightResult(False, "subject_blocked")

    # Missing lineage may exist as private+incomplete, but it cannot back a target that needs
    # organization-visible authority.
    if obj.target is LearningTarget.ORGANIZATION:
        if not obj.lineage_complete:
            return PreflightResult(False, "lineage_incomplete_for_organization")
        if obj.visibility.scope not in (VisibilityScope.ORGANIZATION, VisibilityScope.PUBLIC):
            return PreflightResult(False, "organization_not_org_visible")

    # A user-scoped preference must resolve exactly one source-authorized subject (the contract
    # caps it; preflight rejects a subject-scoped proposal whose principal is unset).
    if obj.subject_principal is None and obj.target in (LearningTarget.BEHAVIOR,
                                                        LearningTarget.ADAPTIVE):
        # Behavior/Adaptive without a resolved subject are org-derived — allowed — but a private
        # scope with no principal is an incomplete subject and is rejected.
        if obj.visibility.scope is VisibilityScope.PRIVATE and not obj.visibility.principals:
            return PreflightResult(False, "unresolved_subject")

    # A Runtime lease must carry a future expiry within the tenant ceiling.
    if obj.target is LearningTarget.RUNTIME:
        if obj.expires_at is None:
            return PreflightResult(False, "runtime_missing_expiry")
        if obj.expires_at <= now:
            return PreflightResult(False, "runtime_expiry_in_past")
        if (obj.expires_at - now).total_seconds() > policy.max_runtime_ttl_seconds:
            return PreflightResult(False, "runtime_ttl_over_ceiling")

    return PreflightResult(True, "admitted")


@dataclass(frozen=True, slots=True)
class GovernanceDecision:
    """Where governance sends a validated proposal, and why. Never looser than the policy allows."""

    target_state: LearningState        # TEMPORARY | HUMAN_REVIEW | PROMOTED | REJECTED
    reason_code: str

    @property
    def needs_human(self) -> bool:
        return self.target_state is LearningState.HUMAN_REVIEW

    @property
    def rejected(self) -> bool:
        return self.target_state is LearningState.REJECTED


def govern(obj: LearningObject, policy: LearningPolicy) -> GovernanceDecision:
    """Decide the lifecycle path for a validated, preflight-admitted proposal."""
    # Runtime is an immediate expiring lease — never a reviewable durable proposal.
    if obj.target is LearningTarget.RUNTIME:
        return GovernanceDecision(LearningState.TEMPORARY, "runtime_lease")

    # A metric is a measurement, not a claim; it is published, never reviewed.
    if obj.target is LearningTarget.METRICS:
        return GovernanceDecision(LearningState.PROMOTED, "metric_published")

    # A knowledge suggestion ALWAYS stops at human review — this cannot be removed from policy.
    if obj.target is LearningTarget.KNOWLEDGE_SUGGESTION:
        return GovernanceDecision(LearningState.HUMAN_REVIEW, "knowledge_review")

    # Organization brain edits default to human review.
    if obj.target is LearningTarget.ORGANIZATION and policy.organization_requires_review:
        return GovernanceDecision(LearningState.HUMAN_REVIEW, "organization_review")

    # Constrained (narrower-than-organization) durable visibility also defaults to human review —
    # a private/participant learned value is exactly the kind that needs a human to bless it.
    if obj.visibility.scope in (VisibilityScope.PRIVATE, VisibilityScope.PARTICIPANTS):
        return GovernanceDecision(LearningState.HUMAN_REVIEW, "constrained_visibility_review")

    # Behavior/Adaptive with organization-visible backing may promote directly.
    return GovernanceDecision(LearningState.PROMOTED, "auto_promote")


__all__ = ["GovernanceDecision", "PreflightResult", "govern", "preflight"]
