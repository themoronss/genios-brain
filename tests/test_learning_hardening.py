"""Layer 6 safety ratchets added by the Atlas/Theory hardening pass."""
from __future__ import annotations

import inspect
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from genios_engine.api import account_routes, learning_routes
from genios_engine.api.learning_routes import _can_view
from genios_engine.contracts.learning import (
    LearningEvidence,
    LearningObject,
    LearningState,
    LearningTarget,
    LearningUnit,
)
from genios_engine.contracts.visibility import ORG, PRIVATE, Visibility
from genios_engine.feedback.governance import (
    LearningPolicy,
    ValidationResult,
    preflight_learning,
    validate_learning,
)
from genios_engine.feedback.orchestrator import review_learning, rollback_learning, run_learning
from genios_engine.feedback.store import (
    _publish_brain,
    _source_visibility,
    apply_path,
    apply_path_result,
    expire_memories,
    load_batch,
    load_learning_object,
    persist_object,
    publish,
    record_evaluation,
)
from genios_engine.feedback.units import (
    DeliveryFact,
    FeedbackFact,
    LearningBatch,
    OutcomeFact,
    feedback_learning,
    outcome_analysis,
    performance_optimization,
    preference_learning,
)
from genios_engine.platform.auth import AuthCtx


NOW = datetime(2026, 8, 8, 12, tzinfo=timezone.utc)
ORG_VISIBILITY = Visibility(scope=ORG, derived_from="test:org").model_dump()


def _evidence(count: int = 3, *, positive: int | None = None,
              negative: int = 0) -> LearningEvidence:
    positive = count - negative if positive is None else positive
    return LearningEvidence(
        observations=count, distinct_days=min(count, 3), positive=positive,
        negative=negative, confidence_bp=8_000,
        source_refs=tuple(f"source_{index}" for index in range(count)),
        independent_refs=tuple(f"origin_{index}" for index in range(count)),
        trace_ids=tuple(f"trace_{index}" for index in range(count)),
    )


def _learning(*, target: LearningTarget = LearningTarget.ADAPTIVE,
              subject: str = "subject", value: dict | None = None,
              visibility: dict | None = None, **changes) -> LearningObject:
    values = {
        "org_id": "org_1", "unit": LearningUnit.ADAPTIVE, "target": target,
        "subject_key": subject, "value": value or {"choice": "a"},
        "evidence": _evidence(), "observed_at": NOW,
        "visibility": ORG_VISIBILITY if visibility is None else visibility,
        "lineage_complete": True,
    }
    values.update(changes)
    return LearningObject(**values)


def _outcome(index: int, label: str) -> OutcomeFact:
    return OutcomeFact(
        outcome_id=f"outcome_{index}", capability_id="sales.followup", play_id="play_1",
        label=label, closed_at=NOW - timedelta(days=index % 3), progress_bp=8_000,
        trace_id=f"trace_{index}", independence_key=f"execution_{index}",
        visibility=ORG_VISIBILITY, lineage_complete=True,
    )


def test_missing_or_partial_visibility_is_never_treated_as_org_visible():
    for raw in (None, {}, {"scope": "org"}):
        visibility, complete = _source_visibility(raw)
        assert complete is False
        assert visibility["scope"] == PRIVATE
        assert _can_view(raw, "owner@example.com") is False


def test_learning_v2_requires_an_explicit_complete_visibility_shape():
    with pytest.raises(ValueError, match="visibility requires"):
        _learning(visibility={})


def test_neutral_outcomes_do_not_inflate_confidence_and_ids_ignore_eval_clock():
    labelled = (_outcome(0, "succeeded"),)
    with_neutral = labelled + tuple(
        _outcome(index, "completed_unproven") for index in range(1, 10))
    sparse = outcome_analysis(LearningBatch("org_1", NOW, outcomes=labelled))[0]
    noisy = outcome_analysis(LearningBatch("org_1", NOW, outcomes=with_neutral))[0]
    assert sparse.evidence.confidence_bp == noisy.evidence.confidence_bp == 1_000

    tomorrow = outcome_analysis(LearningBatch(
        "org_1", NOW + timedelta(days=1), outcomes=with_neutral))[0]
    assert tomorrow.learning_id == noisy.learning_id
    assert tomorrow.to_semantic_dict() == noisy.to_semantic_dict()


