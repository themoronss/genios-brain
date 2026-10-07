"""STEP-01 · the ideal reader answers what a case wrote down — and refuses to guess.

    pytest tests/replays/test_ideal_reader.py -q

A founder case's cassette is recorded from its own `read` and `model` blocks: what a faithful
model answers to each prompt AS WRITTEN — production's own verdict where `04` §2 records it
(the AI filter junked the 30 Sep portal mail), a careful reading otherwise. Never the answer the
founder wishes the model gave: a prompt that drops a live application is the engine's failure,
and the exam must show it.

The reader is handed the REAL prompts here, built by the production builders, and must find the
object each prompt is about, answer it in the site's own shape, and resolve every authored quote
to its offsets in the fenced content the extractor was shown. Anything it cannot answer raises —
a cassette is never recorded from a guess.
"""
from __future__ import annotations

import copy

import pytest

from genios_engine.capture.esqe.relevance import _PROMPT_HEAD, _item_block
from genios_engine.capture.gate import relevance as gate
from genios_engine.capture.semantic.injection import fence
from genios_engine.capture.semantic.profiles import render_prompt
from genios_engine.capture.semantic.schema_gen import generate_schema_block
from genios_engine.capture.semantic.vocabulary import vocabulary_block
from tests.replays import founder_case as fc
from tests.replays.ideal_reader import IdealReader, IdealReaderError, validate_extraction

ASK = ("Hi Arjun,\n\nThanks for the call last week. Could you send us your latest deck and the "
       "July revenue? Our partners meet on Monday.\n\nBest,\nKavya Menon\nPrincipal, Lotus "
       "Ventures")
DIGEST = "Your weekly digest. Twelve rounds closed this week. Unsubscribe any time."

CASE = {
    "case_id": "F92", "title": "An investor asks for the deck", "kind": "must_detect",
    "label_row": 10, "labelled_by": "claude", "replays": [],
    "founder": {"name": "Arjun Rao", "email": "arjun@nimbuslabs.test", "company": "Nimbus Labs",
                "timezone": "Asia/Kolkata"},
    "sweeps": ["2026-09-18T12:00:00Z"],
    "objects": [
        {"id": "ask", "source": "gmail", "sweep": 0, "occurred_at": "2026-09-18T09:30:00Z",
         "from": "Kavya Menon <kavya@lotusvc.test>", "to": ["arjun@nimbuslabs.test"],
         "subject": "Deck before Monday?", "body": ASK, "labels": ["INBOX"],
         "read": {
             "gate": "keep", "relevance": "business",
             "extraction": {
                 "intent": "request", "stance": "positive", "topics": ["seed round"],
                 "entity_mentions": [
                     {"surface_form": "Kavya Menon", "entity_type": "person",
                      "quote": "Kavya Menon"},
                     {"surface_form": "Lotus Ventures", "entity_type": "organization",
                      "quote": "Lotus\nVentures"}],
                 "questions": [{"text": "Send the latest deck and the July revenue",
                                "asked_by": "Kavya Menon", "asked_of": "Arjun Rao",
                                "quote": "Could you send us your latest deck and the July "
                                         "revenue?"}],
                 "dates_mentioned": [{"as_written": "Monday", "certainty": "relative",
                                      "earliest": "2026-09-21T00:00:00+05:30",
                                      "latest": "2026-09-21T23:59:59+05:30",
                                      "resolved_against": "2026-09-18T09:30:00Z",
                                      "quote": "Monday"}],
                 "implied_actions": ["send the latest deck and the July revenue"]}}},
        {"id": "digest", "source": "gmail", "sweep": 0, "occurred_at": "2026-09-18T08:00:00Z",
         "from": "Round Up <digest@roundup.test>", "to": ["arjun@nimbuslabs.test"],
         "subject": "This week in funding", "body": DIGEST, "labels": ["INBOX"],
         "read": {"gate": {"disposition": "drop", "relevance": 0.4, "reason": "a digest"},
                  "relevance": "not_business"}},
    ],
    "expected": {"cards": [{"about": ["Kavya"], "min": 1, "max": 1}]},
    "forbidden": {"names": [], "phrases": []},
    "witness": None, "not_expressible": {},
    "model": {},
}


