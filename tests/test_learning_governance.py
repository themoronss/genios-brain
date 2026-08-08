"""Layer 6 · Phase 4 — preflight + governance (pure)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningState,
    LearningTarget,
    Visibility,
    VisibilityScope,
)
from genios_engine.feedback.governance import govern, preflight

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
POLICY = LearningPolicy(org_id="org_1", revision=1)


def _ev():
    return LearningEvidence(observations=5, independent_refs=3, distinct_days=2, positive=4,
                            negative=1, confidence_bp=7000)


def _obj(target=LearningTarget.ORGANIZATION, scope=VisibilityScope.ORGANIZATION, **over):
    base = dict(org_id="org_1", unit="u", target=target, subject="rule_x", proposed_value={},
                evidence=_ev(), visibility=Visibility(scope=scope), first_seen_at=NOW,
                last_seen_at=NOW, policy_key="policy:org_1:1")
    base.update(over)
    return LearningObject(**base)


def test_preflight_stops_when_consent_disabled():
    off = LearningPolicy(org_id="org_1", revision=1, learning_enabled=False)
    assert preflight(_obj(), off, now=NOW).reason_code == "consent_disabled"


def test_preflight_blocks_target_and_subject():
    p = LearningPolicy(org_id="org_1", revision=1, blocked_targets=("organization",))
    assert preflight(_obj(), p, now=NOW).reason_code == "target_blocked"
    p2 = LearningPolicy(org_id="org_1", revision=1, blocked_subject_prefixes=("rule_",))
    assert preflight(_obj(), p2, now=NOW).reason_code == "subject_blocked"


def test_preflight_organization_needs_org_visible_lineage():
    assert preflight(_obj(scope=VisibilityScope.PRIVATE), POLICY, now=NOW).reason_code == \
        "organization_not_org_visible"
    assert preflight(_obj(lineage_complete=False), POLICY, now=NOW).reason_code == \
        "lineage_incomplete_for_organization"
    assert preflight(_obj(), POLICY, now=NOW).ok is True


def test_preflight_runtime_ttl_ceiling():
    within = _obj(target=LearningTarget.RUNTIME, scope=VisibilityScope.PRIVATE,
                  expires_at=NOW + timedelta(hours=1))
    assert preflight(within, POLICY, now=NOW).ok is True
    over = _obj(target=LearningTarget.RUNTIME, scope=VisibilityScope.PRIVATE,
                expires_at=NOW + timedelta(days=30))
    assert preflight(over, POLICY, now=NOW).reason_code == "runtime_ttl_over_ceiling"


def test_govern_routes_by_target():
    assert govern(_obj(target=LearningTarget.RUNTIME, scope=VisibilityScope.PRIVATE,
                       expires_at=NOW + timedelta(hours=1)), POLICY).target_state \
        is LearningState.TEMPORARY
    assert govern(_obj(target=LearningTarget.METRICS), POLICY).target_state is LearningState.PROMOTED
    assert govern(_obj(target=LearningTarget.KNOWLEDGE_SUGGESTION), POLICY).needs_human is True
    assert govern(_obj(target=LearningTarget.ORGANIZATION), POLICY).needs_human is True


def test_govern_constrained_visibility_needs_review():
    d = govern(_obj(target=LearningTarget.BEHAVIOR, scope=VisibilityScope.PARTICIPANTS), POLICY)
    assert d.needs_human is True and d.reason_code == "constrained_visibility_review"


def test_govern_auto_promotes_org_visible_behavior():
    d = govern(_obj(target=LearningTarget.BEHAVIOR, scope=VisibilityScope.ORGANIZATION), POLICY)
    assert d.target_state is LearningState.PROMOTED
