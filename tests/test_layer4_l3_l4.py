"""
Tests for L3 Policy Suggestions and L4 Eval.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from layers.layer3_decision.decision_engine import DecisionEngine
from layers.layer4_learning.l1_outcomes.outcome_normalizer import normalize_outcome
from layers.layer4_learning.l2_memory_writeback.candidate_generator import generate_candidates
from layers.layer4_learning.l2_memory_writeback.write_policy_gate import gate_updates
from layers.layer4_learning.l3_policy_suggestions.suggestion_generator import (
    generate_suggestions,
)
from layers.layer4_learning.l4_eval.eval_aggregator import compute_eval_metrics


def _get_decision(intent="Follow up with Investor X"):
    r = RetrievalEngine()
    j = JudgementEngine()
    d = DecisionEngine()
    bundle = r.run(intent=intent, workspace_id="w1", actor_id="u1")
    report = j.run(bundle)
    return d.run(bundle, report)


# --- L3 Policy Suggestions ---

def test_suggestion_on_approval():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved", "approve")
    suggestions = generate_suggestions(decision, outcome)
    assert len(suggestions) > 0
    assert suggestions[0].suggestion_type == "threshold_change"


def test_suggestion_on_rejection():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "rejected", "reject", "Tone was wrong")
    suggestions = generate_suggestions(decision, outcome)
    assert any(s.suggestion_type == "guardrail" for s in suggestions)


def test_suggestion_on_tool_error():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "failed", tool_errors=[{"code": "TIMEOUT"}])
    suggestions = generate_suggestions(decision, outcome)
    assert any(s.suggestion_type == "new_policy" for s in suggestions)


# --- L4 Eval ---

def test_eval_success():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved")
    updates = gate_updates(generate_candidates(decision, outcome), "approved")
    metrics = compute_eval_metrics(decision, outcome, updates)
    assert metrics.quality_score >= 0.7
    assert metrics.success_rate == 1.0
    assert metrics.red_flag_count == 0


def test_eval_failure():
    decision = _get_decision()
    errors = [{"code": "TIMEOUT"}, {"code": "RATE_LIMIT"}]
    outcome = normalize_outcome(decision, "failed", tool_errors=errors)
    updates = []
    metrics = compute_eval_metrics(decision, outcome, updates)
    assert metrics.quality_score < 0.5
    assert metrics.success_rate == 0.0
    assert metrics.red_flag_count >= 1


def test_eval_high_latency():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved", latency_ms=10000.0)
    metrics = compute_eval_metrics(decision, outcome, [])
    assert any("latency" in f.lower() for f in metrics.red_flags)
