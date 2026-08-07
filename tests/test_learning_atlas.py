"""Atlas Layer 6: contracts, eleven units, governance, persistence and wiring."""
from __future__ import annotations

import inspect
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genios_engine.contracts.learning import (
    ALLOWED_LEARNING_TRANSITIONS,
    BrainTarget,
    LearningEvidence,
    LearningObject,
    LearningState,
    LearningTarget,
    LearningUnit,
    can_transition_learning,
)
from genios_engine.contracts.visibility import ORG, Visibility
from genios_engine.feedback.governance import (
    LearningPolicy,
    ValidationResult,
    lifecycle_path,
    validate_learning,
)
from genios_engine.feedback.store import load_batch, publish
from genios_engine.feedback.units import (
    ALL_ANALYSIS_UNITS,
    DeliveryFact,
    EnterpriseFact,
    FeedbackFact,
    LearningBatch,
    OutcomeFact,
    knowledge_evolution,
    outcome_analysis,
    performance_optimization,
    preference_learning,
    run_units,
    temporary_memory,
)

NOW = datetime(2026, 8, 7, 12, tzinfo=timezone.utc)
ORG_VISIBILITY = Visibility(scope=ORG, derived_from="test:org").model_dump()


def evidence(count: int = 3, confidence: int = 8_000) -> LearningEvidence:
    return LearningEvidence(
        observations=count, distinct_days=min(count, 3), positive=count, negative=0,
        confidence_bp=confidence, source_refs=tuple(f"src_{i}" for i in range(count)))


def learning(**changes) -> LearningObject:
    values = {
        "org_id": "org_1", "unit": LearningUnit.ADAPTIVE,
        "target": LearningTarget.ADAPTIVE,
        "subject_key": "notification_style", "value": {"channel": "slack"},
        "evidence": evidence(), "observed_at": NOW, "visibility": ORG_VISIBILITY,
        "lineage_complete": True,
    }
    values.update(changes)
    return LearningObject(**values)


def test_learning_object_is_immutable_content_addressed_and_round_trips():
    item = learning()
    item.verify_round_trip()
    assert item.learning_id.startswith("learn_")
    assert len(item.semantic_hash) == 64
    with pytest.raises(TypeError):
        item.value["channel"] = "email"


def test_contract_has_no_expert_brain_target_and_knowledge_cannot_escape_review_target():
    assert "expert" not in {target.value for target in BrainTarget}
    with pytest.raises(ValueError, match="knowledge evolution"):
        learning(unit=LearningUnit.KNOWLEDGE, target=LearningTarget.ADAPTIVE)


def test_runtime_memory_is_always_leased_and_other_targets_cannot_smuggle_a_ttl():
    with pytest.raises(ValueError, match="requires expires_at"):
        learning(unit=LearningUnit.TEMPORARY_MEMORY, target=LearningTarget.RUNTIME)
    with pytest.raises(ValueError, match="only runtime"):
        learning(expires_at=NOW + timedelta(days=1))


def test_promotion_state_machine_is_the_atlas_path_and_reversible_after_publication():
    assert can_transition_learning(LearningState.OBSERVED, LearningState.CANDIDATE)
    assert can_transition_learning(LearningState.GOVERNED, LearningState.HUMAN_REVIEW)
    assert can_transition_learning(LearningState.PUBLISHED, LearningState.ROLLED_BACK)
    assert not can_transition_learning(LearningState.OBSERVED, LearningState.PUBLISHED)
    assert set(ALLOWED_LEARNING_TRANSITIONS) == set(LearningState)


def _outcomes(successes: int, failures: int, neutral: int = 0) -> tuple[OutcomeFact, ...]:
    labels = (["succeeded"] * successes + ["expired_untouched"] * failures
              + ["completed_unproven"] * neutral)
    return tuple(OutcomeFact(
        outcome_id=f"out_{i}", capability_id="sales.followup", play_id="investor_update",
        label=label, closed_at=NOW - timedelta(days=i % 6),
        progress_bp=10_000 if label == "succeeded" else 2_000,
        reminders_sent=i % 2, escalations_fired=int(i % 4 == 0), seconds_to_close=3_600,
        trace_id=f"trace_{i}", independence_key=f"exec_{i}",
        visibility=ORG_VISIBILITY, lineage_complete=True)
        for i, label in enumerate(labels))


def test_outcome_analysis_uses_real_effectiveness_and_keeps_unproven_neutral():
    batch = LearningBatch("org_1", NOW, outcomes=_outcomes(3, 2, 4))
    item = outcome_analysis(batch)[0]
    assert item.value["success_bp"] == 6_000
    assert item.value["unproven"] == 4
    assert item.evidence.positive == 3 and item.evidence.negative == 2
    assert item.evidence.observations == 9