def test_preferences_are_actor_scoped_order_stable_and_keep_competing_evidence():
    facts = (
        FeedbackFact(
            "fb_1", "cohort", "accepted", NOW - timedelta(days=2),
            preference_key="channel", preference_value="slack", preference_scope="user",
            preference_category="notification_style", actor_key="seat_a",
            subject_principal="a@example.com", independence_key="card_1",
            visibility=ORG_VISIBILITY, lineage_complete=True),
        FeedbackFact(
            "fb_2", "cohort", "accepted", NOW - timedelta(days=1),
            preference_key="channel", preference_value="email", preference_scope="user",
            preference_category="notification_style", actor_key="seat_a",
            subject_principal="a@example.com", independence_key="card_2",
            visibility=ORG_VISIBILITY, lineage_complete=True),
        FeedbackFact(
            "fb_3", "cohort", "accepted", NOW,
            preference_key="channel", preference_value="slack", preference_scope="user",
            preference_category="notification_style", actor_key="seat_a",
            subject_principal="a@example.com", independence_key="card_3",
            visibility=ORG_VISIBILITY, lineage_complete=True),
        FeedbackFact(
            "fb_4", "cohort", "accepted", NOW,
            preference_key="channel", preference_value="slack", preference_scope="user",
            preference_category="notification_style", actor_key="seat_b",
            subject_principal="b@example.com", independence_key="card_4",
            visibility=ORG_VISIBILITY, lineage_complete=True),
    )
    forward = preference_learning(LearningBatch("org_1", NOW, feedback=facts))
    reverse = preference_learning(LearningBatch("org_1", NOW, feedback=tuple(reversed(facts))))
    assert [item.learning_id for item in forward] == [item.learning_id for item in reverse]
    assert {item.subject_key for item in forward} == {
        "preference:user:seat_a:channel", "preference:user:seat_b:channel"}
    seat_a = next(item for item in forward if "seat_a" in item.subject_key)
    assert seat_a.value["value"] == "slack"
    assert seat_a.evidence.conflict_bp == 3_333
    assert seat_a.evidence.source_refs == ("fb_1", "fb_2", "fb_3")
    for item in forward:
        assert item.visibility["scope"] == PRIVATE
        assert item.visibility["principals"] == (item.subject_principal,)
        assert preflight_learning(item, LearningPolicy()) is None


def test_bad_timing_is_timing_evidence_not_negative_quality_feedback():
    timing = FeedbackFact(
        "fb_timing", "sales.followup", "wrong", NOW, reason="bad_timing",
        source_ref="revision_timing", independence_key="card_timing",
        visibility=ORG_VISIBILITY, lineage_complete=True)
    relevance = FeedbackFact(
        "fb_relevance", "sales.followup", "wrong", NOW, reason="not_relevant",
        source_ref="revision_relevance", independence_key="card_relevance",
        visibility=ORG_VISIBILITY, lineage_complete=True)

    item = feedback_learning(
        LearningBatch("org_1", NOW, feedback=(timing, relevance)))[0]

    assert item.value["timing"] == 1
    assert item.value["rejected"] == 1
    assert item.value["neutral"] == 1
    assert item.evidence.negative == 1


def test_personal_preference_never_widens_beyond_subject_or_source_acl():
    source_visibility = Visibility(
        scope=PRIVATE, principals=["someone-else@example.com"],
        derived_from="test:private-thread").model_dump()
    fact = FeedbackFact(
        "fb_private", "cohort", "accepted", NOW,
        preference_key="channel", preference_value="slack", preference_scope="user",
        preference_category="notification_style", actor_key="seat_a",
        subject_principal="a@example.com", independence_key="card_private",
        visibility=source_visibility, lineage_complete=True)

    item = preference_learning(LearningBatch("org_1", NOW, feedback=(fact,)))[0]

    assert item.visibility["scope"] == PRIVATE
    assert item.visibility["principals"] == ("a@example.com",)
    assert item.lineage_complete is False
    assert preflight_learning(item, LearningPolicy()).reason_code == (
        "evidence_lineage_incomplete")


def test_runtime_retention_ceiling_is_checked_before_value_persistence():
    policy = LearningPolicy(max_temporary_ttl_hours=1)
    exact = _learning(
        unit=LearningUnit.TEMPORARY_MEMORY, target=LearningTarget.RUNTIME,
        expires_at=NOW + timedelta(hours=1), metadata={"explicit": True})
    too_long = _learning(
        unit=LearningUnit.TEMPORARY_MEMORY, target=LearningTarget.RUNTIME,
        expires_at=NOW + timedelta(hours=1, microseconds=1), metadata={"explicit": True})
    assert preflight_learning(exact, policy) is None
    assert validate_learning(exact, policy).state is LearningState.VALIDATED
    assert preflight_learning(too_long, policy).reason_code == "runtime_ttl_exceeds_policy"


def test_runtime_review_policy_is_rejected_by_contract_and_owner_api(monkeypatch):
    item = _learning(
        unit=LearningUnit.TEMPORARY_MEMORY, target=LearningTarget.RUNTIME,
        expires_at=NOW + timedelta(hours=1), metadata={"explicit": True})
    invalid = LearningPolicy(require_human_targets=frozenset({LearningTarget.RUNTIME}))
    assert preflight_learning(item, invalid).reason_code == "runtime_review_policy_unsupported"

    monkeypatch.setattr(learning_routes, "_graph", object())
    with pytest.raises(HTTPException) as exc:
        learning_routes.put_policy(
            learning_routes.PolicyUpdate(require_human_targets=["runtime"]),
            ctx=AuthCtx(org_id="org_1", actor_id="owner_1", scopes=None))
    assert exc.value.status_code == 422
    assert "explicit expiring lease" in str(exc.value.detail)


def test_disabled_learning_commits_tenant_retention_without_claiming_a_run(monkeypatch):
    from genios_engine.feedback import orchestrator

    calls: list[tuple] = []

    class Engine:
        @contextmanager
        def begin(self):
            calls.append(("transaction",))
            yield object()

    monkeypatch.setattr(orchestrator, "expire_memories",
                        lambda _c, org, at: calls.append(("expire", org, at)) or 2)
    monkeypatch.setattr(orchestrator, "lock_learning_tenant",
                        lambda _c, org: calls.append(("tenant_lock", org)))
    monkeypatch.setattr(orchestrator, "ensure_policy",
                        lambda _c, org, **_kw: calls.append(("policy", org)) or
                        LearningPolicy(revision=4, enabled=False))
    monkeypatch.setattr(orchestrator, "claim_run",
                        lambda *_a, **_kw: pytest.fail("disabled learning claimed a run"))

    result = run_learning(SimpleNamespace(engine=Engine()), "org_1", eval_time=NOW)

    assert result["reason"] == "learning_disabled"
    assert result["memories_expired"] == 2
    assert calls[0] == ("transaction",)
    assert calls[1] == ("tenant_lock", "org_1")
    assert calls[2][0:2] == ("expire", "org_1")
    assert calls[4:6] == [("tenant_lock", "org_1"), ("policy", "org_1")]
    assert len([call for call in calls if call[0] == "transaction"]) == 2


