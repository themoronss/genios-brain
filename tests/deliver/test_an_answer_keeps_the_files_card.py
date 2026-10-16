"""STEP-14 · answering keeps the file's card — "your answer is in; the file is read again", one card from question
to move (s14-D3).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_an_answer_keeps_the_files_card.py -q

Tree `yc2_w27_s14` M42.C3.L-interface.V4.U05 (`deliver/actions.ingest_action`, `answer`; STEP-14 §8.4 item 3). STEP-13
U06's Answer resolved the question card and acted its signal, so the decision the answer led to was a second card.
Now the Answer keeps your words on the file, as before, and VERSIONS the card — answered: its headline "your answer
is in; the file is read again", its situation the question you answered, the Monitor lane, nothing to press — while
its signal stays open and nothing resolves it. The file's next review versions it again: a decision, or another
question. Decision → question → answer → decision is ONE card.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import founder_questions as Q
from genios_engine.deliver import actions
from genios_engine.deliver.card_builder import BUILDER_VERSION
from tests.deliver.test_a_question_card import _build, _cards, _queued
from tests.deliver.test_answering_a_question import AT, WORDS, _card, _press, cards  # noqa: F401
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _write, admitted, world)
from tests.reason.expert.test_a_held_file_asks import FIND_OUT, _questions

pytestmark = pytest.mark.pg


def _row(store, org, card_id):
    with store.engine.connect() as c:
        return c.execute(text(
            "select k.state, k.resolved_at, k.version, k.headline, k.situation, k.output_lane, k.actions, "
            "       s.status from cards k join signals s on s.org_id = k.org_id and s.signal_id = k.signal_id "
            " where k.org_id = :o and k.card_id = :c"), {"o": org, "c": card_id}).one()


def _versions(store, card_id):
    with store.engine.connect() as c:
        return [(r.cause, r.detail) for r in c.execute(text(
            "select cause, detail from card_events where card_id = :c and kind = 'card.versioned' "
            "order by occurred_at, id"), {"c": card_id})]


def test_your_answer_versions_the_files_card_and_closes_nothing(world, cards):
    store, org, _registry, anchor, card = _card(world, cards)
    [asked] = _questions(store, org, anchor)
    out = _press(store, cards, org, card.card_id, "answer", words=WORDS)
    assert out == {"ok": True, "state": "queued", "action": "answer", "question_id": asked.question_id, "version": 2}
    [kept] = _questions(store, org, anchor)
    assert kept.state == Q.ANSWERED
    row = _row(store, org, card.card_id)
    assert (row.state, row.resolved_at, row.status, row.version) == ("queued", None, "open", 2)
    assert (row.headline, row.situation, row.output_lane) == (actions.ANSWERED_HEADLINE, FIND_OUT, "monitor")
    assert [a["type"] for a in row.actions] == ["snooze"], "nothing to press but later"
    [(cause, detail)] = _versions(store, card.card_id)
    assert cause == "answered" and detail["before"]["headline"] == FIND_OUT and detail["words"]["mode"] == "answered"
    assert detail["words"]["ask"] == asked.question_id, "the ask it answered"
    with store.engine.connect() as c:
        assert c.execute(text("select occurred_at from card_events where card_id = :c and kind = 'card.versioned'"),
                         {"c": card.card_id}).scalar() == AT, "dated by your press"
    assert WORDS not in str(detail), "your words are kept on the question, never in the card's history"
    # ⛔ RESTATED by `yc2_w27_s14` M42.C3.L-interface.V4.U06 (the STEP-14 crosscheck, finding 2): this pinned that no
    # door showed the answered card until the file's next version — the card on no route, against s14-D3. It stays.
    assert _queued(cards, org, AT) == [card.card_id], "your answer is in: the card stays where you see it"


def test_the_decision_your_answer_leads_to_is_the_same_cards_next_version(world, cards):
    store, org, registry, anchor, card = _card(world, cards)
    _anchor, _situations, events = _fund(store, org)
    _press(store, cards, org, card.card_id, "answer", words=WORDS)
    _write(store, org, anchor, "ffp-fund-act-after-answer-0", events)
    later = AT + timedelta(hours=1)
    _compile(store, org, registry, covered={anchor: "ffp-fund-act-after-answer-0"}, at=later)
    counts = _build(store, cards, org, at=later)
    [one] = _cards(store, org)
    assert (one.card_id, one.builder_version, counts["versioned"]) == (card.card_id, BUILDER_VERSION, 1), counts
    assert [c for c, _ in _versions(store, card.card_id)] == ["answered", "updated"]
    assert _queued(cards, org, later) == [card.card_id]


def test_another_question_after_your_answer_is_the_same_cards_next_version(world, cards):
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, anchor, card = _card(world, cards)
    _anchor, _situations, events = _fund(store, org)
    _press(store, cards, org, card.card_id, "answer", words=WORDS)
    later = AT + timedelta(hours=1)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=later)
    _build(store, cards, org, at=later)
    [one] = _cards(store, org)
    assert (one.card_id, one.headline) == (card.card_id, "Who at the fund decides?")
    assert [c for c, _ in _versions(store, card.card_id)] == ["answered", "asked"]


def test_a_snoozed_question_answered_stays_where_you_put_it(world, cards):
    store, org, _registry, _anchor, card = _card(world, cards)
    _press(store, cards, org, card.card_id, "snooze", snooze_option="3d")
    with store.engine.connect() as c:
        until = c.execute(text("select snooze_until from cards where card_id = :c"), {"c": card.card_id}).scalar()
    out = _press(store, cards, org, card.card_id, "answer", words=WORDS)
    assert out["state"] == "snoozed" and out["version"] == 2
    with store.engine.connect() as c:
        assert c.execute(text("select snooze_until from cards where card_id = :c"), {"c": card.card_id}).scalar() \
            == until


def test_a_card_that_names_no_file_keeps_its_words_when_answered(world, cards):
    """A question card from before 0220 is no file's card: the answer is kept, the card is not versioned and its
    words are not rewritten — nothing says "the file is read again" over a card no version will reach."""
    store, org, _registry, anchor, card = _card(world, cards)
    with store.engine.begin() as c:
        c.execute(text("update cards set file_id = null where card_id = :c"), {"c": card.card_id})
    out = _press(store, cards, org, card.card_id, "answer", words=WORDS)
    assert out["ok"] is True and out["version"] is None
    row = _row(store, org, card.card_id)
    assert (row.headline, row.version) == (FIND_OUT, 1) and _versions(store, card.card_id) == []
    [kept] = _questions(store, org, anchor)
    assert kept.state == Q.ANSWERED