def _reader(case=CASE) -> IdealReader:
    return IdealReader(fc.parse_case(copy.deepcopy(case), source="test.json"))


def _extraction_prompt(text: str) -> str:
    return render_prompt("email", schema=generate_schema_block(), vocab=vocabulary_block(),
                         envelope="direction: inbound", content=fence(text).text).text


def test_the_junk_filter_is_answered_per_object_from_a_single_prompt():
    reader = _reader()
    res = reader.call(gate._GATE_PROMPT.format(source="gmail",
                                               content=f"Deck before Monday?\n\n{ASK}"))
    assert res.ok and res.parsed["disposition"] == "keep" and 0 < res.parsed["relevance"] <= 1
    res = reader.call(gate._GATE_PROMPT.format(source="gmail",
                                               content=f"This week in funding\n\n{DIGEST}"))
    assert res.parsed == {"disposition": "drop", "relevance": 0.4, "reason": "a digest"}


def test_the_batch_junk_filter_answers_every_index_in_order():
    emails = f"[0] This week in funding\n\n{DIGEST}\n\n[1] Deck before Monday?\n\n{ASK[:300]}"
    res = _reader().call(gate._GATE_BATCH_PROMPT.format(n=2, last=1, emails=emails))
    assert [(a["i"], a["disposition"]) for a in res.parsed] == [(0, "drop"), (1, "keep")]


def test_relevance_answers_by_the_item_number_it_was_given():
    class Candidate:
        def __init__(self, subject, snippet):
            self.subject, self.snippet = subject, snippet

    prompt = (_PROMPT_HEAD + _item_block(1, Candidate("Deck before Monday?", ASK))
              + _item_block(2, Candidate("This week in funding", DIGEST)))
    verdicts = {v["item"]: v for v in _reader().call(prompt).parsed["verdicts"]}
    assert verdicts[1]["business"] is True and verdicts[1]["category"] == "working"
    assert verdicts[2]["business"] is False


def test_an_extraction_cites_offsets_into_the_content_it_was_shown():
    content = f"Deck before Monday?\n\n{ASK}"
    res = _reader().call(_extraction_prompt(content))
    out = validate_extraction(res.parsed)
    spans = [e for m in out.entity_mentions for e in m.evidence] + \
            [e for q in out.questions for e in q.evidence] + \
            [e for d in out.dates_mentioned for e in d.evidence]
    assert len(spans) == 4
    for span in spans:
        assert content[span.start_offset:span.end_offset] == span.quote
    assert out.entity_mentions[0].confidence_bp > 0, "a claim without confidence is defaulted"


def test_a_quote_the_content_does_not_contain_is_refused():
    case = copy.deepcopy(CASE)
    case["objects"][0]["read"]["extraction"]["questions"][0]["quote"] = "Could you send the deck?"
    with pytest.raises(IdealReaderError, match="not in the content"):
        _reader(case).call(_extraction_prompt(f"Deck before Monday?\n\n{ASK}"))


def test_an_object_the_case_does_not_hold_is_refused():
    with pytest.raises(IdealReaderError, match="no object"):
        _reader().call(gate._GATE_PROMPT.format(source="gmail",
                                                content="An unrelated subject\n\nunrelated words"))


def test_a_site_the_object_has_no_answer_for_is_refused():
    with pytest.raises(IdealReaderError, match="extraction"):
        _reader().call(_extraction_prompt(f"This week in funding\n\n{DIGEST}"))


DECIDER = ("You are the chief of staff of a busy founder. GeniOS has flagged ONE situation.\n"
           "SITUATION: admin contact — Lotus Ventures asked for a deck\n"
           "PLAYS YOU CAN RECOMMEND:\n"
           "- play_id=admin.pb.briefing.one_page_brief | brief | steps: [] | formula utility 4701 "
           "(importance 2321)\n"
           "- play_id=admin.pb.inbox.triage_to_five_outcomes | triage | steps: [] | formula "
           "utility 4959 (importance 2321)\n")


