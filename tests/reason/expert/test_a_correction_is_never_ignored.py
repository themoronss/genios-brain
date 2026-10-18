"""STEP-16 · never silently — a move made over your correction, or in the words of a card you called wrong, is ONE question.

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_correction_is_never_ignored.py

Tree `yc2_w27_s16` M46.C4.L-logic.V3.U06 (`reason/expert/verify`; STEP-16 §8.4 item 5). The expert follows your
correction, or says — citing it — why the file now outweighs it. A move (act or find out) over a correction the
dossier showed that no fact, inference or pattern cites is HELD: the file asks "You said “…” on <date>; does it still
hold?". So is a move in the words of a card you called wrong that cites neither the card nor your verdict. A review
with no move notes an uncited correction. A move already held keeps its own one question. Pure, on the dossier the
expert is really shown (`tests/reason/expert/check_world`).
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from genios_engine.context.file_judgments import PriorCard, Verdict
from genios_engine.context.founder_corrections import Correction
from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import verify as V
from tests.reason.expert import check_world as W

SAID_AT = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
WORDS = "Marco asked for news only on real milestones — don't push him."
MOVE = "Send Marco the short deck and offer two times for a call"


def _correction(n: int = 1, *, words: str = WORDS, scope: str = "file", at: datetime = SAID_AT) -> Correction:
    return Correction(correction_id=f"fc_{n:024d}", file_id=W.FILE, card_id=None, feedback_id=None, reason=None,
                      words=words, scope=scope, kind="investor" if scope == "kind" else None, brief_line_id=None,
                      corrected_by="user_arjun", corrected_at=at, state="standing")


def _ref(n: int = 1) -> str:
    return f"corr:fc_{n:024d}"


def _world(*, corrections=(), wrong_headline: str | None = None, **kw):
    parts = W.parts(**kw)
    if wrong_headline is not None:
        card = PriorCard(card_id="card_wrong", subject_node_id=W.FILE, headline=wrong_headline, level="prescriptive",
                         state="acted", created_at=SAID_AT, resolved_at=None, events=(),
                         verdicts=(Verdict(cause="wrong", reason="bad_timing", at=SAID_AT),))
        parts = dataclasses.replace(parts, judgments=dataclasses.replace(parts.judgments, cards=(card,)))
    parts = dataclasses.replace(parts, corrections=tuple(corrections))
    return D.build_dossier(parts), D.people_of(parts, us=W.US, our_names=W.OUR_NAMES)


def _check(review: ExpertReview, dossier, people) -> C.CheckedReview:
    return V.check_review(review, dossier.text, people, evidence_ids=dossier.catalogue.evidence_ids)


def _citing(*refs: str, **over) -> ExpertReview:
    raw = W.answer(**over)
    raw["inferences"] = [*raw["inferences"], {"claim": "the founder's correction still holds for this file",
                                               "based_on": list(refs)}]
    return ExpertReview.from_mapping(raw)


def test_a_faithful_review_with_no_correction_is_shown_as_before():
    dossier, people = _world()
    checked = _check(W.review(), dossier, people)
    assert checked.fate == C.SHOWN and not any(v.line in ("correction", "called_wrong") for v in checked.verdicts)


def test_a_move_over_a_correction_it_does_not_cite_is_one_question_naming_it():
    dossier, people = _world(corrections=(_correction(),))
    checked = _check(W.review(), dossier, people)
    assert checked.fate == C.HELD
    assert checked.question == f"You said “{WORDS}” on 18 Aug; does it still hold?"
    assert checked.because == C.HELD_BECAUSE[C.CORRECTION_UNHEEDED]
    [verdict] = [v for v in checked.verdicts if v.line == "correction"]
    assert (verdict.verdict, verdict.reason, verdict.detail) == (C.DROPPED, C.CORRECTION_UNHEEDED, _ref())
    assert checked.words.headline is None, "nothing of the move reaches a card"


@pytest.mark.parametrize("scope", ["file", "kind"])
def test_a_review_that_cites_your_correction_is_shown(scope):
    dossier, people = _world(corrections=(_correction(scope=scope),))
    checked = _check(_citing(_ref()), dossier, people)
    assert checked.fate == C.SHOWN, checked.verdicts
    assert not any(v.line == "correction" for v in checked.verdicts)


def test_a_pattern_citing_it_counts_as_citing_it():
    dossier, people = _world(corrections=(_correction(),))
    raw = W.answer()
    raw["patterns"] = [*raw["patterns"], {"kind": "pattern", "claim": "he wants milestones only",
                                           "based_on": [_ref()]}]
    assert _check(ExpertReview.from_mapping(raw), dossier, people).fate == C.SHOWN


def test_the_newest_correction_it_does_not_cite_is_the_one_asked():
    older = _correction(1, words="Marco prefers mail to calls.", at=SAID_AT.replace(day=10))
    newer = _correction(2, at=SAID_AT)
    dossier, people = _world(corrections=(newer, older))
    checked = _check(W.review(), dossier, people)
    assert checked.question == f"You said “{WORDS}” on 18 Aug; does it still hold?"
    [verdict] = [v for v in checked.verdicts if v.line == "correction"]
    assert verdict.detail == f"{_ref(2)}, {_ref(1)}"
    asked_older = _check(_citing(_ref(2)), dossier, people)
    assert asked_older.question == "You said “Marco prefers mail to calls.” on 10 Aug; does it still hold?"


def test_a_review_with_no_move_notes_the_correction_it_does_not_cite():
    dossier, people = _world(corrections=(_correction(),))
    checked = _check(W.review(mode="wait", move=False), dossier, people)
    assert checked.fate == C.SHOWN
    [note] = [v for v in checked.verdicts if v.line == "correction"]
    assert (note.verdict, note.reason) == (C.NOTED, C.UNCITED_CORRECTION)


def test_a_move_already_held_keeps_its_own_question_and_the_verdict_is_written():
    dossier, people = _world(corrections=(_correction(),))
    held = W.review(fact1={"quote": "a quote Marco never wrote"})
    checked = _check(held, dossier, people)
    assert checked.fate == C.HELD and "does it still hold" not in (checked.question or "")
    assert any(v.line == "correction" and v.reason == C.CORRECTION_UNHEEDED for v in checked.verdicts)


def test_a_move_in_the_words_of_a_card_you_called_wrong_is_one_question():
    dossier, people = _world(wrong_headline="Send Marco the short deck and two times for a call")
    checked = _check(W.review(), dossier, people)
    assert checked.fate == C.HELD
    assert checked.question == ("You called “Send Marco the short deck and two times for a call” wrong; "
                                "should we advise it again?")
    [verdict] = [v for v in checked.verdicts if v.line == "called_wrong"]
    assert (verdict.verdict, verdict.reason, verdict.detail) == (C.DROPPED, C.CALLED_WRONG, "card:card_wrong")


def test_citing_the_card_you_called_wrong_lets_the_move_stand():
    dossier, people = _world(wrong_headline="Send Marco the short deck and two times for a call")
    assert _check(_citing("card:card_wrong"), dossier, people).fate == C.SHOWN


def test_a_move_in_other_words_is_no_repeat():
    dossier, people = _world(wrong_headline="Ask Introly to chase Altavia's partners")
    assert _check(W.review(), dossier, people).fate == C.SHOWN


@pytest.mark.parametrize("move, card, repeats", [
    (MOVE, "Send Marco the short deck and two times for a call", True),
    (MOVE, "Send Marco the deck", True),
    ("Send the short deck to Marco now", "Send Marco the deck", True),
    (MOVE, "Ask Introly to chase Altavia's partners", False),
    (MOVE, "Send", False),                                   # one content word is no headline to repeat
    ("Send Marco a note", "Send Marco the deck today", False),   # two of four content words
    (None, "Send Marco the deck", False),
])
def test_what_repeating_a_card_means(move, card, repeats):
    assert V.repeats(move, card) is repeats


def test_the_people_carry_what_the_dossier_showed():
    """The check reads exactly what the dossier printed: the corrections' ids and words, the day you said them, and
    the cards of the file you called wrong — never a card you only snoozed."""
    dossier, people = _world(corrections=(_correction(),), wrong_headline="Send Marco the deck")
    assert people.corrections == (D.CorrectionSeen(ref=_ref(), words=WORDS, said_on="18 Aug", scope="file"),)
    assert people.called_wrong == (D.CalledWrong(ref="card:card_wrong", headline="Send Marco the deck"),)
    assert _ref() in dossier.catalogue.evidence_ids and "card:card_wrong" in dossier.catalogue.evidence_ids
