"""STEP-13 · what the check found is written down in closed words, and reads back as it was stored.

    .venv/bin/python -m pytest -q tests/reason/expert/test_the_claim_check_contract.py

Tree `yc2_w27_s13` M35.C1.L-contract.V0.U02 (`contracts/claim_check.py`). A verdict per line — kept,
corrected by one named means, dropped for one closed reason, or noted — and the checked review: the move's
fate, the one question a held file asks, the card's words once checked, the ids its standing facts cite.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from genios_engine.contracts import claim_check as C

pytestmark = pytest.mark.unit

WORDS = C.CardWords(headline="Send Neel the one-page pre-read", situation="A first call with a fund",
                    done_when="Neel has the pre-read before the call", draft="Hi Neel, …", to="Neel",
                    evidence=("evt_a", "loop:l1", "evt_a"), quotes=("could we talk", ""))


def _checked(**over) -> C.CheckedReview:
    base = dict(verdicts=(C.LineVerdict("fact:1", C.KEPT),
                          C.LineVerdict("fact:2", C.DROPPED, C.MISQUOTED, "quote: send the deck"),
                          C.LineVerdict("move", C.CORRECTED, C.BY_CALCULATOR, "number:52 -> 48 (num:gap)"),
                          C.LineVerdict("situation", C.NOTED, C.SPEAKS_OF_YOU, "the founder")),
                fate=C.SHOWN, words=WORDS, cited=("evt_b", "evt_a", "evt_a"))
    base.update(over)
    return C.CheckedReview(**base)


def test_a_checked_review_keeps_a_verdict_per_line_and_what_stands():
    checked = _checked()
    assert checked.cited == ("evt_a", "evt_b"), "sorted, once each"
    assert checked.stands("fact:1") and not checked.stands("fact:2") and checked.stands("move")
    assert [v.line for v in checked.dropped] == ["fact:2"]
    assert checked.reasons == (C.MISQUOTED,)
    assert checked.version == C.CHECK_VERSION


def test_a_checked_review_round_trips_as_stored():
    for checked in (_checked(),
                    _checked(fate=C.HELD, question="Did Neel ask for the deck?", because="misquoted: fact 2",
                             words=C.CardWords(None, "A first call with a fund", None, None, None)),
                    _checked(fate=C.REFUSED, because="nothing_stands", cited=(),
                             verdicts=(C.LineVerdict("fact:1", C.DROPPED, C.UNCITED),))):
        again = C.CheckedReview.from_mapping(checked.as_mapping())
        assert again == checked and again.as_mapping() == checked.as_mapping()


@pytest.mark.parametrize("line, verdict, reason", [
    ("fact:1", "kept", "misquoted"),           # a kept line has no reason
    ("fact:1", "dropped", None),               # a dropped line always has one
    ("fact:1", "dropped", "rude"),             # a reason outside the closed list
    ("fact:1", "corrected", "misquoted"),      # a correction names HOW, not why
    ("fact:1", "noted", "misquoted"),          # a note is a note
    ("fact:1", "fixed", None),                 # a verdict outside the closed list
    ("fact:0", "kept", None),                  # facts count from one
    ("fact", "kept", None),
    ("claim:1", "kept", None),
    ("headline", "kept", None),                # the card's line is the MOVE
])
def test_a_verdict_is_closed_and_names_a_real_line(line, verdict, reason):
    with pytest.raises(ValueError):
        C.LineVerdict(line, verdict, reason)


@pytest.mark.parametrize("over, says", [
    ({"fate": "maybe"}, "fate"),
    ({"fate": C.HELD, "because": "misquoted"}, "asks its question"),
    ({"fate": C.HELD, "question": "Did Neel ask?"}, "says why"),
    ({"fate": C.SUPPRESSED}, "says why"),
    ({"fate": C.REFUSED, "because": "nothing_stands"}, "no standing fact"),
    ({"verdicts": (C.LineVerdict("fact:1", C.KEPT), C.LineVerdict("fact:1", C.DROPPED, C.UNCITED))},
     "one verdict"),
    ({"verdicts": (C.LineVerdict("move", C.NOTED, C.SPEAKS_OF_YOU),
                   C.LineVerdict("move", C.NOTED, C.SPEAKS_OF_YOU))}, "one verdict"),
])
def test_a_fate_that_is_not_shown_says_why_and_a_held_one_asks(over, says):
    with pytest.raises(ValueError, match=says):
        _checked(**over)


def test_a_line_carries_its_verdict_and_its_notes_beside_it():
    checked = _checked(verdicts=(C.LineVerdict("situation", C.KEPT),
                                 C.LineVerdict("situation", C.NOTED, C.SPEAKS_OF_YOU, "the founder"),
                                 C.LineVerdict("prose", C.NOTED, C.UNHELD_NUMBER, "number:3")))
    assert checked.stands("situation") and checked.notes == (C.SPEAKS_OF_YOU, C.UNHELD_NUMBER)
    assert checked.reasons == ()


def test_the_reasons_dropped_are_counted_once_each_in_one_order():
    """What a health check counts: each reason once, in one order whatever order the lines dropped in."""
    reasons = (C.UNSUPPORTED, C.MISQUOTED, C.WRONG_NUMBER, C.UNCITED, C.UNKNOWN_EVIDENCE, C.UNQUOTED)
    verdicts = tuple(C.LineVerdict(f"fact:{n}", C.DROPPED, reason) for n, reason in enumerate(reasons, 1))
    checked = _checked(verdicts=verdicts + (C.LineVerdict("fact:9", C.DROPPED, C.UNSUPPORTED),))
    assert checked.reasons == tuple(sorted(set(reasons)))


def test_every_reason_note_and_fate_is_spelled_once():
    for vocabulary in (C.REASONS, C.NOTES, C.CORRECTIONS, C.FATES, C.VERDICTS):
        assert len(vocabulary) == len(set(vocabulary))
    assert not set(C.REASONS) & set(C.NOTES) and not set(C.REASONS) & set(C.CORRECTIONS)


def test_the_headline_says_where_it_came_from_once_each():
    assert WORDS.evidence == ("evt_a", "loop:l1") and WORDS.quotes == ("could we talk",)
    assert C.CardWords.from_mapping(WORDS.as_mapping()) == WORDS


def test_card_words_withheld_read_back_as_withheld():
    words = C.CardWords(headline="Send Neel the pre-read", situation=None, done_when="", draft=None,
                        to=None)
    assert C.CardWords.from_mapping(words.as_mapping()) == C.CardWords(
        "Send Neel the pre-read", None, None, None, None)


def test_a_checked_review_is_frozen():
    with pytest.raises(FrozenInstanceError):
        _checked().fate = C.HELD                                   # type: ignore[misc]


def test_a_stored_check_that_is_not_an_object_is_a_value_error():
    with pytest.raises(ValueError, match="an object"):
        C.CheckedReview.from_mapping(["shown"])
