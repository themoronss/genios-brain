"""
Integration test — Full Layer 4 pipeline.

Tests the complete learning engine with Layers 1-3 outputs.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine
from layers.layer3_decision.decision_engine import DecisionEngine
from layers.layer4_learning.learning_engine import LearningEngine


def _run_full(intent: str, execution_result: str, **kwargs):
    """Run Layer 1 → 2 → 3 → 4."""
    r = RetrievalEngine()
    j = JudgementEngine()
    d = DecisionEngine()
    l = LearningEngine()
    bundle = r.run(intent=intent, workspace_id="w1", actor_id="u1")
    report = j.run(bundle)
    packet = d.run(bundle, report)
    return l.run(packet, execution_result, **kwargs)


def test_full_pipeline_approved():
    report = _run_full("Follow up with Investor X", "approved", user_feedback="approve")

    # Backward compat
    assert report.outcome == "approved"
    assert len(report.memory_updates) > 0

    # Outcome record
    assert report.outcome_record.execution_result == "approved"
    assert report.outcome_record.user_feedback == "approve"

    # Memory updates: at least one auto-approved
    assert any(u.auto_approved for u in report.memory_updates)

    # Policy suggestions: approval → threshold suggestion
    assert len(report.policy_suggestions) > 0

    # Eval
    assert report.eval_metrics.quality_score >= 0.7
    assert report.eval_metrics.success_rate == 1.0

    # Meta
    assert report.learning_version == "v1"
    assert report.learning_metrics.updates_proposed > 0


def test_full_pipeline_rejected():
    report = _run_full(
        "Cold outreach to investors", "rejected",
        user_feedback="reject", user_comment="Not the right time"
    )

    assert report.outcome == "rejected"
    assert report.eval_metrics.quality_score < 0.5
    assert report.eval_metrics.success_rate == 0.0
    assert len(report.policy_suggestions) > 0


def test_full_pipeline_auto_executed():
    report = _run_full("What is the status?", "auto_executed")

    assert report.outcome == "auto_executed"
    assert report.eval_metrics.success_rate == 1.0


def test_full_pipeline_failed_with_errors():
    report = _run_full(
        "Follow up with Investor X", "failed",
        tool_errors=[{"code": "TIMEOUT", "retried": True}],
        latency_ms=8000.0,
    )

    assert report.outcome == "failed"
    assert report.eval_metrics.red_flag_count >= 1
    assert report.outcome_record.retries == 1


def test_backward_compat_with_orchestrator():
    """Ensure old interface still works."""
    r = RetrievalEngine()
    j = JudgementEngine()
    d = DecisionEngine()
    l = LearningEngine()

    bundle = r.run("Follow up with Investor X", "w1", "u1")
    report = j.run(bundle)
    packet = d.run(bundle, report)

    # Old interface: just decision + result
    result = l.run(packet, "approved")

    assert result.outcome == "approved"
    assert isinstance(result.memory_updates, list)
