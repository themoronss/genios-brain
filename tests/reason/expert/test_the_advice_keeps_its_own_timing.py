"""STEP-13b · a duration in the advice's own words is the advice, not a claim about the file.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_advice_keeps_its_own_timing.py

Tree `yc2_w27_s13b` M37.C4.L-logic.V10.U05 (`reason/expert/verify`). "Within 24 hours", "in 2 days" in the move's, the
draft's or doing-nothing's words: 142 of Haiku's drops were `wrong_number`, 47 in doing-nothing and 40 in the move and
its draft. It stands when it agrees with the move's `by_when` (code computes the distance from the dossier's instant),
and is corrected to "by <by_when>" when it does not; with no `by_when` it drops as today. A count about the file ("2
decks") and a number the file's lines hold are held as before (RULE 08). Only the move, the draft and doing-nothing.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

TOMORROW, NEXT_WEEK = "2026-08-21", "2026-08-27"          # the dossier is as of 2026-08-20 09:00 UTC


def _check(**over):
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people)


def _v(checked, line):
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


@pytest.mark.parametrize("by_when, said", [(TOMORROW, "within 24 hours"), (TOMORROW, "in 1 day"),
                                           ("2026-08-22", "in 2 days"), ("2026-08-22", "within 48 hours"), ("2026-08-22", "within 47 hours"),
                                           (NEXT_WEEK, "within 1 week"), (NEXT_WEEK, "after 7 days")])
def test_a_duration_that_agrees_with_by_when_stands_as_written(by_when, said):
    what = f"Send Marco the short deck {said}"
    checked = _check(move={"what": what, "by_when": by_when})
    assert _v(checked, "move").verdict == C.KEPT, _v(checked, "move")
    assert checked.words.headline == what


@pytest.mark.parametrize("by_when, said, corrected", [
    (TOMORROW, "within 2 days", "by 2026-08-21"), (TOMORROW, "in 48 hours", "by 2026-08-21"),
    (NEXT_WEEK, "within 2 weeks", "by 2026-08-27"), ("2026-08-22", "within 24 hours", "by 2026-08-22"), ("2026-08-22", "in 3 days", "by 2026-08-22")])
def test_a_duration_that_disagrees_is_corrected_to_by_when(by_when, said, corrected):
    checked = _check(move={"what": f"Send Marco the short deck {said}", "by_when": by_when})
    verdict = _v(checked, "move")
    assert (verdict.verdict, verdict.reason) == (C.CORRECTED, C.BY_WHEN), verdict
    assert checked.words.headline == f"Send Marco the short deck {corrected}"
    assert verdict.detail == f"Send Marco the short deck {said} -> {checked.words.headline}"


def test_with_no_by_when_it_drops_as_today():
    checked = _check(move={"what": "Send Marco the short deck within 24 hours", "by_when": None})
    assert (_v(checked, "move").verdict, _v(checked, "move").reason) == (C.DROPPED, C.WRONG_NUMBER)


def test_the_draft_and_what_doing_nothing_costs_are_the_advice_too():
    ok = _check(draft="Hi Marco, the short deck is attached; I will follow up within 24 hours. Arjun",
                scenarios={**W.ANSWER["scenarios"], "do_nothing": "the introduction goes cold within 24 hours"})
    assert _v(ok, "draft").verdict == _v(ok, "do_nothing").verdict == C.KEPT
    off = _check(draft="Hi Marco, the short deck is attached; I will follow up in 5 days. Arjun",
                 scenarios={**W.ANSWER["scenarios"], "do_nothing": "the introduction goes cold in 5 days"})
    assert (_v(off, "draft").verdict, _v(off, "draft").reason) == (C.CORRECTED, C.BY_WHEN)
    assert off.words.draft.endswith("I will follow up by 2026-08-21. Arjun")
    assert (_v(off, "do_nothing").verdict, _v(off, "do_nothing").reason) == (C.CORRECTED, C.BY_WHEN)
    assert off.words.do_nothing == "the introduction goes cold by 2026-08-21"


def test_a_count_about_the_file_is_still_held_to_its_lines():
    for what in ("Send Marco the 2 short decks", "Send Marco the short deck; he has 3 open asks",
                 "Send Marco the short deck within 2 meetings"):
        checked = _check(move={"what": what})
        assert (_v(checked, "move").verdict, _v(checked, "move").reason) == (C.DROPPED, C.WRONG_NUMBER), what


def test_a_duration_the_lines_the_text_is_held_to_hold_is_left_as_written():
    """"6 days" is on the lines of a fact the move rests on (their reply time): the file's own figure, never the advice's —
    so it is not rewritten to a date, however far it is from `by_when`."""
    held = _check(move={"what": "Send Marco the short deck; he usually replies in 6 days",
                        "rests_on": ["fact:1", "fact:3"]})
    assert _v(held, "move").verdict == C.KEPT
    assert held.words.headline == "Send Marco the short deck; he usually replies in 6 days"
    unheld = _check(move={"what": "Send Marco the short deck; he usually replies in 6 days"})
    assert _v(unheld, "move").reason == C.BY_WHEN, "on lines the move does not rest on, it is the advice's"
    still = _check(scenarios={**W.ANSWER["scenarios"],
                              "do_nothing": "after 3 days of nothing the file has been quiet 12 days"})
    assert (_v(still, "do_nothing").verdict, _v(still, "do_nothing").reason) == (C.DROPPED, C.WRONG_NUMBER), \
        "a count about the file ('quiet 12 days') beside the advice's duration is still held to its lines"


def test_the_other_card_words_are_not_the_advice():
    for line, over in (("situation", {"frames": {**W.ANSWER["frames"], "primary": "A deck is asked within 24 hours"}}),
                       ("done_when", {"done_when": "Marco has the deck within 24 hours"})):
        checked = _check(**over)
        assert (_v(checked, line).verdict, _v(checked, line).reason) == (C.DROPPED, C.WRONG_NUMBER), line
