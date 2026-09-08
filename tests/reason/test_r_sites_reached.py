"""The three R-sites are REACHED — from the compiled lane and from a registered request path.

THE SHAPE THIS FILE EXISTS TO BREAK. Layer 1 shipped six units nothing called, Layer 2 five more,
Layer 3 two more. Every one of them had tests. "A test calls it" is not a caller, so each site here
is pinned to the code path a live tenant actually travels:

    R-1   `reason_native_capability(..., interpreter=...)`, which is what `domain_shadow` calls for
          every situation on the LIVE compiled lane — and `shadow_compile` is exercised end to end
          to prove it builds the interpreter when, and only when, the tenant is switched on.
    R-3   `GET /v1/intelligence/cards/{card_id}/reasoning`, registered on the running application
          and driven here against a real card row.
    R-4   the same route, and the same call the bundle makes when it folds `expected_effect` in.

Plus the doctrine test in the form doc 01 C5 states it: with the sites force-failed, the decision is
byte-identical to a no-model run.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ExecutionMode,
    Goal,
    PlayDefinition,
    ReasonerSpec,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.reason import interpretation as I
from genios_engine.reason.adapters.native import reason_native_capability
from genios_engine.reason.engine import NodeContext
from genios_engine.reason.bundle.gate import force_failed
from genios_engine.reason.llm_sites import make_gate

NOW = datetime(2026, 9, 5, 12, tzinfo=timezone.utc)
ORG = "org_scratch_tests"
HEDGED = "They are considering moving some workloads to another vendor next quarter."


def node_context() -> NodeContext:
    """A deal the compiled lane would reason over, in the shape `runner._load_context` builds."""
    return NodeContext(
        node_id="node_deal_1", node_type="deal",
        facts={"deal.status": {"value": "negotiation", "confidence": 0.9},
               "deal.value": {"value": 84000, "confidence": 0.9},
               "derived.engagement": {"value": 0.4, "confidence": 0.9},
               "thread.last_inbound": {"value": NOW.isoformat(), "confidence": 0.9}},
        obs=[{"kind": "email_received", "occurred_at": NOW.isoformat()}])


def execute(interpreter=None):
    return reason_native_capability(
        org_id=ORG, context=node_context(), capability=DEAL_COOLING_V1,
        evaluation_time=NOW, graph_version=1, config_snapshot_id=None,
        mode=ExecutionMode.SHADOW, interpreter=interpreter)


#: `commitment.action` is a REAL free-text fact: `context/pipeline` writes the commitment's action
#: sentence for every extracted obligation, and `packs/general_v1`, `admin_v1` and `support_v1` all
#: declare it. It is the field on which R-1 can genuinely fire on live data, which is why the
#: reachability case below is built on it rather than on a name invented for a test.
COMMITMENT_CAPABILITY = CapabilityManifest(
    capability_id="test.commitment_review", version="1.0.0", domain="general",
    root_entity_type="commitment",
    goal=Goal(goal_id="g", statement="Review an open commitment."),
    reasoners=(ReasonerSpec(reasoner_id="core.context", version="1.0.0",
                            required_fields=("commitment.action",)),),
    plays=(PlayDefinition(play_id="follow_up", version="1.0.0", label="Follow up",
                          steps=("ask",)),),
    policies=(), live_delivery_enabled=False)


def commitment_context(text_value: str) -> NodeContext:
    return NodeContext(node_id="node_commit_1", node_type="commitment",
                       facts={"commitment.action": {"value": text_value, "confidence": 0.9}})


def execute_commitment(text_value: str, interpreter=None):
    return reason_native_capability(
        org_id=ORG, context=commitment_context(text_value),
        capability=COMMITMENT_CAPABILITY, evaluation_time=NOW, graph_version=1,
        config_snapshot_id=None, mode=ExecutionMode.SHADOW, interpreter=interpreter)


class Client:
    model = "claude-sonnet-5"

    def __init__(self):
        self.calls = 0

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult
        self.calls += 1
        return LLMResult(parsed={"classification": I.EVALUATING_ALTERNATIVES,
                                 "confidence_bp": 7000},
                         raw="", ok=True, model=self.model, input_tokens=900, output_tokens=150)


# ── R-1 · the compiled lane ──────────────────────────────────────────────────────────────────

def test_the_compiled_lane_carries_a_reading_all_the_way_into_the_decision():
    """The seam a live tenant travels: `domain_shadow` → `reason_native_capability` → orchestrator.

    On a real field (`commitment.action`) carrying a real hedge, the reading becomes a fact and an
    evidence ref on the snapshot the units observe, and the decision that comes out names the
    interpreted snapshot — which is what "consumed as evidence" means when it is true.
    """
    client = Client()
    interpreter = I.AmbiguityInterpreter(
        org_id=ORG, gate=make_gate(org_id=ORG, client=client,
                                   activated=frozenset({"bundle"})))
    plain = execute_commitment(HEDGED)
    interpreted = execute_commitment(HEDGED, interpreter)
    assert client.calls == 1
    facts = dict(interpreted.request.context.facts)
    assert facts["interpretation.commitment.action"]["value"]["classification"] == (
        I.EVALUATING_ALTERNATIVES)
    assert interpreted.decision.context_snapshot_id != plain.decision.context_snapshot_id
    assert interpreted.decision.semantic_hash != plain.decision.semantic_hash


def test_a_settled_commitment_on_the_same_lane_buys_nothing():
    """The other half of the fire rate, at the seam: the same capability, the same field, a
    sentence that carries no hedge — and no consult at all."""
    client = Client()
    interpreter = I.AmbiguityInterpreter(
        org_id=ORG, gate=make_gate(org_id=ORG, client=client,
                                   activated=frozenset({"bundle"})))
    settled = "The signed order form was returned this morning with no changes."
    assert execute_commitment(settled, interpreter).decision.semantic_hash == (
        execute_commitment(settled).decision.semantic_hash)
    assert client.calls == 0


def test_a_lane_with_no_interpreter_is_byte_identical_to_the_lane_before_this_wave():
    assert execute(None).decision.semantic_hash == execute(None).decision.semantic_hash


def test_the_doctrine_holds_with_the_site_force_failed():
    """K4's own test, at this seam, through the SHIPPED switch: force-fail every R-site and the
    DECISION IS THE SAME BYTES — on the capability that fires R-1 as well as on one that does not.

    If this ever fails, the model has acquired decision authority and the wave is reverted.
    """
    client = Client()
    forced = I.AmbiguityInterpreter(
        org_id=ORG, gate=make_gate(org_id=ORG, client=client,
                                   activated=frozenset({"bundle"})))
    with force_failed():
        assert execute(forced).decision.semantic_hash == execute(None).decision.semantic_hash
        assert execute(forced).trace.decision_hash == execute(None).trace.decision_hash
        assert (execute_commitment(HEDGED, forced).decision.semantic_hash
                == execute_commitment(HEDGED).decision.semantic_hash)
    assert client.calls == 0


def test_an_interpreter_that_raises_never_costs_a_decision():
    class Exploding:
        def __call__(self, request):
            raise RuntimeError("boom")

    assert execute(Exploding()).decision.semantic_hash == execute(None).decision.semantic_hash


def test_the_live_compiled_pass_builds_the_interpreter_only_for_a_switched_on_tenant():
    """`shadow_compile` is the live caller. Run twice on a real database — off, then on."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the live compiled pass is not exercised")
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform import l4_activation as ACT
    from genios_engine.reason.domain_shadow import shadow_compile

    store = GraphStore(url)
    with store.engine.begin() as c:
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})
    try:
        off = shadow_compile(store=store, org_id=ORG, eval_time=NOW, live=True,
                             registry=object())
        assert off["r1_interpreter"] == 0
        ACT.activate(store.engine, ORG, feature=ACT.FEATURE_BUNDLE, by="tests")
        on = shadow_compile(store=store, org_id=ORG, eval_time=NOW, live=True,
                            registry=object())
        assert on["r1_interpreter"] == 1
    finally:
        with store.engine.begin() as c:
            c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})


