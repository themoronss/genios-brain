"""STEP-14 · reason hands the file on — a file's new decision or question leaves its card to be VERSIONED, never
expires it REPLACED.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_a_file_hands_its_card_on.py -q

Tree `yc2_w27_s14` M42.C2.L-integration.V2.U02 (`reason/domain_shadow._emit_capability_signal`'s file branch) and
M42.C2.L-integration.V2.U05 (`reason/expert/asks`); STEP-14 §8.4 items 1-2, `03` F176, F52, F53, s14-F3, s14-F5.
Until STEP-14 the file branch retired the file's old decision AND expired its card REPLACED, and the pipeline built
the new signal a second card — 10 replacements over 9 golden cases, eight must-detect cases lost. Now reason
retires the old signal and leaves the card: delivery versions it onto the file's new signal (`deliver/store`,
M42.C3). The same advice is RENEWED, not replaced: inside its last twelve hours (`change_gate.FILE_RENEW_MARGIN`) a
standing decision is decided again and its advice re-emitted, so the card is quietly versioned before its window
lapses. A review that names no move still clears the file's decision, its card RULE_CLEARED (F175) — unless the file
asks: then the question is the card's next version. Our own failure clears nothing.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore
from genios_engine.reason.change_gate import FILE_RENEW_MARGIN
from genios_engine.reason.expert import decide as expert
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _open_signals, _write, admitted, world)
from tests.reason.expert.test_a_file_keeps_one_decision import FIRST, OTHER_MOVE, SECOND, expiries  # noqa: F401

pytestmark = pytest.mark.pg


def _carded(store, org, registry):
    """The file decided once from its first review, and its card built."""
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    [first] = _open_signals(store, org, anchor)
    pipeline.build_cards_for_org(graph=store, card_store=CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]),
                                 org_id=org, eval_time=NOW)
    [card] = _cards(store, org)
    assert (card.signal_id, card.state) == (first.signal_id, "queued"), card
    return anchor, events, first, card


def _cards(store, org):
    with store.engine.connect() as c:
        return c.execute(text("select card_id, signal_id, state from cards where org_id = :o order by created_at"),
                         {"o": org}).all()


def _signal_status(store, org, signal_id):
    with store.engine.connect() as c:
        return c.execute(text("select status from signals where org_id = :o and signal_id = :s"),
                         {"o": org, "s": signal_id}).scalar()


def test_other_advice_retires_the_signal_and_leaves_the_card_to_be_versioned(world, expiries):
    store, org, registry, _ = world
    anchor, events, first, card = _carded(store, org, registry)
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    [second] = _open_signals(store, org, anchor)
    assert counts.get("expert_emitted") == 1 and second.signal_id != first.signal_id, counts
    assert _signal_status(store, org, first.signal_id) == "expired"
    assert _cards(store, org) == [card], "the card stays, for delivery to version onto the new signal"
    assert expiries == [], "never expired REPLACED"


def test_the_same_advice_inside_its_renewal_margin_is_renewed_not_left_to_lapse(world, expiries):
    """`03` F52, F53: the change gate lets the file be decided again in its last twelve hours, and the file branch
    no longer answers "standing" there — the same advice is re-emitted, the card left to be versioned quietly."""
    store, org, registry, _ = world
    anchor, _events, first, card = _carded(store, org, registry)
    inside = NOW + timedelta(hours=expert.EXPIRY_HOURS) - FILE_RENEW_MARGIN + timedelta(hours=6)
    counts = _compile(store, org, registry, covered={anchor: FIRST}, at=inside)
    [renewed] = _open_signals(store, org, anchor)
    assert counts.get("expert_emitted") == 1 and renewed.signal_id != first.signal_id, counts
    assert _cards(store, org) == [card] and expiries == []


def test_the_same_advice_before_its_margin_stands(world, expiries):
    store, org, registry, _ = world
    anchor, _events, first, card = _carded(store, org, registry)
    before = NOW + timedelta(hours=expert.EXPIRY_HOURS) - FILE_RENEW_MARGIN - timedelta(hours=1)
    counts = _compile(store, org, registry, covered={anchor: FIRST}, at=before)
    assert counts.get("expert_unchanged") == 1, counts
    assert [s.signal_id for s in _open_signals(store, org, anchor)] == [first.signal_id]
    with store.engine.begin() as c:            # the gate forgets it: the file branch itself still says standing
        c.execute(text("delete from reasoning_fingerprints where org_id = :o"), {"o": org})
    again = _compile(store, org, registry, covered={anchor: FIRST}, at=before)
    assert again.get("expert_standing") == 1 and _cards(store, org) == [card] and expiries == [], again


def test_a_question_after_a_decision_leaves_the_card_to_the_question(world, expiries):
    store, org, registry, _ = world
    anchor, events, first, card = _carded(store, org, registry)
    _write(store, org, anchor, SECOND, events, mode="find_out")
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    assert counts.get("expert_cleared") == 1 and counts.get("expert_question_asked") == 1, counts
    assert [s.rule_id for s in _open_signals(store, org, anchor)] == ["founder_question"]
    assert _signal_status(store, org, first.signal_id) == "expired"
    assert _cards(store, org) == [card] and expiries == [], "the question is the card's next version"


@pytest.mark.parametrize("over", [{"mode": "wait", "next_move": None}, {"mode": "nothing", "next_move": None}],
                         ids=["wait", "nothing"])
def test_a_review_that_names_no_move_still_clears_the_card(world, expiries, over):
    """F175: the rule that fired no longer holds — no successor to version, so the card goes, said."""
    store, org, registry, _ = world
    anchor, events, first, card = _carded(store, org, registry)
    _write(store, org, anchor, SECOND, events, **over)
    counts = _compile(store, org, registry, covered={anchor: SECOND}, at=NOW + timedelta(hours=6))
    assert counts.get("expert_cleared") == 1, counts
    assert expiries == [("rule_cleared", (first.signal_id,))]
    assert [c.state for c in _cards(store, org)] == ["expired"]


# ── M42.C2.L-integration.V2.U05 · a file's QUESTION hands the file on (`reason/expert/asks`) ───────────────────
def _asked_and_carded(store, org, registry):
    """The file asks its question, and the question's card is built."""
    from tests.reason.expert.test_a_held_file_asks import _find_out
    anchor, _situations, events = _fund(store, org)
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"})
    [question] = _open_signals(store, org, anchor)
    pipeline.build_cards_for_org(graph=store, card_store=CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]),
                                 org_id=org, eval_time=NOW)
    [card] = _cards(store, org)
    assert (card.signal_id, card.state) == (question.signal_id, "queued"), card
    return anchor, events, question, card


