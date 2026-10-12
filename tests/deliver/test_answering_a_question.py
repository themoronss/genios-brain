"""STEP-13 · your answer: the question card's Answer action answers the file's question, once.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_answering_a_question.py

Tree `yc2_w27_s13` M36.C2.L-interface.V4.U06 (`deliver/actions.ingest_action`, `answer`; `POST /cards/{id}/action`
with `words`; `06` D60). `answer` with your words answers the question the card asks — kept once on the file
(`context/founder_questions`), the card resolved, its signal acted, the press recorded without your words —
and the file's next dossier shows it. An answer that says nothing is refused; a question card offers only
`answer` and the deferrals; no other card is a question; an answered question cannot be answered again.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import founder_questions as Q
from genios_engine.deliver import actions
from genios_engine.deliver.store import CardStore
from tests.deliver.test_a_question_card import _asked, _build, _cards, _queued
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, world)
from tests.reason.expert.test_a_held_file_asks import _questions
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

pytestmark = pytest.mark.pg

AT = NOW + timedelta(minutes=5)
WORDS = "This quarter's — he wants the Q3 numbers before the partner meeting."


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _press(store, cards, org, card_id, action, **kw):
    return actions.ingest_action(card_store=cards, graph=store, org_id=org, card_id=card_id,
                                 actor="founder@meridian.test", action=action, eval_time=AT,
                                 allow_any_assignee=True, **kw)


def _card(world, cards):
    store, org, registry, anchor, events = _asked(world)
    _build(store, cards, org)
    [card] = _cards(store, org)
    return store, org, registry, anchor, card


def test_your_answer_answers_the_files_question_and_resolves_its_card(world, cards):
    store, org, _registry, anchor, card = _card(world, cards)
    [asked] = _questions(store, org, anchor)
    out = _press(store, cards, org, card.card_id, "answer", words=f"  {WORDS}  ", surface="web")
    assert out == {"ok": True, "state": "resolved", "action": "answer", "question_id": asked.question_id}
    [kept] = _questions(store, org, anchor)
    assert kept.state == Q.ANSWERED
    with store.engine.connect() as c:
        answered = Q.by_id(c, org, asked.question_id)
        row = c.execute(text("select k.state, k.resolved_at, s.status from cards k join signals s on "
                             "s.org_id = k.org_id and s.signal_id = k.signal_id where k.org_id = :o "
                             "and k.card_id = :k"), {"o": org, "k": card.card_id}).one()
        pressed = c.execute(text("select type, detail from human_events where org_id = :o "
                                 "and type = 'card.answer'"), {"o": org}).one()
        logged = c.execute(text("select kind, cause, detail from card_events where org_id = :o and "
                                "card_id = :k and kind = 'human.card_action'"),
                           {"o": org, "k": card.card_id}).one()
    assert (answered.answer, answered.answered_by, answered.answered_at) == (WORDS, "founder@meridian.test", AT)
    assert (row.state, row.resolved_at, row.status) == ("resolved", AT, "acted")
    assert pressed.detail == {"question_id": asked.question_id, "surface": "web"}
    assert logged.cause == "answer" and WORDS not in str(logged.detail) and WORDS not in str(pressed.detail)
    assert _queued(cards, org, AT) == [], "answered, it leaves the queue"


def test_the_files_next_dossier_shows_your_answer(world, cards):
    from genios_engine.reason.expert import dossier as D
    store, org, _registry, anchor, card = _card(world, cards)
    _press(store, cards, org, card.card_id, "answer", words=WORDS)
    with store.engine.connect() as c:
        parts = D.read_parts(c, org, anchor, now=AT + timedelta(hours=1))
    assert [a.answer for a in parts.answers] == [WORDS]
    assert WORDS in D.build_dossier(parts).text


def test_an_answer_is_kept_once(world, cards):
    store, org, _registry, anchor, card = _card(world, cards)
    _press(store, cards, org, card.card_id, "answer", words=WORDS)
    again = _press(store, cards, org, card.card_id, "answer", words="No — last quarter's.")
    assert again["ok"] is False
    [kept] = _questions(store, org, anchor)
    with store.engine.connect() as c:
        assert Q.by_id(c, org, kept.question_id).answer == WORDS


@pytest.mark.parametrize("words", [None, "", "   "])
def test_an_answer_that_says_nothing_is_refused_and_changes_nothing(world, cards, words):
    store, org, _registry, anchor, card = _card(world, cards)
    assert _press(store, cards, org, card.card_id, "answer", words=words) == {
        "ok": False, "error": "answer_says_nothing"}
    [asked] = _questions(store, org, anchor)
    assert asked.state == Q.OPEN and _cards(store, org)[0].state == "queued"


def test_an_answer_past_its_length_is_refused(world, cards):
    store, org, _registry, _anchor, card = _card(world, cards)
    out = _press(store, cards, org, card.card_id, "answer", words="x" * (actions.MAX_ANSWER_CHARS + 1))
    assert out["error"] == "answer_too_long"


@pytest.mark.parametrize("action", ["run_play", "do_it_myself"])
def test_a_question_card_offers_no_instruction(world, cards, action):
    store, org, _registry, _anchor, card = _card(world, cards)
    out = _press(store, cards, org, card.card_id, action)
    assert out == {"ok": False, "error": "not_offered", "offered": sorted(actions.QUESTION_OFFERS)}
    assert _cards(store, org)[0].state == "queued"


def test_a_question_card_can_wait(world, cards):
    store, org, _registry, _anchor, card = _card(world, cards)
    out = _press(store, cards, org, card.card_id, "snooze", snooze_option="4h")
    assert out["ok"] is True and out["state"] == "snoozed"


def test_no_other_card_is_a_question(world, cards):
    """⛔ THE NEGATIVE CONTROL: the file's decision card is no question — `answer` is refused there."""
    from tests.reason.expert.test_a_covered_file_decides_once import _fund
    from tests.reason.expert.test_a_covered_file_decides_once import _write as _write_act
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write_act(store, org, anchor, "ffp-fund-act-review-000000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"})
    _build(store, cards, org)
    [decision] = _cards(store, org)
    assert _press(store, cards, org, decision.card_id, "answer", words=WORDS) == {
        "ok": False, "error": "not_a_question"}


