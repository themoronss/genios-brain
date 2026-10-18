"""STEP-14 fix · a material version pushed today spends the day's push budget, as a new card does.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_a_version_push_spends_the_budget.py -q

Tree `yc2_w27_s14` M42.C3.L-integration.V2.U08 (the STEP-14 crosscheck, finding 12). `deliver/router.budget_full` — the
per-seat daily push budget — counted the cards CREATED today; a file's card is created once and versioned after, so a
material version pushed today spent nothing and the budget never bound it. Now a card versioned MATERIALLY today counts
as one of the day's, beside the cards created today (each card once). A quiet version (a rewording, a renewal) is
never pushed and counts nothing. The bound, declared: a push CHANNEL still never carries a version — the outbox
deduplicates on (card, channel, recipient) and the impression is recorded once per card; production registers the
in-app surface only, so it is latent — owner STEP-15 (the channels, with the brief).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.deliver import router

pytestmark = pytest.mark.pg
ORG = "org_s14_version_budget"
TODAY = datetime(2026, 10, 14, 9, tzinfo=timezone.utc)


@pytest.fixture
def store():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    engine = create_engine(url)

    def clean():
        with engine.begin() as c:
            c.execute(text("delete from card_events where org_id = :o"), {"o": ORG})
            c.execute(text("delete from cards where org_id = :o"), {"o": ORG})
            c.execute(text("delete from orgs where id = :o"), {"o": ORG})
    clean()
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name, email) values (:o, 'vb', 'vb@example.test')"), {"o": ORG})
    yield type("S", (), {"engine": engine})()
    clean()
    engine.dispose()


def _card(c, card_id, created):
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, assignee, level, urgency_band, headline, situation, score, "
        "why, actions, artifact, state, expires_at, created_at, file_id) values (:c, :s, :o, 'seat_1', 'prescriptive', "
        "'high', 'h', 's', 50, cast('[]' as jsonb), cast('[]' as jsonb), cast('{}' as jsonb), 'surfaced', :exp, :at, "
        ":f)"), {"c": card_id, "s": "sig_" + card_id, "o": ORG, "exp": created + timedelta(days=9), "at": created,
                 "f": "file_" + card_id})


def _versioned(c, card_id, at, material):
    c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, occurred_at) values "
                   "(:i, :c, :o, 'card.versioned', :cause, 'system', cast(:d as jsonb), :at)"),
              {"i": f"cev_{card_id}_{at:%H%M}", "c": card_id, "o": ORG, "cause": "updated" if material else "renewed",
               "d": json.dumps({"material": material, "version": 2}), "at": at})


def test_a_material_version_today_spends_the_budget(store):
    with store.engine.begin() as c:
        _card(c, "c_old", TODAY - timedelta(days=3))
        _versioned(c, "c_old", TODAY + timedelta(hours=1), material=True)
    assert router.budget_full(store, ORG, "seat_1", TODAY, 1), "the version pushed today is one of the day's"
    assert not router.budget_full(store, ORG, "seat_1", TODAY, 2)


def test_a_quiet_version_spends_nothing(store):
    """⛔ THE NEGATIVE CONTROL: a renewal is never pushed, and counts nothing."""
    with store.engine.begin() as c:
        _card(c, "c_old", TODAY - timedelta(days=3))
        _versioned(c, "c_old", TODAY + timedelta(hours=1), material=False)
        _versioned(c, "c_old", TODAY - timedelta(days=1), material=True)          # yesterday's: not today's
    assert not router.budget_full(store, ORG, "seat_1", TODAY, 1)


def test_a_card_created_and_versioned_today_counts_once(store):
    with store.engine.begin() as c:
        _card(c, "c_new", TODAY)
        _versioned(c, "c_new", TODAY + timedelta(hours=2), material=True)
    assert router.budget_full(store, ORG, "seat_1", TODAY, 1) and not router.budget_full(store, ORG, "seat_1", TODAY, 2)
