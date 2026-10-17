"""STEP-13b · each sentence of an expert card says whether it came from the file, the engine or the expert's own.

    .venv/bin/python -m pytest -q tests/deliver/test_a_card_says_which_source_it_came_from.py

Tree `yc2_w27_s13b` M37.C4.L-integration.V11.U03 (`reason/expert/decide.sources_of`, read by `deliver/card_builder`).
The headline and the draft stand on the move's ground: the file's evidence (as ever), and — when the move is guided by
them — the ENGINE's lines (the capability's or playbook's name, "not yet reviewed" where true) and the expert's OWN
experience ("from experience"). No model. A decision of a review checked before this version, or one citing neither,
carries none and shows as before.
"""
from __future__ import annotations

import dataclasses

import pytest

from genios_engine.contracts import claim_check as C
from genios_engine.reason.expert import decide as D
from tests.reason.expert import check_world as W

pytestmark = pytest.mark.unit

WORDS = C.CardWords(headline="Send Marco the short deck", situation="An introduced investor asked for a deck",
                    done_when="Marco has the deck", draft="Hi Marco, the deck is attached. Arjun",
                    to="Marco", evidence=("evt_marco_0811", "loop:ask_deck"), quotes=("could you send a short deck",))
PB = C.EngineCited(ref="pb:founder_office.pb.investor.run_the_round", words="A partner meeting follows a deck.",
                   source="Run the round", reviewed=False)
RULE = C.EngineCited(ref="rule:follow_up", words="Follow up once.", source="fundraising.rules", reviewed=True)
OWN = {"kind": "practice", "claim": "a request answered the same day keeps a thread warm", "why": "attention"}


def _checked(*verdicts, engine=(), **over):
    base = dict(verdicts=verdicts, fate=C.SHOWN, words=WORDS, cited=("evt_marco_0811",), engine=engine)
    base.update(over)
    return C.CheckedReview(**base)


def _review(**move):
    return W.review(own=[OWN], move=move)


def test_a_review_citing_no_engine_and_no_own_carries_nothing_new():
    plain = D.sources_of(_checked())
    assert set(plain["headline"]) == {"evidence", "quotes"} and set(plain["draft"]) == {"to", "evidence", "quotes"}
    assert D.sources_of(_checked(), W.review()) == plain, "handing the review changes nothing without engine or own"
    assert "engine" not in plain and "own" not in plain


def test_a_checked_review_from_before_carries_none():
    old = D.sources_of(_checked(engine=()), _review(guided_by=["own:1"]))
    assert set(old["headline"]) == {"evidence", "quotes"}, "no verdict says own:1 stood: nothing is claimed of it"


def test_the_headline_and_the_draft_say_they_came_from_the_file_and_the_engine():
    review = _review(guided_by=[PB.ref])
    sources = D.sources_of(_checked(C.LineVerdict("guided_by", C.KEPT), engine=(PB, RULE)), review)
    for part in ("headline", "draft"):
        assert sources[part]["from"] == ["file", "engine"]
        assert sources[part]["engine"] == [{
            "ref": PB.ref, "said": "the engine: Run the round, not yet reviewed", "words": PB.words}]
    assert sources["headline"]["evidence"] == ["evt_marco_0811", "loop:ask_deck"]


def test_a_reviewed_engine_line_is_not_said_to_be_unreviewed():
    sources = D.sources_of(_checked(C.LineVerdict("guided_by", C.KEPT), engine=(RULE,)), _review(guided_by=[RULE.ref]))
    assert sources["headline"]["engine"][0]["said"] == "the engine: fundraising.rules"


def test_the_experts_own_experience_is_said_to_be_from_experience():
    sources = D.sources_of(_checked(C.LineVerdict("own:1", C.KEPT), C.LineVerdict("guided_by", C.KEPT)),
                           _review(guided_by=["own:1"]))
    assert sources["headline"]["from"] == ["file", "own"]
    assert sources["headline"]["own"] == [{"said": "from experience", "claim": OWN["claim"]}]


def test_a_line_that_fell_is_not_a_source():
    fell = _checked(C.LineVerdict("own:1", C.DROPPED, C.OWN_STATES_A_NUMBER, "3"),
                    C.LineVerdict("guided_by", C.DROPPED, C.UNKNOWN_EVIDENCE, "own:1"), engine=(PB,))
    assert set(D.sources_of(fell, _review(guided_by=["own:1", PB.ref]))["headline"]) == {"evidence", "quotes"}


def test_all_three_sources_together_and_a_held_file_names_none():
    sources = D.sources_of(_checked(C.LineVerdict("own:1", C.KEPT), C.LineVerdict("guided_by", C.KEPT), engine=(PB,)),
                           _review(guided_by=["own:1", PB.ref]))
    assert sources["headline"]["from"] == ["file", "engine", "own"]
    held = D.sources_of(_checked(C.LineVerdict("own:1", C.KEPT), C.LineVerdict("guided_by", C.KEPT), engine=(PB,),
                                 fate=C.HELD, because="m", question="Whom?"),
                        _review(guided_by=["own:1", PB.ref]))
    assert set(held["headline"]) == {"question", "because"}, "a held file's headline is its question"


def test_the_render_block_carries_it_and_the_card_builder_reads_it():
    from datetime import datetime, timezone
    from genios_engine.deliver import card_builder as B
    review = _review(guided_by=[PB.ref])
    checked = _checked(C.LineVerdict("guided_by", C.KEPT), engine=(PB,))
    render = D._render(review, checked, eval_time=datetime(2026, 8, 20, tzinfo=timezone.utc))
    assert render["sources"]["headline"]["from"] == ["file", "engine"]
    [headline, *_] = B._sentence_sources({"capability_render": render})
    assert headline["from"] == ["file", "engine"] and headline["sentence"] == "headline"


def test_it_names_the_file_only_when_the_headline_cites_it():
    bare = dataclasses.replace(WORDS, evidence=(), quotes=())
    sources = D.sources_of(_checked(C.LineVerdict("guided_by", C.KEPT), engine=(PB,), words=bare),
                           _review(guided_by=[PB.ref]))
    assert sources["headline"]["from"] == ["engine"]
