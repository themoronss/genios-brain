"""STEP-13 · every text the founder reads is the checked one (crosscheck X03, X19, X24, X10).

    .venv/bin/python -m pytest -q tests/reason/expert/test_every_text_the_founder_reads_is_checked.py

Tree `yc2_w27_s13` M35.C3.L-integration.V2.U05. Four texts reached the founder past the check:
  * the "cost of ignoring" on every shown decision card was the review's raw `scenarios.do_nothing`
    (`decide.capability_for` copied it; `verify` only noted its numbers as prose nobody reads) — X03;
  * a proposed kind went into the brief's pending line in its RAW `why`, a corrected number uncorrected —
    X19;
  * a card's success signal and cost of ignoring carried no source, and the draft's "source" was only
    whom it goes to — X24;
  * a held file's recipient question repeated the move's raw words, a corrected number uncorrected, and
    its `because` was the check's internals ("misquoted: <the model's quote> (fact 1)") — X10.
Now `do_nothing` is checked as a card text (names and numbers on the standing facts' lines, "you" noted)
and carried in `CardWords`, which the decision reads; the kind's `why` is carried as checked and the brief's
line is written from it; every card sentence has an entry that cites or labels; the recipient questions
name the move in its checked words, and a held `because` is one closed phrase the founder can read. The
golden set's authored answers, and the prompt's scenario hints, speak to you.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.deliver import card_builder as B
from genios_engine.reason.expert import decide as D
from genios_engine.reason.expert import prompt as P
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

SEQUOIA = "Sequoia leads the round without you and the 9M allocation is gone by Friday"
WRONG = {"claim": "Marco answered our first mail in 9 days"}            # his reply time is 6 days


def _check(**over) -> C.CheckedReview:
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict | None:
    return next((v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED), None)


def _capability(review, checked):
    return D.capability_for(review, checked, root_entity_type="person", domain="founder_office",
                            eval_time=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc))


def test_x03_an_invented_cost_of_ignoring_never_reaches_the_card():
    scenarios = {**W.ANSWER["scenarios"], "do_nothing": SEQUOIA}
    review = W.review(scenarios=scenarios)
    checked = _check(scenarios=scenarios)
    assert _verdict(checked, "do_nothing").verdict == C.DROPPED and checked.words.do_nothing is None
    assert checked.fate == C.SHOWN, "the move still stands — only the sentence is withheld"
    assert _capability(review, checked).do_nothing_consequence == D.DO_NOTHING_WITHHELD
    assert D.sources_of(checked)["do_nothing"] == {"inference": D.DO_NOTHING_WITHHELD}


def test_a_cost_of_ignoring_that_stands_is_the_one_the_card_says():
    checked = _check()
    assert _verdict(checked, "do_nothing").verdict == C.KEPT
    assert checked.words.do_nothing == W.ANSWER["scenarios"]["do_nothing"]
    assert _capability(W.review(), checked).do_nothing_consequence == W.ANSWER["scenarios"]["do_nothing"]


def test_a_corrected_number_reaches_the_cost_of_ignoring_corrected():
    scenarios = {**W.ANSWER["scenarios"], "do_nothing": "Marco, who answered our first mail in 9 days, moves on"}
    checked = _check(fact3=WRONG, scenarios=scenarios)
    assert checked.words.do_nothing == "Marco, who answered our first mail in 6 days, moves on"


def test_a_cost_of_ignoring_in_the_third_person_is_noted():
    scenarios = {**W.ANSWER["scenarios"], "do_nothing": "Marco moves on and Arjun loses the introduction"}
    checked = _check(scenarios=scenarios)
    assert any(v.line == "do_nothing" and v.verdict == C.NOTED and v.reason == C.SPEAKS_OF_YOU
               for v in checked.verdicts)
    assert checked.words.do_nothing


def test_x19_the_kind_s_reason_is_carried_as_checked():
    kind = {"kind": "investor", "why": "Marco, who answered our first mail in 9 days, backs AI tooling",
            "evidence": [W.REPLY_TIME, W.INTRO]}
    checked = _check(fact3=WRONG, proposed_kind=kind)
    assert checked.words.kind == "Marco, who answered our first mail in 6 days, backs AI tooling"
    withheld = _check(proposed_kind={**kind, "why": "Marco backs AI tooling at Sequoia"})
    assert withheld.words.kind is None and not withheld.stands("kind")


def test_x24_every_sentence_of_a_shown_card_cites_or_labels_and_the_draft_cites_its_ground():
    checked = _check()
    sources = D.sources_of(checked)
    assert set(sources) == {"headline", "situation", "draft", "done_when", "do_nothing"}
    assert sources["draft"] == {"to": "Marco", "evidence": [W.ASK, W.ASK_DECK],
                                "quotes": [W.ANSWER["facts"][0]["quote"]]}
    assert sources["done_when"] == {"inference": D.DONE_WHEN_IS}
    assert sources["do_nothing"] == {"inference": D.DO_NOTHING_IS}
    why = B._sentence_sources({"capability_render": {"sources": sources}})
    assert [w["sentence"] for w in why] == list(B.CARD_SENTENCES) == [
        "headline", "situation", "draft", "done_when", "do_nothing"]
    assert all(w.get("evidence") or w.get("inference") for w in why), why


def test_x10_a_recipient_question_names_the_move_in_its_checked_words():
    """X10's run: the move's number corrected, the question repeated it uncorrected."""
    what = "Send Marco the short deck; he answered our first mail in 9 days"
    checked = _check(fact3=WRONG, move={"what": what, "to": "Arjun Rao",
                                        "rests_on": ["fact:1", "fact:2", "fact:3"]})
    assert checked.fate == C.HELD and checked.because == C.HELD_BECAUSE[C.RECIPIENT_IS_US]
    assert checked.question == ("Whom should “Send Marco the short deck; he answered our first mail in 6 days” "
                                "go to? It is addressed to you.")
    connector = _check(fact3=WRONG, alternative="", move={"what": what, "to": "Introly",
                                                           "rests_on": ["fact:1", "fact:2", "fact:3"]})
    assert connector.because == C.HELD_BECAUSE[C.RECIPIENT_IS_CONNECTOR]
    assert connector.question.startswith("“Send Marco the short deck; he answered our first mail in 6 days” "
                                         "goes to Introly")


@pytest.mark.parametrize("fact1, reason", [
    ({"quote": None}, C.UNQUOTED),
    ({"quote": "could you send your financials before we set up a call"}, C.MISQUOTED),
    ({"claim": "Neel asked for a short deck before setting up a call"}, C.UNSUPPORTED),
    ({"claim": "Marco asked for 3 short decks before setting up a call"}, C.WRONG_NUMBER),
])
def test_x10_a_held_because_is_a_closed_phrase_never_the_checks_detail(fact1, reason):
    checked = _check(fact1=fact1)
    assert checked.fate == C.HELD and checked.because == C.HELD_BECAUSE[reason]
    assert checked.because in C.HELD_BECAUSE.values()


def test_a_headline_that_fails_holds_with_the_moves_own_phrase():
    checked = _check(move={"what": "Send Marco the 12-slide deck and offer two times for a call"})
    assert checked.fate == C.HELD and checked.because == C.HELD_BECAUSE[C.HELD_MOVE]


def test_the_prompts_scenario_hints_speak_to_you():
    assert P.SCHEMA["scenarios"]["act"] == "if you act now"
    scenarios = next(step for step in P.CHECKLIST if step.name == "scenarios")
    assert "if you act now" in scenarios.asks and "the founder acts" not in scenarios.asks


THIRD_PERSON = re.compile(r"\b(?:the founder|founder's|Arjun|Nimbus|Kitebird)\b", re.I)


def test_no_authored_cost_of_ignoring_speaks_of_you_in_the_third_person():
    """The 22 the crosscheck counted (§8.1, X03): reworded to "you"."""
    found = []
    for path in sorted((Path(__file__).parents[2] / "replays" / "specs" / "founder").glob("F*.json")):
        for i, entry in enumerate((json.loads(path.read_text()).get("model") or {}).get("expert") or ()):
            text = ((entry.get("answer") or {}).get("scenarios") or {}).get("do_nothing") or ""
            if THIRD_PERSON.search(text):
                found.append(f"{path.stem}[{i}]: {text}")
    assert found == []


def test_a_question_never_repeats_words_that_did_not_stand():
    """The move's own words failed (a number on no line): the question names it as "the move"."""
    from datetime import timedelta
    dossier, people = W.world(asks_a_call=True, meeting_at=W.NOW + timedelta(days=5))
    review = W.review(move={"what": "Book the 3 calls Marco asked for", "answers": W.ASK_MEET,
                            "rests_on": ["fact:1"]})
    checked = check_review(review, dossier.text, people)
    assert checked.fate == C.HELD and checked.question.startswith("The move is already answered.")
    assert "3 calls" not in checked.question
