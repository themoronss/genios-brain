"""STEP-13 §3.1 · every claim has a source — a fact stands on its own lines, and a decisive one quotes its mail.

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify_claims.py

Tree `yc2_w27_s13` M35.C2.L-logic.V1.U02 (`reason/expert/verify`). A fact cites at least one id, every id it
cites was printed; a fact the move rests on that cites a mail whose words the dossier shows QUOTES them,
and they are there; every name it writes is on its lines (the card validator's own rule). A fact that
fails drops — the review stays (`06` D59). An inference or a pattern stands while one of its grounds
stands. On a real dossier (`check_world`); each rule shown failing on its own mutation.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import check_review, quoted_in
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit


def _check(ask_words: str | None = None, **over) -> C.CheckedReview:
    dossier, people = W.world(**({"ask_words": ask_words} if ask_words else {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


def test_the_faithful_review_stands_whole():
    checked = _check()
    assert checked.dropped == () and checked.fate == C.SHOWN, checked.verdicts
    assert [_verdict(checked, f"fact:{n}").verdict for n in (1, 2, 3, 4)] == [C.KEPT] * 4
    assert _verdict(checked, "inference:1").verdict == _verdict(checked, "pattern:1").verdict == C.KEPT


@pytest.mark.parametrize("fact, reason", [
    ({"evidence": []}, C.UNCITED),
    ({"evidence": ["evt_never_shown"]}, C.UNKNOWN_EVIDENCE),
    ({"evidence": [W.ASK, "evt_never_shown"]}, C.UNKNOWN_EVIDENCE),
    ({"quote": None}, C.UNQUOTED),
    ({"quote": "could you send your financials before we set up a call"}, C.MISQUOTED),
    ({"quote": "deck"}, C.MISQUOTED),                                # one word is no quote
    ({"claim": "Neel asked for a short deck before setting up a call"}, C.UNSUPPORTED),
])
def test_a_decisive_fact_that_fails_drops_and_names_why(fact, reason):
    checked = _check(fact1=fact)
    assert _verdict(checked, "fact:1") == C.LineVerdict(
        "fact:1", C.DROPPED, reason, _verdict(checked, "fact:1").detail)
    assert not checked.stands("fact:1") and checked.stands("fact:2")


def test_a_fact_the_move_does_not_rest_on_needs_no_quote():
    """Fact 4 cites the introduction's words and the move does not rest on it: no quote is asked."""
    checked = _check(fact4={"quote": None})
    assert _verdict(checked, "fact:4").verdict == C.KEPT
    assert _verdict(_check(fact4={"quote": "meet Marco Ruiz"}), "fact:4").verdict == C.KEPT


def test_a_move_that_names_nothing_rests_on_every_fact():
    """A first-version answer names no `rests_on`: every fact is decisive, so each mail it cites is quoted."""
    checked = _check(move={"rests_on": []})
    assert _verdict(checked, "fact:4") == C.LineVerdict("fact:4", C.DROPPED, C.UNQUOTED)


def test_a_fact_on_a_reading_needs_no_quote_and_is_held_to_its_line():
    """Only a mail's words can be quoted: a decisive fact on a reading — the ask's loop, a calculator —
    needs none, and is held to the line that prints it."""
    checked = _check(move={"rests_on": ["fact:2", "fact:3"]})
    assert _verdict(checked, "fact:2").verdict == _verdict(checked, "fact:3").verdict == C.KEPT


def test_a_name_on_another_line_does_not_ground_a_fact():
    """'Partners' is in the introduction's words, not on the line fact 3 cites, nor in the file's head —
    and citing the introduction too grounds it."""
    claim = "Marco of Altavia Partners answered in 6 days"
    checked = _check(fact3={"claim": claim})
    assert _verdict(checked, "fact:3") == C.LineVerdict("fact:3", C.DROPPED, C.UNSUPPORTED, "name:Partners")
    both = _check(fact3={"claim": claim, "evidence": [W.REPLY_TIME, W.INTRO]})
    assert _verdict(both, "fact:3").verdict == C.KEPT


