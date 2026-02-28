"""
Tests for J4 — Priority Scoring and J5 — Multi-Factor Evaluation.
"""

from layers.layer1_retrieval.retrieval_engine import RetrievalEngine
from layers.layer2_judgement.j4_priority.urgency_scorer import score_urgency
from layers.layer2_judgement.j4_priority.importance_scorer import score_priority
from layers.layer2_judgement.j5_multifactor.factor_extractors import (
    extract_all_factors,
    extract_actor_factors,
    extract_org_factors,
)
from layers.layer2_judgement.j5_multifactor.ranker import rank_factors
from layers.layer2_judgement.j5_multifactor.constraint_compiler import (
    evaluate_multifactor,
)
from layers.layer2_judgement.j2_policy.violation_engine import evaluate_policies
from layers.layer2_judgement.j3_risk.risk_aggregator import assess_risk
from core.contracts.judgement_report import RankedFactor


def _get_bundle(intent: str = "Follow up with Investor X"):
    engine = RetrievalEngine()
    return engine.run(intent=intent, workspace_id="w1", actor_id="u1")


# --- J4 Priority ---

def test_urgency_follow_up():
    bundle = _get_bundle("Follow up with Investor X")
    score, reasons = score_urgency(bundle, "follow_up")
    assert score >= 0.5
    assert len(reasons) > 0


def test_urgency_general():
    bundle = _get_bundle("What is the status?")
    score, reasons = score_urgency(bundle, "general")
    assert score <= 0.5


def test_priority_follow_up():
    bundle = _get_bundle("Follow up with Investor X")
    report = score_priority(bundle, "follow_up")
    assert report.score > 0.3
    assert report.distraction_flag is False
    assert len(report.reasons) > 0


def test_priority_general():
    bundle = _get_bundle("What is the status?")
    report = score_priority(bundle, "general")
    assert report.score < 0.6


# --- J5 Multi-Factor ---

def test_extract_actor_factors():
    bundle = _get_bundle("Follow up with Investor X")
    factors = extract_actor_factors(bundle)
    names = [f.name for f in factors]
    assert "preferred_tone" in names
    assert "actor_authority" in names


def test_extract_org_factors_vip():
    bundle = _get_bundle("Follow up with Investor X")
    factors = extract_org_factors(bundle)
    assert len(factors) > 0
    assert any(f.value == "VIP" for f in factors)


def test_extract_all_factors():
    bundle = _get_bundle("Follow up with Investor X")
    factors = extract_all_factors(bundle, "follow_up")
    categories = {f.category for f in factors}
    assert "actor" in categories
    assert "org" in categories


def test_rank_factors():
    factors = [
        RankedFactor(name="a", category="actor", weight=0.9),
        RankedFactor(name="b", category="org", weight=0.3),
        RankedFactor(name="c", category="tool", weight=0.7),
    ]
    ranked, confidence = rank_factors(factors, top_n=2)
    assert len(ranked) == 2
    assert ranked[0].name == "a"  # highest weight
    assert 0.0 <= confidence <= 1.0


def test_rank_factors_empty():
    ranked, confidence = rank_factors([])
    assert len(ranked) == 0
    assert confidence == 0.0


def test_multifactor_produces_constraints():
    bundle = _get_bundle("Follow up with Investor X")
    policy = evaluate_policies(bundle)
    risk = assess_risk(bundle, "follow_up")
    report = evaluate_multifactor(bundle, "follow_up", policy, risk)
    assert len(report.ranked_factors) > 0
    assert len(report.constraints) > 0
    assert report.confidence > 0


def test_multifactor_has_approval_constraint():
    bundle = _get_bundle("Follow up with Investor X")
    policy = evaluate_policies(bundle)
    risk = assess_risk(bundle, "follow_up")
    report = evaluate_multifactor(bundle, "follow_up", policy, risk)
    # VIP → needs_approval → constraint should say "do not send without approval"
    assert any("approval" in c.lower() for c in report.constraints)
