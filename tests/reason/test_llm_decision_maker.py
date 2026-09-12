"""TEST MODE — Layer 4's Decision Maker as a model call (`reason/llm_decision_maker.py`).

What these pin:

* **Off means off.** With the switch down, `DecisionMaker.decide` is the formula, byte for byte.
* **On means the model decides.** Its scores rank the plays and pick the winner, its confidence
  is the decision's, and it may act where the formula's 4,500 floor would have deferred.
* **Hard eliminations still bind.** A play a unit's policy check eliminated cannot win.
* **Failure is DEFER, never the formula** — no client, a bad answer twice, the daily cap.
* **Terminal runs never reach the model.**
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.reasoning import (
    CandidateCheck,
    CandidateDisposition,
    CapabilityManifest,
    CheckOutcome,
    ContextSnapshot,
    DecisionOutcome,
    EvidenceRef,
    ExecutionMode,
    Goal,
    PlayDefinition,
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.reason import llm_decision_maker as llm_dm
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.decision_maker import DecisionMaker
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.replay import replay_persisted
from genios_engine.reason.store import ReasoningStore

NOW = datetime(2026, 9, 12, 12, tzinfo=timezone.utc)


def _play(play_id: str, *, impact=6_000, success=6_000, effort=2_000, risk=1_000):
    return PlayDefinition(play_id=play_id, version="1", label=play_id.replace("_", " ").title(),
                          steps=("Prepare a grounded draft",), impact_bp=impact,
                          success_probability_bp=success, effort_bp=effort, risk_bp=risk)


def _request(*, plays=None, root="deal_1", org="org_1",
             mode=ExecutionMode.LIVE) -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling", version="1.0.0", domain="sales",
        root_entity_type="deal", goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.confidence", "1"),),
        plays=tuple(plays or (_play("restore_momentum"),)), policies=(), metadata={})
    context = ContextSnapshot(org_id=org, graph_version=17, root_entity_id=root,
                              root_entity_type="deal", evaluation_time=NOW,
                              selector_version="selector.v1", facts={"deal.status": "open"})
    return ReasoningRequest(org_id=org, capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1", mode=mode)


def _results(confidence=8_000, checks=()):
    return [ReasonerResult(reasoner_id="core.confidence", reasoner_version="1",
                           status=ResultStatus.COMPLETED, matched=True,
                           metrics={"confidence_bp": confidence}, checks=tuple(checks))]


def _answer(scores, *, outcome="decision", confidence=7_000, rationale="Reply today."):
    return {"outcome": outcome, "scores": scores, "confidence_bp": confidence,
            "rationale": rationale, "missing": []}


class FakeLLM:
    model = "fake-model"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=4096):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, LLMResult):
            return answer
        return LLMResult(parsed=answer, raw=json.dumps(answer), input_tokens=10,
                         output_tokens=5, model=self.model)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    llm_dm._reset_for_tests()
    monkeypatch.setattr(llm_dm, "_record_cost", lambda **_kw: None)
    yield
    llm_dm._reset_for_tests()


def _decide(request, results, llm):
    return llm_dm.decide_with_llm(request, results, uncertainty=(), degraded=False, llm=llm)


def _by_play(synthesis):
    return {item.play_id: item for item in synthesis.candidates}


# ---------------------------------------------------------------------------------------------
# The switch
# ---------------------------------------------------------------------------------------------

def test_switch_off_leaves_the_formula_untouched(monkeypatch):
    monkeypatch.setattr(llm_dm, "enabled_for", lambda _org, _mode=None: False)
    fake = FakeLLM()
    monkeypatch.setattr(llm_dm, "client", lambda: fake)

    synthesis = DecisionMaker().decide(_request(), _results(), terminal=None, uncertainty=(),
                                       degraded=False)

    assert fake.prompts == []
    assert all(llm_dm.LLM_UTILITY_COMPONENT not in item.score_components
               for item in synthesis.candidates)


def test_switch_on_routes_the_decision_to_the_model(monkeypatch):
    fake = FakeLLM(_answer({"restore_momentum": 6_100}))
    monkeypatch.setattr(llm_dm, "enabled_for", lambda _org, _mode=None: True)
    monkeypatch.setattr(llm_dm, "client", lambda: fake)

    synthesis = DecisionMaker().decide(_request(), _results(), terminal=None, uncertainty=(),
                                       degraded=False)

    assert len(fake.prompts) == 1
    assert synthesis.decision.outcome == DecisionOutcome.DECISION
    assert _by_play(synthesis)["restore_momentum"].utility_bp == 6_100


def test_terminal_runs_never_reach_the_model(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(llm_dm, "enabled_for", lambda _org, _mode=None: True)
    monkeypatch.setattr(llm_dm, "client", lambda: fake)

    synthesis = DecisionMaker().decide(_request(), _results(), terminal=DecisionOutcome.NO_ACTION,
                                       uncertainty=(), degraded=False)

    assert fake.prompts == []
    assert synthesis.decision.outcome == DecisionOutcome.NO_ACTION


def test_the_org_allow_list_scopes_the_switch(monkeypatch):
    monkeypatch.setattr(llm_dm, "_settings", lambda: SimpleNamespace(
        l4_llm_decision_maker=True, l4_llm_decision_maker_orgs="org_a, org_b"))
    assert llm_dm.enabled_for("org_a") and llm_dm.enabled_for("org_b")
    assert not llm_dm.enabled_for("org_c")

    monkeypatch.setattr(llm_dm, "_settings", lambda: SimpleNamespace(
        l4_llm_decision_maker=False, l4_llm_decision_maker_orgs="org_a"))
    assert not llm_dm.enabled_for("org_a")


def test_an_empty_allow_list_enables_no_org(monkeypatch):
    """Fails CLOSED. The switch on with an empty list used to mean every org — one env var away
    from putting every tenant's decisions on a paid model call."""
    monkeypatch.setattr(llm_dm, "_settings", lambda: SimpleNamespace(
        l4_llm_decision_maker=True, l4_llm_decision_maker_orgs=""))
    assert not llm_dm.enabled_for("org_c")


