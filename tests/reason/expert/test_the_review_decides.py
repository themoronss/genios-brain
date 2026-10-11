"""STEP-12 M33 · a covered file's review is ONE audited Layer 4 decision — its mode the outcome, code's numbers.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_review_decides.py

Tree `yc2_w27_s12` M33.C1.L-logic.V0.U01 (`reason/expert/decide.py`), under `06` D1. The review's mode is
the outcome — act a decision, find out a question, wait and blocked a watch, nothing declared silence —
and `output_lane.route` the lane; the next move is the play; the confidence is code's, from the source
events the review's facts cite (one event 6,000, each more half the headroom, none 4,000 and held); the
appraisal's urgency and stakes are the candidates' urgency and the file's importance. Only a valid
review decides, nothing asks a model, and the same request decides the same way twice.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from genios_engine.contracts.expert_review import MODES, ExpertReview
from genios_engine.contracts.reasoning import (CandidateDisposition, DecisionOutcome, ExecutionMode,
                                               OutputLane)
from genios_engine.reason import llm_decision_maker
from genios_engine.reason.decision_maker import BELOW_FLOOR_REASON, IMPORTANCE_ABSENT_REASON
from genios_engine.reason.expert import decide as D
from genios_engine.reason.expert import store
from genios_engine.reason.replay import replay_execution

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 5, 9, tzinfo=timezone.utc)
ORG, FILE = "org_decides", "node_kestrel"


def _raw(**over) -> dict:
    raw = {
        "facts": [{"claim": "Neel wrote asking for a first call", "evidence": ["evt_neel_0927"]},
                  {"claim": "The call is booked", "evidence": ["evt_invite_1008"]},
                  {"claim": "Neel is the person this file follows", "evidence": ["num:reply_days"]}],
        "inferences": [{"claim": "This is a first call with a fund", "based_on": ["fact:1", "fact:2"]}],
        "patterns": [],
        "hypotheses": [],
        "unknowns": [{"question": "Does the fund invest pre-seed?", "relevance": "decides the pitch"}],
        "frames": {"primary": "a first call with a fund", "rivals": ["an exploratory chat"]},
        "expected_vs_actual": {"stage": None, "expected": "a pre-read before the call",
                               "actual": "nothing sent yet"},
        "scenarios": {"do_nothing": "the call runs cold", "act": "a pre-read frames the call",
                      "best": "a partner meeting follows", "worst": "a polite pass",
                      "signals_to_watch": ["a reply to the pre-read"]},
        "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                      "reasons": ["the call is close"]},
        "mode": "act",
        "next_move": {"who": "the founder", "what": "Send Neel a one-page pre-read",
                      "for_whom": "Neel", "by_when": "2026-10-08"},
        "alternative": "send it after the call",
        "wait_or_stop": "if no reply by the call, raise it on the call",
        "done_when": "the call happens and its next step is logged",
        "draft": "Hi Neel, ahead of our call, a one-page note on where we are."}
    raw.update(over)
    return raw


def _row(status: str = store.VALID, **over) -> store.StoredReview:
    raw = _raw(**over)
    return store.StoredReview(
        file_id=FILE, fingerprint="ffp-0123456789abcdef01234567", model="claude-sonnet-5",
        prompt_version="expert-review.v2", dossier_digest="d" * 64, status=status,
        reason=None if status == store.VALID else "uncited_fact",
        review=ExpertReview.from_mapping(raw) if status == store.VALID else None, raw=raw,
        input_tokens=10, output_tokens=10, cost_micro_usd=1, reviewed_at=NOW)


def _decide(row=None, **kw):
    request = D.request_for(row or _row(), org_id=ORG, root_entity_type="company",
                            domain="founder_office", eval_time=NOW, graph_version=7, **kw)
    return request, D.decide(request)


# ── the mode is the outcome, and the lane is the router's ─────────────────────────────────────
@pytest.mark.parametrize("mode, outcome, lane", [
    ("act", DecisionOutcome.DECISION, OutputLane.DECISION),
    ("find_out", DecisionOutcome.INSUFFICIENT_CONTEXT, OutputLane.INVESTIGATION),
    ("wait", DecisionOutcome.DEFER, OutputLane.MONITOR),
    ("blocked", DecisionOutcome.DEFER, OutputLane.MONITOR),
    ("nothing", DecisionOutcome.NO_ACTION, OutputLane.SUPPRESS),
])
def test_the_mode_is_the_outcome_and_the_router_picks_the_lane(mode, outcome, lane):
    moving = mode in ("act", "find_out")
    _, execution = _decide(_row(mode=mode, **({} if moving else {"next_move": None})))
    decision = execution.decision
    assert (decision.outcome, decision.output_lane) == (outcome, lane)
    assert decision.lane_reason
    assert f"{D.MODE_MARKER}:{mode}" in decision.uncertainty, "the mode travels beside the outcome"
    assert (decision.selected_candidate_id is not None) == (outcome == DecisionOutcome.DECISION)
    if outcome in (DecisionOutcome.NO_ACTION, DecisionOutcome.INSUFFICIENT_CONTEXT):
        assert decision.candidates == ()


def test_every_mode_of_the_contract_has_its_outcome():
    assert set(D.OUTCOME_OF) == set(MODES)


def test_the_next_move_is_the_play_and_it_moves_nothing_itself():
    request, execution = _decide()
    selected = execution.selected_candidate
    assert selected.play_id == D.MOVE_PLAY
    assert selected.parameters["label"] == "Send Neel a one-page pre-read"
    meta = selected.parameters["metadata"]
    assert (meta["who"], meta["for_whom"], meta["by_when"]) == ("the founder", "Neel", "2026-10-08")
    assert selected.parameters["read_only"] is True and meta["external_recipient_required"] is False
    assert execution.decision.outcome_window_days == 3, "by the 8th, from the 5th"
    assert any(c.reason_code == "read_only_policy_pass" for c in selected.checks), \
        "the constraint gate every delivered decision carries"
    assert request.capability.do_nothing_consequence == "the call runs cold"


@pytest.mark.parametrize("by_when, days", [(None, D.DEFAULT_WINDOW_DAYS), ("2026-10-01", 1),
                                           ("2026-10-25", 20)])
def test_the_moves_window_is_its_date_or_a_week(by_when, days):
    move = dict(_raw()["next_move"], by_when=by_when)
    _, execution = _decide(_row(next_move=move))
    assert execution.decision.outcome_window_days == days


def test_a_review_that_names_no_move_keeps_a_watch():
    request, execution = _decide(_row(mode="wait", next_move=None))
    assert [p.play_id for p in request.capability.plays] == [D.WATCH_PLAY]
    assert execution.decision.selected_candidate_id is None
    assert [c.play_id for c in execution.decision.candidates] == [D.WATCH_PLAY], \
        "a watch is kept on the record, nothing selected"


# ── confidence is code's, from the source events the facts cite ──────────────────────────────
@pytest.mark.parametrize("events, confidence", [(1, 6_000), (2, 8_000), (3, 9_000), (4, 9_500)])
def test_each_cited_event_raises_the_confidence_by_half_the_headroom(events, confidence):
    facts = [{"claim": f"a mail, number {chr(97 + i)}", "evidence": [f"evt_{i}"]} for i in range(events)]
    _, execution = _decide(_row(facts=facts))
    assert execution.decision.confidence_bp == confidence


def test_code_readings_alone_earn_no_assertion_the_move_is_held():
    facts = [{"claim": "the reply time is measured", "evidence": ["num:reply_days"]},
             {"claim": "the playbook expects a pre-read", "evidence": ["pb:first_call"]}]
    _, execution = _decide(_row(facts=facts))
    decision = execution.decision
    assert decision.confidence_bp == D.NO_EVENT_BP
    assert (decision.outcome, decision.output_lane) == (DecisionOutcome.DEFER, OutputLane.MONITOR)
    assert f"{BELOW_FLOOR_REASON}:{D.NO_EVENT_BP}<4500" in decision.uncertainty


def test_an_event_cited_twice_is_one_event_and_the_words_move_nothing():
    twice = [{"claim": "Neel wrote", "evidence": ["evt_neel_0927"]},
             {"claim": "Neel wrote again, the same mail", "evidence": ["evt_neel_0927"]}]
    once = [{"claim": "something else entirely about Neel", "evidence": ["evt_neel_0927"]}]
    assert _decide(_row(facts=twice))[1].decision.confidence_bp == \
        _decide(_row(facts=once))[1].decision.confidence_bp == D.ONE_EVENT_BP


# ── D1: the appraisal sets urgency and importance ───────────────────────────────────────────────
@pytest.mark.parametrize("stakes, urgency, numbers", [
    ("low", "high", (2_500, 8_000)), ("high", "low", (8_000, 2_500)), ("medium", "medium", (5_000, 5_000)),
])
def test_the_appraisal_sets_the_urgency_and_the_importance(stakes, urgency, numbers):
    """Stakes → importance, urgency → urgency, each its own; medium is the formula's neutral 5,000."""
    _, execution = _decide(_row(appraisal={"stakes": stakes, "urgency": urgency,
                                           "reversibility": "reversible", "reasons": ["why"]}))
    parts = execution.selected_candidate.score_components
    assert (parts["importance"], parts["urgency"]) == numbers
    assert not any(str(u).startswith(IMPORTANCE_ABSENT_REASON) for u in execution.decision.uncertainty), \
        "the importance is measured, never the neutral fallback"


