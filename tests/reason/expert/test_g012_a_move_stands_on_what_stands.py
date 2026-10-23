"""G012 F4 + P-c · the claim check refuses what is wrong, not what the dossier itself says (`reason/expert/verify`).

    .venv/bin/python -m pytest -q tests/reason/expert/test_g012_a_move_stands_on_what_stands.py

On the design partner's 21 live file judgments (23 Oct 2026) 15 moves were held, each becoming a question card.
The check held them on: a count or a connective opening a sentence read as a name (`test_verify_names`); the clock
a time is written in; the digits of an id the claim wrote bare; a sentence the dossier prints with no id to cite,
cited by its words or its section — and, whatever fell, on ONE fallen fact beside standing ones. Replayed with the
live pass's people: 5 moves shown before, 10 after. The golden set: 63 → 63.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import _invented, check_review, figures_in, statements_cited
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit


def _check(**over) -> C.CheckedReview:
    dossier, people = W.world()
    return check_review(W.review(**over), dossier.text, people)


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


# ── what the dossier itself says ───────────────────────────────────────────────────────────────────────────────

def test_the_clock_a_time_is_written_in_is_no_name():
    _dossier, people = W.world()
    assert _invented("Marco wrote at noon UTC", "Marco asked for the short deck", people) is None


def test_an_id_written_bare_is_no_number():
    assert not figures_in("The situation sit_24c2276debaf4aae93bb0c0e is dormant").values
    assert figures_in("The situation is 12 days quiet").values, "a number beside it is still read"


@pytest.mark.parametrize("cited", ["No mailbox is shown to have read this file's mail.",
                                   "No mailbox is shown to have read this file's mail"])
def test_a_sentence_the_dossier_prints_with_no_id_is_cited_by_its_own_words(cited):
    checked = _check(fact3={"claim": "No mailbox is shown to have read this file's mail", "evidence": [cited]})
    assert _verdict(checked, "fact:3").verdict == C.KEPT, _verdict(checked, "fact:3")


def test_a_section_with_no_id_is_cited_by_its_letter_or_title_and_one_with_ids_never():
    """`# C · THE HISTORY` prints no id: "C" and "THE HISTORY" are its lines. `## WHAT HAPPENED` prints mail: a
    mail is cited by its id, so the section's name grounds nothing it holds."""
    review = W.review(fact3={"claim": "No comparable past work of this kind is on record", "evidence": ["C"]},
                      fact4={"claim": "Marco asked for a short deck", "evidence": ["WHAT HAPPENED"]})
    text = ("# C · THE HISTORY — comparable past work, and how it went\n"
            "No comparable past work of this kind is on record.\n"
            "## WHAT HAPPENED\n- [evt_marco_0811] 2026-08-11 09:14 UTC · Marco Ruiz wrote\n")
    said = statements_cited(review, text, {})
    assert said["C"][0].line == "No comparable past work of this kind is on record."
    assert "WHAT HAPPENED" not in said


def test_a_cited_statement_still_holds_only_its_own_names():
    checked = _check(fact3={"claim": "Priya Nair is shown to have read this file's mail",
                            "evidence": ["No mailbox is shown to have read this file's mail."]})
    assert _verdict(checked, "fact:3").reason == C.UNSUPPORTED, _verdict(checked, "fact:3")


# ── P-c · a move stands on the facts of it that stand ──────────────────────────────────────────────────────────

def test_a_fallen_reading_beside_a_standing_mail_keeps_the_move():
    """The move rests on Marco's mail (fact 1) and his open ask (fact 2); fact 2 writes a number its line does not
    hold and falls — the move answers the mail that stands, and is shown without it."""
    checked = _check(fact2={"claim": "Marco has asked for the short deck 7 times"})
    assert _verdict(checked, "fact:2").verdict == C.DROPPED, "the premise: the reading falls"
    assert checked.fate == C.SHOWN, (checked.fate, checked.because)


def test_a_move_whose_only_mail_fell_is_held_as_before():
    checked = _check(fact1={"claim": "Priya asked for a short deck before setting up a call"})
    assert _verdict(checked, "fact:1").reason == C.UNSUPPORTED
    assert checked.fate == C.HELD, checked.fate


def test_a_move_whose_words_need_the_fallen_fact_is_held_as_before():
    """Its words are checked on the standing facts alone: a number only the fallen fact wrote holds it."""
    checked = _check(fact2={"claim": "Marco has asked for the short deck 7 times"},
                     move={"what": "Send Marco the short deck with the 7 slides he asked for"})
    assert checked.fate == C.HELD, checked.fate


def test_a_move_may_rest_on_a_statement_the_dossier_prints_and_is_never_asked_its_quote():
    """A cited statement is no mail: resting the move on it asks no quote of it (`_Run.mail`)."""
    checked = _check(fact3={"claim": "No mailbox is shown to have read this file's mail",
                            "evidence": ["No mailbox is shown to have read this file's mail."]},
                     move={"rests_on": ["fact:1", "fact:3"]})
    assert _verdict(checked, "fact:3").verdict == C.KEPT, _verdict(checked, "fact:3")


# ── H-08 · a move that names no one and nothing is no move ─────────────────────────────────────────────────────

_EMPTY_MOVE = {"to": None, "who": None, "what": None, "answers": None, "by_when": None, "for_whom": None,
               "rests_on": ["fact:1", "fact:2"]}


@pytest.mark.parametrize("mode", ["nothing", "wait"])
def test_a_review_that_does_not_move_reads_an_empty_move_as_none(mode):
    """The shape the design partner's `nothing` / `wait` answers printed (23 Oct): every field null but rests_on."""
    from genios_engine.contracts.expert_review import ExpertReview
    raw = W.answer(mode=mode)
    raw["next_move"] = dict(_EMPTY_MOVE)
    assert ExpertReview.from_mapping(raw).next_move is None


@pytest.mark.parametrize("mode", ["act", "find_out"])
def test_a_review_that_moves_still_owes_its_move(mode):
    """Unchanged for a moving review: malformed, so the one repair asks for the move."""
    from genios_engine.contracts.expert_review import ExpertReview
    raw = W.answer(mode=mode)
    raw["next_move"] = dict(_EMPTY_MOVE)
    with pytest.raises(ValueError, match="who makes the next move"):
        ExpertReview.from_mapping(raw)


def test_a_review_that_does_not_move_keeps_a_move_it_did_write():
    from genios_engine.contracts.expert_review import ExpertReview
    raw = W.answer(mode="wait")
    assert ExpertReview.from_mapping(raw).next_move is not None, "a written move is read as written"



def test_a_sample_size_a_claim_repeats_from_its_calculator_is_no_number():
    """`figures` strips "(n = 4)" from a calculator's line; a claim that repeats it is grounded on the value alone."""
    checked = _check(fact3={"claim": "Marco's reply time was 6 days (n=1)",
                            "evidence": ["num:their_reply_time:marco@altavia.test"]})
    assert _verdict(checked, "fact:3").verdict == C.KEPT, _verdict(checked, "fact:3")      # never "1 -> 6"


def test_a_count_in_a_claim_is_still_checked():
    checked = _check(fact3={"claim": "Marco replied 9 times in a week", "evidence": ["num:their_reply_time:marco@altavia.test"]})
    assert _verdict(checked, "fact:3").verdict != C.KEPT, _verdict(checked, "fact:3")      # "9" is read and checked
