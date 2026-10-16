"""STEP-14 · one file, one card — both builders VERSION the file's card, never insert a second.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_one_file_one_card.py -q

Tree `yc2_w27_s14` M42.C3.L-integration.V2.U03 (`deliver/pipeline`; STEP-14 §8.4 items 1-3, s14-D1, `03` F176). The
decision loop and STEP-13's question builder (`_build_question_cards`) find the file's card (`CardStore.file_card`)
and version it onto the file's new signal (`CardStore.version_card`) — a question card is the file's card asking.
A MATERIAL version (another ask, recipient, date, lane or mode) is pushed under today's band and budget; a reworded
or renewed one is not (counted `versioned`, `renewed`). A card an agent holds makes the file's next version wait. A
file card whose signal closed and that no version reached is expired REPLACED at the end of the pass, counted — a
card from before 0220 among them, once. `files_with_two_open_cards` is measured every pass, and is 0.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.card_builder import BUILDER_VERSION
from genios_engine.deliver.store import QUESTION_CARD_BUILDER, CardStore
from genios_engine.reason.change_gate import FILE_RENEW_MARGIN
from genios_engine.reason.expert import decide as expert
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _open_signals, _write, admitted, world)
from tests.reason.expert.test_a_file_keeps_one_decision import FIRST, OTHER_MOVE, SECOND

pytestmark = pytest.mark.pg


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _build(store, cards, org, at):
    return pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=at)


def _cards(store, org):
    with store.engine.connect() as c:
        return c.execute(text("select card_id, signal_id, state, version, headline, builder_version, file_id "
                              "from cards where org_id = :o order by created_at, card_id"), {"o": org}).all()


def _events(store, card_id, kind):
    with store.engine.connect() as c:
        return [(r.cause, r.detail) for r in c.execute(text(
            "select cause, detail from card_events where card_id = :c and kind = :k order by occurred_at, id"),
            {"c": card_id, "k": kind})]


def _first(world, cards):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    counts = _build(store, cards, org, NOW)
    [card] = _cards(store, org)
    assert counts["built"] == 1 and (card.file_id, card.version) == (anchor, 1), counts
    return store, org, registry, anchor, events, card


def test_other_advice_is_a_version_of_the_files_card_never_a_second(world, cards):
    store, org, registry, anchor, events, first = _first(world, cards)
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    later = NOW + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: SECOND}, at=later)
    counts = _build(store, cards, org, later)
    [card] = _cards(store, org)
    [signal] = _open_signals(store, org, anchor)
    assert (card.card_id, card.signal_id, card.version, card.headline) == (
        first.card_id, signal.signal_id, 2, OTHER_MOVE["what"])
    assert (counts["built"], counts["versioned"], counts["renewed"]) == (0, 1, 0), counts
    assert counts["lane_recall_balanced"] is True and counts["files_with_two_open_cards"] == 0
    [(cause, detail)] = _events(store, card.card_id, "card.versioned")
    assert cause == "updated" and detail["material"] is True and detail["words"]["mode"] == "act"
    assert counts["quiet_version_not_pushed"] == 0, "a material version goes through the push gate"


def test_the_same_advice_renewed_is_a_quiet_version(world, cards):
    store, org, registry, anchor, _events_, first = _first(world, cards)
    inside = NOW + timedelta(hours=expert.EXPIRY_HOURS) - FILE_RENEW_MARGIN + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: FIRST}, at=inside)
    counts = _build(store, cards, org, inside)
    [card] = _cards(store, org)
    assert (card.card_id, card.version, card.state) == (first.card_id, 2, "queued")
    assert (counts["versioned"], counts["renewed"], counts["pushed"], counts["quiet_version_not_pushed"]) == (
        1, 1, 0, 1), counts
    assert [cause for cause, _ in _events(store, card.card_id, "card.versioned")] == ["renewed"]


def test_a_question_and_the_decision_after_it_are_versions_of_one_card(world, cards):
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, anchor, events, first = _first(world, cards)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    later = NOW + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"}, at=later)
    asked = _build(store, cards, org, later)
    [card] = _cards(store, org)
    assert (card.card_id, card.version, card.builder_version) == (first.card_id, 2, QUESTION_CARD_BUILDER)
    assert (asked["question_cards"], asked["versioned"]) == (0, 1), asked
    [(cause, detail)] = _events(store, card.card_id, "card.versioned")
    with store.engine.connect() as c:
        question_id = c.execute(text("select question_id from founder_questions where org_id = :o"), {"o": org}).scalar()
    assert (cause, detail["words"]["mode"], detail["words"]["ask"]) == ("asked", "question", question_id)
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    again = later + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: SECOND}, at=again)
    _build(store, cards, org, again)
    [card] = _cards(store, org)
    assert (card.card_id, card.version, card.builder_version) == (first.card_id, 3, BUILDER_VERSION)
    assert [cause for cause, _ in _events(store, card.card_id, "card.versioned")] == ["asked", "updated"]


def test_a_card_an_agent_holds_makes_the_files_next_version_wait(world, cards):
    from genios_engine.deliver import agent_api
    store, org, registry, anchor, events, first = _first(world, cards)
    # ⛔ RESTATED by `yc2_w27_s14` M42.C1.L-data.V1.U04 (the STEP-14 crosscheck, finding 6): this set the card's STATE
    # to `claimed` with no claim — the shape a late result leaves, held forever. An agent holds a card by its claim.
    assert agent_api.claim(store, org, first.signal_id, "agent_1", eval_time=NOW + timedelta(minutes=1))["ok"]
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    later = NOW + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: SECOND}, at=later)
    counts = _build(store, cards, org, later)
    assert counts["version_waits"] == 1 and counts["built"] == 0 and counts["file_cards_replaced"] == 0, counts
    [card] = _cards(store, org)
    assert (card.signal_id, card.state) == (first.signal_id, "claimed"), "the agent's card is left as it is"


def test_a_file_card_no_version_reached_is_replaced_at_the_end_of_the_pass(world, cards):
    store, org, registry, anchor, events, first = _first(world, cards)
    with store.engine.begin() as c:            # its signal closed, and nothing of the file's follows
        c.execute(text("update signals set status = 'expired' where signal_id = :s"), {"s": first.signal_id})
    counts = _build(store, cards, org, NOW + timedelta(hours=1))
    assert counts["file_cards_replaced"] == 1, counts
    assert [c.state for c in _cards(store, org)] == ["expired"]
    assert [cause for cause, _ in _events(store, first.card_id, "card.expired")] == ["replaced"]


def test_a_card_from_before_0220_is_replaced_once_by_the_files_card(world, cards):
    """The one-time churn at switch-on (STEP-14 §8.7): an open expert card that names no file is not found as the
    file's card — the file's next decision is a new card, and the old one is replaced at the end of the pass."""
    store, org, registry, anchor, events, first = _first(world, cards)
    with store.engine.begin() as c:
        c.execute(text("update cards set file_id = null where card_id = :c"), {"c": first.card_id})
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    later = NOW + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: SECOND}, at=later)
    counts = _build(store, cards, org, later)
    old, new = _cards(store, org)
    assert (old.card_id, old.state, new.state, new.file_id) == (first.card_id, "expired", "queued", anchor)
    assert (counts["built"], counts["file_cards_replaced"], counts["files_with_two_open_cards"]) == (1, 1, 0)


def test_two_open_cards_of_one_file_are_counted(world, cards):
    """The measurement reads a file's cards by their file, and — before 0220 — by the expert card's subject."""
    store, org, registry, anchor, _events_, first = _first(world, cards)
    with store.engine.begin() as c:
        c.execute(text("update cards set file_id = null where card_id = :c"), {"c": first.card_id})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, state, "
            " expires_at, file_id, capability_key) values ('card_twin', :s, :o, 'prescriptive', 'high', 'h', 's', 50, "
            " 'queued', :exp, :f, :cap)"),
            {"s": "sig_twin", "o": org, "exp": NOW + timedelta(days=3), "f": anchor, "cap": expert.CAPABILITY_ID})
        c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
                       "eval_time) values ('sig_twin', :o, 'file_review', :n, 50, 'file_review', :t)"),
                  {"o": org, "n": anchor, "t": NOW})
    assert _build(store, cards, org, NOW + timedelta(minutes=5))["files_with_two_open_cards"] == 1


def test_the_same_move_in_other_words_at_its_renewal_is_a_quiet_rewording(world, cards):
    """A new review inside the renewal margin gives the same move, its reading of the file in other words: the
    file branch re-emits it (no longer "standing" there), and the card's version is REWORDED — not pushed."""
    store, org, registry, anchor, events, first = _first(world, cards)
    _write(store, org, anchor, SECOND, events,
           frames={"primary": "a fund two days from its partner meeting", "rivals": ["a check-in"]})
    inside = NOW + timedelta(hours=expert.EXPIRY_HOURS) - FILE_RENEW_MARGIN + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: SECOND}, at=inside)
    counts = _build(store, cards, org, inside)
    assert (counts["versioned"], counts["reworded"], counts["renewed"], counts["pushed"]) == (1, 1, 0, 0), counts
    [(cause, detail)] = _events(store, first.card_id, "card.versioned")
    assert cause == "reworded" and detail["changed"] == ["situation"]
