"""STEP-13 · a decisive claim on words nobody was shown is unquoted (crosscheck X22).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_unquoted.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U16 (`reason/expert/verify`). A fact the move rests on QUOTES the mail it
cites — but only a mail whose words the dossier shows could be quoted, so a decisive fact citing a mail
nobody was shown the words of (an older touch past `TOUCHES_WHOLE`, a mail memory holds no words for), or a
meeting with no words, needed no quote at all: "Marco said in the meeting he will lead the round" stood
under "Send Marco the term sheet draft" (X22's run). It needs a quote it cannot have: `unquoted`.

What such an event DOES show is its own line — when, which way, with whom. So a decisive fact about a
meeting itself ("a call is booked for the 25th", "memory holds no words for it") stands on that line, as
the golden set's authored answers rest on it (F07, F28, F29, F54 — measured, 12 Oct); only a claim that
reports what was SAID there needs the words. A mail is cited for what it says: a decisive fact citing only
mails whose words are not shown is unquoted, whatever it claims.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

HELD_ON = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
BOOKED_FOR = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)
TERM_SHEET = {"what": "Send Marco the term sheet draft", "rests_on": ["fact:1", "fact:2"]}


def _check(world_kw=None, **over) -> C.CheckedReview:
    dossier, people = W.world(**(world_kw or {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


@pytest.mark.parametrize("claim", [
    "Marco said in the meeting he will lead the round",
    "In the meeting Marco agreed to lead the round",
    "Marco told us at the meeting that he will not lead the round",
])
def test_what_was_said_in_a_meeting_with_no_words_is_unquoted(claim):
    """X22's own run: the meeting prints when and with whom — not a word of what was said."""
    checked = _check({"meeting_at": HELD_ON}, fact1={"claim": claim, "evidence": [W.MEETING], "quote": None},
                     move=TERM_SHEET, draft=None)
    assert _verdict(checked, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.UNQUOTED, W.MEETING)
    assert checked.fate == C.HELD and checked.words.headline is None


@pytest.mark.parametrize("claim", ["Marco asked for the deck in July", "Marco wrote in July",
                                   "Marco's July note is about the deck"])
def test_a_decisive_fact_on_a_mail_whose_words_are_not_shown_is_unquoted(claim):
    """`evt_old_0` is listed "(older — its words not shown)": nobody can say what it says."""
    checked = _check({"older": 6}, fact1={"claim": claim, "evidence": ["evt_old_0"], "quote": None})
    assert _verdict(checked, "fact:1") == C.LineVerdict("fact:1", C.DROPPED, C.UNQUOTED, "evt_old_0")
    assert checked.fate == C.HELD


def test_a_quote_given_for_words_nobody_was_shown_drops_too():
    checked = _check({"older": 6}, fact1={"claim": "Marco asked for the deck in July", "evidence": ["evt_old_0"],
                                          "quote": "could you send the deck"})
    assert _verdict(checked, "quote:1").reason == C.MISQUOTED
    assert _verdict(checked, "fact:1").reason == C.UNQUOTED


@pytest.mark.parametrize("meeting_at, claim", [
    (HELD_ON, "A meeting with Marco was held on 14 Aug"),
    (HELD_ON, "Memory holds no words for the meeting, so nothing on file says what was agreed there"),
    (HELD_ON, "Nothing on file says what was agreed at the meeting with Marco"),
    (BOOKED_FOR, "A call with Marco is booked for 25 Aug"),
])
def test_a_decisive_fact_about_the_meeting_itself_stands_on_its_line(meeting_at, claim):
    checked = _check({"meeting_at": meeting_at}, fact1={"claim": claim, "evidence": [W.MEETING], "quote": None})
    assert _verdict(checked, "fact:1").verdict == C.KEPT, checked.verdicts
    assert checked.fate == C.SHOWN


def test_a_fact_the_move_does_not_rest_on_needs_no_words():
    checked = _check({"older": 6}, fact4={"claim": "Marco wrote in July", "evidence": ["evt_old_0"]})
    assert _verdict(checked, "fact:4").verdict == C.KEPT and checked.fate == C.SHOWN


def test_a_decisive_fact_quoting_a_shown_mail_beside_one_not_shown_is_held_to_its_quote():
    """The quote rule governs a fact that cites a mail whose words ARE shown (U09)."""
    checked = _check({"older": 6}, fact1={"evidence": [W.ASK, "evt_old_0"]})
    assert _verdict(checked, "fact:1").verdict == C.KEPT and checked.fate == C.SHOWN