def test_the_decider_starts_from_the_formula_and_moves_only_what_the_case_names():
    """Its prompt says START from the formula's utility and move it only for a reason: every
    listed play keeps the formula's number unless the case moves it."""
    case = copy.deepcopy(CASE)
    case["model"] = {"decider": [{"when": ["Lotus Ventures"], "answer": {
        "outcome": "decision", "confidence_bp": 6200, "move": {"one_page_brief": 6800},
        "rationale": "an investor asked for the deck before a partner meeting"}}]}
    parsed = _reader(case).call(DECIDER).parsed
    assert parsed["outcome"] == "decision" and parsed["confidence_bp"] == 6200
    assert parsed["scores"] == {"admin.pb.briefing.one_page_brief": 6800,
                                "admin.pb.inbox.triage_to_five_outcomes": 4959}
    assert parsed["missing"] == []


def test_a_decider_move_naming_no_listed_play_is_refused():
    case = copy.deepcopy(CASE)
    case["model"] = {"decider": [{"when": ["Lotus Ventures"], "answer": {
        "outcome": "decision", "confidence_bp": 6000, "move": {"send_the_deck": 9000}}}]}
    with pytest.raises(IdealReaderError, match="send_the_deck"):
        _reader(case).call(DECIDER)


def test_a_situation_the_case_does_not_answer_is_refused():
    with pytest.raises(IdealReaderError, match="decider"):
        _reader().call(DECIDER.replace("Lotus Ventures", "someone else entirely"))


def test_r1_reads_each_item_by_the_rules_its_own_prompt_states():
    from genios_engine.reason.llm_interpretation import build_prompt
    prompt = build_prompt([
        {"field": "meeting.start_at", "text": "2026-09-22T05:30:00Z", "conflict": False},
        {"field": "meeting.status", "text": "confirmed", "conflict": False},
        {"field": "mailbox.message_1", "text": "We will send the signed copy on Friday",
         "conflict": False},
        {"field": "mailbox.message_2", "text": "We are considering two other offers",
         "conflict": False},
        {"field": "deal.stage", "text": "maybe next quarter", "conflict": True}])
    readings = {r["item"]: r for r in _reader().call(prompt).parsed["readings"]}
    assert [readings[i]["classification"] for i in range(1, 6)] == [
        "NOT_INTERPRETABLE", "DECISION_MADE", "COMMITMENT_MADE", "EVALUATING_ALTERNATIVES",
        "SPECULATION_ONLY"]
    assert [readings[i]["ambiguous"] for i in range(1, 6)] == [False, False, False, True, True]
    assert all(2000 <= r["confidence_bp"] <= 8000 for r in readings.values())


def test_an_unknown_prompt_is_refused():
    with pytest.raises(IdealReaderError, match="unknown"):
        _reader().call("a prompt no site in the engine writes")


def test_a_refusal_is_not_an_exception_production_can_swallow():
    assert not issubclass(IdealReaderError, Exception)


def test_an_item_with_no_text_is_answered_as_a_model_answers_nothing():
    """Every calendar event reaches the relevance page with no subject and no snippet."""
    from pathlib import Path

    from tests.replays.ideal_reader import NO_TEXT

    class Candidate:
        subject, snippet = "", ""

    source = (Path(__file__).resolve().parents[2] / "genios_engine" / "capture" / "esqe"
              / "relevance.py").read_text(encoding="utf-8")
    assert f'"{NO_TEXT}"' in source, "the empty-item literal moved; move NO_TEXT with it"
    verdict = _reader().call(_PROMPT_HEAD + _item_block(1, Candidate())).parsed["verdicts"][0]
    assert verdict["item"] == 1 and verdict["business"] is False
    assert verdict["category"] == "unknown" and verdict["asks_for_reply"] is None


