"""STEP-14 · the queue answers at an instant — what the app showed then, by the queue's own predicate.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_the_queue_answers_at_an_instant.py -q

Tree `yc2_w27_s14` M42.C4.L-data.V0.U01 (`deliver/store.CardStore.queue(…, eval_time=)`; s14-D4, s14-F2). The board
counted a card as passed when `cards.state` said open — not whether the app queue would show it: 6 of the 21
must-detect passes were cards the app never showed. A reader that wants "what did the app show at the sweep's
instant" must ask the queue itself, never a copy of its predicate: so the queue takes the instant. Wall clock when
none is given, as before.
"""
from __future__ import annotations

import os
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.deliver import pipeline
from genios_engine.deliver.store import CardStore
from tests.reason.expert.test_a_covered_file_decides_once import (  # noqa: F401 — fixtures
    NOW, _compile, _fund, _write, admitted, world)

pytestmark = pytest.mark.pg


@pytest.fixture
def cards():
    return CardStore(os.environ["GENIOS_TEST_DATABASE_URL"])


def test_the_queue_shows_what_the_app_showed_at_that_instant(world, cards):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-instant-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-instant-review-000"})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    with store.engine.connect() as c:
        card_id, expires = c.execute(text("select card_id, expires_at from cards where org_id = :o"), {"o": org}).one()
    shown = cards.queue(org, admin=True, record_impressions=False, eval_time=NOW)
    assert [r["card_id"] for r in shown] == [card_id]
    assert cards.queue(org, admin=True, record_impressions=False, eval_time=expires) == [], "its window had closed"
    assert cards.queue(org, admin=True, record_impressions=False) == [], "today, by the wall clock, long closed"
    with store.engine.connect() as c:
        assert c.execute(text("select count(*) from card_events where org_id = :o and kind = 'card.surfaced' "
                              "and cause = 'dashboard'"), {"o": org}).scalar() == 0, "a reader leaves no impression"


def test_a_card_the_app_would_not_show_is_not_shown_at_any_instant(world, cards):
    store, org, registry, _ = world
    anchor, _situations, events = _fund(store, org)
    _write(store, org, anchor, "ffp-fund-instant-review-000", events)
    _compile(store, org, registry, covered={anchor: "ffp-fund-instant-review-000"})
    pipeline.build_cards_for_org(graph=store, card_store=cards, org_id=org, eval_time=NOW)
    with store.engine.begin() as c:
        c.execute(text("update cards set surfaces = array['ask', 'api'] where org_id = :o"), {"o": org})
    assert cards.queue(org, admin=True, record_impressions=False, eval_time=NOW) == []
    assert cards.queue(org, admin=True, record_impressions=False, eval_time=NOW + timedelta(hours=1)) == []
