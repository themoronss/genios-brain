"""STEP-06 · History says why each card left — every ending kind is an outcome it shows.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/deliver/test_history_says_why_a_card_left.py -q

Tree `yc2_w27_s06 · M24.C1.L-interface.V2.U02`. History's "last action" line is the newest event of a
kind in `CardStore._OUTCOME_KINDS`. Three endings were written and never shown (`speedrun008/YC-II
W27/` 03 F75): `card.resolved` (the team lane), `card.retired` (STEP-04's repair) and, from STEP-06 on,
`card.expired` (every expiry that used to write nothing). A card that left that way showed no reason.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.deliver.store import CardStore

NOW = datetime.now(timezone.utc)


@pytest.fixture
def env():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    store = CardStore(url)
    org = f"org_why_{uuid.uuid4().hex[:8]}"
    with store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": org})
    yield store, org
    with store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org})


def _card_that_left(store, org, card_id, *, state, kind, cause, actor="system"):
    with store.engine.begin() as c:
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
            "situation, score, state, created_at, expires_at, resolved_at) values "
            "(:id, :sig, :o, 'prescriptive', 'high', 'h', 's', 60, :state, :created, :expires, "
            " :resolved)"),
            {"id": card_id, "sig": f"sig_{card_id}", "o": org, "state": state,
             "created": NOW - timedelta(days=2), "expires": NOW + timedelta(days=5),
             "resolved": NOW - timedelta(hours=1) if state == "resolved" else None})
        c.execute(text(
            "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, "
            "occurred_at) values (:id, :c, :o, :k, :cause, :a, cast(:d as jsonb), :at)"),
            {"id": f"cev_{uuid.uuid4().hex}", "c": card_id, "o": org, "k": kind, "cause": cause,
             "a": actor, "d": json.dumps({}), "at": NOW - timedelta(minutes=30)})


@pytest.mark.parametrize("state, kind, cause", [
    ("expired", "card.expired", "replaced"),
    ("expired", "card.expired", "rule_cleared"),
    ("resolved", "card.resolved", "situation_cleared"),
    ("expired", "card.retired", "subject_is_us"),
    ("expired", "window.lapsed", "expired"),
    ("expired", "card.dismissed", "extension"),
])
def test_every_ending_kind_reaches_the_history_line(env, state, kind, cause):
    store, org = env
    card = f"{org}_{kind.replace('.', '_')}_{cause}"
    _card_that_left(store, org, card, state=state, kind=kind, cause=cause)
    [row] = [r for r in store.history(org, admin=True) if r["card_id"] == card]
    assert (row["last_event_kind"], row["last_action"]) == (kind, cause)


def test_the_kinds_are_the_writers_own():
    from genios_engine.platform import card_lifecycle as cl
    assert set(cl.KINDS) <= set(CardStore._OUTCOME_KINDS)
    assert "card.resolved" in CardStore._OUTCOME_KINDS