def test_held_duplicate_is_reevaluated_under_the_current_policy_revision(monkeypatch):
    from genios_engine.feedback import orchestrator

    item = _learning()
    policy = LearningPolicy(revision=8)
    conn = object()
    applied = []
    evaluations = []

    class Engine:
        @contextmanager
        def begin(self):
            yield conn

    monkeypatch.setattr(orchestrator, "expire_memories", lambda *_a: 0)
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_a: None)
    monkeypatch.setattr(orchestrator, "ensure_policy", lambda *_a, **_kw: policy)
    monkeypatch.setattr(orchestrator, "claim_run", lambda *_a: ("run_8", True))
    monkeypatch.setattr(orchestrator, "persist_input_rejections", lambda *_a: 0)
    monkeypatch.setattr(orchestrator, "run_units", lambda _batch: [item])
    monkeypatch.setattr(orchestrator, "persist_object", lambda *_a, **_kw: False)
    monkeypatch.setattr(orchestrator, "load_learning_object",
                        lambda *_a, **_kw: (item, LearningState.OBSERVED))

    def apply(_conn, stored, path, at, **kwargs):
        applied.append((stored, path, at, kwargs))
        return ValidationResult(LearningState.PUBLISHED, "published_to_dynamic_target")

    monkeypatch.setattr(orchestrator, "apply_path_result", apply)
    monkeypatch.setattr(orchestrator, "record_evaluation",
                        lambda *args, **kwargs: evaluations.append((args, kwargs)))
    monkeypatch.setattr(orchestrator, "complete_run", lambda *_a, **_kw: None)

    result = run_learning(
        SimpleNamespace(engine=Engine()), "org_1", eval_time=NOW,
        batch=LearningBatch("org_1", NOW))

    assert result["objects_inserted"] == 0
    assert result["objects_reevaluated"] == 1
    assert result["published"] == 1
    assert applied[0][3]["initial_state"] is LearningState.OBSERVED
    assert [step.state for step in applied[0][1]] == [
        LearningState.CANDIDATE, LearningState.VALIDATED,
        LearningState.GOVERNED, LearningState.PROMOTED]
    assert applied[0][3]["audit_detail"] == {
        "run_id": "run_8", "policy_revision": 8, "reevaluation": True}
    assert evaluations[0][1]["policy_revision"] == 8
    assert evaluations[0][1]["prior_state"] is LearningState.OBSERVED
    assert evaluations[0][1]["result_state"] is LearningState.PUBLISHED
    assert evaluations[0][1]["reason_code"] == "published_to_dynamic_target"
    assert evaluations[0][1]["object_inserted"] is False


def test_new_preflight_block_rejects_a_previously_held_duplicate(monkeypatch):
    from genios_engine.feedback import orchestrator

    item = _learning()
    policy = LearningPolicy(
        revision=12, blocked_targets=frozenset({LearningTarget.ADAPTIVE}))
    conn = object()
    transitions = []
    evaluations = []

    class Engine:
        @contextmanager
        def begin(self):
            yield conn

    monkeypatch.setattr(orchestrator, "expire_memories", lambda *_a: 0)
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_a: None)
    monkeypatch.setattr(orchestrator, "ensure_policy", lambda *_a, **_kw: policy)
    monkeypatch.setattr(orchestrator, "claim_run", lambda *_a: ("run_12", True))
    monkeypatch.setattr(orchestrator, "persist_input_rejections", lambda *_a: 0)
    monkeypatch.setattr(orchestrator, "run_units", lambda _batch: [item])
    monkeypatch.setattr(orchestrator, "persist_preflight_rejection", lambda *_a: None)
    monkeypatch.setattr(
        orchestrator, "persist_object",
        lambda *_a, **_kw: pytest.fail("blocked proposal was persisted again"))
    monkeypatch.setattr(orchestrator, "load_learning_object",
                        lambda *_a, **_kw: (item, LearningState.CANDIDATE))
    monkeypatch.setattr(
        orchestrator, "transition",
        lambda _c, _i, state, reason, **kwargs:
        transitions.append((state, reason, kwargs)))
    monkeypatch.setattr(orchestrator, "record_evaluation",
                        lambda *args, **kwargs: evaluations.append((args, kwargs)))
    monkeypatch.setattr(orchestrator, "complete_run", lambda *_a, **_kw: None)

    result = run_learning(
        SimpleNamespace(engine=Engine()), "org_1", eval_time=NOW,
        batch=LearningBatch("org_1", NOW))

    assert result["objects_reevaluated"] == 1
    assert result["rejected"] == 1 and result["preflight_rejected"] == 1
    assert transitions[0][0:2] == (
        LearningState.REJECTED, "target_blocked_by_policy")
    assert transitions[0][2]["detail"] == {
        "run_id": "run_12", "policy_revision": 12, "reevaluation": True}
    assert evaluations[0][1]["prior_state"] is LearningState.CANDIDATE
    assert evaluations[0][1]["result_state"] is LearningState.REJECTED
    assert evaluations[0][1]["reason_code"] == "target_blocked_by_policy"