def test_a_message_that_states_no_completion_is_read_as_not_resolved():
    prompt = ("You read ONE message that landed on an open business situation and answer ONE "
              "question:\n<<<CONTENT_0123456789abcdef>>>\nHi Arjun,\n\nCould you share the "
              "metrics before Monday?\n\nThanks\n<<<END_0123456789abcdef>>>\n")
    answer = _reader().call(prompt).parsed
    message = prompt.split("<<<CONTENT_0123456789abcdef>>>\n")[1].split("\n<<<END")[0]
    assert answer["verdict"] == "NOT_RESOLVED" and answer["certainty"] == "INTENT_ONLY"
    assert answer["quote"] == "Could you share the metrics before Monday?"
    assert message[answer["start_offset"]:answer["end_offset"]] == answer["quote"]
    assert answer["scope"] == []


def test_a_completion_the_case_knows_about_is_authored_and_located():
    case = copy.deepcopy(CASE)
    case["model"] = {"resolution": [{"when": ["sorting this"], "answer": {
        "verdict": "RESOLVED", "certainty": "EXPLICIT_COMPLETION", "scope": ["situation"],
        "quote": "Thanks for sorting this on the call yesterday"}}]}
    prompt = ("You read ONE message that landed on an open business situation and answer ONE "
              "question:\n<<<CONTENT_0123456789abcdef>>>\nThanks for sorting this on the call "
              "yesterday — all good from our side.\n<<<END_0123456789abcdef>>>\n")
    answer = _reader(case).call(prompt).parsed
    assert answer["verdict"] == "RESOLVED" and answer["scope"] == ["situation"]
    assert answer["start_offset"] == 0 and answer["quote"].startswith("Thanks for sorting")


def test_the_decider_scores_exactly_the_plays_its_template_names():
    """`parse_answer` refuses any other set: an ineligible play the prompt lists is not scored."""
    case = copy.deepcopy(CASE)
    case["model"] = {"decider": [{"when": ["Lotus Ventures"], "answer": {
        "outcome": "defer", "confidence_bp": 4000}}]}
    prompt = DECIDER + ('Answer with ONLY this JSON object, no prose around it:\n{"outcome": '
                        '"decision | defer", "scores": {"admin.pb.briefing.one_page_brief": '
                        '"<int 0-10000>"}, "confidence_bp": "<int 0-10000>"}')
    assert _reader(case).call(prompt).parsed["scores"] == {"admin.pb.briefing.one_page_brief": 4701}


def test_a_refused_answer_is_an_authoring_error_never_a_second_recording():
    case = copy.deepcopy(CASE)
    case["model"] = {"decider": [{"when": ["Lotus Ventures"], "answer": {
        "outcome": "defer", "confidence_bp": 4000}}]}
    prompt = DECIDER + "\nCORRECTION — your previous answer was refused. scores must have exactly"
    with pytest.raises(IdealReaderError, match="refused"):
        _reader(case).call(prompt)


# ── STEP-07 · the company brief rides in every judging prompt, and decides no match ─────────────

def _brief_block(*lines) -> str:
    from genios_engine.contracts.company_brief import CompanyBriefLine, compose
    return compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao", us=(),
                   lines=[CompanyBriefLine(line_id=f"l{n}", **line)
                          for n, line in enumerate(lines)]).prompt_block()


def test_a_term_the_company_brief_names_never_matches_through_the_brief():
    """The brief is the same in every prompt of a case. A `when` term it also names — here the
    investor's firm, on the brief's in-motion line — must still pick out the ONE situation it was
    written for, never every situation whose prompt carries the brief."""
    case = copy.deepcopy(CASE)
    case["model"] = {"decider": [{"when": ["Lotus Ventures"], "answer": {
        "outcome": "decision", "confidence_bp": 6200,
        "rationale": "an investor asked for the deck before a partner meeting"}}]}
    block = _brief_block({"section": "in_motion", "text": "Fundraising — Lotus Ventures engaged"})
    elsewhere = DECIDER.replace("Lotus Ventures", "someone else entirely")
    with_brief = elsewhere.replace("SITUATION:", block + "\nSITUATION:", 1)
    assert "Lotus Ventures" in with_brief
    with pytest.raises(IdealReaderError, match="decider"):
        _reader(case).call(with_brief)
    named = DECIDER.replace("SITUATION:", block + "\nSITUATION:", 1)
    assert _reader(case).call(named).parsed["outcome"] == "decision"