def test_a_star_enables_every_org(monkeypatch):
    monkeypatch.setattr(llm_dm, "_settings", lambda: SimpleNamespace(
        l4_llm_decision_maker=True, l4_llm_decision_maker_orgs="*"))
    assert llm_dm.enabled_for("org_c") and llm_dm.enabled_for("any_org")


def test_a_non_live_run_buys_no_model_call_unless_shadow_is_paid(monkeypatch):
    """Shadow, simulation and replay runs cannot deliver: they are measurement, and measurement
    must not spend on the model unless `l4_llm_shadow_paid` says so."""
    monkeypatch.setattr(llm_dm, "_settings", lambda: SimpleNamespace(
        l4_llm_decision_maker=True, l4_llm_decision_maker_orgs="org_a",
        l4_llm_shadow_paid=False))
    assert llm_dm.enabled_for("org_a", ExecutionMode.LIVE)
    for mode in (ExecutionMode.SHADOW, ExecutionMode.SIMULATION, ExecutionMode.REPLAY):
        assert not llm_dm.enabled_for("org_a", mode), mode
    assert not llm_dm.enabled_for_request(_request(org="org_a", mode=ExecutionMode.SHADOW))
    assert llm_dm.enabled_for_request(_request(org="org_a"))

    monkeypatch.setattr(llm_dm, "_settings", lambda: SimpleNamespace(
        l4_llm_decision_maker=True, l4_llm_decision_maker_orgs="org_a",
        l4_llm_shadow_paid=True))
    assert llm_dm.enabled_for("org_a", ExecutionMode.SHADOW)


def test_a_shadow_decision_never_reaches_the_model(monkeypatch):
    """The call site, not just the predicate: a SHADOW request goes to the formula."""
    monkeypatch.setattr(llm_dm, "_settings", lambda: SimpleNamespace(
        l4_llm_decision_maker=True, l4_llm_decision_maker_orgs="org_1"))
    called = []
    monkeypatch.setattr(llm_dm, "decide_with_llm", lambda *a, **k: called.append(1))

    DecisionMaker().decide(_request(mode=ExecutionMode.SHADOW), _results(),
                           terminal=None, uncertainty=(), degraded=False)

    assert called == []


# ---------------------------------------------------------------------------------------------
# The model decides
# ---------------------------------------------------------------------------------------------