def test_terminal_duplicate_is_not_reopened_by_a_later_weekly_run(monkeypatch):
    from genios_engine.feedback import orchestrator

    item = _learning()
    conn = object()

    class Engine:
        @contextmanager
        def begin(self):
            yield conn

    monkeypatch.setattr(orchestrator, "expire_memories", lambda *_a: 0)
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_a: None)
    monkeypatch.setattr(orchestrator, "ensure_policy",
                        lambda *_a, **_kw: LearningPolicy(revision=9))
    monkeypatch.setattr(orchestrator, "claim_run", lambda *_a: ("run_9", True))
    monkeypatch.setattr(orchestrator, "persist_input_rejections", lambda *_a: 0)
    monkeypatch.setattr(orchestrator, "run_units", lambda _batch: [item])
    monkeypatch.setattr(orchestrator, "persist_object", lambda *_a, **_kw: False)
    monkeypatch.setattr(orchestrator, "load_learning_object",
                        lambda *_a, **_kw: (item, LearningState.PUBLISHED))
    monkeypatch.setattr(orchestrator, "apply_path_result",
                        lambda *_a, **_kw: pytest.fail("terminal duplicate was reopened"))
    monkeypatch.setattr(orchestrator, "record_evaluation",
                        lambda *_a, **_kw: pytest.fail("terminal duplicate was re-evaluated"))
    monkeypatch.setattr(orchestrator, "complete_run", lambda *_a, **_kw: None)

    result = run_learning(
        SimpleNamespace(engine=Engine()), "org_1", eval_time=NOW,
        batch=LearningBatch("org_1", NOW))

    assert result["objects_reevaluated"] == 0
    assert result["objects_unchanged"] == 1
    assert result["states"] == {}


def test_tighter_policy_does_not_regress_candidate_to_observed(monkeypatch):
    from genios_engine.feedback import store

    item = _learning()
    monkeypatch.setattr(store, "transition",
                        lambda *_a, **_kw: pytest.fail("candidate was regressed"))
    final = apply_path(
        object(), item,
        (ValidationResult(LearningState.OBSERVED, "repetition_pending"),), NOW,
        initial_state=LearningState.CANDIDATE,
        audit_detail={"run_id": "run_10", "policy_revision": 10,
                      "reevaluation": True})
    assert final is LearningState.CANDIDATE


def test_evaluation_ledger_records_exact_run_policy_and_result():
    item = _learning()

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params):
            self.calls.append((str(statement), dict(params)))

    conn = Connection()
    record_evaluation(
        conn, item, run_id="run_11", policy_revision=11, evaluation_time=NOW,
        prior_state=LearningState.OBSERVED, result_state=LearningState.CANDIDATE,
        reason_code="confidence_pending", object_inserted=False)

    sql, params = conn.calls[0]
    assert "insert into learning_object_evaluations" in sql
    assert params["run"] == "run_11" and params["revision"] == 11
    assert params["prior"] == "observed" and params["result"] == "candidate"
    assert params["inserted"] is False


def test_memory_expiry_query_is_tenant_scoped():
    class Result:
        def __init__(self, row=None):
            self.row = row

        def first(self):
            return self.row

        def all(self):
            return []

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params):
            sql = str(statement)
            self.calls.append((sql, dict(params)))
            return Result(SimpleNamespace(id="org_a") if "from orgs" in sql else None)

    conn = Connection()
    assert expire_memories(conn, "org_a", NOW) == 0
    assert "from orgs" in conn.calls[0][0]
    sql, params = conn.calls[1]
    assert "m.org_id=:o" in sql
    assert params == {"o": "org_a", "at": NOW}


def test_stored_learning_identity_is_verified_before_state_mutation():
    item = _learning()

    class Result:
        def first(self):
            return SimpleNamespace(
                org_id=item.org_id, learning_id=item.learning_id,
                semantic_hash="0" * 64, payload=item.to_semantic_dict(),
                current_state="published")

    class Connection:
        def execute(self, _statement, _params):
            return Result()

    with pytest.raises(RuntimeError, match="hash mismatch"):
        load_learning_object(Connection(), item.org_id, item.learning_id, for_update=True)


def test_review_approval_revalidates_current_consent(monkeypatch):
    from genios_engine.feedback import orchestrator

    item = _learning()
    monkeypatch.setattr(orchestrator, "load_learning_object",
                        lambda *_a, **_kw: (item, LearningState.HUMAN_REVIEW))
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_a: None)
    monkeypatch.setattr(orchestrator, "ensure_policy",
                        lambda *_a, **_kw: LearningPolicy(revision=9, enabled=False))
    monkeypatch.setattr(orchestrator, "transition",
                        lambda *_a, **_kw: pytest.fail("stale proposal was promoted"))
    with pytest.raises(RuntimeError, match="learning_disabled"):
        review_learning(object(), org_id="org_1", learning_id=item.learning_id,
                        decision="approve", actor="owner@example.com", at=NOW)