def test_a_new_question_retires_the_old_and_leaves_its_card_to_the_new(world, expiries):
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, _ = world
    anchor, events, question, card = _asked_and_carded(store, org, registry)
    _find_out(store, org, anchor, "ffp-fund-findout-review-001", events, question="Who at the fund decides?")
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-001"}, at=NOW + timedelta(hours=1))
    [new] = _open_signals(store, org, anchor)
    assert new.signal_id != question.signal_id and _signal_status(store, org, question.signal_id) == "expired"
    assert _cards(store, org) == [card] and expiries == [], "never expired REPLACED: asked again, a version"


def test_a_decision_after_a_question_retires_it_and_leaves_its_card_to_the_decision(world, expiries):
    store, org, registry, _ = world
    anchor, events, question, card = _asked_and_carded(store, org, registry)
    _write(store, org, anchor, "ffp-fund-act-review-000000", events)
    counts = _compile(store, org, registry, covered={anchor: "ffp-fund-act-review-000000"},
                      at=NOW + timedelta(hours=1))
    assert counts.get("expert_question_retired") == 1 and counts.get("expert_emitted") == 1, counts
    assert [s.rule_id for s in _open_signals(store, org, anchor)] == ["file_review"]
    assert _signal_status(store, org, question.signal_id) == "expired"
    assert _cards(store, org) == [card] and expiries == [], "the decision is the card's next version"


def test_a_question_no_move_follows_still_closes_its_card(world, expiries):
    """A review that names no move and asks nothing: nothing will version the question's card, so it goes."""
    store, org, registry, _ = world
    anchor, events, question, _card = _asked_and_carded(store, org, registry)
    _write(store, org, anchor, "ffp-fund-wait-review-00000", events, mode="wait", next_move=None)
    _compile(store, org, registry, covered={anchor: "ffp-fund-wait-review-00000"}, at=NOW + timedelta(hours=1))
    assert _open_signals(store, org, anchor) == [] and [c.state for c in _cards(store, org)] == ["expired"]
    # ⛔ RESTATED by `yc2_w27_s14` M43.C4.L-integration.V2.U08 (the STEP-14 crosscheck, finding 13): it closed REPLACED,
    # and nothing replaced it — the health check failed on a path the code takes by design. It says why: settled.
    assert expiries == [("question_settled", (question.signal_id,))]


def test_a_question_whose_file_left_coverage_still_closes_its_card(world, expiries):
    """`03` X26: the file is no longer the expert's — its situations decide on their own — so its question's card
    goes with the question: nothing of the file's will version it."""
    from tests.reason.expert.test_a_held_file_asks import _other_file
    store, org, registry, _ = world
    _anchor, _events, question, _card = _asked_and_carded(store, org, registry)
    other, other_events = _other_file(store, org)
    _write(store, org, other, "ffp-programme-review-0000", other_events)
    _compile(store, org, registry, covered={other: "ffp-programme-review-0000"}, at=NOW + timedelta(hours=1))
    assert [c.state for c in _cards(store, org)] == ["expired"]
    # ⛔ RESTATED by M43.C4.L-integration.V2.U08 (finding 13): REPLACED said nothing replaced it — its own cause.
    assert ("left_coverage", (question.signal_id,)) in expiries
