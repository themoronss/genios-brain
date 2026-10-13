"""STEP-13 · a held question says truly why, and never repeats the words that failed (second crosscheck G2, `03` X10).

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_held_question_says_truly_why.py

Tree `yc2_w27_s13` M36.C2.L-logic.V2.U10 (fix) — `reason/expert/verify.check_review`. A move held because a fact it
rests on fell — or its own words failed — asked "Is it so: “<the fell claim / the move as written>”? It is not in
what it cites.": the very words the check dropped (the misattributed name, the wrong number) reached the question
card (the acceptance's three strict xfails, `tests/replays/test_every_claim_is_checked.py`), and "It is not in what
it cites" was said of words the mail holds — an unquoted claim, a paraphrased quote (X10 part 2).

Now the held file asks what the next step is with its counterparty, and says why the one found is held in closed
words of ours, one per reason it fell — never a word of the claim or the move that failed.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

ASKS = "What is the next step with Marco Ruiz? We held the one we found: "


def _check(**over) -> C.CheckedReview:
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)


#: Each way fact 1 — the move rests on it — falls, the words it wrote, and why the question says it is held.
FELL = [
    ("uncited", {"claim": "Marco asked for a short deck from Larkspur", "evidence": [], "quote": None},
     C.UNCITED, "a fact your move rests on cites nothing on the file"),
    ("unknown", {"claim": "Marco asked for a short deck from Larkspur", "evidence": ["evt_never_shown"]},
     C.UNKNOWN_EVIDENCE, "a fact your move rests on cites something the file does not show"),
    ("unquoted", {"claim": "Marco asked for a short deck before a call", "quote": None},
     C.UNQUOTED, "a fact your move rests on quotes nothing from the mail it cites"),
    ("misquoted", {"claim": "Marco asked for a short deck before a call", "quote": "send the short deck first"},
     C.MISQUOTED, "the words a fact your move rests on quotes are not in the mail it cites"),
    ("misattributed", {"claim": "Priya Nair asked for a short deck before a call"},
     C.UNSUPPORTED, "a fact your move rests on names someone its lines do not"),
    ("wrong number", {"claim": "Marco asked for a 12-slide deck before setting up a call"},
     C.WRONG_NUMBER, "a fact your move rests on has a number its lines do not hold"),
]


@pytest.mark.parametrize("fact1, reason, why", [f[1:] for f in FELL], ids=[f[0] for f in FELL])
def test_a_held_move_says_truly_why_and_never_repeats_the_fell_claim(fact1, reason, why):
    checked = _check(fact1=fact1)
    assert checked.fate == C.HELD and next(v for v in checked.verdicts if v.line == "fact:1").reason == reason
    assert checked.because == why == C.HELD_BECAUSE[reason]
    assert checked.question == f"{ASKS}{why}."
    for words in ("short deck", "Larkspur", "Priya", "12-slide", "send the short deck first", "Is it so"):
        assert words not in checked.question, words


def test_x10_2_an_unquoted_claim_is_never_said_to_be_missing_from_the_mail():
    """The mail SAYS it — the claim is the card's headline — so "it is not in what it cites" was false."""
    checked = _check(fact1={"quote": None})
    assert "not in" not in checked.question and "quotes nothing" in checked.question


@pytest.mark.parametrize("what, reason, why", [
    ("Send Marco the 12-slide deck and offer two times for a call", C.WRONG_NUMBER,
     "the move has a number the facts it rests on do not hold"),
    ("Send Marco and Priya Nair the short deck", C.UNSUPPORTED,
     "the move names someone the facts it rests on do not")], ids=["wrong-number", "a-name-off-its-ground"])
def test_a_move_whose_own_words_failed_says_so_and_never_repeats_them(what, reason, why):
    checked = _check(move={"what": what})
    assert next(v for v in checked.verdicts if v.line == "move").reason == reason
    assert checked.fate == C.HELD and checked.because == C.HELD_BECAUSE[C.HELD_MOVE]
    assert checked.question == f"{ASKS}{why}."
    assert "12-slide" not in checked.question and "Priya" not in checked.question


def test_a_find_out_review_whose_ground_fell_asks_the_same_way():
    checked = _check(mode="find_out", move={"what": "Find out whether Marco wants the deck first"}, draft=None,
                     fact1={"quote": None})
    assert checked.fate == C.HELD and checked.question == f"{ASKS}{C.HELD_BECAUSE[C.UNQUOTED]}."