def test_review_locks_tenant_then_policy_before_proposal_for_update(monkeypatch):
    """Erasure, policy updates and review share one non-inverting lock order."""
    from genios_engine.feedback import orchestrator

    item = _learning(policy_key="policy_z")
    order: list[tuple] = []

    monkeypatch.setattr(
        orchestrator, "lock_learning_tenant",
        lambda _conn, org: order.append(("tenant", org)))

    def load(_conn, org, learning_id, **kwargs):
        order.append(("object", org, learning_id, bool(kwargs.get("for_update"))))
        return item, LearningState.HUMAN_REVIEW

    def policy(_conn, org, policy_key="default", **kwargs):
        order.append(("policy", org, policy_key, kwargs.get("for_share")))
        return LearningPolicy(revision=7, enabled=False)

    monkeypatch.setattr(orchestrator, "load_learning_object", load)
    monkeypatch.setattr(orchestrator, "ensure_policy", policy)

    with pytest.raises(RuntimeError, match="learning_disabled"):
        review_learning(
            object(), org_id="org_1", learning_id=item.learning_id,
            decision="approve", actor="owner@example.com", at=NOW)

    assert order == [
        ("tenant", "org_1"),
        ("object", "org_1", item.learning_id, False),
        ("policy", "org_1", "policy_z", True),
        ("object", "org_1", item.learning_id, True),
    ]


def test_metrics_publication_cannot_use_dynamic_brain_rollback(monkeypatch):
    from genios_engine.feedback import orchestrator

    item = _learning(target=LearningTarget.METRICS, unit=LearningUnit.PERFORMANCE)
    monkeypatch.setattr(orchestrator, "load_learning_object",
                        lambda *_a, **_kw: (item, LearningState.PUBLISHED))
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_a: None)
    with pytest.raises(RuntimeError, match="dynamic brain"):
        rollback_learning(object(), org_id="org_1", learning_id=item.learning_id,
                          actor="owner@example.com", at=NOW, reason="bad metric")


def test_rollback_rejects_review_proposal_before_subject_lock(monkeypatch):
    """Review takes proposal-row then subject locks; rollback must not invert that ordering."""
    from genios_engine.feedback import orchestrator

    item = _learning(target=LearningTarget.ADAPTIVE)
    monkeypatch.setattr(orchestrator, "load_learning_object",
                        lambda *_a, **_kw: (item, LearningState.HUMAN_REVIEW))
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_a: None)

    class Connection:
        def execute(self, *_args, **_kwargs):
            pytest.fail("a non-published proposal must be rejected before advisory locking")

    with pytest.raises(RuntimeError, match="only published learning"):
        rollback_learning(Connection(), org_id="org_1", learning_id=item.learning_id,
                          actor="owner@example.com", at=NOW, reason="not published")


def test_rollback_locks_sorted_policies_before_subject_and_object(monkeypatch):
    """A predecessor with another policy cannot invert review/publication locking."""
    from genios_engine.feedback import orchestrator

    current = _learning(policy_key="policy_z")
    predecessor = _learning(
        policy_key="policy_a", value={"choice": "older"},
        observed_at=NOW - timedelta(days=1),
        first_seen_at=NOW - timedelta(days=1),
        last_seen_at=NOW - timedelta(days=1))
    order: list[tuple] = []

    monkeypatch.setattr(
        orchestrator, "lock_learning_tenant",
        lambda _conn, org: order.append(("tenant", org)))

    def load(_conn, _org, learning_id, **kwargs):
        for_update = bool(kwargs.get("for_update"))
        order.append(("object", learning_id, for_update))
        if learning_id == current.learning_id and for_update:
            raise RuntimeError("stop_after_required_lock_order")
        if learning_id == current.learning_id:
            return current, LearningState.PUBLISHED
        assert learning_id == predecessor.learning_id
        return predecessor, LearningState.SUPERSEDED

    def policy(_conn, _org, policy_key="default", **kwargs):
        order.append(("policy", policy_key, kwargs.get("for_share")))
        return LearningPolicy(revision=3)

    monkeypatch.setattr(orchestrator, "load_learning_object", load)
    monkeypatch.setattr(orchestrator, "ensure_policy", policy)

    class Result:
        def __init__(self, row=None):
            self.row = row

        def first(self):
            return self.row

    class Connection:
        def execute(self, statement, _params=None):
            sql = " ".join(str(statement).split())
            if "pg_advisory_xact_lock" in sql:
                order.append(("subject_advisory",))
                return Result()
            if "learning_id=:id and active" in sql and "for update" not in sql:
                order.append(("active_snapshot",))
                return Result(SimpleNamespace(
                    entry_id="entry_2", supersedes_entry_id="entry_1"))
            if "entry_id=:entry and brain=:brain" in sql and "for update" not in sql:
                order.append(("predecessor_snapshot",))
                return Result(SimpleNamespace(
                    learning_id=predecessor.learning_id, ended_reason="superseded"))
            pytest.fail(f"unexpected SQL before lock-order sentinel: {sql}")

    with pytest.raises(RuntimeError, match="stop_after_required_lock_order"):
        rollback_learning(
            Connection(), org_id="org_1", learning_id=current.learning_id,
            actor="owner@example.com", at=NOW, reason="bad inference")

    assert order == [
        ("tenant", "org_1"),
        ("object", current.learning_id, False),
        ("active_snapshot",),
        ("predecessor_snapshot",),
        ("object", predecessor.learning_id, False),
        ("policy", "policy_a", True),
        ("policy", "policy_z", True),
        ("subject_advisory",),
        ("object", current.learning_id, True),
    ]