def test_knowledge_evolution_only_suggests_review_after_a_sustained_poor_cohort():
    small = LearningBatch("org_1", NOW, outcomes=_outcomes(1, 3))
    assert knowledge_evolution(small) == []
    poor = LearningBatch("org_1", NOW, outcomes=_outcomes(2, 8))
    suggestion = knowledge_evolution(poor)[0]
    assert suggestion.target is LearningTarget.KNOWLEDGE_SUGGESTION
    assert suggestion.value["suggestion_type"] == "review_play"
    path = lifecycle_path(suggestion, LearningPolicy())
    assert path[-1].state is LearningState.HUMAN_REVIEW


def test_preference_and_memory_units_refuse_silence_and_implicit_memory():
    feedback = (
        FeedbackFact("fb_1", "card_1", "ignored", NOW, explicit=False,
                     actor_key="seat_1", subject_principal="user@example.com",
                     visibility=ORG_VISIBILITY, lineage_complete=True),
        FeedbackFact("fb_2", "card_2", "accepted", NOW, explicit=True,
                     preference_key="channel", preference_value="slack",
                     preference_scope="user", preference_category="notification_style",
                     actor_key="seat_1", subject_principal="user@example.com",
                     visibility=ORG_VISIBILITY, lineage_complete=True),
    )
    events = (
        EnterpriseFact("evt_1", "call_founder", "note", NOW,
                       value={"text": "call tomorrow"}, expires_at=NOW + timedelta(days=1),
                       visibility=ORG_VISIBILITY, lineage_complete=True),
        EnterpriseFact("evt_2", "call_founder", "temporary_memory", NOW,
                       value={"text": "call tomorrow"}, explicit_memory=True,
                       expires_at=NOW + timedelta(days=1), visibility=ORG_VISIBILITY,
                       lineage_complete=True),
    )
    batch = LearningBatch("org_1", NOW, feedback=feedback, events=events)
    assert len(preference_learning(batch)) == 1
    memories = temporary_memory(batch)
    assert len(memories) == 1 and memories[0].target is LearningTarget.RUNTIME


def test_performance_unit_does_not_call_open_or_suppressed_delivery_a_failure():
    deliveries = (
        DeliveryFact("d_1", "slack", "delivered", NOW - timedelta(seconds=2), NOW, attempts=1,
                     visibility=ORG_VISIBILITY, lineage_complete=True),
        DeliveryFact("d_2", "slack", "queued", NOW, attempts=0, deferrals=2,
                     visibility=ORG_VISIBILITY, lineage_complete=True),
        DeliveryFact("d_3", "slack", "suppressed", NOW, attempts=0,
                     visibility=ORG_VISIBILITY, lineage_complete=True),
        DeliveryFact("d_4", "slack", "failed", NOW, attempts=5,
                     visibility=ORG_VISIBILITY, lineage_complete=True),
    )
    item = performance_optimization(LearningBatch("org_1", NOW, deliveries=deliveries))[0]
    assert item.value["failed"] == 1
    assert item.value["open"] == 1 and item.value["suppressed"] == 1
    assert item.value["delivered_bp"] == 5_000


def test_all_ten_analysis_units_run_and_validation_is_the_eleventh_unit():
    feedback: list[FeedbackFact] = []
    for i in range(3):
        at = NOW - timedelta(days=i)
        feedback.extend([
            FeedbackFact(f"fb_b_{i}", f"card_b_{i}", "accepted", at,
                         preference_key="report_length", preference_value="short",
                         preference_scope="user", preference_category="communication_style",
                         actor_key="seat_1", subject_principal="user@example.com",
                         visibility=ORG_VISIBILITY, lineage_complete=True),
            FeedbackFact(f"fb_a_{i}", f"card_a_{i}", "accepted", at,
                         preference_key="notify", preference_value="slack",
                         preference_scope="user", preference_category="notification_style",
                         actor_key="seat_1", subject_principal="user@example.com",
                         visibility=ORG_VISIBILITY, lineage_complete=True),
        ])
    events = tuple(EnterpriseFact(
        f"evt_{i}", "weekly_review", "metrics_review", NOW - timedelta(days=i),
        visibility=ORG_VISIBILITY, lineage_complete=True)
        for i in range(3)) + (EnterpriseFact(
            "evt_memory", "investor_meeting", "temporary_memory", NOW,
            value={"date": "friday"}, explicit_memory=True,
            expires_at=NOW + timedelta(days=2), visibility=ORG_VISIBILITY,
            lineage_complete=True),)
    deliveries = (DeliveryFact(
        "d_1", "slack", "delivered", NOW - timedelta(seconds=1), NOW,
        visibility=ORG_VISIBILITY, lineage_complete=True),)
    batch = LearningBatch("org_1", NOW, feedback=tuple(feedback), outcomes=_outcomes(2, 8),
                          events=events, deliveries=deliveries)
    produced = {item.unit for item in run_units(batch)}
    assert produced == set(LearningUnit) - {LearningUnit.VALIDATION}
    assert len(ALL_ANALYSIS_UNITS) == 10
    assert validate_learning(learning(), LearningPolicy()).state is LearningState.VALIDATED