def test_the_route_carries_your_words(monkeypatch):
    """`POST /cards/{id}/action` hands `words` to the action, as it hands `surface`."""
    from tests.test_card_history_routes import FakeStore, client
    seen: list[dict] = []

    def fake_ingest(**kwargs):
        seen.append(kwargs)
        return {"ok": True, "state": "resolved"}
    monkeypatch.setattr(actions, "ingest_action", fake_ingest)
    api = client(monkeypatch, FakeStore())
    assert api.post("/cards/card_1/action", json={"action": "answer", "words": WORDS}).status_code == 200
    assert seen[0]["action"] == "answer" and seen[0]["words"] == WORDS


@pytest.mark.parametrize("action", ["answer", "snooze"])
def test_a_card_whose_question_is_no_longer_open_takes_no_press(world, cards, action):
    """Proved by its question's own authority on every press: answered elsewhere, the card is stale."""
    store, org, _registry, anchor, card = _card(world, cards)
    [asked] = _questions(store, org, anchor)
    with store.engine.begin() as c:
        Q.answer(c, org_id=org, question_id=asked.question_id, words="answered in the app", by="u", at=AT)
    out = _press(store, cards, org, card.card_id, action, words=WORDS, snooze_option="4h")
    assert out == {"ok": False, "error": "stale_or_unauthorized_card", "code": "V-09"}


def test_a_question_you_answered_is_never_carded_again(world, cards):
    """⛔ `03` X25 (M36.C2.L-data.V2.U12). Your answer moves the file; a later review asks another question, on its
    own card; a later one still asks the words you answered. Nothing is asked: the open question it no longer
    asks retires, its card REPLACED, and no card asks you again what you told us."""
    from genios_engine.platform import card_lifecycle
    from tests.reason.expert.test_a_covered_file_decides_once import _fund
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, anchor, card = _card(world, cards)
    _anchor, _situations, events = _fund(store, org)
    _press(store, cards, org, card.card_id, "answer", words=WORDS)
    later = AT + timedelta(hours=1)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=later)
    assert _build(store, cards, org, at=later)["question_cards"] == 1
    last = later + timedelta(hours=1)
    _find_out(store, org, anchor, "ffp-fund-findout-review-002", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-002"}, at=last)
    assert counts.get("expert_question_answered_already") == 1, counts
    assert _build(store, cards, org, at=last)["question_cards"] == 0
    answered, other = _cards(store, org)
    assert (answered.card_id, answered.state) == (card.card_id, "resolved")
    assert other.state == "expired"
    with store.engine.connect() as c:
        cause = c.execute(text("select cause from card_events where org_id = :o and card_id = :k "
                               "and kind = :kind"), {"o": org, "k": other.card_id,
                                                     "kind": card_lifecycle.EXPIRED}).scalar()
    assert cause == card_lifecycle.REPLACED
    states = sorted((q.question, q.state, q.retired_why) for q in _questions(store, org, anchor))
    assert states == sorted([("Did Arjun ask for last quarter's metrics or this quarter's?", Q.ANSWERED, None),
                             ("Who at the fund decides?", Q.RETIRED, Q.NO_LONGER_ASKED)])
    assert _queued(cards, org, last) == []


def test_the_answer_button_says_what_it_does():
    """⛔ `03` X42: the card's Answer action was annotated `none` (`api/routes._ACTION_EFFECT`) — a surface labelling
    transitions honestly read "answer" as a button that does nothing. It keeps your words; it sends nothing."""
    from genios_engine.api.routes import _annotate_effects
    [answer, snooze] = _annotate_effects([{"type": "answer", "label": "Answer", "question_id": "fq_x"},
                                         {"type": "snooze"}])
    assert (answer["effect"], snooze["effect"]) == ("answer_kept", "defer_surface")
