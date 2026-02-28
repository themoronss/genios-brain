"""
Integration test — Full Layer 2 pipeline.

Tests the complete judgement engine with Layer 1 ContextBundle
for multiple intent types.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.judgement_engine import JudgementEngine


def _run_full(intent: str):
    """Run both Layer 1 and Layer 2."""
    retrieval = RetrievalEngine()
    judgement = JudgementEngine()
    bundle = retrieval.run(intent=intent, workspace_id="w1", actor_id="u1")
    report = judgement.run(bundle)
    return report


# --- Full Pipeline Tests ---

def test_follow_up_vip():
    report = _run_full("Follow up with Investor X tomorrow")

    # Policy: VIP → needs_approval
    assert report.policy.status == "needs_approval"
    assert report.needs_approval is True

    # Risk: VIP + irreversible email → medium/high
    assert report.risk.level in ("medium", "high")
    assert len(report.risk.sensitive_entities) > 0
    assert report.risk.reversibility == "irreversible"

    # Sufficiency: should be complete (mock has all data)
    assert isinstance(report.need_more_info.value, bool)

    # Priority: follow-up to VIP → high
    assert report.priority.score > 0.3

    # Multi-factor: should have ranked factors + constraints
    assert len(report.multi_factor.ranked_factors) > 0
    assert len(report.multi_factor.constraints) > 0

    # ok_to_act: true (approval route, not blocked)
    assert report.ok_to_act is True

    # Version + metrics
    assert report.judgement_version == "v1"
    assert report.metrics.checks_run > 0


def test_schedule_meeting():
    report = _run_full("Schedule a meeting with John next week")

    # Risk should be lower for meetings
    assert report.risk.reversibility == "reversible"
    assert report.risk.score < 0.5

    # Priority
    assert report.priority.score > 0


def test_cold_outreach():
    report = _run_full("Cold outreach to potential investors")

    # Cold outreach → external comm → higher risk
    assert any("external" in s.lower() for s in report.risk.sensitive_entities)

    # Policy should flag it
    assert report.needs_approval is True or report.policy.status == "needs_approval"


def test_general_intent():
    report = _run_full("What is the current status?")

    # General → low risk, no tools, low priority
    assert report.risk.level == "low"
    assert report.risk.reversibility == "reversible"
    assert report.priority.score < 0.6


def test_backward_compat_with_layer3():
    """Ensure the old fields that Layer 3 uses still work."""
    report = _run_full("Follow up with Investor X")

    # Layer 3 uses these fields
    assert hasattr(report, "risk")
    assert hasattr(report, "policy")
    assert hasattr(report, "ok_to_act")
    assert hasattr(report, "needs_approval")

    # Layer 3 accesses .risk.reasons and .policy.reasons
    assert isinstance(report.risk.reasons, list)
    assert isinstance(report.policy.reasons, list)
    assert isinstance(report.risk.level, str)
