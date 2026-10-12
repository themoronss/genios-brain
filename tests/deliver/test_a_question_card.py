"""STEP-13 · a held file asks you its question on its own card — the file's one card.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/deliver/test_a_question_card.py

Tree `yc2_w27_s13` M36.C2.L-interface.V3.U05 (`deliver/pipeline`: `question_card`, `_build_question_cards`;
`06` D60, `03` F184). Each open question signal with no live card gets one, through its own door
(`deliver/store.QUESTION_CARD_SQL`): the question as its headline, the file as the expert read it — checked,
labelled an inference — as its situation, the Investigation lane, `review` (a request for one answer, never an
instruction) and an Answer action. A pass later builds nothing again; the same question re-asked keeps its
card; a new question replaces it; a decision retires it and the file's decision card is built through the
decision's door. The pass's lane recall stays balanced: a question card is a card.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.contracts.expert_review import ExpertReview
from genios_engine.deliver import pipeline
from genios_engine.deliver.store import QUESTION_CARD_BUILDER, CardStore
from genios_engine.reason.expert import asks
from genios_engine.reason.expert.decide import SITUATION_IS
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _open_signals, _review, world)
from tests.reason.expert.test_a_held_file_asks import FIND_OUT, HELD_Q, _find_out, _held, _questions, _write
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401

pytestmark = pytest.mark.pg


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _build(store, cards, org, at=NOW):
    return pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=at)


def _cards(store, org):
    with store.engine.connect() as c:
        return c.execute(text(
            "select card_id, signal_id, state, level, headline, situation, why, actions, output_lane, "
            "builder_version, render_mode, abstained_because, surfaces, assignee, expires_at from cards "
            "where org_id = :o "
            "order by created_at, card_id"), {"o": org}).all()


def _queued(cards, org, at):
    import genios_engine.deliver.store as store_module

    class _Clock(store_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return at
    original = store_module.datetime
    store_module.datetime = _Clock
    try:
        return [r["card_id"] for r in cards.queue(org, admin=True, record_impressions=False)]
    finally:
        store_module.datetime = original


def _asked(world):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    return store, org, registry, anchor, events


def test_a_held_file_asks_its_question_on_its_own_card(world, cards):
    store, org, _registry, anchor, _events = _asked(world)
    counts = _build(store, cards, org)
    assert counts["question_cards"] == 1 and counts["built"] == 1, counts
    assert counts["lane_recall_balanced"] is True and counts["cards_output_lane_investigation"] == 1
    [card] = _cards(store, org)
    [question] = _questions(store, org, anchor)
    [signal] = _open_signals(store, org, anchor)
    assert (card.signal_id, card.headline, card.level, card.output_lane, card.builder_version,
            card.render_mode) == (signal.signal_id, FIND_OUT, "review", "investigation", QUESTION_CARD_BUILDER,
                                  "question")
    assert card.situation and card.abstained_because == question.why
    assert card.actions[0] == {"type": "answer", "label": "Answer", "question_id": question.question_id}
    assert [a["type"] for a in card.actions] == list(pipeline.QUESTION_ACTIONS)
    assert card.why[0] == {"sentence": "headline", "question": FIND_OUT, "because": question.why,
                           "source": "expert_check"}
    assert "agent" not in card.surfaces
    with store.engine.connect() as c:
        held_until = c.execute(text("select authority_expires_at from signals where org_id = :o and "
                                    "signal_id = :s"), {"o": org, "s": signal.signal_id}).scalar()
    assert card.expires_at <= held_until, "never outlives the authority it is read by"
    assert _queued(cards, org, NOW) == [card.card_id], "it reaches the queue"


def test_a_held_review_asks_the_checks_question_over_the_files_checked_reading(world, cards):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    review = ExpertReview.from_mapping(_review(sorted(events)[0]))
    held = _held(review)
    _write(store, org, anchor, "ffp-fund-held-review-00000", events, checked=held)
    _compile(store, org, registry, covered={anchor: "ffp-fund-held-review-00000"})
    _build(store, cards, org)
    [card] = _cards(store, org)
    assert (card.headline, card.situation) == (HELD_Q, held.words.situation)
    # ⛔ RESTATED by M36.C2.L-logic.V2.U10 (`03` X10): `because` was the check's internal reason ("misquoted
    # (fact 1)", and with a real check "misquoted: <the model's quote> (fact 1)"). One closed phrase, for you.
    assert card.why[0]["because"] == asks.WHY_NOT_CONFIRMED == card.abstained_because
    assert card.why[1] == {"sentence": "situation", "inference": SITUATION_IS, "source": "expert_check"}


def test_a_pass_later_builds_nothing_again(world, cards):
    store, org, _registry, _anchor, _events = _asked(world)
    _build(store, cards, org)
    again = _build(store, cards, org, at=NOW + timedelta(hours=1))
    assert (again["question_cards"], again["built"], again["already_built"], again["build_in_progress"]) == (
        0, 0, 0, 0), "a carded question is not even selected"
    assert len(_cards(store, org)) == 1


def test_the_same_question_asked_again_keeps_its_card(world, cards):
    store, org, registry, anchor, _events = _asked(world)
    _build(store, cards, org)
    [first] = _cards(store, org)
    with store.engine.begin() as c:            # the gate has no memory of it: decided again, re-bound
        c.execute(text("delete from reasoning_fingerprints where org_id = :o"), {"o": org})
    later = NOW + timedelta(hours=30)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"}, at=later)
    assert _build(store, cards, org, at=later)["question_cards"] == 0
    [card] = _cards(store, org)
    assert card.card_id == first.card_id and card.state == "queued"
    assert _queued(cards, org, later) == [card.card_id], "re-bound, still read through its door"


def test_a_new_question_replaces_the_old_card(world, cards):
    store, org, registry, anchor, events = _asked(world)
    _build(store, cards, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    later = NOW + timedelta(hours=1)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=later)
    assert _build(store, cards, org, at=later)["question_cards"] == 1
    old, new = _cards(store, org)
    assert old.state == "expired" and (new.state, new.headline) == ("queued", "Who at the fund decides?")
    assert _queued(cards, org, later) == [new.card_id]


def test_a_decision_retires_the_question_card(world, cards):
    from tests.reason.expert.test_a_covered_file_decides_once import _write as _write_act
    store, org, registry, anchor, events = _asked(world)
    _build(store, cards, org)
    _write_act(store, org, anchor, "ffp-fund-act-review-000000", events)
    later = NOW + timedelta(hours=1)
    _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"}, at=later)
    counts = _build(store, cards, org, at=later)
    assert counts["question_cards"] == 0
    question_card, *rest = _cards(store, org)
    assert (question_card.builder_version, question_card.state) == (QUESTION_CARD_BUILDER, "expired")
    assert all(c.builder_version != QUESTION_CARD_BUILDER for c in rest)


def test_a_question_goes_where_the_files_decision_would(world, cards, monkeypatch):
    """Routed by the same rule as every card (`router.resolve_assignee`), over the file's own facts."""
    from genios_engine.deliver import router
    store, org, _registry, anchor, _events = _asked(world)
    asked_about = []

    def _owner(_store, _org, facts, attrs):
        asked_about.append((facts, attrs))
        return "seat_founder", "rule1_owner"
    monkeypatch.setattr(router, "resolve_assignee", _owner)
    _build(store, cards, org)
    [card] = _cards(store, org)
    assert card.assignee == "seat_founder" and len(asked_about) == 1


