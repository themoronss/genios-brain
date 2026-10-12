"""STEP-13 · a misshapen move field drops its line, not the review (`06` D59; crosscheck X15).

    .venv/bin/python -m pytest -q tests/reason/expert/test_a_misshapen_move_field_drops_its_line.py

Tree `yc2_w27_s13` M35.C1.L-contract.V0.U04 (`contracts/expert_review.validate`, `reason/expert/verify`). The
review run refuses WHOLE only what `verify.STRUCTURAL` names — and STEP-13's contract put two optional
slips there: a `rests_on` holding one ref that is no fact of the review beside the facts it does name, and
an `answers` that is no `loop:` id. Either sent the file back to the per-situation path over one optional
field, while an `answers` naming an UNPRINTED ask already lost only its line. Now each is that line's
verdict: the stray ref is dropped and the move stands on the facts it names; a non-ask `answers` is
dropped `unknown_evidence`, as an unshown ask is. A move resting on NO fact of the review is still refused
whole (§8.4.1: a move with no ground is no move).
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import UNGROUNDED_MOVE, UNKNOWN_EVIDENCE, validate
from genios_engine.reason.expert.verify import STRUCTURAL, check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit


def _structure(review, dossier) -> list[tuple[str, str]]:
    """What the review run refuses whole (`reason/expert/review._parse`)."""
    return [(kind, detail) for kind, detail in validate(review, dossier.catalogue).problems
            if kind in STRUCTURAL]


def _verdict(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


@pytest.mark.parametrize("stray", [W.ASK, "fact:9", "inference:1", "evt_x"])
def test_a_stray_ref_beside_the_facts_a_move_names_drops_alone(stray):
    """`rests_on: ["fact:1", "fact:2", "evt_x"]` — X15's own counter-example — is no structural slip: the
    move stands on facts 1 and 2, and the stray ref is the line that drops."""
    dossier, people = W.world()
    review = W.review(move={"rests_on": ["fact:1", "fact:2", stray]})
    assert _structure(review, dossier) == [], "never refused whole"
    assert (UNKNOWN_EVIDENCE, f"the next move rests on {stray}, no fact of the review") in \
        validate(review, dossier.catalogue).problems, "validate still names it"
    checked = check_review(review, dossier.text, people)
    assert checked.fate == C.SHOWN and checked.words.headline == W.ANSWER["next_move"]["what"]
    assert _verdict(checked, "rests_on") == C.LineVerdict("rests_on", C.DROPPED, C.UNKNOWN_EVIDENCE, stray)
    assert checked.stands("fact:1") and checked.stands("fact:2")
    assert checked.words.evidence == (W.ASK, W.ASK_DECK), "the move rests on the facts it named, only"


def test_a_stray_ref_does_not_make_every_fact_decisive():
    """The valid refs still say which facts the move rests on: fact 4 (the introduction's mail) needs no
    quote, as it needs none when `rests_on` is clean."""
    dossier, people = W.world()
    checked = check_review(W.review(move={"rests_on": ["fact:1", "evt_x"]}), dossier.text, people)
    assert _verdict(checked, "fact:4").verdict == C.KEPT
    assert checked.words.evidence == (W.ASK,)


def test_a_clean_rests_on_has_no_such_line():
    dossier, people = W.world()
    checked = check_review(W.review(), dossier.text, people)
    assert not any(v.line == "rests_on" for v in checked.verdicts)


def test_every_fact_of_the_review_may_be_named_the_last_one_too():
    dossier, people = W.world()
    review = W.review(move={"rests_on": ["fact:1", "fact:4"]})
    assert validate(review, dossier.catalogue).ok
    assert not any(v.line == "rests_on" for v in check_review(review, dossier.text, people).verdicts)


@pytest.mark.parametrize("rests_on", [["evt_x"], ["fact:9"], ["inference:1", "fact:0"]])
def test_a_move_resting_on_no_fact_of_the_review_is_still_refused_whole(rests_on):
    dossier, _ = W.world()
    review = W.review(move={"rests_on": rests_on})
    assert {kind for kind, _ in _structure(review, dossier)} == {UNGROUNDED_MOVE}


@pytest.mark.parametrize("answers", [W.ASK, "promise:p1", "sit:sit_marco", "num:days_quiet"])
def test_an_answers_that_is_no_ask_drops_its_line_and_the_move_stands(answers):
    """X15's second slip: a mail, a promise, a situation or a calculator is no ask. As an `answers`
    naming an ask the dossier never printed, the line drops `unknown_evidence` — the move stands."""
    dossier, people = W.world()
    review = W.review(move={"answers": answers})
    assert _structure(review, dossier) == [], "never refused whole"
    assert (UNKNOWN_EVIDENCE, f"the next move answers {answers}, no ask") in \
        validate(review, dossier.catalogue).problems
    checked = check_review(review, dossier.text, people)
    assert _verdict(checked, "answers") == C.LineVerdict("answers", C.DROPPED, C.UNKNOWN_EVIDENCE, answers)
    assert checked.fate == C.SHOWN and checked.words.headline and checked.words.draft


def test_an_ask_the_dossier_printed_is_still_read():
    dossier, people = W.world()
    checked = check_review(W.review(), dossier.text, people)
    assert _verdict(checked, "answers").verdict == C.KEPT
    assert _structure(W.review(), dossier) == [] and validate(W.review(), dossier.catalogue).ok