def test_rollback_restores_the_verified_superseded_predecessor(monkeypatch):
    from genios_engine.feedback import orchestrator

    personal_visibility = Visibility(
        scope=PRIVATE, principals=["owner@example.com"],
        derived_from="test:personal-preference").model_dump()
    current = _learning(
        subject="preference:user:seat_a:channel", value={"choice": "email"},
        visibility=personal_visibility, subject_principal="owner@example.com")
    predecessor = _learning(subject=current.subject_key, value={"choice": "slack"},
                            observed_at=NOW - timedelta(days=1),
                            first_seen_at=NOW - timedelta(days=1),
                            last_seen_at=NOW - timedelta(days=1),
                            visibility=personal_visibility,
                            subject_principal="owner@example.com")
    transitions = []

    def load(_conn, _org, learning_id, **_kwargs):
        if learning_id == current.learning_id:
            return current, LearningState.PUBLISHED
        assert learning_id == predecessor.learning_id
        return predecessor, LearningState.SUPERSEDED

    monkeypatch.setattr(orchestrator, "load_learning_object", load)
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_a: None)
    monkeypatch.setattr(orchestrator, "ensure_policy",
                        lambda *_a, **_kw: LearningPolicy(revision=3))
    monkeypatch.setattr(orchestrator, "transition",
                        lambda _c, item, state, reason, **_kw:
                        transitions.append((item.learning_id, state, reason)))

    class Result:
        def __init__(self, row=None, rowcount=1):
            self.row = row
            self.rowcount = rowcount

        def first(self):
            return self.row

    class Connection:
        def execute(self, statement, _params=None):
            sql = str(statement)
            if "and learning_id=:id and active" in sql:
                return Result(SimpleNamespace(
                    entry_id="entry_8", supersedes_entry_id="entry_7"))
            if "and entry_id=:entry and brain=:brain" in sql:
                return Result(SimpleNamespace(
                    learning_id=predecessor.learning_id, ended_reason="superseded"))
            return Result()

    result = rollback_learning(
        Connection(), org_id="org_1", learning_id=current.learning_id,
        actor="owner@example.com", at=NOW, reason="bad inference")

    assert result["restored_learning_id"] == predecessor.learning_id
    assert transitions == [
        (current.learning_id, LearningState.ROLLED_BACK, "human_rollback"),
        (predecessor.learning_id, LearningState.PUBLISHED,
         "predecessor_restored_by_rollback"),
    ]


def test_brain_acl_change_is_a_material_version(monkeypatch):
    from genios_engine.feedback import store

    item = _learning()
    old_visibility = Visibility(scope="public", derived_from="test:public").model_dump()
    latest = SimpleNamespace(
        entry_id="entry_7", learning_id="learn_old", version=7, active=True,
        value={"choice": "a"}, confidence_bp=8_000, visibility=old_visibility,
        last_seen_at=NOW)

    class Result:
        def __init__(self, row=None, rowcount=1):
            self.row = row
            self.rowcount = rowcount

        def first(self):
            return self.row

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.calls.append((sql, dict(params or {})))
            if "order by version desc" in sql:
                return Result(latest)
            if "and active for update" in sql:
                return Result(latest)
            return Result()

    conn = Connection()
    old_item = _learning()
    monkeypatch.setattr(store, "load_learning_object",
                        lambda *_a, **_kw: (old_item, LearningState.PUBLISHED))
    monkeypatch.setattr(store, "transition", lambda *_a, **_kw: None)

    assert _publish_brain(conn, item, NOW) is True
    insert = next(params for sql, params in conn.calls
                  if "insert into learned_brain_entries" in sql)
    assert insert["version"] == 8
    assert insert["supersedes"] == "entry_7"


def test_publish_after_rollback_links_the_actual_active_predecessor(monkeypatch):
    from genios_engine.feedback import store

    item = _learning(value={"choice": "c"})
    latest_rolled_back = SimpleNamespace(
        entry_id="entry_2", learning_id="learn_2", version=2, active=False,
        value={"choice": "b"}, confidence_bp=8_000, visibility=ORG_VISIBILITY)
    active_restored = SimpleNamespace(
        entry_id="entry_1", learning_id="learn_1", version=1, active=True,
        value={"choice": "a"}, confidence_bp=8_000, visibility=ORG_VISIBILITY,
        last_seen_at=NOW - timedelta(days=1))

    class Result:
        def __init__(self, row=None, rowcount=1):
            self.row = row
            self.rowcount = rowcount

        def first(self):
            return self.row

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.calls.append((sql, dict(params or {})))
            if "order by version desc" in sql:
                return Result(latest_rolled_back)
            if "and active for update" in sql:
                return Result(active_restored)
            return Result()

    conn = Connection()
    old_item = _learning(value={"choice": "a"})
    monkeypatch.setattr(store, "load_learning_object",
                        lambda *_a, **_kw: (old_item, LearningState.PUBLISHED))
    monkeypatch.setattr(store, "transition", lambda *_a, **_kw: None)

    assert _publish_brain(conn, item, NOW) is True
    insert = next(params for sql, params in conn.calls
                  if "insert into learned_brain_entries" in sql)
    lineage = next(params for sql, params in conn.calls
                   if "set supersedes_learning_id" in sql)
    assert insert["version"] == 3
    assert insert["supersedes"] == "entry_1"
    assert lineage["prior"] == "learn_1"


