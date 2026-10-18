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
from genios_engine.contracts.claim_check import CHECK_VERSION
from genios_engine.reason.expert import decide as D
from tests.reason.expert.checks import as_written
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


def _row(status: str = store.VALID, checked=None, **over) -> store.StoredReview:
    raw = _raw(**over)
    review = ExpertReview.from_mapping(raw) if status == store.VALID else None
    return store.StoredReview(
        file_id=FILE, fingerprint="ffp-0123456789abcdef01234567", model="claude-sonnet-5",
        prompt_version="expert-review.v2", dossier_digest="d" * 64, status=status,
        reason=None if status == store.VALID else "uncited_fact", review=review, raw=raw,
        input_tokens=10, output_tokens=10, cost_micro_usd=1, reviewed_at=NOW,
        # STEP-13: a review decides through its check — here, one that keeps every line.
        checked=checked if checked is not None else (as_written(review) if review else None))


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


@pytest.mark.parametrize("cited, events", [
    (["evt_1"], 1), (["m33_fund_mail"], 1), (["num:reply_days", "pb:first_call", "hist:times_seen@admin",
                                              "whatif:7", "sit:sit_1", "loop:l1", "promise:p1",
                                              "wave:w1"], 0),
])
def test_a_source_event_is_any_id_the_dossier_prints_without_a_kind(cited, events):
    """Capture names its events `evt_…`; a tenant's events may carry other ids. The dossier prints
    every reading of code's with its kind (`num:`, `pb:`, `sit:` …), so an event is an id with none."""
    facts = [{"claim": "the record says so", "evidence": [c]} for c in cited]
    confidence = _decide(_row(facts=facts))[1].decision.confidence_bp
    assert confidence == (D.NO_EVENT_BP if events == 0 else D.ONE_EVENT_BP)


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
    # ⛔ RESTATED by yc2_w27_s13/M35.C3.L-integration.V1.U06 (X12, `06` D48): the run is keyed on the review AND its
    # check, so a review checked again under a newer check is a new decision of the file.
    assert (request.trigger_kind, request.trigger_ref) == (
        D.TRIGGER_KIND, f"ffp-0123456789abcdef01234567@{CHECK_VERSION}")
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


@pytest.mark.parametrize("mode, missing", [("find_out", (D.F_ANSWER,)), ("nothing", ())])
def test_a_mode_that_moves_nothing_ends_the_run_before_the_gate(mode, missing):
    """`find_out` and `nothing` decide no move, so nothing may stand behind one: the run ends at the
    reader and the constraint gate never runs — the audit store refuses a check with no candidate."""
    moving = mode == "find_out"
    _, execution = _decide(_row(mode=mode, **({} if moving else {"next_move": None})))
    by_unit = {r.reasoner_id: r for r in execution.ordered_results}
    assert by_unit["core.constraint"].status.value == "skipped"
    assert not any(r.checks for r in execution.ordered_results)
    assert set(missing) <= set(execution.decision.uncertainty)


def test_the_capability_version_is_its_manifests_own_address():
    """The audit store keeps one manifest per (capability, version), and the manifest is the review's:
    the same review is the same version, another review another."""
    first, _ = _decide()
    again, _ = _decide()
    other, _ = _decide(_row(next_move=dict(_raw()["next_move"], what="Call Neel instead")))
    assert first.capability.version == again.capability.version != other.capability.version
    assert first.capability.version.startswith(D.DECIDE_VERSION + ".")


# ── M33.C1.L-logic.V1.U16 · the play says what done looks like ────────────────────────────────
def test_the_reviews_done_when_is_the_plays_success():
    """The card's success signal is read off the audited play (`deliver/card_builder._play_success`):
    the move's — and the watch's — is the review's own `done_when`, never NULL."""
    request, _execution = _decide()
    [play] = request.capability.plays
    assert play.success_events == (_raw()["done_when"],)
    watch, _ = _decide(_row(mode="wait", next_move=None))
    assert watch.capability.plays[0].success_events == (_raw()["done_when"],)


def test_the_cards_success_signal_is_the_reviews_done_when():
    from genios_engine.deliver.card_builder import _play_success
    request, _execution = _decide()
    [play] = request.capability.plays
    assert _play_success({}, {"play_success_events": list(play.success_events),
                              "play": play.play_id}) == _raw()["done_when"]


