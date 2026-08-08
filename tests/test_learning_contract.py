"""Layer 6 · Phase 1 — the LearningObject v2 contract (pure)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts.learning import (
    LEARNING_VERSION,
    LearningEvidence,
    LearningObject,
    LearningPolicy,
    LearningState,
    LearningTarget,
    Visibility,
    VisibilityScope,
    learning_can_transition,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _ev(**over) -> LearningEvidence:
    base = dict(observations=5, independent_refs=3, distinct_days=2, positive=4, negative=1,
                confidence_bp=7000)
    base.update(over)
    return LearningEvidence(**base)


def _obj(**over) -> LearningObject:
    base = dict(org_id="org_1", unit="feedback", target=LearningTarget.ORGANIZATION,
                subject="rule_x", proposed_value={"action": "mute"}, evidence=_ev(),
                visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
                first_seen_at=NOW, last_seen_at=NOW, policy_key="policy:org_1:1")
    base.update(over)
    return LearningObject(**base)


def test_identity_is_content_addressed_and_stable():
    a, b = _obj(), _obj()
    assert a.learning_id == b.learning_id == f"lo_{a.semantic_hash()[:24]}"
    assert a.schema_version == LEARNING_VERSION == "learning.v2"


def test_a_different_value_is_a_different_object():
    assert _obj().learning_id != _obj(proposed_value={"action": "keep"}).learning_id


def test_no_expert_target_exists():
    assert "expert" not in {t.value for t in LearningTarget}


def test_only_runtime_may_carry_an_expiry():
    LearningObject(org_id="o", unit="u", target=LearningTarget.RUNTIME, subject="s",
                   proposed_value={}, evidence=_ev(), visibility=Visibility(VisibilityScope.PRIVATE),
                   first_seen_at=NOW, last_seen_at=NOW, policy_key="p", expires_at=NOW)  # ok
    with pytest.raises(ValueError, match="Runtime"):
        _obj(target=LearningTarget.ORGANIZATION, expires_at=NOW)


def test_a_subject_preference_is_capped_private_to_one_principal():
    ok = _obj(target=LearningTarget.BEHAVIOR, subject_principal="seat_1",
              visibility=Visibility(VisibilityScope.PRIVATE, principals=("seat_1",)))
    assert ok.subject_principal == "seat_1"
    with pytest.raises(ValueError):        # org-visible subject pref is rejected
        _obj(subject_principal="seat_1", visibility=Visibility(VisibilityScope.ORGANIZATION))
    with pytest.raises(ValueError):        # wrong principal set
        _obj(target=LearningTarget.BEHAVIOR, subject_principal="seat_1",
             visibility=Visibility(VisibilityScope.PRIVATE, principals=("seat_2",)))


def test_evidence_scores_are_integer_basis_points():
    with pytest.raises(ValueError):
        _ev(confidence_bp=10001)
    with pytest.raises(ValueError):
        _ev(confidence_bp=70.5)            # no floats
    with pytest.raises(ValueError):
        _ev(observations=-1)


def test_policy_knowledge_review_cannot_be_disabled():
    LearningPolicy(org_id="o", revision=1)   # default true, ok
    with pytest.raises(ValueError):
        LearningPolicy(org_id="o", revision=1, knowledge_requires_review=False)


def test_lifecycle_candidate_never_regresses_and_terminals_stop():
    assert learning_can_transition(LearningState.OBSERVED, LearningState.CANDIDATE)
    assert not learning_can_transition(LearningState.CANDIDATE, LearningState.OBSERVED)
    assert learning_can_transition(LearningState.GOVERNED, LearningState.HUMAN_REVIEW)
    assert learning_can_transition(LearningState.PROMOTED, LearningState.PUBLISHED)
    for terminal in (LearningState.REJECTED, LearningState.EXPIRED, LearningState.ROLLED_BACK):
        assert not learning_can_transition(terminal, LearningState.PUBLISHED)


def test_missing_lineage_can_be_marked_incomplete():
    o = _obj(lineage_complete=False)
    assert o.lineage_complete is False
