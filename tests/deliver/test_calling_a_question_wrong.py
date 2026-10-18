"""STEP-16 · *don't ask me this* — a question card called wrong is a verdict on its file, and the question is retired.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_calling_a_question_wrong.py

Tree `yc2_w27_s16` M46.C3.L-integration.V4.U06 (`deliver/actions.ingest_action`; S16-D10, `s16-F13`, `s16-F15`). `wrong`
on a question card, in ONE transaction: the verdict through the one writer, bound to the question's own authority
(its rule `founder_question`, no pack revision — so calibration, which scores pack rules on revision-bound cards,
never reads it); the file's question retired `CALLED_WRONG` and its signal acted; your words, if any, a correction of
the file. And the sweep's half (`reason/expert/asks.ask_the_founder`, s16-F15): a later review that asks those words
again files no question and no signal — the file is held with no card, counted `expert_question_called_wrong`.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import founder_corrections as C
from genios_engine.context import founder_questions as Q
from genios_engine.deliver import actions
from genios_engine.deliver import verdicts as V
from genios_engine.deliver.store import CardStore
from tests.deliver.test_a_question_card import _asked, _build, _cards
from tests.reason.expert.test_a_covered_file_decides_once import NOW, _compile, world  # noqa: F401 — fixtures
from tests.reason.expert.test_a_held_file_asks import FIND_OUT, _find_out, _questions
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

pytestmark = pytest.mark.pg

AT = NOW + timedelta(minutes=5)
FOUNDER = "founder@meridian.test"
WORDS = "Banyan Seed is no fund we are raising from — stop asking."


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _question_card(world, cards):
    store, org, registry, anchor, events = _asked(world)
    _build(store, cards, org)
    [card] = _cards(store, org)
    return store, org, registry, anchor, events, card


def _press(store, org, card, action="wrong", **kw):
    kw.setdefault("reason", "not_relevant" if action == "wrong" else None)
    return actions.ingest_action(card_store=None, graph=store, org_id=org, card_id=card.card_id, actor=FOUNDER,
                                 action=action, eval_time=AT, allow_any_assignee=True, **kw)


def _row(store, org, card):
    with store.engine.connect() as c:
        return c.execute(text(
            "select k.state, s.status from cards k join signals s on s.org_id = k.org_id "
            "and s.signal_id = k.signal_id where k.org_id = :o and k.card_id = :c"),
            {"o": org, "c": card.card_id}).one()


def test_a_question_card_offers_your_wrong():
    assert "wrong" in actions.QUESTION_OFFERS


def test_wrong_on_a_question_card_retires_it_and_keeps_your_verdict_bound_to_the_question(world, cards):
    store, org, _registry, anchor, _events, card = _question_card(world, cards)
    [asked] = _questions(store, org, anchor)
    out = _press(store, org, card)
    assert out["ok"] is True and out["state"] == "acted" and out["question_id"] == asked.question_id, out
    assert tuple(_row(store, org, card)) == ("acted", "acted"), "the card taken down, its signal acted"
    with store.engine.connect() as c:
        retired = Q.by_id(c, org, asked.question_id)
        verdict = c.execute(text(
            "select feedback_id, capability_id, rule_id, authority_pack_revision, cause, reason, occurred_at "
            "from card_feedback_verdicts where org_id = :o and card_id = :k"), {"o": org, "k": card.card_id}).one()
    assert (retired.state, retired.retired_why, retired.retired_at) == (Q.RETIRED, Q.CALLED_WRONG, AT)
    assert (verdict.feedback_id, verdict.capability_id, verdict.rule_id, verdict.authority_pack_revision) == (
        V.feedback_id_of(org, card.card_id), "expert.file_review", "founder_question", 0)
    assert (verdict.cause, verdict.reason, verdict.occurred_at) == ("wrong", "not_relevant", AT)
    assert "correction_id" not in out, "no words: a verdict on the file, no correction"


def test_your_words_on_a_question_card_are_a_correction_of_its_file(world, cards):
    store, org, _registry, anchor, _events, card = _question_card(world, cards)
    out = _press(store, org, card, reason="wrong_subject", words=WORDS)
    with store.engine.connect() as c:
        [kept] = C.standing_for(c, org, anchor).corrections
    assert out["correction_id"] == kept.correction_id
    assert (kept.file_id, kept.card_id, kept.reason, kept.words, kept.scope) == (
        anchor, card.card_id, "wrong_subject", WORDS, C.FILE)
    assert kept.feedback_id == V.feedback_id_of(org, card.card_id)


def test_calibration_never_reads_a_questions_verdict(world, cards):
    """Calibration's judgments are the audited decision cards' (`reason/authority.AUDITED_CARD_JUDGMENTS_CTES`); a
    question binds no pack revision and its rule is no pack's, so its verdict is in none of them."""
    from genios_engine.reason.authority import AUDITED_CARD_JUDGMENTS_CTES
    store, org, _registry, _anchor, _events, card = _question_card(world, cards)
    _press(store, org, card)
    with store.engine.connect() as c:
        judged = c.execute(text("with " + AUDITED_CARD_JUDGMENTS_CTES + " select card_id from canonical_judgments"),
                           {"o": org, "as_of": AT + timedelta(days=1)}).scalars().all()
    assert card.card_id not in judged


def test_a_later_review_asking_the_words_you_called_wrong_asks_nothing(world, cards):
    """The sweep's half (s16-F15): the same words asked again — no question filed, no signal, no card; the file is
    held with no card and counted so."""
    store, org, registry, anchor, events, card = _question_card(world, cards)
    _press(store, org, card)
    later = AT + timedelta(hours=1)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question=FIND_OUT)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=later)
    assert counts.get("expert_question_called_wrong") == 1 and not counts.get("expert_question_asked"), counts
    built = _build(store, cards, org, at=later)
    assert built["question_cards"] == 0, built
    with store.engine.connect() as c:
        open_signals = c.execute(text("select count(*) from signals where org_id = :o and rule_id = 'founder_question' "
                                      "and status = 'open'"), {"o": org}).scalar()
    assert open_signals == 0
    assert [(q.question, q.state, q.retired_why) for q in _questions(store, org, anchor)] == [
        (FIND_OUT, Q.RETIRED, Q.CALLED_WRONG)], "never asked again in its words"


def test_other_words_are_asked_on_a_card_of_their_own(world, cards):
    """The negative control: a question in other words is the file's to ask — on a new card, the old one decided."""
    store, org, registry, anchor, events, card = _question_card(world, cards)
    _press(store, org, card)
    later = AT + timedelta(hours=1)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=later)
    assert counts.get("expert_question_asked") == 1, counts
    built = _build(store, cards, org, at=later)
    assert built["question_cards"] == 1, built