# ── STEP-13 · M35.C3.L-integration.V2.U02 — decided through the review's check ─────────────────
def _checked(fate: str, **over):
    from genios_engine.contracts import claim_check as C
    review = ExpertReview.from_mapping(_raw())
    base = dict(verdicts=(), fate=fate, cited=D.cited_ids(review),
                words=C.CardWords(headline=None if fate != C.SHOWN else review.next_move.what,
                                  situation=review.frames.primary, done_when=review.done_when,
                                  draft=None, to=None))
    if fate == C.HELD:
        base.update(question="Is it so: \u201cNeel wrote asking for a first call\u201d? It is not in what it cites.",
                    because="misquoted: send the deck (fact 1)")
    if fate == C.SUPPRESSED:
        base.update(because="answered:evt_meeting")
    base.update(over)
    return C.CheckedReview(**base)


def test_a_held_move_is_a_question_to_find_out_first():
    from genios_engine.contracts import claim_check as C
    request, execution = _decide(_row(checked=_checked(C.HELD)))
    decision = execution.decision
    assert (decision.outcome, decision.output_lane) == (DecisionOutcome.INSUFFICIENT_CONTEXT,
                                                        OutputLane.INVESTIGATION)
    facts = request.context.facts
    assert facts[D.F_MODE]["value"] == "find_out" and D.F_NEXT_MOVE not in facts
    assert facts[D.F_CHECK]["value"]["fate"] == C.HELD
    assert facts[D.F_CHECK]["value"]["question"].startswith("Is it so:")
    render = request.capability.metadata["render"]
    assert render["fallback"]["headline"].startswith("Is it so:"), "a held file's card asks its question"
    assert render["draft"] is None and render["artifact_kind"] == "none"


def test_an_ask_already_answered_needs_nothing():
    from genios_engine.contracts import claim_check as C
    request, execution = _decide(_row(checked=_checked(C.SUPPRESSED)))
    assert (execution.decision.outcome, execution.decision.output_lane) == (DecisionOutcome.NO_ACTION,
                                                                            OutputLane.SUPPRESS)
    assert request.context.facts[D.F_CHECK]["value"]["because"] == "answered:evt_meeting"


def test_the_card_and_the_play_speak_only_the_checked_words():
    from genios_engine.contracts import claim_check as C
    review = ExpertReview.from_mapping(_raw())
    corrected = _checked(C.SHOWN, words=C.CardWords(
        headline="Send Neel the one-page pre-read before the call", situation=None,
        done_when=None, draft=None, to=None))
    request, execution = _decide(_row(checked=corrected))
    selected = execution.selected_candidate
    assert selected.parameters["label"] == "Send Neel the one-page pre-read before the call"
    render = request.capability.metadata["render"]
    assert render["fallback"] == {"headline": "Send Neel the one-page pre-read before the call",
                                  "situation": ""}, "a withheld line is empty, never the unchecked words"
    assert render["draft"] is None, "the draft the check withheld is not on the card"
    [play] = request.capability.plays
    assert play.success_events == ("Send Neel the one-page pre-read before the call — done",), \
        "a withheld done-when is the move itself, made"
    assert review.draft and review.done_when not in play.success_events


def test_confidence_counts_only_what_the_standing_facts_cite():
    from genios_engine.contracts import claim_check as C
    whole = _decide()[1].decision.confidence_bp
    one = _decide(_row(checked=_checked(C.SHOWN, cited=("evt_neel_0927", "num:reply_days"))))[1]
    assert one.decision.confidence_bp == D.ONE_EVENT_BP < whole, \
        "a dropped fact's mail is not counted: one standing event, the base"


def test_a_review_without_a_check_or_with_nothing_standing_decides_nothing():
    from genios_engine.contracts import claim_check as C
    bare = replace(_row(), checked=None)
    with pytest.raises(ValueError, match="only a checked review decides"):
        D.request_for(bare, org_id=ORG, root_entity_type="company", domain="founder_office",
                      eval_time=NOW, graph_version=7)
    refused = _checked(C.REFUSED, cited=(), because="nothing_stands", words=C.CardWords(None, None, None,
                                                                                         None, None))
    with pytest.raises(ValueError, match="nothing standing"):
        D.request_for(_row(checked=refused), org_id=ORG, root_entity_type="company",
                      domain="founder_office", eval_time=NOW, graph_version=7)


def test_a_held_decision_replays_from_its_snapshot_as_it_was():
    from genios_engine.contracts import claim_check as C
    _request, first = _decide(_row(checked=_checked(C.HELD)))
    _replayed, comparison = replay_execution(first, D.orchestrator())
    assert comparison.matches, comparison.differences



