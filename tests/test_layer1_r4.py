"""
Tests for R4 — Policy Retrieval sub-modules.
Tests policy store, loader, and matcher.
"""

from core.stores.policy_store import PolicyStore
from layers.layer1_retrieval.r4_policies.policy_loader import PolicyLoader
from layers.layer1_retrieval.r4_policies.policy_matcher import PolicyMatcher
from core.contracts.query_plan import QueryPlan


# --- Policy Store ---

def test_policy_store_default_returns_policies():
    store = PolicyStore(use_db=False)
    policies = store.get_by_workspace("w1")
    assert len(policies) >= 2


def test_policy_store_wrong_workspace():
    store = PolicyStore(use_db=False)
    policies = store.get_by_workspace("nonexistent")
    assert len(policies) == 0


def test_policy_store_by_type():
    store = PolicyStore(use_db=False)
    org_policies = store.get_by_type("w1", "org")
    assert all(p["policy_type"] == "org" for p in org_policies)


# --- Policy Loader ---

def test_policy_loader_returns_policies():
    loader = PolicyLoader()
    plan = QueryPlan(
        intent_type="follow_up",
        raw_intent="Follow up",
        required_contexts=["policies"],
    )
    policies = loader.load("w1", plan)
    assert len(policies) >= 2


# --- Policy Matcher ---

def test_policy_matcher_vip_match():
    matcher = PolicyMatcher()
    policies = PolicyStore(use_db=False).get_by_workspace("w1")
    entity_data = {"Investor X": {"tier": "VIP"}}

    policy_ctx, sources = matcher.match(
        policies=policies,
        intent_type="follow_up",
        entities=["Investor X"],
        entity_data=entity_data,
    )

    # VIP policy should match
    matched_ids = [r.get("id") for r in policy_ctx.rules]
    assert "P_VIP_APPROVAL" in matched_ids
    assert len(sources) > 0


def test_policy_matcher_cold_outreach():
    matcher = PolicyMatcher()
    policies = PolicyStore(use_db=False).get_by_workspace("w1")

    policy_ctx, sources = matcher.match(
        policies=policies,
        intent_type="cold_outreach",
        entities=[],
        entity_data={},
    )

    matched_ids = [r.get("id") for r in policy_ctx.rules]
    assert "P_COLD_OUTREACH_REVIEW" in matched_ids


def test_policy_matcher_no_vip_no_match():
    matcher = PolicyMatcher()
    policies = PolicyStore(use_db=False).get_by_workspace("w1")
    entity_data = {"Regular Guy": {"tier": "standard"}}

    policy_ctx, sources = matcher.match(
        policies=policies,
        intent_type="follow_up",
        entities=["Regular Guy"],
        entity_data=entity_data,
    )

    matched_ids = [r.get("id") for r in policy_ctx.rules]
    assert "P_VIP_APPROVAL" not in matched_ids


def test_policy_matcher_trace_populated():
    matcher = PolicyMatcher()
    policies = PolicyStore(use_db=False).get_by_workspace("w1")

    policy_ctx, _ = matcher.match(
        policies=policies,
        intent_type="follow_up",
        entities=[],
        entity_data={},
    )

    assert len(policy_ctx.trace) == len(policies)
    assert all("matched" in t for t in policy_ctx.trace)
