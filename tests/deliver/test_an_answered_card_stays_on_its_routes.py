"""STEP-14 fix · your answered card stays where you see it — "your answer is in; the file is read again" (s14-D3).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_an_answered_card_stays_on_its_routes.py -q

Tree `yc2_w27_s14` M42.C3.L-interface.V4.U06 (fix of M42.C3.L-interface.V4.U05; the STEP-14 crosscheck, finding 2,
BLOCKING). The answer versioned the file's card, as s14-D3 says — and then no door showed it: STEP-13's question door
(`deliver/store.QUESTION_CARD_SQL`) admits a card only while its question is OPEN, and an answer closes it. So the
card was on no route — `GET /cards` omitted it, `GET /cards/{id}` was a 404, History skipped it (its state stays
`queued`), `doors()` said `()`, and its one offered action, snooze, was refused V-09 — until the file's next review,
a model call inside the day's caps. On the pushed line the answered card was resolved and showed in History: a
regression for the founder, against s14-D3 and `08` §0c.

Now the question door admits the ANSWERED version of a file's card: its question answered, the card still on that
question's signal, waiting in the Monitor lane the answer put it in (`ANSWERED_LANE`) — and nothing else (a question
answered with no version written is still stale). It offers what it shows: later, and nothing to answer again
(`actions.ANSWERED_OFFERS`). Every open file card passes exactly one door, and the health check says so
(`scripts/pipeline_health.check_every_file_card_passes_one_door`).
"""
from __future__ import annotations

import importlib
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import actions
from genios_engine.deliver import store as S
from tests.deliver.test_a_question_card import _queued
from tests.deliver.test_answering_a_question import AT, WORDS, _card, _press, cards  # noqa: F401 — a fixture
from tests.reason.expert.test_a_covered_file_decides_once import admitted, world  # noqa: F401 — fixtures
from tests.reason.expert.test_a_held_file_asks import _questions

pytestmark = pytest.mark.pg


def _answered(world, cards):
    store, org, registry, anchor, card = _card(world, cards)
    assert _press(store, cards, org, card.card_id, "answer", words=WORDS)["ok"]
    return store, org, registry, anchor, card


def test_your_answered_card_is_on_the_queue_and_its_detail(world, cards):
    store, org, _registry, _anchor, card = _answered(world, cards)
    assert _queued(cards, org, AT) == [card.card_id], "the queue shows it: your answer is in"
    detail = cards.get_authoritative_card(card.card_id, org, eval_time=AT)
    assert detail is not None and detail["headline"] == actions.ANSWERED_HEADLINE, "GET /cards/{id} reads it"
    assert cards.doors(org, eval_time=AT) == {card.card_id: ("question",)}, "exactly one door"
    later = AT + timedelta(hours=1)
    assert _queued(cards, org, later) == [card.card_id], "and it stays until the file's next version"


def test_your_answered_card_can_wait_and_comes_back(world, cards):
    store, org, _registry, _anchor, card = _answered(world, cards)
    out = _press(store, cards, org, card.card_id, "snooze", snooze_option="4h")
    assert out["ok"] is True and out["state"] == "snoozed", out
    assert cards.get_authoritative_card(card.card_id, org, eval_time=AT)["state"] == "snoozed"
    back = _press(store, cards, org, card.card_id, "requeue")
    assert back["ok"] is True and back["state"] == "queued", back


def test_your_answered_card_is_not_answered_again(world, cards):
    store, org, _registry, anchor, card = _answered(world, cards)
    again = _press(store, cards, org, card.card_id, "answer", words="No — last quarter's.")
    assert again == {"ok": False, "error": "not_offered", "offered": sorted(actions.ANSWERED_OFFERS)}
    assert {a["type"] for a in cards.get_card(card.card_id)["actions"]} <= actions.ANSWERED_OFFERS, \
        "it offers what the press accepts"
    from genios_engine.context import founder_questions as Q
    [kept] = _questions(store, org, anchor)
    with store.engine.connect() as c:
        assert Q.by_id(c, org, kept.question_id).answer == WORDS, "your answer is kept once"


@pytest.mark.parametrize("action", ["run_play", "do_it_myself"])
def test_your_answered_card_offers_no_instruction(world, cards, action):
    store, org, _registry, _anchor, card = _answered(world, cards)
    assert _press(store, cards, org, card.card_id, action) == {
        "ok": False, "error": "not_offered", "offered": sorted(actions.ANSWERED_OFFERS)}


def test_a_question_answered_with_no_version_written_is_still_stale(world, cards):
    """⛔ THE NEGATIVE CONTROL: only the ANSWERED VERSION passes — a question card whose question was answered
    elsewhere, its words still the question, passes no door (STEP-13's stale press, kept)."""
    from genios_engine.context import founder_questions as Q
    store, org, _registry, anchor, card = _card(world, cards)
    [asked] = _questions(store, org, anchor)
    with store.engine.begin() as c:
        Q.answer(c, org_id=org, question_id=asked.question_id, words="answered in the app", by="u", at=AT)
    assert cards.doors(org, eval_time=AT) == {card.card_id: ()} and _queued(cards, org, AT) == []


def test_the_answered_lane_is_the_one_the_answer_writes():
    assert S.ANSWERED_LANE == actions.ANSWERED_LANE


def test_the_health_check_says_every_file_card_passes_one_door(world, cards):
    ph = importlib.import_module("scripts.pipeline_health")
    store, org, _registry, _anchor, card = _answered(world, cards)
    with store.engine.connect() as c:
        ok = ph.check_every_file_card_passes_one_door(c, org, now=AT)
    assert ok.ok and not ok.no_data and ok.measured == "0 of 1 open file card(s) pass no door or two", ok
    with store.engine.begin() as c:                      # stamped for no door: it would vanish
        c.execute(text("update cards set builder_version = 'card-builder.v6-lane-and-eleven-reasons' "
                       "where card_id = :c"), {"c": card.card_id})
    with store.engine.connect() as c:
        bad = ph.check_every_file_card_passes_one_door(c, org, now=AT)
    assert not bad.ok and bad.detail == [f"{card.card_id} passes no door"], bad
    assert ph.check_every_file_card_passes_one_door in ph.CHECKS