# ── STEP-14 · the decision carries the gold lines (`yc2_w27_s14` M43.C2.L-integration.V3.U04, s14-F6–F9, `03` F179) ──
from genios_engine.reason.expert.card_lines import CardLines, MOVE_DATE, REPLY_TIME, WINDOW_SAID  # noqa: E402

LINES = CardLines(why_now="Neel wrote on 27 Sep", what_remains=("Neel asked for a first call, since 27 Sep",),
                  subject="Neel Rao", company="Kestrel Capital", kind_of_work="investor", role="lead",
                  window_days=4, window_from=REPLY_TIME)


def _with_lines(row, lines=LINES):
    return replace(row, card_lines=lines)


def _thaw(value):
    """A manifest's metadata, frozen (mappings read-only, lists tuples), as plain JSON-shaped values."""
    from collections.abc import Mapping
    if isinstance(value, Mapping):
        return {k: _thaw(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(v) for v in value]
    return value


def _gold(request):
    return _thaw(request.capability.metadata["render"]["gold"])


def test_the_decision_is_version_1_2_0():
    assert D.DECIDE_VERSION == "1.2.0"


def test_the_render_block_carries_the_gold_lines():
    request, _ = _decide(_with_lines(_row()))
    gold = _gold(request)
    assert gold == {
        "subject": "Neel Rao", "company": "Kestrel Capital", "kind_of_work": "investor", "role": "lead",
        "why_now": "Neel wrote on 27 Sep", "what_remains": ["Neel asked for a first call, since 27 Sep"],
        "recommended": {"who": "the founder", "what": "Send Neel a one-page pre-read", "for_whom": "Neel",
                        "by_when": "2026-10-08", "to": None},
        "alternative": "send it after the call", "wait_or_stop": "if no reply by the call, raise it on the call",
        "window": {"days": 3, "from": MOVE_DATE, "said": WINDOW_SAID[MOVE_DATE]}}


def test_a_move_with_no_date_takes_the_files_window():
    move = dict(_raw()["next_move"], by_when=None)
    request, execution = _decide(_with_lines(_row(next_move=move)))
    assert execution.decision.outcome_window_days == 4, "the file's measured reply time, never a default week"
    assert _gold(request)["window"] == {
        "days": 4, "from": REPLY_TIME, "said": WINDOW_SAID[REPLY_TIME]}
    watch, _ = _decide(_with_lines(_row(mode="wait", next_move=None)))
    assert [p.window_days for p in watch.capability.plays] == [4], "a watch keeps the file's window too"


def test_a_review_before_0221_keeps_its_own_words_and_a_default_window():
    move = dict(_raw()["next_move"], by_when=None)
    request, execution = _decide(_row(next_move=move))
    gold = _gold(request)
    assert gold["subject"] is None and gold["what_remains"] == [] and gold["why_now"] is None
    assert gold["recommended"]["what"] == "Send Neel a one-page pre-read"
    assert gold["window"] == {"days": D.DEFAULT_WINDOW_DAYS, "from": "default", "said": WINDOW_SAID["default"]}
    assert execution.decision.outcome_window_days == D.DEFAULT_WINDOW_DAYS


def test_the_gold_lines_are_the_checked_words_never_the_unchecked():
    from genios_engine.contracts import claim_check as C
    withheld = _checked(C.SHOWN, words=C.CardWords(headline="Send Neel a one-page pre-read", situation=None,
                                                   done_when=None, draft=None, to=None, alternative=None,
                                                   wait_or_stop=None))
    request, execution = _decide(_with_lines(_row(checked=withheld)))
    gold = request.capability.metadata["render"]["gold"]
    assert (gold["alternative"], gold["wait_or_stop"]) == (None, None)
    meta = execution.selected_candidate.parameters["metadata"]
    assert (meta["alternative"], meta["wait_or_stop"]) == (None, None), "the play carries what the check held"


def test_a_held_file_recommends_no_move():
    from genios_engine.contracts import claim_check as C
    request, _ = _decide(_with_lines(_row(checked=_checked(C.HELD))))
    gold = request.capability.metadata["render"]["gold"]
    assert gold["recommended"] is None and gold["subject"] == "Neel Rao"


def test_the_card_lines_are_part_of_the_capabilitys_address():
    one = _decide(_with_lines(_row()))[0].capability.version
    other = _decide(_with_lines(_row(), replace(LINES, why_now="Neel wrote again on 1 Oct")))[0].capability.version
    assert one != other, "a decision on other lines is another decision"
