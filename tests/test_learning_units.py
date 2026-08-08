"""Layer 6 · Phase 3 — the analysis units (pure, deterministic, integer bp)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.contracts.learning import LearningPolicy, LearningTarget
from genios_engine.feedback.delivery_facts import DeliveryFact
from genios_engine.feedback.store import LearningBatch
from genios_engine.feedback.units import (
    ALL_ANALYSIS_UNITS,
    run_all_units,
    unit_knowledge_evolution,
    unit_outcome_analysis,
    unit_performance_optimization,
    unit_recommendation_learning,
    validate_learning,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
POLICY = LearningPolicy(org_id="org_1", revision=1)


def _outcome(play, label, **over):
    base = dict(execution_id=f"e_{play}_{label}", capability_id="sales", play_id=play, label=label,
                reminders_sent=0, escalations_fired=0, closed_at=NOW)
    base.update(over)
    return base


def _batch(**over):
    base = dict(org_id="org_1", since=NOW - timedelta(days=28))
    base.update(over)
    return LearningBatch(**base)


def test_outcome_analysis_counts_and_neutral_does_not_inflate_confidence():
    batch = _batch(outcomes=(_outcome("followup", "succeeded"),
                             _outcome("followup", "completed_unproven"),
                             _outcome("followup", "cancelled_by_world")))
    objs = unit_outcome_analysis(batch, POLICY, NOW)
    assert len(objs) == 1 and objs[0].target is LearningTarget.METRICS
    v = objs[0].proposed_value
    assert v["succeeded"] == 1 and v["neutral_unproven"] == 1 and v["failed"] == 1
    # confidence = graded/total = 2/3; neutral is excluded from graded
    assert objs[0].evidence.confidence_bp == round(2 * 10000 / 3)


def test_recommendation_penalises_attention_cost():
    cheap = tuple(_outcome("cheap", "succeeded") for _ in range(4))
    noisy = tuple(_outcome("noisy", "succeeded", reminders_sent=4, escalations_fired=1)
                  for _ in range(4))
    objs = {o.subject: o for o in unit_recommendation_learning(_batch(outcomes=cheap + noisy),
                                                               POLICY, NOW)}
    assert objs["play:cheap"].proposed_value["efficacy_bp"] > objs["play:noisy"].proposed_value["efficacy_bp"]


def test_performance_optimization_only_pre_delivery_failure_is_negative():
    facts = (
        DeliveryFact("d1", "e1", "slack", "high", "delivered", NOW, NOW, None, None, None, 1, False),
        DeliveryFact("d2", "e2", "slack", "high", "failed", None, None, None, None, None, 4, True),  # pre-delivery
        DeliveryFact("d3", "e3", "slack", "high", "failed", NOW, None, None, None, None, 2, False),  # post-delivery
    )
    obj = unit_performance_optimization(_batch(delivery=facts), POLICY, NOW)[0]
    assert obj.proposed_value["pre_delivery_failures"] == 1   # d2 only, not d3
    assert obj.target is LearningTarget.METRICS


def test_knowledge_evolution_only_for_sustained_poor_outcomes():
    good = tuple(_outcome("good", "succeeded") for _ in range(5))
    bad = tuple(_outcome("bad", "cancelled_by_world") for _ in range(5))
    subjects = {o.subject for o in unit_knowledge_evolution(_batch(outcomes=good + bad), POLICY, NOW)}
    assert subjects == {"play:bad"}                           # only the failing play escalates
    objs = unit_knowledge_evolution(_batch(outcomes=bad), POLICY, NOW)
    assert objs[0].target is LearningTarget.KNOWLEDGE_SUGGESTION


def test_validation_gates_brains_but_passes_artifacts():
    from genios_engine.contracts.learning import (LearningEvidence, LearningObject, Visibility,
                                                  VisibilityScope)
    weak = LearningObject(org_id="o", unit="pattern_learning", target=LearningTarget.ORGANIZATION,
                          subject="s", proposed_value={}, first_seen_at=NOW, last_seen_at=NOW,
                          policy_key="p", visibility=Visibility(VisibilityScope.ORGANIZATION),
                          evidence=LearningEvidence(observations=1, independent_refs=1,
                                                    distinct_days=1, positive=1, negative=0,
                                                    confidence_bp=1000))
    ok, reason = validate_learning(weak, POLICY)
    assert ok is False and reason == "insufficient_observations"
    metric = LearningObject(org_id="o", unit="outcome_analysis", target=LearningTarget.METRICS,
                            subject="s", proposed_value={}, first_seen_at=NOW, last_seen_at=NOW,
                            policy_key="p", visibility=Visibility(VisibilityScope.ORGANIZATION),
                            evidence=LearningEvidence(observations=1, independent_refs=1,
                                                      distinct_days=1, positive=1, negative=0,
                                                      confidence_bp=100))
    assert validate_learning(metric, POLICY)[0] is True       # a metric is not a claim to believe


def test_empty_batch_emits_nothing_from_every_unit():
    assert run_all_units(_batch(), POLICY, NOW) == []


def test_there_are_ten_analysis_units_in_canonical_order():
    assert len(ALL_ANALYSIS_UNITS) == 10
    assert ALL_ANALYSIS_UNITS[1].__name__ == "unit_outcome_analysis"
