"""
Tests for J2 — Policy Compliance and J3 — Risk Assessment.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.j2_policy.violation_engine import evaluate_policies
from layers.layer2_judgement.j2_policy.approval_resolver import resolve_approvers
from layers.layer2_judgement.j3_risk.sensitive_entity_detector import (
    detect_sensitive_entities,
)
from layers.layer2_judgement.j3_risk.reversibility_scorer import score_reversibility
from layers.layer2_judgement.j3_risk.risk_aggregator import assess_risk


def _get_bundle(intent: str = "Follow up with Investor X"):
    engine = RetrievalEngine()
    return engine.run(intent=intent, workspace_id="w1", actor_id="u1")


# --- J2 Policy ---

def test_policy_vip_needs_approval():
    bundle = _get_bundle("Follow up with Investor X")
    verdict = evaluate_policies(bundle)
    assert verdict.status == "needs_approval"
    assert len(verdict.reasons) > 0


def test_policy_cold_outreach_risk_flag():
    bundle = _get_bundle("Cold outreach to new investor")
    verdict = evaluate_policies(bundle)
    assert any("risk" in v.lower() for v in verdict.violations) or verdict.status == "needs_approval"


def test_policy_general_allow():
    bundle = _get_bundle("What is the status?")
    verdict = evaluate_policies(bundle)
    # General intent with no VIP entity → fewer policy triggers
    assert verdict.status in ("allow", "needs_approval")


def test_approval_resolver():
    approvers = resolve_approvers(
        ["Approval required by policy P_VIP"],
        [{"policy_type": "org", "effect": {"requires_approval": True}}],
    )
    assert "founder" in approvers


# --- J3 Risk ---

def test_sensitive_entity_vip():
    bundle = _get_bundle("Follow up with Investor X")
    sensitive = detect_sensitive_entities(bundle, "follow_up")
    assert any("VIP" in s for s in sensitive)


def test_sensitive_entity_cold_outreach():
    bundle = _get_bundle("Cold outreach to new leads")
    sensitive = detect_sensitive_entities(bundle, "cold_outreach")
    assert "external_communication" in sensitive


def test_reversibility_email():
    rev, penalty = score_reversibility("follow_up")
    assert rev == "irreversible"
    assert penalty > 0


def test_reversibility_meeting():
    rev, penalty = score_reversibility("schedule_meeting")
    assert rev == "reversible"
    assert penalty == 0.0


def test_risk_aggregator_follow_up():
    bundle = _get_bundle("Follow up with Investor X")
    risk = assess_risk(bundle, "follow_up")
    assert risk.level in ("low", "medium", "high")
    assert len(risk.reasons) > 0
    assert len(risk.sensitive_entities) > 0
    assert risk.reversibility == "irreversible"
    assert 0.0 <= risk.score <= 1.0


def test_risk_aggregator_general():
    bundle = _get_bundle("What is the status?")
    risk = assess_risk(bundle, "general")
    assert risk.level == "low"
    assert risk.reversibility == "reversible"
