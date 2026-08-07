from __future__ import annotations

import math
from datetime import datetime, timezone
from itertools import permutations
from types import SimpleNamespace

import pytest

from genios_engine.reason import intelligence
from genios_engine.reason.composer import plan_composites
from genios_engine.reason.intelligence import (
    _envelope,
    _fixed_recommendation,
    _prompt,
    _route,
    _validated_explanation,
)
from genios_engine.reason.runner import _neighborhood, _verified_stakeholder_count
from genios_engine.reason.authority import AUDITED_SIGNAL_PREDICATE, projected_score


NOW = datetime(2026, 8, 6, 12, 30, tzinfo=timezone.utc)


def test_basis_point_utility_projection_uses_half_up_rounding():
    assert projected_score(7_649) == 76
    assert projected_score(7_650) == 77
    assert projected_score(10_000) == 100


def test_live_authority_requires_exact_embedded_policy_and_gating_proofs():
    sql = AUDITED_SIGNAL_PREDICATE.lower()
    assert "authority_gating_result.output->'matched'='true'::jsonb" in sql
    assert "authority_embedded_check" in sql and "authority_missing_check" in sql
    assert "read_only_policy_pass" in sql
    assert "human_approval_boundary_pass" in sql
    assert "evidence_policy_pass" in sql
    assert "verified_recipient_guard_pass" in sql
    assert "select count(*) from reasoning_candidate_checks" not in sql


def _signal(*, rule_id: str, reason_code: str, score: int, play: str,
            subject_node_id: str = "deal_1", marker: str | None = None):
    return SimpleNamespace(
        rule_id=rule_id,
        reason_code=reason_code,
        score=score,
        play=play,
        evidence={"field": "deal.status", "value": "open"},
        display_name="Acme",
        subject_node_id=subject_node_id,
        score_inputs={"marker": marker or rule_id, "C": 90},
        reasoning_run_id=f"run_{rule_id}",
    )


@pytest.mark.parametrize(
    "confidence",
    [-math.inf, -100.0, -1.0, 0.0, 0.499, 0.5, 0.8, 1.0, 100.0, math.inf, math.nan],
)
def test_route_never_grants_autonomous_authority(confidence):
    route = _route(confidence)
    assert route in {"flag", "notify"}
    assert route != "autonomous"


def test_fixed_recommendation_uses_the_stable_top_signal_for_action():
    top = _signal(rule_id="cooling_deal", reason_code="cooling_deal", score=82,
                  play="restore_momentum")
    secondary = _signal(rule_id="single_threaded", reason_code="single_threaded_deal", score=71,
                        play="multithread_account")

    first = _fixed_recommendation([top, secondary], "Acme")
    second = _fixed_recommendation([top, secondary], "Acme")

    assert first == second
    assert first["action"] == "restore_momentum"
    assert "cooling deal" in first["headline"]
    assert "single threaded deal" in first["headline"]
    assert secondary.play not in first.values()


def test_fixed_recommendation_has_a_deterministic_no_signal_fallback():
    assert _fixed_recommendation([], "Acme") == {
        "headline": "No audited recommendation yet",
        "action": "no_action",
        "reasoning": "No open signal with a complete Layer 4 reasoning trace matched.",
    }


def test_unlinked_signal_cannot_select_an_action():
    signal = _signal(rule_id="legacy", reason_code="cooling_deal", score=99,
                     play="restore_momentum")
    signal.reasoning_run_id = None

    assert _fixed_recommendation([signal], "Acme")["action"] == "no_action"


def test_prompt_allows_only_an_explanation_output_field():
    signal = _signal(rule_id="cooling_deal", reason_code="cooling_deal", score=82,
                     play="restore_momentum")
    fixed = _fixed_recommendation([signal], "Acme")
    prompt = _prompt("Should I follow up?", "sales", [signal], [], fixed, {}, "Acme")

    assert "ALREADY fixed" in prompt
    assert "Do not choose, modify, rank, or add an action" in prompt
    assert "Do not output confidence" in prompt
    output_contract = prompt.split("Return STRICT JSON only:", 1)[1]
    assert '"explanation"' in output_contract
    assert '"action"' not in output_contract
    assert '"confidence"' not in output_contract


