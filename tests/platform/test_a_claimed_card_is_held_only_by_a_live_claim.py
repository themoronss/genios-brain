"""STEP-14 fix · a card an agent claimed is held only while the claim is live — never forever.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_a_claimed_card_is_held_only_by_a_live_claim.py -q

Tree `yc2_w27_s14` M42.C1.L-data.V1.U04 (fix of M42.C1.L-data.V1.U03; the STEP-14 crosscheck, finding 6). An agent
claims the file's card; the file's next decision retires its signal; the agent's late result takes the V-08 path,
closes the claim and leaves the card `claimed`. `card_lifecycle._HELD` read the STATE, so from then on the card was
held: the sweep never freed it (it wants an open claim), it never lapsed (`LAPSE_STATES`), the end of the pass skipped
it (`state <> 'claimed'`), every later decision of the file waited (`version_waits`) and 0220's index — which counts
`claimed` — let no second card in. New in STEP-14 (at 6650b1c4 REPLACED closed it). Latent: no live agent in production.

Now `held` is read from a LIVE claim only (open, no result); a `claimed` card with none is versioned like any card
and comes back `surfaced`; the end of the pass may close one whose signal closed; and the health check counts the
cards `claimed` with no live claim (`check_no_card_is_claimed_by_nobody`).
"""
from __future__ import annotations

import importlib
import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import agent_api, pipeline
from genios_engine.deliver.store import CardStore
from genios_engine.platform import card_lifecycle
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _write, admitted, world)
from tests.reason.expert.test_a_file_keeps_one_decision import FIRST, OTHER_MOVE, SECOND

pytestmark = pytest.mark.pg


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def _card(store, org):
    with store.engine.connect() as c:
        return c.execute(text("select card_id, signal_id, state, version from cards where org_id = :o"),
                         {"o": org}).one()


def _claimed_then_decided_again(world, cards):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    first = _card(store, org)
    t1 = NOW + timedelta(hours=1)
    assert agent_api.claim(store, org, first.signal_id, "agent_s14", eval_time=t1)["ok"]
    _write(store, org, anchor, SECOND, events, next_move=OTHER_MOVE)
    t2 = t1 + timedelta(minutes=2)
    _compile(store, org, registry, covered={anchor: SECOND}, at=t2)
    waiting = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=t2)
    assert waiting["version_waits"] == 1, "while the claim is live, the file's next version waits"
    late = agent_api.result(store, org, first.signal_id, "agent_s14", "done", eval_time=t1 + timedelta(minutes=5))
    assert late.get("code") == "V-08", late
    return store, org, registry, anchor, first, t1


def test_a_claim_closed_late_holds_nothing(world, cards):
    store, org, _registry, anchor, first, t1 = _claimed_then_decided_again(world, cards)
    assert _card(store, org).state == "claimed", "the late result left the card claimed"
    with store.engine.connect() as c:
        assert card_lifecycle.file_card(c, org_id=org, file_id=anchor).held is False, "no live claim, nothing held"
    later = t1 + timedelta(hours=6)
    again = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=later)
    assert (again["versioned"], again["version_waits"]) == (1, 0), again
    card = _card(store, org)
    assert (card.card_id, card.state, card.version) == (first.card_id, "surfaced", 2), \
        "the file's next decision versions it, and it is in front of the founder again"
    assert card.signal_id != first.signal_id


def test_a_live_claim_still_holds_the_card(world, cards):
    """⛔ THE NEGATIVE CONTROL: an open claim, no result — the file's next version waits, as STEP-14 §8.7 says."""
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, FIRST, events)
    _compile(store, org, registry, covered={anchor: FIRST})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    first = _card(store, org)
    t1 = NOW + timedelta(hours=1)
    assert agent_api.claim(store, org, first.signal_id, "agent_s14", eval_time=t1)["ok"]
    with store.engine.connect() as c:
        assert card_lifecycle.file_card(c, org_id=org, file_id=anchor).held is True


def test_a_claimed_card_whose_signal_closed_is_closed_at_the_end_of_the_pass(world, cards):
    store, org, _registry, _anchor, first, t1 = _claimed_then_decided_again(world, cards)
    with store.engine.begin() as c:                      # the file's new decision retired too: no version to take
        c.execute(text("update signals set status = 'expired' where org_id = :o"), {"o": org})
    out = pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=t1 + timedelta(hours=6))
    assert out["file_cards_replaced"] == 1 and _card(store, org).state == "expired", out


def test_the_health_check_counts_cards_claimed_by_nobody(world, cards):
    ph = importlib.import_module("scripts.pipeline_health")
    store, org, _registry, _anchor, first, _t1 = _claimed_then_decided_again(world, cards)
    with store.engine.connect() as c:
        bad = ph.check_no_card_is_claimed_by_nobody(c, org)
    assert not bad.ok and bad.measured == "1 of 1 claimed card(s) have no live claim", bad
    assert bad.detail == [first.card_id]
    assert ph.check_no_card_is_claimed_by_nobody in ph.CHECKS