def test_publisher_rechecks_stale_review_under_subject_lock():
    item = _learning(
        observed_at=NOW - timedelta(days=1),
        first_seen_at=NOW - timedelta(days=1),
        last_seen_at=NOW - timedelta(days=1))
    newer = SimpleNamespace(
        entry_id="entry_new", learning_id="learn_new", version=4, active=True,
        value={"choice": "new"}, confidence_bp=8_000, visibility=ORG_VISIBILITY,
        last_seen_at=NOW)

    class Result:
        def __init__(self, row=None):
            self.row = row
            self.rowcount = 1

        def first(self):
            return self.row

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.calls.append((sql, dict(params or {})))
            if "order by version desc" in sql or "and active for update" in sql:
                return Result(newer)
            return Result()

    conn = Connection()
    with pytest.raises(RuntimeError, match="newer learning value"):
        _publish_brain(conn, item, NOW)
    assert any("pg_advisory_xact_lock" in sql for sql, _ in conn.calls)
    assert not any("insert into learned_brain_entries" in sql for sql, _ in conn.calls)


def test_dashboard_terminal_action_atomically_versions_l6_feedback():
    from genios_engine.deliver.actions import ingest_action

    class Result:
        def __init__(self, rows=()):
            self.rows = list(rows)

        def mappings(self):
            return self

        def first(self):
            return self.rows[0] if self.rows else None

    class Connection:
        def __init__(self):
            self.calls = []

        def execute(self, statement, params=None):
            sql = " ".join(str(statement).split())
            self.calls.append((sql, dict(params or {})))
            if sql.startswith("select id from orgs"):
                return Result([SimpleNamespace(id="org_1")])
            if sql.startswith("select k.card_id"):
                return Result([{
                    "card_id": "card_1", "signal_id": "signal_1", "org_id": "org_1",
                    "assignee": "seat_1", "state": "queued",
                    "expires_at": NOW + timedelta(days=1), "pack_id": "sales",
                    "pack_version": "v1", "authority_pack_revision": 4,
                    "capability_id": "sales.followup", "capability_version": "v2",
                    "rule_id": "followup",
                }])
            if sql.startswith("insert into card_feedback_verdicts"):
                return Result([SimpleNamespace(verdict_version=1)])
            return Result()

    class Engine:
        def __init__(self, conn):
            self.conn = conn

        @contextmanager
        def begin(self):
            yield self.conn

    conn = Connection()
    result = ingest_action(
        card_store=object(), graph=SimpleNamespace(engine=Engine(conn)), org_id="org_1",
        card_id="card_1", actor="seat_1", action="wrong", reason="wrong_facts",
        eval_time=NOW)

    sql = "\n".join(statement for statement, _ in conn.calls)
    assert result == {"ok": True, "state": "acted", "action": "wrong",
                      "feedback_changed": True, "verdict_version": 1,
                      "reason": "wrong_facts"}
    assert "insert into card_events" in sql
    assert "insert into card_feedback_verdicts" in sql
    assert "insert into card_feedback_revisions" in sql
    assert conn.calls[0][0].startswith("select id from orgs")
    assert conn.calls[1][0].startswith("select graph_version from graph_versions")
    assert conn.calls[2][0].startswith("select k.card_id")
    revision = next(params for statement, params in conn.calls
                    if statement.startswith("insert into card_feedback_revisions"))
    assert revision["at"] == NOW and revision["actor"] == "seat_1"
    assert revision["cause"] == "wrong" and revision["reason"] == "wrong_facts"
    assert ingest_action(
        card_store=object(), graph=object(), org_id="org_1", card_id="card_1",
        actor="seat_1", action="run_play", reason="wrong_facts", eval_time=NOW
    ) == {"ok": False, "error": "reason_only_allowed_for_wrong"}


def test_performance_freshness_includes_latest_delivery_lifecycle_event():
    created = NOW - timedelta(days=7)
    failed_at = NOW - timedelta(minutes=1)
    fact = DeliveryFact(
        "delivery_1", "webhook", "failed", created, lifecycle_at=failed_at,
        attempts=3, execution_id="execution_1", trace_id="trace_1",
        independence_key="execution_1", visibility=ORG_VISIBILITY,
        lineage_complete=True)
    item = performance_optimization(
        LearningBatch("org_1", NOW, deliveries=(fact,)))[0]

    assert item.observed_at == failed_at
    assert item.last_seen_at == failed_at
    assert item.evidence.freshness_bp > 9_000


def test_post_delivery_execution_failure_is_not_transport_failure():
    delivered_at = NOW - timedelta(hours=2)
    failed_at = NOW - timedelta(hours=1)
    fact = DeliveryFact(
        "delivery_1", "agent", "failed", NOW - timedelta(hours=3), delivered_at,
        lifecycle_status="failed", lifecycle_at=failed_at, accepted_at=delivered_at,
        attempts=1, execution_id="execution_1", trace_id="trace_1",
        independence_key="execution_1", visibility=ORG_VISIBILITY,
        lineage_complete=True)
    item = performance_optimization(
        LearningBatch("org_1", NOW, deliveries=(fact,)))[0]

    assert item.value["delivered"] == 1
    assert item.value["failed"] == 0
    assert item.value["delivered_bp"] == 10_000
    assert item.observed_at == failed_at


def test_metric_insert_conflict_is_not_reported_as_published(monkeypatch):
    from genios_engine.feedback import store

    item = _learning(target=LearningTarget.METRICS, unit=LearningUnit.PERFORMANCE)
    transitions = []

    class Result:
        def first(self):
            return None

    class Connection:
        def execute(self, _statement, _params):
            return Result()

    monkeypatch.setattr(store, "transition",
                        lambda _c, _i, state, reason, **_kw:
                        transitions.append((state, reason)))
    outcome = apply_path_result(
        Connection(), item, (), NOW, initial_state=LearningState.PROMOTED)
    assert outcome == ValidationResult(
        LearningState.REJECTED, "metric_identity_conflict")
    assert transitions == [(LearningState.REJECTED, "metric_identity_conflict")]