def test_the_models_scores_pick_the_winner_even_against_the_formula():
    # The formula prefers `strong` (far higher impact/success); the model prefers `gentle`.
    plays = (_play("strong", impact=9_500, success=9_000), _play("gentle", impact=2_000))
    fake = FakeLLM(_answer({"strong": 3_000, "gentle": 8_200}, confidence=6_600,
                           rationale="A soft check-in fits a cooling deal."))

    synthesis = _decide(_request(plays=plays), _results(), fake)
    by_play = _by_play(synthesis)

    assert synthesis.decision.outcome == DecisionOutcome.DECISION
    assert by_play["gentle"].rank_position == 1 and by_play["strong"].rank_position == 2
    selected = next(c for c in synthesis.candidates
                    if c.candidate_id == synthesis.decision.selected_candidate_id)
    assert selected.play_id == "gentle"
    assert synthesis.decision.confidence_bp == 6_600
    assert selected.parameters["llm_rationale"] == "A soft check-in fits a cooling deal."
    # The formula's own answer is still on the record, for comparison.
    assert "formula_utility" in selected.score_components


def test_the_model_may_act_where_the_old_floor_would_have_deferred():
    # 3,000 < the 4,500 floor: the formula DEFERs this. The model is allowed to disagree.
    synthesis = _decide(_request(), _results(confidence=3_000),
                        FakeLLM(_answer({"restore_momentum": 5_000}, confidence=3_200)))

    assert synthesis.decision.outcome == DecisionOutcome.DECISION
    assert synthesis.decision.confidence_bp == 3_200


def test_the_model_may_defer():
    synthesis = _decide(_request(), _results(),
                        FakeLLM(_answer({"restore_momentum": 4_000}, outcome="defer")))

    assert synthesis.decision.outcome == DecisionOutcome.DEFER
    assert synthesis.decision.selected_candidate_id is None
    assert llm_dm.LLM_DEFERRED_REASON in synthesis.decision.uncertainty


def test_an_eliminated_play_cannot_win_and_is_not_offered():
    plays = (_play("blocked"), _play("allowed"))
    check = CandidateCheck(play_id="blocked", stage="policy", outcome=CheckOutcome.ELIMINATE,
                           reason_code="tenant_policy_block", evaluator_id="core.constraint",
                           evaluator_version="1")
    fake = FakeLLM(_answer({"allowed": 5_500}))

    synthesis = _decide(_request(plays=plays), _results(checks=(check,)), fake)
    by_play = _by_play(synthesis)

    assert by_play["blocked"].disposition == CandidateDisposition.ELIMINATED
    assert by_play["blocked"].rank_position is None
    assert by_play["allowed"].rank_position == 1
    assert "BLOCKED by a safety/policy check (tenant_policy_block)" in fake.prompts[0]


def test_a_scoring_gate_is_advice_the_model_may_overrule():
    # `legacy.score_gate` eliminating is a threshold judgement, not safety: in this mode the
    # model sees it and may still act. The check still travels on the candidate for the store.
    gate = CandidateCheck(play_id="restore_momentum", stage="precondition",
                          outcome=CheckOutcome.ELIMINATE, reason_code="legacy_score_gate_failed",
                          evaluator_id="legacy.score_gate", evaluator_version="1.0.0",
                          detail={"score": 38, "score_min": 42})
    fake = FakeLLM(_answer({"restore_momentum": 6_000}))

    synthesis = _decide(_request(), _results(checks=(gate,)), fake)
    winner = _by_play(synthesis)["restore_momentum"]

    assert synthesis.decision.outcome == DecisionOutcome.DECISION
    assert winner.disposition == CandidateDisposition.ELIGIBLE and winner.rank_position == 1
    assert [c.reason_code for c in winner.checks] == ["legacy_score_gate_failed"]
    assert "advice, not a veto" in fake.prompts[0] and "score 38 < 42" in fake.prompts[0]