def _make_envelope(*, action: str = "restore_momentum"):
    return _envelope(
        "org_1",
        42,
        recommendation={
            "headline": "Restore Acme momentum",
            "action": action,
            "reasoning": "The cooling-deal signal is strongest.",
        },
        confidence=0.73,
        derivation=[{
            "rule_id": "cooling_deal",
            "conclusion": "cooling_deal",
            "matched_facts": {"derived.engagement": 0.4},
            "about": "Acme",
            "score": 82.0,
        }],
        uncertainty=[],
        route="notify",
        evaluation_time=NOW,
        decision_key="sales:should i follow up?",
        triggered_by="query",
        foresight={"close_probability": 0.43},
        explanation="The relationship is cooling while the deal remains open.",
    )


def test_envelope_is_deterministic_for_identical_explicit_inputs():
    first = _make_envelope()
    second = _make_envelope()

    assert first == second
    assert first["decision_id"] == second["decision_id"]
    assert first["as_of"] == {"graph_version": 42, "timestamp": NOW.isoformat()}


def test_envelope_identity_changes_when_the_semantic_decision_changes():
    restore = _make_envelope(action="restore_momentum")
    multithread = _make_envelope(action="multithread_account")

    assert restore != multithread
    assert restore["decision_id"] != multithread["decision_id"]


def test_envelope_identity_covers_the_rendered_explanation():
    first = _make_envelope()
    second = _make_envelope()
    second = _envelope(
        "org_1", 42, recommendation=second["recommendation"], confidence=0.73,
        derivation=second["derivation"], uncertainty=[], route="notify",
        evaluation_time=NOW, decision_key="sales:should i follow up?", triggered_by="query",
        foresight={"close_probability": 0.43},
        explanation="A different but still grounded rendering.",
    )

    assert first["decision_id"] != second["decision_id"]


@pytest.mark.parametrize(
    ("explanation", "reason"),
    [
        ("You should email the CFO now.", "action_language"),
        ("The deal is cooling and worth $9000000.", "invented_number"),
        ("The deal is cooling because Priya objected.", "invented_entity"),
        ("Acme is not cooling.", "unsupported_negation"),
        ("The deal is cooling because budget approval happened.", "ungrounded_term"),
    ],
)
def test_explanation_renderer_rejects_new_actions_numbers_and_entities(explanation, reason):
    signal = _signal(rule_id="cooling_deal", reason_code="cooling_deal", score=82,
                     play="restore_momentum")
    fixed = _fixed_recommendation([signal], "Acme")

    accepted, rejected_for = _validated_explanation(
        explanation, fixed=fixed, signals=[signal], facts=[], extra={}, focus="Acme")

    assert accepted is None
    assert rejected_for == reason


def test_explanation_renderer_accepts_concise_grounded_non_prescriptive_prose():
    signal = _signal(rule_id="cooling_deal", reason_code="cooling_deal", score=82,
                     play="restore_momentum")
    fixed = _fixed_recommendation([signal], "Acme")

    accepted, rejected_for = _validated_explanation(
        "Acme has a cooling deal signal.", fixed=fixed, signals=[signal], facts=[],
        extra={}, focus="Acme")

    assert accepted == "Acme has a cooling deal signal."
    assert rejected_for is None


def test_query_identity_covers_user_supplied_facts(monkeypatch):
    signal = _signal(rule_id="cooling_deal", reason_code="cooling_deal", score=82,
                     play="restore_momentum")
    monkeypatch.setattr(intelligence, "_retrieve", lambda *_args: ([signal], [], None))

    first, _ = intelligence.run_query(
        org_id="org_1", module_id="sales", question="What now?",
        extra_facts={"segment": "enterprise"}, store=object(), llm=None, registry=None,
        graph_version=42, eval_time=NOW)
    second, _ = intelligence.run_query(
        org_id="org_1", module_id="sales", question="What now?",
        extra_facts={"segment": "startup"}, store=object(), llm=None, registry=None,
        graph_version=42, eval_time=NOW)

    assert first["decision_id"] != second["decision_id"]


