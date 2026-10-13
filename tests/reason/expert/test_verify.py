"""STEP-13 · the checked review — what the founder may be shown of one expert review, and what it asks.

    .venv/bin/python -m pytest -q tests/reason/expert/test_verify.py

The file STEP-13 §6 names. Tree `yc2_w27_s13` M35.C2.L-logic.V2.U05 (`reason/expert/verify.check_review`): the
checks in one order — claims, numbers, people — and the move's FATE. No fact stands: refused. A moving review
whose move lost a fact it rests on, or whose own words or recipient failed: held — the file goes to
Investigation and asks ONE question. Otherwise shown, a find-out review asking its own move. What a dropped
fact cited is never counted. §6's mutations, each caught by its own rule: an uncited fact is dropped, a
wrong number is corrected, a connector target is refused (the answered ask is `answered.py`'s, read live).
"""
from __future__ import annotations

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert.verify import STRUCTURAL, check_review
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit


def _check(world_kw=None, **over) -> C.CheckedReview:
    dossier, people = W.world(**(world_kw or {}))
    return check_review(W.review(**over), dossier.text, people)


def _verdict_of(checked: C.CheckedReview, line: str) -> C.LineVerdict:
    return next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)


def test_the_faithful_review_is_shown_in_its_own_words():
    checked = _check()
    assert checked.fate == C.SHOWN and checked.question is None and checked.because is None
    assert checked.words == C.CardWords(
        headline=W.ANSWER["next_move"]["what"], situation=W.ANSWER["frames"]["primary"],
        done_when=W.ANSWER["done_when"], draft=W.ANSWER["draft"], to="Marco",
        evidence=(W.ASK, W.ASK_DECK), quotes=(W.ANSWER["facts"][0]["quote"],),
        do_nothing=W.ANSWER["scenarios"]["do_nothing"]), \
        "the headline carries the mails and asks its move rests on, and their quotes"
    assert checked.cited == tuple(sorted({W.ASK, W.ASK_DECK, W.REPLY_TIME, W.INTRO}))
    assert all(v.verdict == C.KEPT for v in checked.verdicts), checked.verdicts


def test_a_move_whose_ground_fell_is_held_and_asks_about_it():
    checked = _check(fact1={"quote": "could you send your financials before we set up a call"})
    assert checked.fate == C.HELD
    # ⛔ RESTATED by M35.C3.L-integration.V2.U05 (crosscheck X10): the held `because` is a closed phrase the
    # founder reads on the question card — the model's quote stays in the verdict, never on the card.
    assert checked.because == C.HELD_BECAUSE[C.MISQUOTED]
    assert _verdict_of(checked, "fact:1").detail == "could you send your financials before we set up a call"
    # ⛔ RESTATED by M36.C2.L-logic.V2.U10 (fix, the second crosscheck G2, `03` X10): the question asked
    # "Is it so: “<the fell fact's claim>”? It is not in what it cites." — the words the check dropped, on the
    # question card. It asks what the next step is, and says truly why the one found is held.
    assert checked.question == ("What is the next step with Marco Ruiz? We held the one we found: "
                                f"{C.HELD_BECAUSE[C.MISQUOTED]}.")
    assert "short deck" not in checked.question
    assert checked.words.headline is None and checked.words.draft is None and checked.words.to is None
    assert checked.words.situation, "why it matters is still the expert's reading"
    assert W.ASK not in checked.cited, "a dropped fact's mail is not counted"


def test_a_fact_the_move_does_not_rest_on_falls_alone():
    checked = _check(fact4={"claim": "Introly introduced Marco on 9 March"})
    assert checked.fate == C.SHOWN and not checked.stands("fact:4")
    assert W.INTRO not in checked.cited and W.ASK in checked.cited


def test_a_find_out_review_is_shown_asking_its_own_move():
    move = {"what": "Find out whether Marco wants the deck or a call first", "to": None}
    checked = _check(mode="find_out", move=move, draft=None)
    assert checked.fate == C.SHOWN and checked.question == move["what"]
    assert checked.words.headline == move["what"]


def test_a_find_out_review_whose_ground_fell_asks_about_the_fact_instead():
    checked = _check(mode="find_out", move={"what": "Find out whether Marco wants the deck first"},
                     draft=None, fact1={"quote": None})
    # ⛔ RESTATED by M36.C2.L-logic.V2.U10 (fix, G2): asked about the next step, never in the fell claim's words.
    assert checked.fate == C.HELD and checked.question.startswith("What is the next step with Marco Ruiz?")
    assert "Marco asked" not in checked.question


@pytest.mark.parametrize("mode", ["wait", "nothing", "blocked"])
def test_a_review_that_moves_nothing_is_never_held(mode):
    checked = _check(mode=mode, move=False, draft=None, fact1={"quote": None})
    assert checked.fate == C.SHOWN and checked.question is None
    assert checked.stands("fact:1"), "no move rests on any fact, so none needs a quote"
    assert checked.words.headline == W.ANSWER["frames"]["primary"], "no move: the reading is the headline"


def test_a_review_none_of_whose_facts_stands_is_refused():
    facts = [{"claim": "Neel asked for a deck", "evidence": [W.ASK], "quote": "send a short deck"},
             {"claim": "it waits", "evidence": ["loop:never_shown"]}]
    checked = _check(facts=facts, move={"rests_on": ["fact:1"]}, inferences=[], patterns=[])
    assert checked.fate == C.REFUSED and checked.because == C.NOTHING_STANDS and checked.cited == ()
    assert checked.words == C.CardWords(None, None, None, None, None)
    assert checked.reasons == (C.UNKNOWN_EVIDENCE, C.UNSUPPORTED)


@pytest.mark.parametrize("over, line, verdict, reason", [
    ({"fact2": {"evidence": []}}, "fact:2", C.DROPPED, C.UNCITED),                    # an uncited fact
    ({"fact3": {"claim": "Marco answered our first mail in 9 days"}}, "fact:3", C.CORRECTED,
     C.BY_CALCULATOR),                                                                  # a wrong number
    ({"move": {"to": "Introly"}}, "to", C.DROPPED, C.RECIPIENT_IS_CONNECTOR),          # a connector target
])
def test_step_13s_mutations_are_each_caught_by_their_own_rule(over, line, verdict, reason):
    checked = _check(**over)
    found = next(v for v in checked.verdicts if v.line == line and v.verdict != C.NOTED)
    assert (found.verdict, found.reason) == (verdict, reason)
    clean = next(v for v in _check().verdicts if v.line == line and v.verdict != C.NOTED)
    assert clean.verdict == C.KEPT, "the faithful review keeps the same line"


def test_the_same_review_and_dossier_are_the_same_check_and_it_reads_back_as_stored():
    one, two = _check(fact3={"claim": "Marco answered in 9 days"}), _check(fact3={"claim": "Marco answered in 9 days"})
    assert one == two
    assert C.CheckedReview.from_mapping(one.as_mapping()) == one


def test_only_the_reviews_structure_is_refused_whole_by_the_contract():
    from genios_engine.contracts.expert_review import (NO_NEXT_MOVE, UNGROUNDED_MOVE, UNKNOWN_STAGE)
    assert STRUCTURAL == {NO_NEXT_MOVE, UNGROUNDED_MOVE, UNKNOWN_STAGE}
