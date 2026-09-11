"""CardStore.history / CardStore.timeline against real Postgres.

The route tests double the store; these run the SQL. They need GENIOS_TEST_DATABASE_URL (a local
scratch database, never production) and SKIP without it. Every test seeds its own orgs and deletes
them afterwards — the org foreign key cascades to cards and card_events.
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
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres card history tests skipped")
    store = CardStore(url)
    org, other = f"org_hist_{uuid.uuid4().hex[:8]}", f"org_hist_{uuid.uuid4().hex[:8]}"
    with store.engine.begin() as c:
        for o in (org, other):
            c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": o})
    yield store, org, other
    with store.engine.begin() as c:
        c.execute(text("delete from orgs where id = any(:o)"), {"o": [org, other]})


def seed_card(store, org, card_id, *, state, assignee=None, created=None, expires=None,
              resolved=None, surfaces=("app", "agent", "ask", "api")):
    with store.engine.begin() as c:
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, assignee, level, urgency_band, "
            "headline, situation, score, state, created_at, expires_at, resolved_at, surfaces) "
            "values (:id, :sig, :o, :a, 'prescriptive', 'high', :h, 'situation', 60, :state, "
            ":created, :expires, :resolved, :surfaces)"),
            {"id": card_id, "sig": f"sig_{card_id}", "o": org, "a": assignee,
             "h": f"headline {card_id}", "state": state,
             "created": created or NOW - timedelta(days=2),
             "expires": expires or NOW + timedelta(days=5),
             "resolved": resolved, "surfaces": list(surfaces)})


def seed_event(store, org, card_id, kind, *, cause=None, actor="system", detail=None, at):
    with store.engine.begin() as c:
        c.execute(text(
            "insert into card_events (id, card_id, org_id, kind, cause, actor_id, detail, "
            "occurred_at) values (:id, :c, :o, :k, :cause, :a, cast(:d as jsonb), :at)"),
            {"id": f"cev_{uuid.uuid4().hex}", "c": card_id, "o": org, "k": kind,
             "cause": cause, "a": actor, "d": json.dumps(detail or {}), "at": at})


def ids(rows):
    return [r["card_id"] for r in rows]


def test_history_holds_every_closed_card_and_nothing_live(env):
    store, org, other = env
    seed_card(store, org, f"{org}_acted", state="acted")
    seed_card(store, org, f"{org}_resolved", state="resolved", resolved=NOW - timedelta(hours=1))
    seed_card(store, org, f"{org}_expired", state="expired", expires=NOW - timedelta(days=1))
    # Still `queued`, but past its deadline: the sweep has not run, the card is history anyway.
    seed_card(store, org, f"{org}_lapsed", state="queued", expires=NOW - timedelta(hours=2))
    seed_card(store, org, f"{org}_live", state="queued")
    seed_card(store, org, f"{org}_agent_only", state="acted", surfaces=("agent",))
    seed_card(store, other, f"{other}_acted", state="acted")

    rows = store.history(org, admin=True)
    by_id = {r["card_id"]: r for r in rows}

    assert set(by_id) == {f"{org}_acted", f"{org}_resolved", f"{org}_expired", f"{org}_lapsed"}
    assert by_id[f"{org}_lapsed"]["state"] == "expired"
    assert ids(store.history(org, admin=True, states=("resolved",))) == [f"{org}_resolved"]


def test_the_last_action_is_the_newest_outcome_not_an_impression(env):
    store, org, _ = env
    cid = f"{org}_c"
    seed_card(store, org, cid, state="acted")
    seed_event(store, org, cid, "card.created", at=NOW - timedelta(hours=6))
    seed_event(store, org, cid, "human.card_action", cause="snooze", actor="founder@x.com",
               detail={"until": "later"}, at=NOW - timedelta(hours=4))
    seed_event(store, org, cid, "human.card_action", cause="do_it_myself", actor="founder@x.com",
               detail={"surface": "desktop"}, at=NOW - timedelta(hours=2))
    seed_event(store, org, cid, "card.surfaced", cause="dashboard", at=NOW - timedelta(hours=1))

    row = store.history(org, admin=True)[0]
    assert row["last_action"] == "do_it_myself"
    assert row["last_actor"] == "founder@x.com"
    assert row["last_detail"] == {"surface": "desktop"}
    assert row["closed_at"] == row["last_event_at"]


def test_a_member_sees_their_own_and_unassigned_cards_only(env):
    store, org, _ = env
    seed_card(store, org, f"{org}_mine", state="acted", assignee="seat_a")
    seed_card(store, org, f"{org}_theirs", state="acted", assignee="seat_b")
    seed_card(store, org, f"{org}_unrouted", state="acted")

    assert set(ids(store.history(org, assignee="seat_a"))) == {f"{org}_mine", f"{org}_unrouted"}
    assert len(store.history(org, assignee="seat_a", admin=True)) == 3


def test_history_is_newest_first_windowed_and_paged(env):
    store, org, _ = env
    for i, hours in enumerate((30, 10, 20)):
        cid = f"{org}_{i}"
        seed_card(store, org, cid, state="acted")
        seed_event(store, org, cid, "human.card_action", cause="do_it_myself",
                   at=NOW - timedelta(hours=hours))
    seed_card(store, org, f"{org}_old", state="acted")
    seed_event(store, org, f"{org}_old", "human.card_action", cause="wrong",
               at=NOW - timedelta(days=40))

    since = NOW - timedelta(days=30)
    assert ids(store.history(org, admin=True, since=since)) == [f"{org}_1", f"{org}_2", f"{org}_0"]
    assert ids(store.history(org, admin=True, since=since, limit=1, offset=1)) == [f"{org}_2"]


def test_timeline_is_oldest_first_and_scoped_to_the_org(env):
    store, org, other = env
    cid = f"{org}_c"
    seed_card(store, org, cid, state="acted")
    seed_event(store, org, cid, "human.card_action", cause="do_it_myself", at=NOW - timedelta(hours=1))
    seed_event(store, org, cid, "card.created", at=NOW - timedelta(hours=3))
    # Same card id under another tenant: must never leak into this org's timeline.
    seed_event(store, other, cid, "card.surfaced", cause="dashboard", at=NOW - timedelta(hours=2))

    events = store.timeline(org, cid)
    assert [e["kind"] for e in events] == ["card.created", "human.card_action"]
    assert store.timeline(other, cid)[0]["kind"] == "card.surfaced"