def test_the_formula_reading_is_the_baseline_the_model_calibrates_against():
    # v1-v3 gave no scale and every answer landed near 8500 -> every card CRITICAL. The prompt now
    # carries the formula's own utility per play, the confidence floor and the band cuts.
    plays = (_play("reply", impact=7_500, success=3_000), _play("wait", impact=2_000))
    fake = FakeLLM(_answer({"reply": 5_000, "wait": 3_000}))

    _decide(_request(plays=plays), _results(), fake)

    prompt = fake.prompts[0]
    assert "HOW THE ENGINE'S FORMULA SCORED THIS" in prompt
    assert "formula utility" in prompt and "impact 7500" in prompt
    assert "only recommends acting when confidence >= 4500" in prompt
    assert "CRITICAL" in prompt and "START from the formula's utility" in prompt


def test_r1s_hedge_reading_and_conflicts_are_in_the_decision_prompt():
    # R-1's job, folded in: its closed hedge list (Hinglish included), its six stances, and an
    # unresolved Layer 1 conflict shown as a disagreement to weigh rather than a plain fact.
    request = _request()
    context = request.context
    facts = {**dict(context.facts), "situation.conflict.date.value": {
        "field": "date.value", "resolution": "unresolved_surface_both",
        "values": ["2026-08-14", "2027-08-14"]}}
    request = ReasoningRequest(
        org_id=request.org_id, capability=request.capability,
        context=ContextSnapshot(org_id=context.org_id, graph_version=context.graph_version,
                                root_entity_id=context.root_entity_id,
                                root_entity_type=context.root_entity_type,
                                evaluation_time=context.evaluation_time,
                                selector_version=context.selector_version, facts=facts),
        evaluation_time=request.evaluation_time, trigger_kind=request.trigger_kind,
        config_snapshot_id=request.config_snapshot_id)
    fake = FakeLLM(_answer({"restore_momentum": 5_000}))

    _decide(request, _results(), fake)

    prompt = fake.prompts[0]
    assert "A hedge is not a commitment" in prompt and "'shayad'" in prompt
    assert "commitment made = the writer commits to a specific action" in prompt
    assert "WHERE THE RECORD DISAGREES" in prompt and "2027-08-14" in prompt


def test_the_subject_and_its_messages_lead_the_prompt(monkeypatch):
    monkeypatch.setattr(llm_dm, "business_context", lambda _req: [
        "- this is a person: Maria Exconde",
        "- message 2026-08-11 from Maria Exconde: questions=['What are you building?']"])
    fake = FakeLLM(_answer({"restore_momentum": 6_000}))

    _decide(_request(), _results(), fake)

    prompt = fake.prompts[0]
    assert "WHO AND WHAT" in prompt and "Maria Exconde" in prompt
    assert prompt.index("WHO AND WHAT") < prompt.index("PLAYS YOU CAN RECOMMEND")
    assert "confidence_bp\": 8000" not in prompt       # units give conclusions, not scores


def test_every_play_eliminated_is_blocked_without_a_call():
    check = CandidateCheck(play_id="restore_momentum", stage="policy",
                           outcome=CheckOutcome.ELIMINATE, reason_code="tenant_policy_block",
                           evaluator_id="core.constraint", evaluator_version="1")
    fake = FakeLLM()

    synthesis = _decide(_request(), _results(checks=(check,)), fake)

    assert fake.prompts == []
    assert synthesis.decision.outcome == DecisionOutcome.BLOCKED


# ---------------------------------------------------------------------------------------------
# Failure is DEFER, never the formula
# ---------------------------------------------------------------------------------------------

def test_no_client_defers():
    synthesis = _decide(_request(), _results(), None)

    assert synthesis.decision.outcome == DecisionOutcome.DEFER
    assert f"{llm_dm.LLM_UNAVAILABLE_REASON}:no_client" in synthesis.decision.uncertainty


def test_a_bad_answer_is_corrected_once():
    fake = FakeLLM({"outcome": "maybe"}, _answer({"restore_momentum": 5_000}))

    synthesis = _decide(_request(), _results(), fake)

    assert synthesis.decision.outcome == DecisionOutcome.DECISION
    assert len(fake.prompts) == 2 and "CORRECTION" in fake.prompts[1]


def test_two_bad_answers_defer():
    fake = FakeLLM({"outcome": "maybe"}, {"outcome": "decision", "scores": {"other": 1}})

    synthesis = _decide(_request(), _results(), fake)

    assert synthesis.decision.outcome == DecisionOutcome.DEFER
    assert (f"{llm_dm.LLM_UNAVAILABLE_REASON}:invalid_answer"
            in synthesis.decision.uncertainty)


