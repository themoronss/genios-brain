"""STEP-14 fix · a refused version leaves the file's card where it was — never replaced in the same pass.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_refused_version_leaves_the_card_where_it_was.py -q

Tree `yc2_w27_s14` M43.C4.L-integration.V1.U06 (fix of M43.C4.L-integration.V1.U02 × M42.C3.L-integration.V2.U03; the
STEP-14 crosscheck, finding 3). The reason side retires the file's old signal and hands the file on; the pipeline then
refuses the next version by the card contract (`continue` before `_version_file_card`) — and the end of the pass,
finding a file card on a closed signal that no version reached, expired it REPLACED. Nothing in its place; History
said "replaced"; the refused signal stayed open and was refused, and kept, again every pass (2 rows after 2 passes);
and the health check blamed the reason writers. The comment said the opposite, and its test asserted the headline,
the versions and the count — never the state.

Now a file whose version the contract refused this pass keeps its card as it was: not expired, its words, its state,
its history unchanged (it lapses by its own window, as any card), and counted `file_cards_kept_on_refusal`. A
refusal is kept ONCE per writer, card and rule (`platform/card_refusals.record`). The health check that names the
contract says which file cards wait behind a refused version; the one that counts REPLACED never sees them.
"""
from __future__ import annotations

import importlib
import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _write, admitted, world)
from tests.reason.expert.test_a_file_keeps_one_decision import FIRST, OTHER_MOVE, SECOND

pytestmark = pytest.mark.pg


def _state(store, org, card_id):
    with store.engine.connect() as c:
        row = c.execute(text("select state, headline, version from cards where card_id = :c"), {"c": card_id}).one()
        events = [tuple(r) for r in c.execute(text(
            "select kind, cause from card_events where card_id = :c and kind in ('card.expired', 'card.versioned') "
            "order by occurred_at, id"), {"c": card_id})]
        n = c.execute(text("select count(*) from cards where org_id = :o"), {"o": org}).scalar()
        kept = c.execute(text("select count(*) from card_refusals where org_id = :o"), {"o": org}).scalar()
    return tuple(row), events, n, kept


def _a_card_then_a_refused_decision(world):
    store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    with store.engine.connect() as c:
        card_id, = c.execute(text("select card_id from cards where org_id = :o"), {"o": org}).one()
    before = _state(store, org, card_id)[0]
    _write(store, org, anchor, SECOND, events, next_move={**OTHER_MOVE, "what": "Confirm party.role with Arjun"})
    later = NOW + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: SECOND}, at=later)
    return store, org, cards, card_id, before, later


def test_a_refused_decision_leaves_the_files_card_as_it_was(world):
    store, org, cards, card_id, before, later = _a_card_then_a_refused_decision(world)
    out = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=later)
    assert out["refused_contract:internal"] == 1 and out["versioned"] == 0, out
    assert (out["file_cards_replaced"], out["file_cards_kept_on_refusal"]) == (0, 1), out
    row, events, n, kept = _state(store, org, card_id)
    assert row == before and before[0] == "queued", "its state, its words, its version — as they were"
    assert events == [] and n == 1, "never expired, never replaced, no second card"
    assert kept == 1


def test_a_refusal_is_kept_once_however_many_passes_refuse_it(world):
    store, org, cards, card_id, before, later = _a_card_then_a_refused_decision(world)
    for n in range(3):
        out = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org,
                                           eval_time=later + timedelta(minutes=n))
        assert out["refused_contract:internal"] == 1 and out["file_cards_replaced"] == 0, out
    row, events, _n, kept = _state(store, org, card_id)
    assert (row, events, kept) == (before, [], 1), "one row per writer, card and rule"
    from genios_engine.contracts.card_contract import Refusal
    from genios_engine.platform import card_refusals
    with store.engine.begin() as c:
        ref = c.execute(text("select ref from card_refusals where org_id = :o"), {"o": org}).scalar()
        assert card_refusals.record(c, org_id=org, writer=card_refusals.PIPELINE, ref=ref,
                                    refusals=(Refusal("internal", "party.role"), Refusal("money", "fee"))) == 1, \
            "the same refusal adds nothing; another rule of the same card is its own"


def test_a_refused_question_leaves_the_files_card_as_it_was(world):
    from tests.reason.expert.test_a_held_file_asks import _find_out
    store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    with store.engine.connect() as c:
        card_id, = c.execute(text("select card_id from cards where org_id = :o"), {"o": org}).one()
    before = _state(store, org, card_id)[0]
    _find_out(store, org, anchor, "ffp-fund-findout-review-000", events, question="Is the party.role still open?")
    later = NOW + timedelta(hours=6)
    _compile(store, org, registry, covered={anchor: "ffp-fund-findout-review-000"}, at=later)
    out = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=later)
    assert out["refused_contract:internal"] == 1 and out["question_cards"] == 0, out
    assert (out["file_cards_replaced"], out["file_cards_kept_on_refusal"]) == (0, 1), out
    row, events, n, _kept = _state(store, org, card_id)
    assert (row, events, n) == (before, [], 1)


def test_a_file_whose_signal_closed_with_no_refusal_is_still_replaced(world):
    """⛔ THE NEGATIVE CONTROL: only a refusal keeps the card — a file card whose signal closed and that no version
    reached, with nothing refused, is still closed at the end of the pass, as before."""
    store, org, registry, _ = world
    cards = CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    with store.engine.begin() as c:
        c.execute(text("update signals set status = 'expired' where org_id = :o"), {"o": org})
    out = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW + timedelta(hours=1))
    assert (out["file_cards_replaced"], out["file_cards_kept_on_refusal"]) == (1, 0), out


def test_the_health_check_names_the_contract_not_the_reason_writers(world):
    ph = importlib.import_module("scripts.pipeline_health")
    store, org, cards, card_id, _before, later = _a_card_then_a_refused_decision(world)
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=later)
    with store.engine.connect() as c:
        replaced = ph.check_no_file_card_is_replaced(c, org)
        refused = ph.check_what_the_card_contract_refused(c, org)
    assert replaced.ok, replaced
    assert refused.ok and "1 file card(s) wait on their last words behind a refused version" in refused.measured, \
        refused
    assert any(card_id in line for line in refused.detail), refused.detail