def test_query_rejects_renderer_protocol_expansion_and_uses_deterministic_fallback(monkeypatch):
    signal = _signal(rule_id="cooling_deal", reason_code="cooling_deal", score=82,
                     play="restore_momentum")
    monkeypatch.setattr(intelligence, "_retrieve", lambda *_args: ([signal], [], None))
    llm = SimpleNamespace(call=lambda *_args, **_kwargs: SimpleNamespace(
        ok=True,
        parsed={"explanation": "You should email the CFO now.", "action": "wire_money"},
    ))

    env, _ = intelligence.run_query(
        org_id="org_1", module_id="sales", question="What now?", extra_facts={},
        store=object(), llm=llm, registry=None, graph_version=42, eval_time=NOW)

    assert env["recommendation"]["action"] == "restore_momentum"
    assert env["explanation"] == env["recommendation"]["reasoning"]
    assert {item["kind"] for item in env["uncertainty"]} >= {"llm_explanation_rejected"}


def test_no_grounding_never_returns_an_actionable_recommendation(monkeypatch):
    monkeypatch.setattr(intelligence, "_retrieve", lambda *_args: ([], [], None))

    env, result = intelligence.run_query(
        org_id="org_1", module_id="sales", question="What now?", extra_facts={},
        store=object(), llm=object(), registry=None, graph_version=42, eval_time=NOW)

    assert result is None
    assert env["recommendation"]["action"] == "no_action"
    assert env["route"] == "flag"


def test_neighborhood_equal_timestamp_tie_is_permutation_invariant():
    timestamp = datetime(2026, 8, 5, 9, tzinfo=timezone.utc)
    fact_idx = {
        "contact_b": {"deal.status": ("lost", timestamp)},
        "contact_a": {"deal.status": ("open", timestamp)},
        "contact_c": {"deal.value": (500_000, timestamp)},
    }
    obs_idx = {
        "contact_a": {"buying_intent"},
        "contact_b": {"objection"},
        "contact_c": {"pricing_discussed"},
    }

    results = []
    for order in permutations(("contact_a", "contact_b", "contact_c")):
        results.append(_neighborhood("deal_1", {"deal_1": order}, obs_idx, fact_idx))

    assert all(result == results[0] for result in results)
    edge_count, observations, facts = results[0]
    assert edge_count == 3
    assert observations == {"buying_intent", "objection", "pricing_discussed"}
    assert facts == {"deal.status": "open", "deal.value": 500_000}


def test_verified_stakeholder_count_excludes_generic_and_unverified_edges():
    adjacency = {"deal_1": {"person_verified", "person_unverified", "company_1", "meeting_1"}}
    node_types = {
        "person_verified": "person",
        "person_unverified": "person",
        "company_1": "company",
        "meeting_1": "meeting",
    }
    facts = {
        "person_verified": {"contact.verified_recipient": (True, NOW, 3, 0.95)},
        "person_unverified": {"contact.verified_recipient": (False, NOW, 3, 0.95)},
        "company_1": {"contact.verified_recipient": (True, NOW, 3, 0.95)},
    }

    assert _verified_stakeholder_count("deal_1", adjacency, node_types, facts) == 1


def test_verified_stakeholder_count_rejects_low_authority_or_low_confidence_claims():
    adjacency = {"deal_1": {"low_rank", "low_confidence"}}
    node_types = {"low_rank": "person", "low_confidence": "person"}
    facts = {
        "low_rank": {"contact.verified_recipient": (True, NOW, 1, 0.99)},
        "low_confidence": {"contact.verified_recipient": (True, NOW, 3, 0.3)},
    }

    assert _verified_stakeholder_count("deal_1", adjacency, node_types, facts) == 0


def test_composite_equal_score_ties_have_a_total_order_under_all_permutations():
    signals = [
        _signal(rule_id="alpha_p2", reason_code="alpha_risk", score=80,
                play="review", subject_node_id="person_2", marker="person_2"),
        _signal(rule_id="alpha_p1", reason_code="alpha_risk", score=80,
                play="review", subject_node_id="person_1", marker="person_1"),
        _signal(rule_id="beta_p3", reason_code="beta_risk", score=80,
                play="review", subject_node_id="person_3", marker="person_3"),
    ]
    adjacency_orders = list(permutations(("person_1", "person_2", "person_3")))

    plans = []
    for signal_order in permutations(signals):
        for neighbor_order in adjacency_orders:
            plans.append(plan_composites(
                ["deal_1"], list(signal_order), {"deal_1": neighbor_order}))

    assert all(plan == plans[0] for plan in plans)
    assert plans[0][0]["codes"] == ["alpha_risk", "beta_risk"]
    assert plans[0][0]["inputs"]["marker"] == "person_1"
    assert plans[0][0]["inputs"]["composite_of"] == ["alpha_risk", "beta_risk"]
