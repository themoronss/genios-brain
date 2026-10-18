"""STEP-14 fix · the same move in other words is one ask — a quiet rewording, never pushed (s14-D1, golden F25).

    .venv/bin/python -m pytest -q tests/contracts/test_a_rewording_of_a_move_is_quiet.py

Tree `yc2_w27_s14` M42.C3.L-integration.V2.U07 (fix of M42.C3.L-integration.V2.U03 `_decision_words`; the STEP-14
crosscheck, finding 7). A review that names no `answers` gave its move the ask "move:<its own words>", so ANY rewording
of the move was another ask — material, pushed. F25 ("the same advice in other words") was `updated` and pushed
twice; across 64 cases 0 versions were `reworded`; with a live model the wording changes on every review, so every
re-review would push. 42 of the 82 recorded moves name `answers`; the other 40 had no way to be quiet.

Now two moves that name no ask are ONE ask when they go to the same recipient, by the same date, in the same lane and
mode, and the shorter's content words are mostly the other's (`card_version.one_ask`: at least `ONE_ASK_SHARE` of its
stems). The bound, declared: a move rewritten past that share is another ask (pushed) — on the golden set's authored
pairs F25 holds 0.89 and F21 0.88; F24's two moves (the deck, then the unit-economics sheet) 0.73, another ask.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import card_version as cv
from genios_engine.contracts.card_version import VersionWords, version_of

pytestmark = pytest.mark.unit

F25_BEFORE = ("Ask the board to approve the ESOP pool now, and have the engagement documents ready to send Kavitha "
              "the day it does.")
F25_AFTER = ("Get the board's approval of the ESOP pool now, and send Kavitha the engagement documents the day it is "
             "given — in time for her to read them before the twelfth.")
F24_BEFORE = "Upload the Phase-1 review deck to the cohort folder by the twelfth, as the programme asked"
F24_AFTER = "Finish the unit economics sheet and upload it to the cohort folder before the review"


def _move(what: str, **over) -> VersionWords:
    return VersionWords(**{"headline": what[:60], "situation": "A board and a hire", "move": what, "lane": "decision",
                           "mode": "act", "ask": "move:" + " ".join(what.lower().split()), **over})


def test_f25_the_same_move_in_other_words_is_a_quiet_rewording():
    v = version_of(_move(F25_BEFORE), _move(F25_AFTER), version=2, signal_id="sig_2")
    assert (v.change, v.material) == ("reworded", False), v
    assert "ask" not in v.changed and v.words.ask == _move(F25_BEFORE).ask, "the ask is the one it answered before"


@pytest.mark.parametrize("before, after", [
    (F24_BEFORE, F24_AFTER),                                                     # another piece of work
    ("Send Arjun the deck and the quarter's metrics", "Ask Arjun when the partner meeting is"),
])
def test_another_move_is_another_ask(before, after):
    v = version_of(_move(before), _move(after), version=2, signal_id="sig_2")
    assert (v.change, v.material, "ask" in v.changed) == ("updated", True, True), v


@pytest.mark.parametrize("field, value", [("recipient", "kavitha@x.test"), ("by_when", "2026-10-12"),
                                          ("lane", "investigation"), ("mode", "wait")])
def test_the_same_words_to_another_end_are_material(field, value):
    v = version_of(_move(F25_BEFORE), _move(F25_AFTER, **{field: value}), version=2, signal_id="sig_2")
    assert v.material and v.change == "updated", v
    assert not cv.one_ask(_move(F25_BEFORE), _move(F25_AFTER, **{field: value})), "another end is no rewording"


def test_an_ask_the_review_names_is_compared_as_named():
    """⛔ THE NEGATIVE CONTROL: a move naming the ask it answers is told by that ask — the words never decide."""
    named = version_of(_move(F25_BEFORE, ask="loop:esop"), _move(F25_AFTER, ask="loop:hire"), version=2,
                       signal_id="sig_2")
    assert (named.change, named.material) == ("updated", True)
    assert not cv.one_ask(_move(F25_BEFORE, ask="loop:esop"), _move(F25_AFTER, ask="loop:hire"))
    assert not cv.one_ask(_move(F25_BEFORE, ask="loop:esop"), _move(F25_AFTER)), "one named, one not: not compared"
    assert not cv.one_ask(_move(F25_BEFORE), _move(F25_AFTER, ask="loop:esop"))


def test_the_share_is_measured_on_content_words():
    assert cv.ONE_ASK_SHARE == 0.8
    assert cv.one_ask(_move(F25_BEFORE), _move(F25_AFTER)) and not cv.one_ask(_move(F24_BEFORE), _move(F24_AFTER))


def test_a_rewording_read_back_is_still_one():
    v = version_of(_move(F25_BEFORE), _move(F25_AFTER), version=2, signal_id="sig_2")
    assert cv.CardVersion.from_mapping(v.as_mapping()) == v
