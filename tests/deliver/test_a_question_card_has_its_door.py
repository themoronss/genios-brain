"""STEP-13 · a question card has its own door in the card store — and only a question passes it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_a_question_card_has_its_door.py

Tree `yc2_w27_s13` M36.C2.L-interface.V2.U09 (`deliver/store`: `QUESTION_CARD_BUILDER`, `QUESTION_CARD_SQL`).
Every reader of a card re-proves the DECISION's authority (`reason/authority.AUTHORITATIVE_SIGNAL_PREDICATE`),
and a question has no selected move — so a question card written to `cards` reached nobody. The insert now
holds a question card to its question's own authority (`QUESTION_SIGNAL_PREDICATE`: the expert's live run that
ended insufficient, the signal bound to it, the question that run asked still open); the queue (`/cards`) and
the card read (`/cards/{id}`) show it while its question is open. A card that names the question builder
without that authority is refused, one bound to another run is refused, and an answered question's card
leaves the queue.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import founder_questions as Q
from genios_engine.deliver.store import QUESTION_CARD_BUILDER, CardStore
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _open_signals, world)
from tests.reason.expert.test_a_held_file_asks import FIND_OUT, _find_out, _questions
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

pytestmark = pytest.mark.pg


def _asked(world):
    """A file that must find out first, swept: its question filed and its question signal open."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    [signal] = _open_signals(store, org, anchor)
    [question] = _questions(store, org, anchor)
    with store.engine.connect() as c:
        bound = c.execute(text("select reasoning_run_id, reasoning_decision_hash, config_snapshot_id, "
                               "authority_expires_at from signals where org_id = :o and signal_id = :s"),
                          {"o": org, "s": signal.signal_id}).one()
    return store, org, anchor, signal, question, bound


def _card(org, signal, question, bound, **over) -> dict:
    card = {"signal_id": signal.signal_id, "org_id": org, "assignee": None, "domain": "founder_office",
            "level": "review", "urgency_band": "low", "score": 0, "score_block": {"S": 0},
            "actions": [{"type": "answer", "question_id": question.question_id}], "why": [],
            "context_tags": [], "surfaces": ["app", "api"], "output_lane": "investigation",
            "lane_reason": "we cannot conclude", "builder_version": QUESTION_CARD_BUILDER,
            "config_snapshot_id": bound.config_snapshot_id, "expires_at": bound.authority_expires_at,
            "_authority_time": NOW,
            "_question_authority": {"reasoning_run_id": bound.reasoning_run_id,
                                    "reasoning_decision_hash": bound.reasoning_decision_hash,
                                    "config_snapshot_id": bound.config_snapshot_id,
                                    "question_id": question.question_id}}
    card.update(over)
    return card


COPY = {"headline": FIND_OUT, "situation": "a fund preparing a partner meeting", "artifact": {},
        "render_mode": "question"}


