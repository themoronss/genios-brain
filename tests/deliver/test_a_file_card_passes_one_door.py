"""STEP-14 · the doors agree on a file card's CURRENT version — every open file card passes exactly one door.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_file_card_passes_one_door.py -q

Tree `yc2_w27_s14` M42.C3.L-interface.V3.U04 (`deliver/store`; STEP-14 §8.4 item 3, s14-F12). A file's card turns from
a decision into a question and back (`CardStore.version_card`), and each version is read through the door of what it
carries now: a decision through the decision's authority, a question through STEP-13's third door
(`QUESTION_CARD_SQL`, keyed on the question builder's stamp — which a version writes). `CardStore.doors` says which
door each open file card passes — the queue, the card detail and the actions read the same three — and the guard
holds exactly one: a card that passed none would vanish, one that passed two would show twice.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import QUESTION_CARD_BUILDER, CardStore
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _open_signals, _write, admitted, world)
from tests.reason.expert.test_a_file_keeps_one_decision import FIRST, OTHER_MOVE, SECOND

pytestmark = pytest.mark.pg


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _queued(cards, org, at):
    from tests.deliver.test_a_question_card import _queued as queued
    return queued(cards, org, at)


def _card_id(store, org):
    with store.engine.connect() as c:
        [card_id] = [r[0] for r in c.execute(text("select card_id from cards where org_id = :o"), {"o": org})]
    return card_id


def test_a_file_card_passes_the_door_of_what_it_carries_now(world, cards):
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    card = _card_id(store, org)
    assert cards.doors(org, eval_time=NOW) == {card: ("decision",)}
    assert _queued(cards, org, NOW) == [card]

    asked = NOW + timedelta(hours=6)                    # the file asks: the card is the question now
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"}, at=asked)
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=asked)
    assert cards.get_card(card)["builder_version"] == QUESTION_CARD_BUILDER
    assert cards.doors(org, eval_time=asked) == {card: ("question",)}
    assert _queued(cards, org, asked) == [card], "shown once, through the question's door"
    assert cards.get_authoritative_card(card, org, eval_time=asked)["card_id"] == card, "its detail reads it"

    decided = asked + timedelta(hours=6)                # and decided again: the decision's door
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    _compile(store, org, registry, covered={anchor: SECOND}, at=decided)
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=decided)
    assert cards.get_card(card)["builder_version"] != QUESTION_CARD_BUILDER
    assert cards.doors(org, eval_time=decided) == {card: ("decision",)}
    assert _queued(cards, org, decided) == [card]
    with store.engine.begin() as c:                     # an expert card from before 0220 is asked about too
        c.execute(text("update cards set file_id = null where card_id = :c"), {"c": card})
    assert cards.doors(org, eval_time=decided) == {card: ("decision",)}


def test_a_decision_whose_authority_no_longer_holds_passes_no_door(world, cards):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    card = _card_id(store, org)
    with store.engine.begin() as c:                     # its score no longer the audited decision's
        c.execute(text("update signals set score = score + 1 where signal_id = (select signal_id from cards "
                       "where card_id = :c)"), {"c": card})
    assert cards.doors(org, eval_time=NOW) == {card: ()} and _queued(cards, org, NOW) == []


def test_a_card_stamped_for_another_door_is_caught(world, cards):
    """⛔ THE NEGATIVE CONTROL: a decision card stamped with the question builder still passes the decision's door —
    but a question card stamped with the decision's builder passes none, and the guard says so."""
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    card = _card_id(store, org)
    assert cards.doors(org, eval_time=NOW) == {card: ("question",)}
    with store.engine.begin() as c:
        c.execute(text("update cards set builder_version = 'card-builder.v6-lane-and-eleven-reasons' "
                       "where card_id = :c"), {"c": card})
    assert cards.doors(org, eval_time=NOW) == {card: ()}, "no door: it would vanish"
    assert _queued(cards, org, NOW) == []


def test_a_card_whose_signal_closed_is_asked_about_by_no_door(world, cards):
    """It is the end of the pass's to close (`pipeline._close_the_files_pass`), not a door's to show."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    with store.engine.begin() as c:
        c.execute(text("update signals set status = 'expired' where org_id = :o"), {"o": org})
    assert cards.doors(org, eval_time=NOW) == {}
