"""STEP-13 §3.2 · every number is a calculation — corrected to its calculator's value, or dropped (RULE 08).

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_numbers.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U03 (`reason/expert/verify`). A number a fact writes must be on the lines
it cites; one that is not is corrected to the ONE value its ONE cited calculator line prints, or the fact
drops (`wrong_number`). Every number in the card's words is on a line the move rests on — corrected by the
same map, wherever the card repeats it; a headline whose number fails holds a moving review, a situation,
a done-when or a draft whose number fails is withheld. A number in prose no founder is shown is noted.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review, value_of
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit


def _check(**over) -> C.CheckedReview:
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


def test_a_wrong_number_on_a_calculator_is_corrected_to_its_value():
    checked = _check(fact3={"claim": "Marco answered our first mail in 9 days"})
    assert _verdict(checked, "fact:3") == C.LineVerdict(
        "fact:3", C.CORRECTED, C.BY_CALCULATOR, f"number:9 -> 6 ({W.REPLY_TIME})")
    assert checked.stands("fact:3") and checked.fate == C.SHOWN


def test_the_correction_reaches_every_card_text_that_repeats_it():
    checked = _check(fact3={"claim": "Marco answered our first mail in 9 days"},
                     move={"rests_on": ["fact:1", "fact:2", "fact:3"],
                           "what": "Send Marco the short deck; he answered our first mail in 9 days"})
    assert checked.words.headline == "Send Marco the short deck; he answered our first mail in 6 days"
    assert _verdict(checked, "move").verdict == C.CORRECTED


def test_a_wrong_number_with_no_one_calculator_drops_its_fact():
    """Fact 4 cites a mail, not a calculator: nothing can say what the number should be."""
    checked = _check(fact4={"claim": "Introly introduced Marco on 7 Aug"})
    # ⛔ RESTATED by M35.C2.L-logic.V1.U10: "7 Aug" is read as the DATE it is (held to the dates its lines
    # print), so the detail names the date, not a bare 7.
    assert _verdict(checked, "fact:4") == C.LineVerdict("fact:4", C.DROPPED, C.WRONG_NUMBER, "number:7 Aug")
    two = _check(fact3={"claim": "Marco answered in 1 day and 9 hours"})
    assert _verdict(two, "fact:3").reason == C.WRONG_NUMBER, "two numbers off: no guess"


def test_a_headline_whose_number_its_ground_does_not_hold_holds_the_move():
    checked = _check(move={"what": "Send Marco the 12-slide deck and offer two times for a call"})
    assert _verdict(checked, "move") == C.LineVerdict("move", C.DROPPED, C.WRONG_NUMBER, "number:12")
    assert checked.fate == C.HELD and checked.words.headline is None and checked.words.draft is None
    # ⛔ RESTATED by M36.C2.L-logic.V2.U10 (fix, the second crosscheck G2, `03` X10): this pinned the question
    # REPEATING the wrong number ("12-slide") — the very echo the acceptance's strict xfails recorded. The
    # question says why the move is held, never the number its check refused.
    assert checked.question and "12" not in checked.question
    assert checked.question.endswith("the move has a number the facts it rests on do not hold.")


@pytest.mark.parametrize("part, text, word", [
    ("situation", {"frames": {"primary": "An investor asked for a deck 3 times", "rivals": ["a pass"]}},
     "situation"),
    ("done_when", {"done_when": "Marco has the deck within 48 hours"}, "done_when"),
    ("draft", {"draft": "Hi Marco, the deck is attached — we grew 40% last month. Arjun"}, "draft"),
])
def test_a_card_text_whose_number_fails_is_withheld_and_the_card_shows_the_rest(part, text, word):
    checked = _check(**text)
    assert _verdict(checked, part).reason == C.WRONG_NUMBER
    assert getattr(checked.words, word) is None
    assert checked.fate == C.SHOWN and checked.words.headline, "the move still stands"


def test_a_number_in_prose_no_founder_sees_is_noted_not_refused():
    checked = _check(hypotheses=[{"proposition": "Altavia has 17 or 29 partners", "needs": "its site"}])
    assert checked.fate == C.SHOWN and checked.dropped == ()
    [note] = [v for v in checked.verdicts if v.verdict == C.NOTED and v.reason == C.UNHELD_NUMBER]
    assert note.line == "prose" and note.detail == "number:17, number:29"


def test_an_ids_digits_are_no_number():
    """`evt_marco_0811` grounds no "811": a fact that writes one is held to its line's own numbers."""
    checked = _check(fact1={"claim": "Marco asked 811 investors for a short deck before setting up a call"})
    assert next(v for v in checked.verdicts if v.line == "fact:1").reason == C.WRONG_NUMBER


@pytest.mark.parametrize("line, ref, value", [
    ("their reply time: once: 6 days [num:x]", "num:x", "6"),
    ("their reply time: usually 6 days (n=4, person) [num:x]", "num:x", "6"),
    ("their reply time: 3 times, median 5 days — too few to call normal [num:x]", "num:x", "5"),
    ("Usual gap between touches: usually 6 days (n=2, file) [num:usual_gap]; longest closed gap: 6 days "
     "[num:longest_gap]; quiet now: 9 days [num:days_quiet]", "num:days_quiet", "9"),
    ("Usual gap between touches: usually 6 days (n=2, file) [num:usual_gap]; quiet now: 9 days "
     "[num:days_quiet]", "num:usual_gap", "6"),
    ("- [wave:w1] a wave: sent to 5, replied 2 of 5 [num:x]", "num:x", None),     # a rate: two numbers
    ("their reply time: not measured [num:x]", "num:x", None),
    ("their reply time: once: 6 days [num:x]", "num:y", None),
])
def test_a_calculator_prints_one_value_beside_its_id(line, ref, value):
    assert value_of(line, ref) == value


# ── M35.C2.L-logic.V1.U10 (fix) · the second crosscheck G6: a count is never the sample size ────────────────────

def test_g6_a_count_is_never_the_sample_size():
    """G6's run: "Marco has 2 open asks", citing the usual gap ("2 times, median 3.48 days"), was KEPT — the count
    the median was taken over grounded a count of something else. It is held to the calculator's value (a bare
    count corrected within no unit, as declared: the noun is not read)."""
    checked = _check(fact3={"claim": "Marco has 2 open asks", "evidence": ["num:usual_gap"]})
    assert _verdict(checked, "fact:3") == C.LineVerdict("fact:3", C.CORRECTED, C.BY_CALCULATOR,
                                                        "number:2 -> 3.48 (num:usual_gap)")


def test_g6_a_card_text_is_never_grounded_on_a_sample_size():
    """The run's own figures (`_Run.figures`) are what every card text's numbers are held to: the sample is
    no figure of theirs either."""
    checked = _check(fact3={"claim": "His usual gap is 3.48 days", "evidence": ["num:usual_gap"]},
                     frames={"primary": "Marco has written 2 times since the introduction", "rivals": ["a pass"]})
    assert _verdict(checked, "situation") == C.LineVerdict("situation", C.DROPPED, C.WRONG_NUMBER, "number:2")


def test_the_calculator_s_own_value_still_grounds():
    """The negative control: the median itself is the calculator's value."""
    checked = _check(fact3={"claim": "His usual gap is 3.48 days", "evidence": ["num:usual_gap"]})
    assert _verdict(checked, "fact:3").verdict == C.KEPT