def test_higher_stakes_and_urgency_rank_the_move_higher():
    low = _decide(_row(appraisal={"stakes": "low", "urgency": "low", "reversibility": "reversible",
                                  "reasons": ["why"]}))[1].selected_candidate.utility_bp
    high = _decide()[1].selected_candidate.utility_bp
    assert high > low


# ── only a valid review decides; no model; the same request, the same decision ─────────────────
@pytest.mark.parametrize("status", [store.REFUSED, store.TRUNCATED, store.FAILED, store.OVER_BUDGET])
def test_only_a_valid_review_decides(status):
    with pytest.raises(ValueError, match="only a valid review decides"):
        D.request_for(_row(status=status), org_id=ORG, root_entity_type="company",
                      domain="founder_office", eval_time=NOW, graph_version=7)


def test_the_decision_maker_asks_no_model(monkeypatch):
    monkeypatch.setattr(llm_decision_maker, "enabled_for", lambda org_id: True)

    def _never(*a, **kw):
        raise AssertionError("the expert's decision asked the test-mode decider")

    monkeypatch.setattr(llm_decision_maker, "decide_with_llm", _never)
    monkeypatch.setattr(llm_decision_maker, "client", _never)
    request = D.request_for(_row(), org_id=ORG, root_entity_type="company", domain="founder_office",
                            eval_time=NOW, graph_version=7)
    synthesis = D.ExpertDecisionMaker().decide(request, [D.ReviewReader().evaluate(request, {})],
                                               terminal=None, uncertainty=(), degraded=False)
    assert synthesis.decision.outcome == DecisionOutcome.DECISION
    assert D.ExpertDecisionMaker.asks_no_model is True
    events = {ref.evidence_id for ref in request.context.evidence if ref.value.startswith("evt_")}
    assert set(synthesis.confidence.counted_groups) == {f"event:{ref.value}"
                                                        for ref in request.context.evidence
                                                        if ref.evidence_id in events}, \
        "each source event is its own origin; code's readings assert none"
    assert synthesis.confidence.settled_by == "confidence_authority"