def test_on_the_shadow_lane_no_question_and_no_card(world, cards):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"}, live=False)
    counts = _build(store, cards, org)
    assert counts["question_cards"] == 0 and _cards(store, org) == []


def test_a_pass_that_cannot_read_its_questions_says_so_and_keeps_going(monkeypatch):
    """⛔ The read failing costs no decision card: counted `questions_unread`, never raised."""
    from types import SimpleNamespace
    monkeypatch.setattr(pipeline, "ensure_default", lambda *_a: None)
    monkeypatch.setattr(pipeline, "_open_signals_without_cards", lambda *_a: [])
    monkeypatch.setattr(pipeline, "_open_situations_without_cards", lambda *_a: [])
    monkeypatch.setattr(pipeline, "_activated_features", lambda *_a: frozenset())
    monkeypatch.setattr(pipeline, "_cohort_absorbed", lambda *_a: set())
    monkeypatch.setattr(pipeline, "_tenant_identities", lambda *_a: ())
    graph = SimpleNamespace(engine=None, record_cost=lambda **_k: None)
    out = pipeline.build_cards_for_org(graph=graph, card_store=SimpleNamespace(), org_id="org_q",
                                       registry=object(), eval_time=NOW)
    assert out["questions_unread"] == 1 and out["question_cards"] == 0


WITHHELD = "Arjun is deciding whether Tiger Global co-leads the round"


def _withheld(world):
    """A find-out file whose reading the check withheld — a party the file never names (`03` X06's run)."""
    from genios_engine.contracts import claim_check as C
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    checked = C.CheckedReview(
        verdicts=(C.LineVerdict("situation", C.DROPPED, C.UNSUPPORTED, "name:Tiger"),), fate=C.SHOWN,
        cited=(sorted(events)[0],), question=FIND_OUT,
        words=C.CardWords(headline=FIND_OUT, situation=None, done_when=None, draft=None, to=None,
                          evidence=(sorted(events)[0],)))
    _write(store, org, anchor, "ffp-fund-withheld-review-0", events, checked=checked, mode="find_out", draft=None,
           frames={"primary": WITHHELD, "rivals": ["a polite check-in"]},
           next_move={"who": "you", "what": FIND_OUT, "for_whom": "Arjun", "by_when": None})
    _compile(store, org, registry, covered={anchor: "ffp-fund-withheld-review-0"})
    return store, org, anchor


def test_a_find_out_card_never_shows_the_reading_the_check_withheld(world, cards):
    """⛔ `03` X06 (M36.C2.L-logic.V2.U10): the check dropped the reading (a party the file never names), yet the
    card's situation was the question's raw `why` — "the expert cannot read this file on without your answer:
    <that reading>" — unlabelled. With no checked reading, the card says why it asks, in our closed words."""
    store, org, _anchor = _withheld(world)
    _build(store, cards, org)
    [card] = _cards(store, org)
    said = " ".join(str(x) for x in (card.headline, card.situation, card.abstained_because, card.why))
    assert "Tiger" not in said and WITHHELD not in said
    assert (card.headline, card.situation) == (FIND_OUT, asks.WHY_FIND_OUT)
    assert [w["sentence"] for w in card.why] == ["headline"], "no reading, so no inference label for one"


def test_a_question_filed_with_raw_words_is_carded_in_closed_ones(world, cards):
    """A question filed before its words were checked (its `why` the check's reason, or the raw reading) is
    carded with the closed phrase: no card text is raw prose."""
    store, org, anchor = _withheld(world)
    raw = "the expert cannot read this file on without your answer: " + WITHHELD
    with store.engine.begin() as c:
        c.execute(text("update founder_questions set why = :w where org_id = :o and file_id = :f"),
                  {"w": raw, "o": org, "f": anchor})
    _build(store, cards, org)
    [card] = _cards(store, org)
    assert card.abstained_because == card.why[0]["because"] == card.situation == asks.WHY_FIND_OUT
    assert "Tiger" not in " ".join(str(x) for x in (card.situation, card.abstained_because, card.why))