def _insert(cards: CardStore, card: dict):
    token = cards.claim_build(card["org_id"], card["signal_id"], eval_time=NOW,
                              builder_version=QUESTION_CARD_BUILDER)
    assert token is not None
    try:
        return cards.insert_card(card, COPY, build_claim_token=token)
    finally:
        cards.release_build(card["org_id"], card["signal_id"], token)


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _queue_at(cards, org, at):
    """The queue as `/cards` reads it, at the sweep's own clock (the fixtures' NOW is a fixed date)."""
    import genios_engine.deliver.store as store_module

    class _Clock(store_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return at
    original = store_module.datetime
    store_module.datetime = _Clock
    try:
        return cards.queue(org, admin=True, record_impressions=False)
    finally:
        store_module.datetime = original


def test_a_question_card_is_written_and_read_through_its_own_door(world, cards):
    store, org, _anchor, signal, question, bound = _asked(world)
    card_id, created, _ = _insert(cards, _card(org, signal, question, bound))
    assert created and card_id
    assert [r["card_id"] for r in _queue_at(cards, org, NOW)] == [card_id], "the queue shows it"
    read = cards.get_authoritative_card(card_id, org, eval_time=NOW)
    assert read is not None and read["headline"] == FIND_OUT and read["output_lane"] == "investigation"


def test_a_card_naming_the_question_builder_without_its_authority_is_refused(world, cards):
    store, org, _anchor, signal, question, bound = _asked(world)
    bare = _card(org, signal, question, bound)
    bare.pop("_question_authority")
    assert _insert(cards, bare) == (None, False, False)


def test_a_questions_authority_under_another_builder_is_refused(world, cards):
    """A card it carried under any other builder would be read through no door — refused, not written."""
    store, org, _anchor, signal, question, bound = _asked(world)
    assert _insert(cards, _card(org, signal, question, bound, builder_version="card.v9")) == (None, False, False)


@pytest.mark.parametrize("field", ["reasoning_run_id", "reasoning_decision_hash", "question_id"])
def test_a_question_card_bound_to_anything_else_is_refused(world, cards, field):
    store, org, _anchor, signal, question, bound = _asked(world)
    card = _card(org, signal, question, bound)
    card["_question_authority"] = {**card["_question_authority"], field: "not_this_one"}
    assert _insert(cards, card) == (None, False, False)


def test_an_answered_questions_card_leaves_the_queue(world, cards):
    store, org, _anchor, signal, question, bound = _asked(world)
    card_id, created, _ = _insert(cards, _card(org, signal, question, bound))
    assert created
    with store.engine.begin() as c:
        Q.answer(c, org_id=org, question_id=question.question_id, words="This quarter's.", by="u",
                 at=NOW + timedelta(minutes=5))
    assert _queue_at(cards, org, NOW) == []
    assert cards.get_authoritative_card(card_id, org, eval_time=NOW) is None


def test_past_its_authority_a_question_card_is_not_read(world, cards):
    store, org, _anchor, signal, question, bound = _asked(world)
    card_id, created, _ = _insert(cards, _card(org, signal, question, bound))
    assert created
    later = bound.authority_expires_at + timedelta(seconds=1)
    assert _queue_at(cards, org, later) == []
    assert cards.get_authoritative_card(card_id, org, eval_time=later) is None


def test_a_decision_card_never_passes_the_question_door(world, cards):
    """⛔ THE NEGATIVE CONTROL: the question door is the question's; a card of the question builder over a
    signal that is no question — the file's decision — is refused, and none is shown."""
    from tests.reason.expert.test_a_covered_file_decides_once import _write
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-act-review-000000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"})
    [decision] = _open_signals(store, org, anchor)
    with store.engine.connect() as c:
        bound = c.execute(text("select reasoning_run_id, reasoning_decision_hash, config_snapshot_id, "
                               "authority_expires_at from signals where org_id = :o and signal_id = :s"),
                          {"o": org, "s": decision.signal_id}).one()
    fake = type("Q", (), {"question_id": "fq_none"})()
    assert _insert(cards, _card(org, decision, fake, bound)) == (None, False, False)
    assert _queue_at(cards, org, NOW) == []


def test_only_a_card_its_builder_wrote_passes_the_door(world, cards):
    store, org, _anchor, signal, question, bound = _asked(world)
    card_id, created, _ = _insert(cards, _card(org, signal, question, bound))
    assert created
    with store.engine.begin() as c:
        c.execute(text("update cards set builder_version = 'card.v9' where org_id = :o and card_id = :k"),
                  {"o": org, "k": card_id})
    assert _queue_at(cards, org, NOW) == []
    assert cards.get_authoritative_card(card_id, org, eval_time=NOW) is None


def test_a_seat_sees_a_question_card_only_as_it_sees_any_card(world, cards):
    """The door keeps the queue's seat rules: a member's strict reach, and a seat's own-or-unassigned."""
    import genios_engine.deliver.store as store_module
    store, org, _anchor, signal, question, bound = _asked(world)
    card_id, created, _ = _insert(cards, _card(org, signal, question, bound, assignee="seat_other"))
    assert created

    def _seen(**kw):
        class _Clock(store_module.datetime):
            @classmethod
            def now(cls, tz=None):
                return NOW
        original = store_module.datetime
        store_module.datetime = _Clock
        try:
            return [r["card_id"] for r in cards.queue(org, record_impressions=False, **kw)]
        finally:
            store_module.datetime = original
    assert _seen(admin=True) == [card_id]
    assert _seen(assignee="seat_me", admin=False) == [], "another seat's card"
    assert _seen(assignee="seat_other", admin=False) == [card_id]
    assert _seen(assignee="seat_me", admin=False, strict_seat=True) == []