def test_the_request_names_its_review_and_what_it_cites():
    request, execution = _decide()
    facts = request.context.facts
    assert facts[D.F_REVIEW]["value"]["fingerprint"] == "ffp-0123456789abcdef01234567"
    assert tuple(facts[D.F_CITED]["value"]) == ("evt_invite_1008", "evt_neel_0927", "num:reply_days")
    two = _decide(_row(facts=[{"claim": "both mails say so", "evidence": ["evt_b", "evt_a"]}]))[0]
    assert tuple(two.context.facts[D.F_CITED]["value"]) == ("evt_a", "evt_b"), \
        "every id a fact cites, not its first"
    assert {ref.value for ref in request.context.evidence} == set(facts[D.F_CITED]["value"])
    assert set(execution.selected_candidate.evidence_ids) == {ref.evidence_id
                                                             for ref in request.context.evidence}
    assert (request.trigger_kind, request.trigger_ref) == (D.TRIGGER_KIND, "ffp-0123456789abcdef01234567")
    assert request.context.root_entity_id == FILE


def test_the_same_request_decides_the_same_way_and_replays():
    request, first = _decide()
    _, second = _decide()
    assert first.decision.semantic_hash == second.decision.semantic_hash
    replayed, comparison = replay_execution(first, D.orchestrator())
    assert comparison.matches, comparison.differences
    assert replayed.request.mode == ExecutionMode.REPLAY


def test_only_the_experts_capability_is_decided_here():
    request, _ = _decide()
    other = replace(request, capability=replace(request.capability, capability_id="expertise.opportunity"),
                    request_id=None, policy_snapshot_id=None)
    with pytest.raises(ValueError, match="not an expert decision"):
        D.decide(other)
    assert D.is_expert(D.CAPABILITY_ID) and not D.is_expert("expertise.opportunity")


def test_the_card_speaks_the_reviews_own_words():
    request, _ = _decide()
    render = request.capability.metadata["render"]
    assert render["fallback"] == {"headline": "Send Neel a one-page pre-read",
                                  "situation": "a first call with a fund"}
    assert render["draft"].startswith("Hi Neel") and render["artifact_kind"] == "draft_message"
    braces = _decide(_row(frames={"primary": "a {stage} call", "rivals": ["x"]}))[0]
    assert braces.capability.metadata["render"]["fallback"]["situation"] == "a {{stage}} call", \
        "the review's words are read literally by the renderer"
