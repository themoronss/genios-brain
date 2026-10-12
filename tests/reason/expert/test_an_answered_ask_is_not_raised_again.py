"""STEP-13 §3.4 · not already done — a move for an ask the file has answered is suppressed, and only that one.

    .venv/bin/python -m pytest -q tests/reason/expert/test_an_answered_ask_is_not_raised_again.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U02 (`reason/expert/verify.answered_by`). The move names the ask it answers
(`NextMove.answers`). An ask our reply closed is not on the dossier at all — it lists open asks only — so a
move cannot name it (`validate`: `unknown_evidence`). What stays open after it is done is a MEETING ask: a
meeting asked for, and then held or booked. A meeting on the file after the ask answers it: the move is
suppressed, its reason the meeting (`answered:<event>`). Atlas replay 04: the exact request, never every
loop with that person — a meeting does not answer a question.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import UNKNOWN_EVIDENCE, validate
from genios_engine.reason.expert.verify import answered_by, check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

BOOK = {"what": "Book the call Marco asked for and send the short deck before it",
        "answers": W.ASK_MEET, "rests_on": ["fact:1"]}


def _at(day: int, hour: int = 10) -> datetime:
    return datetime(2026, 8, day, hour, 0, tzinfo=timezone.utc)


def _check(meeting_at=None, **over) -> C.CheckedReview:
    dossier, people = W.world(asks_a_call=True, meeting_at=meeting_at)
    return check_review(W.review(**over), dossier.text, people)


def test_a_meeting_ask_with_no_meeting_since_is_still_owed():
    checked = _check(move=BOOK)
    assert checked.fate == C.SHOWN
    assert next(v for v in checked.verdicts if v.line == "answers").verdict == C.KEPT


@pytest.mark.parametrize("meeting_at", [_at(25, 15), _at(14)], ids=["booked ahead", "held since"])
def test_a_meeting_on_the_file_after_the_ask_answers_it(meeting_at):
    checked = _check(meeting_at, move=BOOK)
    assert checked.fate == C.SUPPRESSED and checked.because == f"answered:{W.MEETING}"
    assert next(v for v in checked.verdicts if v.line == "answers") == C.LineVerdict(
        "answers", C.DROPPED, C.ANSWERED, f"{W.ASK_MEET} by {W.MEETING}")
    assert checked.words.headline is None and checked.words.draft is None and checked.question is None


def test_a_meeting_before_the_ask_does_not_answer_it():
    assert _check(_at(10), move=BOOK).fate == C.SHOWN


def test_a_meeting_does_not_answer_a_question():
    """Replay 04: close the exact request. The deck is still owed after a call is booked."""
    checked = _check(_at(25, 15))                          # the faithful move answers loop:ask_deck
    assert checked.fate == C.SHOWN
    assert answered_by(W.world(asks_a_call=True, meeting_at=_at(25, 15))[0].text, W.ASK_DECK) is None


def test_an_answered_ask_wins_over_a_move_that_lost_its_ground():
    checked = _check(_at(25, 15), move=BOOK, fact1={"quote": None})
    assert checked.fate == C.SUPPRESSED, "the move is moot either way: its ask is answered"


def test_a_closed_ask_cannot_be_named_at_all():
    """Our reply closed it, so the dossier does not show it: `validate` refuses a move that names it."""
    dossier, _ = W.world()
    review = W.review(move={"answers": "loop:closed_last_week"})
    assert UNKNOWN_EVIDENCE in validate(review, dossier.catalogue).reasons
