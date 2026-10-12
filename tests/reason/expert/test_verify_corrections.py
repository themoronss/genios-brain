"""STEP-13 · a correction rewrites only the sentence that restates the fact (crosscheck X08).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_corrections.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U11 (`reason/expert/verify`). A fact's wrong number corrected by its
calculator was swapped into EVERY card text wherever the bare number appeared: fact 3's "9 days" corrected to
6 turned the draft's "a call at 9:20 tomorrow" into "6:20", "9 slides" into "6 slides", "9 Aug" into "6 Aug"
and "Q2" into "Q6" — a time nobody wrote, in the founder's ready-to-send draft. Now a correction carries the
figure it corrects — its value with its unit (or, a bare count, the word that follows it) — and rewrites it
only where a card text writes that same figure as a value, never inside a date, a time or a code, in a
sentence that restates the fact (two of its words beside the number). Anywhere else the number is left as
written, and held to its own lines like any other.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

WRONG = {"claim": "Marco answered our first mail in 9 days"}           # his reply time is 6 days
ALL = ["fact:1", "fact:2", "fact:3"]


def _check(**over) -> C.CheckedReview:
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


def test_x08_s_draft_keeps_its_time():
    """X08's run: fact 3 is corrected to 6, and the draft proposing a call at 9:20 stays at 9:20 — the
    dossier prints Marco's mail at 09:20, so the draft stands as written."""
    draft = "Hi Marco, the short deck is attached. Would a call at 9:20 tomorrow suit? Arjun"
    checked = _check(fact3=WRONG, draft=draft)
    assert _verdict(checked, "fact:3").verdict == C.CORRECTED
    assert checked.words.draft == draft and _verdict(checked, "draft").verdict == C.KEPT


@pytest.mark.parametrize("text, verdict", [
    ("Send Marco the 9 slides he can read before a call", C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER,
                                                                         "number:9")),
    ("Send Marco the short deck before 9 Aug and offer two times for a call",
     C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:9 Aug")),
    ("Send Marco the short deck and the Q2 numbers, and offer two times for a call",
     C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:q2")),
    ("Send Marco the short deck and offer a call at 9:20", C.LineVerdict("move", C.KEPT)),
])
def test_a_number_that_does_not_restate_the_fact_is_never_rewritten(text, verdict):
    """Each keeps its 9 (or Q2) as written — and is then held to its own lines like any number: the
    9:20 is the time Marco's mail was printed at; the 9 slides, 9 Aug and Q2 are on none of its lines."""
    checked = _check(fact3=WRONG, move={"what": text, "rests_on": ALL})
    assert _verdict(checked, "move") == verdict
    assert checked.words.headline == (text if verdict.verdict == C.KEPT else None)


def test_the_sentence_that_restates_the_fact_is_corrected():
    checked = _check(fact3=WRONG, move={"rests_on": ALL, "what": "Send Marco the short deck; he answered our "
                                                                 "first mail in 9 days, so expect a reply"})
    assert checked.words.headline == ("Send Marco the short deck; he answered our first mail in 6 days, so "
                                      "expect a reply")


def test_the_same_figure_in_a_sentence_about_something_else_is_not_rewritten():
    """"within 9 days" in the done-when is no restatement of how fast he answered: it is left as written,
    and its 9 days is on no line it stands on — withheld, never silently made 6."""
    checked = _check(fact3=WRONG, done_when="Marco has the deck within 9 days")
    assert checked.words.done_when is None
    assert _verdict(checked, "done_when") == C.LineVerdict("done_when", C.DROPPED, C.WRONG_NUMBER, "number:9")


def test_the_fact_s_words_in_another_sentence_do_not_make_this_one_a_restatement():
    checked = _check(fact3=WRONG, move={"rests_on": ALL, "what": "Send Marco the short deck; expect a reply "
                                                                 "within 9 days. He answered our first mail fast."})
    assert _verdict(checked, "move") == C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:9")


@pytest.mark.parametrize("fact, done_when", [
    # a month, and a function word, are no words a sentence restates a fact by
    ({"claim": "In August Marco answered our first mail in 9 days", "evidence": [W.REPLY_TIME, W.INTRO]},
     "In August Marco has the deck within 9 days"),
    ({"claim": "Marco has answered our first mail in 9 days"}, "Our deck has the answer in 9 days"),
])
def test_only_words_that_carry_anything_make_a_restatement(fact, done_when):
    checked = _check(fact3=fact, done_when=done_when)
    assert _verdict(checked, "fact:3").verdict == C.CORRECTED
    assert _verdict(checked, "done_when") == C.LineVerdict("done_when", C.DROPPED, C.WRONG_NUMBER, "number:9")


def test_the_corrected_value_in_another_unit_is_held_to_its_lines():
    """Fact 3's 9 days became 6 days: a done-when writing "6 weeks" is no correction, and no line says it."""
    checked = _check(fact3=WRONG, done_when="Marco has the deck in 6 weeks")
    assert _verdict(checked, "done_when") == C.LineVerdict("done_when", C.DROPPED, C.WRONG_NUMBER, "number:6")


def test_a_time_is_never_a_bare_count_s_restatement():
    """A bare count at the end of its fact ("… is 9") has no word after it — nor has the 9 of "9:20"."""
    checked = _check(fact3={"claim": "Marco's reply time is 9", "evidence": [W.REPLY_TIME]},
                     move={"rests_on": ALL, "what": "Send Marco the short deck; ask about his reply time at 9:20"})
    assert _verdict(checked, "fact:3").verdict == C.CORRECTED
    assert checked.words.headline == "Send Marco the short deck; ask about his reply time at 9:20"


def test_a_correction_keeps_its_unit():
    """The longest gap's "9 days" is corrected to its 5.89 days where the move restates it — and the move's
    "9 mails" is no day-count: it stays 9, on no line, and the move holds."""
    fact = {"claim": "The longest gap between touches was 9 days", "evidence": ["num:longest_gap"]}
    restated = _check(fact3=fact, move={"rests_on": ALL, "what": "Send Marco the short deck; the longest gap "
                                                                 "between touches was 9 days"})
    assert _verdict(restated, "fact:3") == C.LineVerdict("fact:3", C.CORRECTED, C.BY_CALCULATOR,
                                                         "number:9 -> 5.89 (num:longest_gap)")
    assert restated.words.headline == "Send Marco the short deck; the longest gap between touches was 5.89 days"
    mixed = _check(fact3=fact, move={"rests_on": ALL, "what": "Send Marco the short deck; the longest gap "
                                                              "between touches was 9 days, after 9 mails"})
    assert mixed.words.headline is None
    assert _verdict(mixed, "move") == C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:9")


def test_a_bare_count_is_corrected_only_where_the_same_word_follows_it():
    fact = {"claim": "Marco's reply took 9 working days", "evidence": [W.REPLY_TIME]}
    checked = _check(fact3=fact, move={"rests_on": ALL, "what": "Send Marco the short deck; his reply took "
                                                                "9 working days"})
    assert checked.words.headline == "Send Marco the short deck; his reply took 6 working days"
    other = _check(fact3=fact, move={"rests_on": ALL, "what": "Send Marco the short deck; his reply took 9 "
                                                              "working days, and the deck has 9 slides"})
    assert _verdict(other, "move") == C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:9")
