"""STEP-12 · the expert's review has a shape code can check, and it refuses what its dossier does not hold.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_review_contract.py

Tree `yc2_w27_s12` M32.C1.L-contract.V0.U01 (`contracts/expert_review.py`). Plane R had no result
contract (STEP-12 §8.3 N5); the review is the Atlas's `reasoning_result`: facts that cite, inferences
and patterns that rest on something, hypotheses and unknowns, a frame and its rivals, expected vs actual
against the playbook's stage, scenarios, an appraisal in levels with reasons, a mode, a next move, an
alternative, when to wait or stop, done-when and a draft. `validate` refuses an uncited fact, a citation
the dossier never showed, an inference or a pattern resting on nothing it holds, a stage the playbook
lacks, a moving mode with no next move — and any number, anywhere in the review, that the dossier does
not hold. A malformed answer is a ValueError that names the field: the one thing a caller may repair.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from genios_engine.contracts.expert_review import (
    MODES, NO_NEXT_MOVE, NUMBER_NOT_IN_DOSSIER, REFUSALS, UNCITED_FACT, UNGROUNDED_INFERENCE,
    UNGROUNDED_PATTERN, UNKNOWN_EVIDENCE, UNKNOWN_STAGE, DossierCatalogue, ExpertReview, number_tokens,
    validate)

pytestmark = pytest.mark.unit

CATALOGUE = DossierCatalogue(
    evidence_ids=frozenset({"evt_neel_0927", "evt_invite_1008", "pb:first_call", "num:reply_days"}),
    numbers=number_tokens("27 Sep Neel wrote · the call on 8 Oct · last mail to any investor 40 days ago"
                          " · Neel replies in 3 days (n=6)"),
    stages=("first_contact", "first_call", "partner_meeting"))


def _raw(**over) -> dict:
    raw = {
        "facts": [{"claim": "Neel wrote on 27 Sep asking for a first call", "evidence": ["evt_neel_0927"]},
                  {"claim": "The call is booked for 8 Oct", "evidence": ["evt_invite_1008"]}],
        "inferences": [{"claim": "This is a first call with a fund", "based_on": ["fact:1", "fact:2"]}],
        "patterns": [{"kind": "pattern", "claim": "Neel answers within 3 days",
                      "based_on": ["num:reply_days"]},
                     {"kind": "counter_pattern", "claim": "a fund that books the call itself rarely ghosts",
                      "based_on": ["pb:first_call"]}],
        "hypotheses": [{"proposition": "Neel leads deals at this stage", "needs": "his last deals"}],
        "unknowns": [{"question": "Does the fund invest pre-seed?", "relevance": "decides the pitch"}],
        "frames": {"primary": "a first call with a top-tier fund", "rivals": ["an exploratory chat"]},
        "expected_vs_actual": {"stage": "first_call", "expected": "a pre-read before the call",
                               "actual": "nothing sent yet"},
        "scenarios": {"do_nothing": "the call runs cold", "act": "a pre-read frames the call",
                      "best": "a partner meeting follows", "worst": "a polite pass",
                      "signals_to_watch": ["a reply to the pre-read"]},
        "appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                      "reasons": ["the call is close and the fund is the founder's best lead"]},
        "mode": "act",
        "next_move": {"who": "the founder", "what": "send a one-page pre-read",
                      "for_whom": "Neel", "by_when": "2026-10-07"},
        "alternative": "send it after the call",
        "wait_or_stop": "if no reply by the call, raise it on the call",
        "done_when": "the call happens and its next step is logged",
        "draft": "Hi Neel, ahead of our call on 8 Oct, a one-page note on where we are."}
    raw.update(over)
    return raw


def test_a_whole_review_parses_and_validates():
    review = ExpertReview.from_mapping(_raw())
    assert review.mode == "act" and review.next_move.by_when == date(2026, 10, 7)
    assert [p.kind for p in review.patterns] == ["pattern", "counter_pattern"]
    result = validate(review, CATALOGUE)
    assert result.ok and result.reasons == () and result.problems == ()


@pytest.mark.parametrize("over, refusal", [
    ({"facts": [{"claim": "Neel wrote", "evidence": ["evt_made_up"]}]}, UNKNOWN_EVIDENCE),
    ({"inferences": [{"claim": "a fund", "based_on": ["fact:9"]}]}, UNGROUNDED_INFERENCE),
    ({"inferences": [{"claim": "a fund", "based_on": ["fact:0"]}]}, UNGROUNDED_INFERENCE),
    ({"inferences": [{"claim": "a fund", "based_on": []}]}, UNGROUNDED_INFERENCE),
    ({"inferences": [{"claim": "a fund", "based_on": ["evt_made_up"]}]}, UNKNOWN_EVIDENCE),
    ({"patterns": [{"kind": "base_rate", "claim": "most first calls lead nowhere", "based_on": []}]},
     UNGROUNDED_PATTERN),
    ({"patterns": [{"kind": "pattern", "claim": "Neel is quick", "based_on": ["num:made_up"]}]},
     UNKNOWN_EVIDENCE),
    ({"patterns": [{"kind": "pattern", "claim": "Neel is quick", "based_on": ["fact:3"]}]},
     UNGROUNDED_PATTERN),
    ({"expected_vs_actual": {"stage": "term_sheet", "expected": "x", "actual": "y"}}, UNKNOWN_STAGE),
    ({"mode": "find_out", "next_move": None}, NO_NEXT_MOVE),
    ({"mode": "act", "next_move": None}, NO_NEXT_MOVE),
    ({"draft": "Hi Neel, we grew 32% last month."}, NUMBER_NOT_IN_DOSSIER),
    ({"facts": [{"claim": "Neel wrote 12 days ago", "evidence": ["evt_neel_0927"]}]},
     NUMBER_NOT_IN_DOSSIER),
    ({"appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                    "reasons": ["a $2m round rides on it"]}}, NUMBER_NOT_IN_DOSSIER),
    ({"next_move": {"who": "the founder", "what": "send 5 slides", "for_whom": "Neel"}},
     NUMBER_NOT_IN_DOSSIER),
])
def test_what_the_dossier_does_not_hold_is_refused_by_name(over, refusal):
    result = validate(ExpertReview.from_mapping(_raw(**over)), CATALOGUE)
    assert not result.ok and refusal in result.reasons, result.problems


def test_a_fact_with_no_citation_is_refused():
    result = validate(ExpertReview.from_mapping(_raw(facts=[{"claim": "Neel is keen",
                                                              "evidence": []}])), CATALOGUE)
    assert UNCITED_FACT in result.reasons, result.problems


def test_every_refusal_is_named_and_counted_once_per_kind():
    review = ExpertReview.from_mapping(_raw(
        facts=[{"claim": "Neel wrote 12 days ago", "evidence": ["evt_made_up"]},
               {"claim": "it is 99 percent sure", "evidence": []}],
        mode="find_out", next_move=None))
    result = validate(review, CATALOGUE)
    assert set(result.reasons) == {UNKNOWN_EVIDENCE, UNCITED_FACT, NO_NEXT_MOVE, NUMBER_NOT_IN_DOSSIER}
    assert result.reasons == tuple(sorted(result.reasons))
    assert set(result.reasons) <= set(REFUSALS)
    assert (NUMBER_NOT_IN_DOSSIER, "12") in result.problems and (NUMBER_NOT_IN_DOSSIER, "99") in result.problems


@pytest.mark.parametrize("mode", ["wait", "nothing", "blocked"])
def test_a_mode_that_does_not_move_needs_no_next_move(mode):
    review = ExpertReview.from_mapping(_raw(mode=mode, next_move=None, draft=None))
    assert review.next_move is None and review.draft is None
    assert validate(review, CATALOGUE).ok


@pytest.mark.parametrize("over, says", [
    ({"facts": []}, "at least one fact"),
    ({"mode": "panic"}, "mode"),
    ({"appraisal": {"stakes": "very", "urgency": "high", "reversibility": "reversible",
                    "reasons": ["r"]}}, "stakes"),
    ({"appraisal": {"stakes": "high", "urgency": "high", "reversibility": "reversible",
                    "reasons": []}}, "reasons"),
    ({"frames": {"primary": "a first call", "rivals": []}}, "rival frames"),
    ({"scenarios": {"do_nothing": "a", "act": "b", "best": "c", "worst": "d",
                    "signals_to_watch": []}}, "signals to watch"),
    ({"done_when": ""}, "what done looks like"),
    ({"wait_or_stop": None}, "when to wait or stop"),
    ({"facts": "Neel wrote"}, "facts"),
    ({"facts": ["Neel wrote"]}, "a fact"),
    ({"facts": [{"claim": "Neel wrote", "evidence": "evt_neel_0927"}]}, "a fact's evidence"),
    ({"facts": [{"claim": "Neel wrote", "evidence": [{"id": "evt_neel_0927"}]}]},
     "a fact's evidence must be words"),
    ({"inferences": "a fund"}, "inferences"),
    ({"patterns": [{"kind": "rumour", "claim": "x", "based_on": ["pb:first_call"]}]}, "kind"),
    ({"next_move": {"who": "the founder", "what": "x", "for_whom": "Neel", "by_when": "soon"}},
     "by_when"),
    ({"next_move": "send a pre-read"}, "next move"),
    ({"frames": ["a first call"]}, "frames"),
])
def test_a_malformed_answer_is_a_value_error_that_says_what(over, says):
    with pytest.raises(ValueError, match=says):
        ExpertReview.from_mapping(_raw(**over))


def test_an_answer_that_is_not_an_object_is_a_value_error():
    with pytest.raises(ValueError, match="an object"):
        ExpertReview.from_mapping(["facts"])


def test_the_closed_words_are_read_as_a_reader_spells_them():
    review = ExpertReview.from_mapping(_raw(
        mode="Find out", appraisal={"stakes": " Medium", "urgency": "LOW",
                                    "reversibility": "costly to reverse", "reasons": ["r"]},
        patterns=[{"kind": "counter-pattern", "claim": "x", "based_on": ["pb:first_call"]}]))
    assert review.mode == "find_out" and "find_out" in MODES
    assert (review.appraisal.stakes, review.appraisal.urgency) == ("medium", "low")
    assert review.appraisal.reversibility == "costly_to_reverse"
    assert review.patterns[0].kind == "counter_pattern"


def test_a_review_round_trips_through_its_mapping():
    review = ExpertReview.from_mapping(_raw())
    again = ExpertReview.from_mapping(review.as_mapping())
    assert again == review
    assert again.as_mapping()["next_move"]["by_when"] == "2026-10-07"
    bare = ExpertReview.from_mapping(_raw(mode="wait", next_move=None, draft=None, patterns=[]))
    assert ExpertReview.from_mapping(bare.as_mapping()) == bare


def test_a_review_is_frozen():
    review = ExpertReview.from_mapping(_raw())
    with pytest.raises(FrozenInstanceError):
        review.mode = "nothing"                                   # type: ignore[misc]


def test_every_text_the_review_writes_is_read_for_numbers():
    review = ExpertReview.from_mapping(_raw())
    texts = review.texts()
    for expected in ("Neel answers within 3 days", "send a one-page pre-read", "a polite pass",
                     "his last deals", "decides the pitch", "an exploratory chat", "nothing sent yet",
                     "send it after the call", "Hi Neel, ahead of our call on 8 Oct, a one-page note"
                     " on where we are."):
        assert expected in texts, expected


def test_numbers_compare_by_value_not_spelling():
    assert number_tokens("1,400 calls, 2.50 days, on 07 Oct 2026") == {"1400", "2.5", "7", "2026"}
    assert number_tokens("version 1.5.1") == {"1", "5"}
    assert number_tokens("0.50 of it") == {"0.5"}
    assert number_tokens("on 7,8 and 9 Oct, 1,400.50 in all") == {"7", "8", "9", "1400.5"}
    assert number_tokens("forty days") == frozenset()            # words are not read — digits are
    assert number_tokens(None) == frozenset()


def test_a_number_the_dossier_holds_passes_whatever_its_spelling():
    review = ExpertReview.from_mapping(_raw(draft="Hi Neel — our call on 08 Oct; it has been 40.0 days."))
    assert validate(review, CATALOGUE).ok


def test_no_stage_is_fine_when_the_file_has_no_playbook():
    review = ExpertReview.from_mapping(_raw(expected_vs_actual={"expected": "a reply", "actual": "none"}))
    assert review.expected_vs_actual.stage is None
    assert validate(review, DossierCatalogue(CATALOGUE.evidence_ids, CATALOGUE.numbers, ())).ok


def test_a_stage_is_refused_when_the_file_has_no_playbook():
    review = ExpertReview.from_mapping(_raw())
    result = validate(review, DossierCatalogue(CATALOGUE.evidence_ids, CATALOGUE.numbers, ()))
    assert result.reasons == (UNKNOWN_STAGE,)
