"""
Tests for L0 Router, L1 Outcomes, and L2 Memory Writeback.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from layers.layer3_decision.decision_engine import DecisionEngine
from layers.layer4_learning.l0_learning_router.learning_plan_builder import (
    build_learning_plan,
)
from layers.layer4_learning.l1_outcomes.outcome_normalizer import normalize_outcome
from layers.layer4_learning.l2_memory_writeback.candidate_generator import (
    generate_candidates,
)
from layers.layer4_learning.l2_memory_writeback.write_policy_gate import gate_updates


def _get_decision(intent="Follow up with Investor X"):
    r = RetrievalEngine()
    j = JudgementEngine()
    d = DecisionEngine()
    bundle = r.run(intent=intent, workspace_id="w1", actor_id="u1")
    report = j.run(bundle)
    return d.run(bundle, report)


# --- L0 Router ---

def test_plan_on_approval():
    decision = _get_decision()
    plan = build_learning_plan(decision, "approved", "approve")
    assert "outcomes" in plan["modules"]
    assert "memory_writeback" in plan["modules"]
    assert "eval" in plan["modules"]


def test_plan_on_rejection():
    decision = _get_decision()
    plan = build_learning_plan(decision, "rejected", "reject")
    assert "outcomes" in plan["modules"]
    assert "memory_writeback" not in plan["modules"]
    assert "policy_suggestions" in plan["modules"]


# --- L1 Outcomes ---

def test_outcome_normalization():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved", "approve", "", latency_ms=150.0)
    assert outcome.execution_result == "approved"
    assert outcome.user_feedback == "approve"
    assert len(outcome.side_effects) > 0
    assert outcome.latency_ms == 150.0
    assert outcome.tool_call_count > 0


def test_outcome_with_errors():
    decision = _get_decision()
    errors = [{"code": "RATE_LIMIT", "retried": True}, {"code": "TIMEOUT", "retried": False}]
    outcome = normalize_outcome(decision, "failed", tool_errors=errors)
    assert outcome.retries == 1
    assert len(outcome.tool_errors) == 2


# --- L2 Memory Writeback ---

def test_candidate_on_success():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved")
    candidates = generate_candidates(decision, outcome)
    fields = [c.field for c in candidates]
    assert "last_successful_intent" in fields


def test_candidate_on_failure():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "failed")
    candidates = generate_candidates(decision, outcome)
    assert any("failure_case" in c.field for c in candidates)


def test_candidate_on_edit():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved", "edit", "Too formal")
    candidates = generate_candidates(decision, outcome)
    assert any(c.field == "preference_edits" for c in candidates)
    assert any(c.review_required for c in candidates)


def test_gate_auto_approves_safe():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved")
    candidates = generate_candidates(decision, outcome)
    gated = gate_updates(candidates, "approved", "low")
    auto = [u for u in gated if u.auto_approved]
    assert len(auto) > 0


def test_gate_queues_preferences():
    decision = _get_decision()
    outcome = normalize_outcome(decision, "approved", "edit")
    candidates = generate_candidates(decision, outcome)
    gated = gate_updates(candidates, "approved", "low")
    prefs = [u for u in gated if "preference" in u.field]
    for p in prefs:
        assert p.review_required is True