def test_a_transport_failure_defers():
    fake = FakeLLM(LLMResult(parsed={}, raw="", ok=False, error="timeout"))

    synthesis = _decide(_request(), _results(), fake)

    assert f"{llm_dm.LLM_UNAVAILABLE_REASON}:call_failed" in synthesis.decision.uncertainty


def test_the_daily_cap_defers(monkeypatch):
    monkeypatch.setattr(llm_dm, "_daily_cap", lambda: 1)
    fake = FakeLLM(_answer({"restore_momentum": 5_000}))

    first = _decide(_request(root="deal_1"), _results(), fake)
    second = _decide(_request(root="deal_2"), _results(), fake)

    assert first.decision.outcome == DecisionOutcome.DECISION
    assert f"{llm_dm.LLM_UNAVAILABLE_REASON}:daily_call_cap" in second.decision.uncertainty


# ---------------------------------------------------------------------------------------------
# Replay and the store
# ---------------------------------------------------------------------------------------------

def test_the_same_run_is_answered_from_cache_so_replay_matches():
    fake = FakeLLM(_answer({"restore_momentum": 5_000}))

    first = _decide(_request(), _results(), fake)
    second = _decide(_request(), _results(), fake)

    assert len(fake.prompts) == 1
    assert first.decision.semantic_hash == second.decision.semantic_hash


def test_the_store_can_tell_an_llm_decision_from_a_formula_one():
    synthesis = _decide(_request(), _results(), FakeLLM(_answer({"restore_momentum": 5_000})))
    rows = [{"score_components": dict(item.score_components)} for item in synthesis.candidates]

    assert llm_dm.is_llm_decided(rows)
    assert not llm_dm.is_llm_decided([{"score_components": {"impact": 6_000}}])


def test_newer_models_get_no_sampling_params_and_haiku_keeps_temperature_zero():
    # Sonnet 5 / Opus 5 answer a `temperature` with a 400, which would DEFER every decision.
    assert llm_dm.request_kwargs("claude-sonnet-5") == {"thinking": {"type": "disabled"}}
    assert llm_dm.request_kwargs("claude-opus-5") == {"thinking": {"type": "disabled"}}
    assert llm_dm.request_kwargs("claude-fable-5-1") == {}
    assert llm_dm.request_kwargs("claude-haiku-4-5-20251001") == {"temperature": 0}


def test_the_answer_parser_refuses_rather_than_repairs():
    good = llm_dm.parse_answer(_answer({"a": "7000"}), ["a"])
    assert good["scores"] == {"a": 7_000}
    for bad in ({**_answer({"a": 1}), "outcome": "act"},
                _answer({"a": 1, "b": 2}),
                _answer({"a": 10_001}),
                _answer({"a": True}),
                {**_answer({"a": 1}), "confidence_bp": -1}):
        with pytest.raises(llm_dm._Refused):
            llm_dm.parse_answer(bad, ["a"])


# ---------------------------------------------------------------------------------------------
# Real Postgres: the store's fail-closed verifier accepts an LLM decision, and replay matches.
# A fake connection can be made to agree with anything, so this is the only proof that counts.
# ---------------------------------------------------------------------------------------------

PG_NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class ScoringLLM(FakeLLM):
    """Scores whatever plays the prompt offers, reading them off the prompt's own JSON template.

    It prefers them in REVERSE alphabetical order, so the winner is chosen by this answer rather
    than by anything the formula would have picked.
    """

    def __init__(self, confidence=4_000):
        super().__init__()
        self.confidence = confidence

    def call(self, prompt, *, max_tokens=4096):
        self.prompts.append(prompt)
        template = json.loads(prompt.rsplit("\n", 1)[-1])
        ids = sorted(template["scores"], reverse=True)
        answer = _answer({pid: 9_000 - 100 * i for i, pid in enumerate(ids)},
                         confidence=self.confidence)
        return LLMResult(parsed=answer, raw=json.dumps(answer), input_tokens=10,
                         output_tokens=5, model=self.model)