def test_the_files_own_people_ground_a_fact_on_any_of_its_lines():
    """An ask's line prints whose turn it is, not who asked; the file's head and its people name him —
    and a name the file does not show at all is still refused."""
    checked = _check(fact2={"claim": "Marco Ruiz's ask for the deck waits on us"})
    assert _verdict(checked, "fact:2").verdict == C.KEPT
    assert _verdict(_check(fact2={"claim": "Neel's ask for the deck waits on us"}), "fact:2").reason \
        == C.UNSUPPORTED


def test_our_own_names_ground_a_fact():
    checked = _check(fact2={"claim": "His ask for the deck waits on Nimbus Labs"})
    assert _verdict(checked, "fact:2").verdict == C.KEPT


def test_a_dated_claim_is_grounded_by_the_date_its_line_prints():
    """'4 Aug' restates the touch's 2026-08-04: the date's own forms are grounded, a wrong month is not."""
    assert _verdict(_check(), "fact:4").verdict == C.KEPT
    assert _verdict(_check(fact4={"claim": "Introly introduced Marco on 4 March"}), "fact:4").reason \
        == C.UNSUPPORTED


@pytest.mark.parametrize("claim, kept", [
    ("Marco asked for a short deck by 3 September, before setting up a call", True),  # the mail: "3 Sep"
    ("Marco asked for a short deck by 3 Sep, before setting up a call", True),
    ("Marco asked for a short deck by 3 October, before setting up a call", False),   # no line says Oct
])
def test_a_month_written_out_is_grounded_by_its_short_form(claim, kept):
    """A month written out is the month its lines write short (F51: the mail's "4 Aug", the claim's
    "August") — here a month no date on the line expands to (the mail is of 11 Aug); a month no line
    writes is still a name nobody wrote."""
    # ⛔ RESTATED by M35.C2.L-logic.V1.U09: a decisive fact's numbers come from its QUOTE (the mail's head and
    # its calculators aside), so the quote carries the "3 Sep" the claim restates — before, the claim's 3
    # was grounded by another sentence of the mail its quote did not hold.
    checked = _check(fact1={"claim": claim, "quote": "could you send a short deck before we set up a call? "
                                                     "By 3 Sep"},
                     ask_words="Thanks Arjun — could you send a short deck before "
                     "we set up a call? By 3 Sep, ideally. I read everything within a week.")
    assert (_verdict(checked, "fact:1").verdict == C.KEPT) is kept, _verdict(checked, "fact:1")


def test_an_inference_or_pattern_whose_grounds_all_fell_drops():
    checked = _check(fact1={"quote": None})
    assert _verdict(checked, "inference:1") == C.LineVerdict("inference:1", C.DROPPED, C.UNGROUNDED, "fact:1")
    assert _verdict(checked, "pattern:1").verdict == C.KEPT, "fact 3 still stands"
    both = _check(inferences=[{"claim": "a screen", "based_on": ["fact:1", W.ASK_DECK]}], fact1={"quote": None})
    assert _verdict(both, "inference:1").verdict == C.KEPT, "one standing ground is enough"


@pytest.mark.parametrize("quote, words, held", [
    ("could you send a short deck", ["Thanks — could you send a short deck?"], True),
    ("Could you SEND a short deck!", ["thanks, could you send a short deck"], True),
    ("“could you send a short deck”", ["could you send a short   deck before"], True),
    ("send a short", ["could you send a shorter deck"], False),            # whole words only
    ("deck", ["could you send a short deck"], False),                      # one word is no quote
    ("send the financials", ["could you send a short deck"], False),
    ("could you send", [], False),
])
def test_a_quote_is_the_mails_own_words(quote, words, held):
    assert quoted_in(quote, words) is held


@pytest.mark.parametrize("claim, kept", [
    ("Nothing is owed on the deck before Marco writes again", True),
    ("Say whether Marco asked for a short deck", True),
    ("Initech asked for a short deck before setting up a call", False),     # entity-shaped: still refused
])
def test_an_ordinary_word_opening_a_sentence_is_no_invented_name(claim, kept):
    """The stop-list's own rule — a word is exempt once an observed failure earned it — read for the
    expert's texts (`verify.EARNED`): "Nothing", "Say" open sentences; "Initech" is a name nobody wrote."""
    checked = _check(fact1={"claim": claim})
    assert (_verdict(checked, "fact:1").verdict == C.KEPT) is kept, _verdict(checked, "fact:1")