def test_schema_has_governance_lifecycle_three_brains_ttl_metrics_and_human_review():
    sql = (Path(__file__).resolve().parents[1] /
           "migrations/0045_atlas_l6_learning.sql").read_text().lower()
    for table in ("learning_policies", "learning_runs", "learning_objects",
                  "learning_transitions", "learned_brain_entries", "temporary_memories",
                  "knowledge_suggestions", "learning_metrics"):
        assert f"create table if not exists {table}" in sql
    assert "brain in ('organization','behavior','adaptive')" in sql
    assert "knowledge_suggestion" in sql
    assert "references orgs (id) on delete cascade" in sql


def test_live_reader_consumes_all_three_atlas_input_classes_and_real_outcomes():
    source = inspect.getsource(load_batch)
    assert "card_feedback_verdicts" in source
    assert "execution_outcomes" in source
    assert "graph_observations" in source
    assert "delivery_outbox" in source


def test_publisher_has_no_expert_branch_and_scheduler_wires_the_orchestrator():
    from genios_engine.feedback.store import publish_result

    source = inspect.getsource(publish_result)
    assert "BRAIN_TARGETS" in source
    assert "LearningTarget.KNOWLEDGE_SUGGESTION" in source
    assert "Expert" in publish.__doc__
    assert "knowledge suggestions must enter human review" in source
    scheduler = (Path(__file__).resolve().parents[1] / "genios_engine/api/routes.py").read_text()
    assert "run_learning(_graph, org, eval_time=now)" in scheduler


def test_learning_router_is_registered_on_the_application():
    from genios_engine.main import app

    paths = set(app.openapi()["paths"])
    assert "/v1/learning/overview" in paths
    assert "/v1/learning/objects/{learning_id}/review" in paths
    assert "/v1/learning/objects/{learning_id}/rollback" in paths


def test_orchestrator_claims_runs_applies_governance_and_reports_final_states(monkeypatch):
    from genios_engine.feedback import orchestrator

    class Engine:
        @contextmanager
        def begin(self):
            yield object()

    items = [learning(subject_key="one"), learning(subject_key="two")]
    completed = []
    evaluations = []
    monkeypatch.setattr(orchestrator, "lock_learning_tenant", lambda *_args: None)
    monkeypatch.setattr(orchestrator, "expire_memories", lambda _c, _o, _at: 2)
    monkeypatch.setattr(orchestrator, "claim_run",
                        lambda _c, _o, _at, _revision: ("run_1", True))
    monkeypatch.setattr(orchestrator, "load_batch", lambda _c, _o, _at: LearningBatch("org_1", NOW))
    monkeypatch.setattr(orchestrator, "ensure_policy",
                        lambda _c, _o, **_kw: LearningPolicy(revision=1))
    monkeypatch.setattr(orchestrator, "run_units", lambda _batch: items)
    monkeypatch.setattr(orchestrator, "persist_input_rejections", lambda *_args: 0)
    monkeypatch.setattr(orchestrator, "persist_object", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(orchestrator, "lifecycle_path", lambda _i, _p, **_kw: ())
    final = iter((LearningState.PUBLISHED, LearningState.HUMAN_REVIEW))
    monkeypatch.setattr(
        orchestrator, "apply_path_result",
        lambda _c, _i, _p, _at: ValidationResult(next(final), "test_result"))
    monkeypatch.setattr(orchestrator, "record_evaluation",
                        lambda *args, **kwargs: evaluations.append((args, kwargs)))
    monkeypatch.setattr(orchestrator, "complete_run",
                        lambda *args, **kwargs: completed.append((args, kwargs)))

    result = orchestrator.run_learning(type("Store", (), {"engine": Engine()})(),
                                       "org_1", eval_time=NOW)

    assert result["objects_inserted"] == 2
    assert result["objects_reevaluated"] == 0
    assert result["objects_unchanged"] == 0
    assert result["published"] == 1 and result["held"] == 1
    assert result["memories_expired"] == 2
    assert len(completed) == 1
    assert len(evaluations) == 2