def _deal_context(org_id: str) -> ContextSnapshot:
    return ContextSnapshot(
        org_id=org_id, graph_version=21, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=PG_NOW, selector_version="deal_cooling.selector.v1",
        facts={
            "deal.status": {"value": "open", "confidence_bp": 9_500, "src_count": 2},
            "deal.value": {"value": 500_000, "confidence_bp": 9_500, "src_count": 2},
            "derived.engagement": {"value_bp": 4_000, "confidence_bp": 8_500, "src_count": 2},
            "thread.last_inbound": {"value": (PG_NOW - timedelta(days=10)).isoformat(),
                                    "confidence_bp": 9_000, "src_count": 2},
            "relationship.verified_stakeholder_count": {"value": 2},
        },
        observations=({"kind": "customer_reply", "occurred_at": PG_NOW - timedelta(days=10)},),
        neighbor_facts={"deal.status": "open", "contact.verified_recipient": True,
                        "account.alternate_stakeholder_verified": True},
        neighbor_observations=("pricing_discussed", "buying_intent"),
        edge_count=2,
        evidence=(
            EvidenceRef("ev_status", "deal.status", "open", source_ref_id="email_1",
                        fact_version_id="factv_status_1", occurred_at=PG_NOW - timedelta(hours=1),
                        confidence_bp=9_500, authority_rank=3, independence_group="crm"),
            EvidenceRef("ev_engagement", "derived.engagement", 4_000,
                        confidence_bp=8_500, authority_rank=2),
            EvidenceRef("ev_inbound", "thread.last_inbound",
                        (PG_NOW - timedelta(days=10)).isoformat(),
                        confidence_bp=9_000, authority_rank=2),
        ),
        metadata={"tenant_timezone": "Asia/Kolkata"},
    )


@pytest.fixture(scope="module")
def pg_engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres LLM decision test skipped")
    from genios_engine.platform.db import get_engine
    return get_engine(url)


@pytest.fixture
def pg_org(pg_engine, request):
    org_id = f"org_llmdm_{abs(hash(request.node.name)) % 10 ** 9}"
    with pg_engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, :o) "
                          "on conflict (id) do nothing"), {"o": org_id})
    yield org_id
    with pg_engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org_id})


def test_an_llm_decision_persists_verifies_and_replays_on_real_postgres(
        pg_engine, pg_org, monkeypatch):
    fake = ScoringLLM(confidence=4_000)          # under the formula's 4,500 floor
    monkeypatch.setattr(llm_dm, "enabled_for", lambda _org, _mode=None: True)
    monkeypatch.setattr(llm_dm, "client", lambda: fake)
    orchestrator = ReasoningOrchestrator(default_registry())

    execution = orchestrator.execute(ReasoningRequest(
        org_id=pg_org, capability=DEAL_COOLING_V1, context=_deal_context(pg_org),
        evaluation_time=PG_NOW, trigger_kind="email.received", trigger_ref="event_1",
        mode=ExecutionMode.LIVE, config_snapshot_id=None))

    assert len(fake.prompts) == 1
    assert execution.decision.outcome == DecisionOutcome.DECISION
    assert execution.decision.confidence_bp == 4_000
    selected = execution.selected_candidate
    eligible = sorted(c.play_id for c in execution.candidates
                      if c.disposition == CandidateDisposition.ELIGIBLE)
    assert selected.play_id == eligible[-1]      # the model's pick, not the formula's

    store = ReasoningStore(engine=pg_engine)
    bundle = persist_execution(store=store, execution=execution,
                               context_payload_ttl_hours=43_800)
    run_id = bundle["run"]["run_id"]
    with pg_engine.connect() as conn:
        persisted = conn.execute(text(
            "select c.play_id from reasoning_run_outputs o join reasoning_candidates c "
            "on c.org_id=o.org_id and c.candidate_id=o.selected_candidate_id "
            "where o.org_id=:o and o.run_id=:r"), {"o": pg_org, "r": run_id}).scalar()
    assert persisted == selected.play_id

    _replayed, comparison = replay_persisted(store=store, org_id=pg_org, run_id=run_id,
                                             orchestrator=orchestrator)
    assert comparison.matches
    assert len(fake.prompts) == 1                # replay was answered from the cache