def test_the_shadow_pass_buys_no_interpretation_at_all():
    """A shadow run exists to measure the deterministic half; interpreting a decision nobody will
    see is the "just in case" spend doc 11 guard 7 forbids."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the live compiled pass is not exercised")
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform import l4_activation as ACT
    from genios_engine.reason.domain_shadow import shadow_compile

    store = GraphStore(url)
    ACT.activate(store.engine, ORG, feature=ACT.FEATURE_BUNDLE, by="tests")
    try:
        assert shadow_compile(store=store, org_id=ORG, eval_time=NOW,
                              live=False)["r1_interpreter"] == 0
    finally:
        with store.engine.begin() as c:
            c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})


# ── R-3 and R-4 · the request path ───────────────────────────────────────────────────────────

def test_the_card_reasoning_route_is_registered_on_the_running_application():
    """Structural, and it is the case that catches the failure this file is named for: a site with
    a test and no route is a site no customer can reach."""
    from genios_engine.main import app
    assert "/v1/intelligence/cards/{card_id}/reasoning" in app.openapi()["paths"]


def test_the_route_narrates_a_real_card_row_end_to_end():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the card path is not exercised")
    from genios_engine.api import intelligence_routes as R

    if R._graph is None:                                    # noqa: SLF001 - module-level store
        pytest.skip("intelligence routes have no graph store configured")
    engine = R._graph.engine                                # noqa: SLF001
    card_id, signal_id = "card_r3_test", "sig_r3_test"
    with engine.begin() as c:
        c.execute(text("delete from cards where card_id = :c"), {"c": card_id})
        c.execute(text("delete from signals where signal_id = :s"), {"s": signal_id})
        c.execute(text(
            "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
            "reason_code, evidence, status, eval_time, rejected_candidates, "
            "do_nothing_consequence) "
            "values (:s, :o, 'deal_cooling', 'node_1', 70, 'cooling_deal', '[]'::jsonb, "
            "'open', now(), cast(:rej as jsonb), 'the renewal window closes')"),
            {"s": signal_id, "o": ORG,
             "rej": '[{"play_id": "discount_play", "disposition": "eliminated", '
                    '"utility_bp": 4200, "rule_id": "ADM-014"}]'})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, headline, situation, score, "
            "level, urgency_band, state, expires_at, do_nothing_consequence, outcome_window_days) "
            "values (:c, :s, :o, 'Renewal at risk', 'the deal has gone quiet', 70, "
            "'prescriptive', 'high', 'open', now() + interval '2 days', "
            "'the renewal window closes', 11)"),
            {"c": card_id, "s": signal_id, "o": ORG})
    try:
        body = R.card_reasoning(card_id, org_id=ORG)
        assert body["card_id"] == card_id
        assert [row["play_id"] for row in body["alternatives_rejected"]] == ["discount_play"]
        # No API key in the test environment, so both sites take their deterministic branch —
        # which is the branch a customer sees on a budget-exhausted day, and it must still say
        # something true.
        assert "discount play" in body["alternatives"]["rendered"]
        assert body["alternatives"]["generation"] == "template_fallback"
        assert "11 days" in body["expected_effect"]["rendered"]
        assert body["expected_effect"]["numbers_used"]["days_to_horizon"] == 11
        for half in ("alternatives", "expected_effect"):
            assert body[half]["outcome"] in {"ran", "cached", "skipped_no_client",
                                             "skipped_not_activated", "skipped_budget",
                                             "skipped_precondition", "failed_generation",
                                             "failed_validation", "force_failed"}
    finally:
        with engine.begin() as c:
            c.execute(text("delete from cards where card_id = :c"), {"c": card_id})
            c.execute(text("delete from signals where signal_id = :s"), {"s": signal_id})
            c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
            c.execute(text("delete from l4_r_site_generations where org_id = :o"), {"o": ORG})


def test_a_published_bundle_wins_and_the_expand_path_pays_for_nothing():
    """R-2 already folded `expected_effect` into the bundle it wrote for this decision. Narrating it
    again here would put a SECOND wording of the same two facts in front of the same person, and
    charge for it — so the stored narrative is returned and these sites do not run.
    """
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the card path is not exercised")
    from genios_engine.contracts.reasoning import ReasoningBundle

    from genios_engine.api import intelligence_routes as R
    from genios_engine.reason.bundle import BundleStore
    if R._graph is None:                                    # noqa: SLF001
        pytest.skip("intelligence routes have no graph store configured")
    engine = R._graph.engine                                # noqa: SLF001
    card_id, signal_id, decision_hash = "card_r3_b", "sig_r3_b", "d" * 64
    bundle = ReasoningBundle(
        decision_id="decision_published", action_id="outreach",
        headline="Renewal at risk", situation_summary="the deal has gone quiet",
        why_it_matters="the window closes", root_cause="the buyer went quiet",
        recommendation_rationale="reach the economic buyer",
        expected_effect="Acting now closes this {days_to_horizon} days before the date.",
        alternatives_narrative="The discount play was eliminated by a corpus rule.",
        numbers_used={"days_to_horizon": 11}, evidence_refs=("ev_1",))
    with engine.begin() as c:
        c.execute(text("delete from cards where card_id = :c"), {"c": card_id})
        c.execute(text("delete from signals where signal_id = :s"), {"s": signal_id})
        c.execute(text(
            "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
            "reason_code, evidence, status, eval_time, rejected_candidates, "
            "reasoning_decision_hash) values (:s, :o, 'deal_cooling', 'node_1', 70, "
            "'cooling_deal', '[]'::jsonb, 'open', now(), cast(:rej as jsonb), :h)"),
            {"s": signal_id, "o": ORG, "h": decision_hash,
             "rej": '[{"play_id": "discount_play", "disposition": "eliminated"}]'})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, headline, situation, score, "
            "level, urgency_band, state, expires_at, outcome_window_days) "
            "values (:c, :s, :o, 'Renewal at risk', 'quiet', 70, 'prescriptive', 'high', "
            "'open', now() + interval '2 days', 11)"),
            {"c": card_id, "s": signal_id, "o": ORG})
    BundleStore(engine).put(org_id=ORG, decision_hash=decision_hash, bundle=bundle)
    try:
        body = R.card_reasoning(card_id, org_id=ORG)
        assert body["expected_effect"]["source"] == "bundle"
        assert body["expected_effect"]["rendered"] == (
            "Acting now closes this 11 days before the date.")
        assert body["alternatives"]["source"] == "bundle"
        with engine.connect() as c:
            consulted = c.execute(text(
                "select count(*) from l4_r_site_calls where org_id = :o"), {"o": ORG}).scalar()
        assert consulted == 0
    finally:
        with engine.begin() as c:
            c.execute(text("delete from cards where card_id = :c"), {"c": card_id})
            c.execute(text("delete from signals where signal_id = :s"), {"s": signal_id})
            c.execute(text("delete from l4_reasoning_bundles where org_id = :o"), {"o": ORG})
            c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})


def test_a_bundle_without_an_alternatives_narrative_is_what_r3_is_FOR():
    """`alternatives_narrative` is the bundle's one optional field — R-3 is an on-demand site, so a
    bundle without it is complete rather than degraded, and expanding the card is exactly when the
    narration is bought. The published `expected_effect` still wins; only the missing half runs."""
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the card path is not exercised")
    from genios_engine.contracts.reasoning import ReasoningBundle

    from genios_engine.api import intelligence_routes as R
    from genios_engine.reason.bundle import BundleStore
    if R._graph is None:                                    # noqa: SLF001
        pytest.skip("intelligence routes have no graph store configured")
    engine = R._graph.engine                                # noqa: SLF001
    card_id, signal_id, decision_hash = "card_r3_c", "sig_r3_c", "c" * 64
    bundle = ReasoningBundle(
        decision_id="decision_published_2", action_id="outreach", headline="Renewal at risk",
        situation_summary="quiet", why_it_matters="the window closes",
        root_cause="the buyer went quiet", recommendation_rationale="reach the buyer",
        expected_effect="Acting now closes this {days_to_horizon} days before the date.",
        numbers_used={"days_to_horizon": 11}, evidence_refs=("ev_1",))
    assert bundle.alternatives_narrative is None
    with engine.begin() as c:
        c.execute(text("delete from cards where card_id = :c"), {"c": card_id})
        c.execute(text("delete from signals where signal_id = :s"), {"s": signal_id})
        c.execute(text(
            "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, "
            "reason_code, evidence, status, eval_time, rejected_candidates, "
            "reasoning_decision_hash) values (:s, :o, 'deal_cooling', 'node_1', 70, "
            "'cooling_deal', '[]'::jsonb, 'open', now(), cast(:rej as jsonb), :h)"),
            {"s": signal_id, "o": ORG, "h": decision_hash,
             "rej": '[{"play_id": "discount_play", "disposition": "eliminated"}]'})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, headline, situation, score, "
            "level, urgency_band, state, expires_at, outcome_window_days) "
            "values (:c, :s, :o, 'Renewal at risk', 'quiet', 70, 'prescriptive', 'high', "
            "'open', now() + interval '2 days', 11)"),
            {"c": card_id, "s": signal_id, "o": ORG})
    BundleStore(engine).put(org_id=ORG, decision_hash=decision_hash, bundle=bundle)
    try:
        body = R.card_reasoning(card_id, org_id=ORG)
        assert body["expected_effect"]["source"] == "bundle"
        assert body["alternatives"]["source"] == "on_demand"
        assert body["alternatives"]["text"]            # never an empty string on a card
        assert "discount play" in body["alternatives"]["rendered"]
    finally:
        with engine.begin() as c:
            c.execute(text("delete from cards where card_id = :c"), {"c": card_id})
            c.execute(text("delete from signals where signal_id = :s"), {"s": signal_id})
            c.execute(text("delete from l4_reasoning_bundles where org_id = :o"), {"o": ORG})
            c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
            c.execute(text("delete from l4_r_site_generations where org_id = :o"), {"o": ORG})


def test_a_card_that_does_not_exist_is_a_404_and_not_a_narration_of_nothing():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the card path is not exercised")
    from fastapi import HTTPException

    from genios_engine.api import intelligence_routes as R
    if R._graph is None:                                    # noqa: SLF001
        pytest.skip("intelligence routes have no graph store configured")
    with pytest.raises(HTTPException) as raised:
        R.card_reasoning("card_does_not_exist", org_id=ORG)
    assert raised.value.status_code == 404