def test_no_material_brain_publish_reports_exact_rejection_reason(monkeypatch):
    from genios_engine.feedback import store

    item = _learning()
    transitions = []
    monkeypatch.setattr(store, "_publish_brain", lambda *_a, **_kw: False)
    monkeypatch.setattr(store, "transition",
                        lambda _c, _i, state, reason, **_kw:
                        transitions.append((state, reason)))

    outcome = apply_path_result(
        object(), item, (), NOW, initial_state=LearningState.PROMOTED)

    assert outcome == ValidationResult(LearningState.REJECTED, "no_material_change")
    assert transitions == [(LearningState.REJECTED, "no_material_change")]


def test_hardening_migration_and_source_keep_new_db_invariants_wired():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "migrations/0047_l6_learning_hardening.sql").read_text().lower()
    assert "after insert or update on learning_policies" in migration
    assert "before update or delete on learning_policy_revisions" in migration
    assert "organization_authorized boolean not null default false" in migration
    assert "learning_object_v2_projection_matches_payload" in migration
    assert "payload#>>'{observed_at,$datetime}'" in migration
    assert "payload->>'policy_key'=policy_key" in migration
    assert migration.count("visibility ? 'principals'") >= 5
    assert "array_remove(require_human_targets,'runtime')" in migration
    assert "not (require_human_targets @> array['runtime']::text[])" in migration
    assert "create table if not exists learning_object_evaluations" in migration
    assert "learning_runs_evaluation_policy_identity" in migration
    assert "policy_revision,evaluation_time)" in migration
    assert "independent_observations" in migration
    for constraint in ("temporary_memory_visibility_valid",
                       "knowledge_suggestion_visibility_valid",
                       "learning_metric_visibility_valid"):
        assert constraint in migration

    source = inspect.getsource(persist_object)
    assert "independent_observations" in source
    assert "subject_principal" in source
    evaluation_source = inspect.getsource(record_evaluation)
    assert "learning_object_evaluations" in evaluation_source
    loader = inspect.getsource(load_batch)
    assert "x.execution_id=k.execution_id" in loader
    assert "graph_source_refs" in loader
    assert "expected_hash=_get(row, \"execution_hash\")" in loader
    assert "lifecycle_at" in loader


def test_l6_mutating_entrypoints_keep_tenant_root_lock_first():
    """Source ratchets guard entrypoints that need real-Postgres concurrency proof later."""
    from genios_engine.api import intelligence_routes
    from genios_engine.deliver.actions import ingest_action
    from genios_engine.feedback.calibrate import run_calibration
    from genios_engine.feedback.orchestrator import run_learning as orchestrate

    def assert_ordered(source, *needles):
        positions = [source.index(needle) for needle in needles]
        assert positions == sorted(positions), (needles, positions)

    run_source = inspect.getsource(orchestrate)
    # The expiry and analysis transactions independently establish tenant-first ordering.
    first_begin = run_source.index("with store.engine.begin() as conn:")
    expiry_lock = run_source.index("lock_learning_tenant(conn, org_id)", first_begin)
    expiry = run_source.index("expire_memories(conn, org_id, now)", expiry_lock)
    second_begin = run_source.index("with store.engine.begin() as conn:", expiry)
    main_lock = run_source.index("lock_learning_tenant(conn, org_id)", second_begin)
    policy = run_source.index("ensure_policy(conn, org_id, for_share=True)", main_lock)
    assert first_begin < expiry_lock < expiry < second_begin < main_lock < policy

    assert_ordered(
        inspect.getsource(run_calibration),
        "lock_learning_tenant(conn, org_id)",
        "ensure_policy(conn, org_id, for_share=True)",
        "_pack_version(conn, org_id, pack_id, lock=True)")
    assert_ordered(
        inspect.getsource(learning_routes.create_memory),
        "lock_learning_tenant(conn, ctx.org_id)",
        "viewer = _viewer(conn, ctx)",
        "policy = ensure_policy(conn, ctx.org_id, for_share=True)",
        "persist_object(conn, item")
    assert_ordered(
        inspect.getsource(learning_routes.put_policy),
        "lock_learning_tenant(conn, ctx.org_id)",
        "ensure_policy(conn, ctx.org_id, for_share=False)",
        "for update")

    # Both feedback ingresses bind org erasure, graph proof and card row in that order.
    for feedback_entrypoint in (intelligence_routes.intelligence_feedback, ingest_action):
        assert_ordered(
            inspect.getsource(feedback_entrypoint),
            "lock_tenant_for_mutation(c, org_id)",
            "select graph_version from graph_versions",
            "select k.card_id")


def test_workspace_reset_erases_inputs_and_rejections_but_preserves_consent_policy():
    tables = account_routes._ORG_SCOPED_TABLES
    assert "learning_event_inbox" in tables
    assert "learning_input_rejections" in tables
    assert "learning_object_evaluations" in tables
    assert tables.index("learning_object_evaluations") < tables.index("learning_objects")
    assert tables.index("learning_input_rejections") < tables.index("learning_runs")
    assert "learning_policies" not in tables
    assert "learning_policy_revisions" not in tables
