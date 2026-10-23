"""A meeting follow-up card opens — GeniOS-011 S36.U1 (`l5-meeting-followup-cards-fail-every-door`).

The P-16 post-meeting follow-up (`reason/meetings/passes.emit_followups`) is a durable card written by
`reason/team/emit.emit_situation` with `capability_id='meeting.followup'`: its signal's rule id IS that
capability and it has no reasoning run. The situation door (`deliver/store.SITUATION_CARD_SQL`) admitted only a
`team.*` / `verify.*` capability, so the follow-up passed no door at all — never in `GET /cards`, and the desktop
moment's pinned `open_card` (`/dashboard/cards?card=<id>`) answered 404 "card not found or no longer actionable".
The door now keys on what only that writer writes — its builder stamp, no reasoning run, rule id = capability —
and never on a capability's prefix.

Driven through the REAL pass over a real transcript, then read back through every route the card has: the queue
(the seat's own and the admin's), `GET /cards`, `GET /cards/{id}` and one action. The door is not widened past its
builder: a look-alike with another builder, or with a rule id that is not its capability, stays hidden.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/scratch pytest tests/test_a_meeting_followup_card_opens_pg.py
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

#: ⛔ Read when each test runs, never at import (`YC-II W27/03` F142): set by `_clock`.
NOW: datetime = None  # type: ignore[assignment]
_ORGS: list[str] = []


@pytest.fixture(autouse=True)
def _clock():
    global NOW
    NOW = datetime.now(timezone.utc).replace(microsecond=0)


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import account_routes
    from genios_engine.api import auth_routes
    from genios_engine.api import routes
    app = FastAPI()
    for module in (auth_routes, account_routes, routes):
        app.include_router(module.router)
    yield TestClient(app)
    from genios_engine.platform.realtime import stop_realtime
    stop_realtime()
    for org in _ORGS:
        try:
            with _engine().begin() as c:
                c.execute(text("delete from orgs where id=:o"), {"o": org})
        except Exception:      # noqa: BLE001 — the scratch database is dropped after the run
            pass


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _founder(client) -> dict:
    uid = uuid.uuid4().hex[:8]
    res = client.post("/auth/register", json={"name": "Founder", "email": f"founder_{uid}@followup.test",
                                              "password": "founder-pass-1", "company": f"Followup {uid}"})
    assert res.status_code == 200, res.text
    body = res.json()
    _ORGS.append(body["org_id"])
    return {**body, "email": f"founder_{uid}@followup.test", "uid": uid}


def _a_meeting_raised_one_item(org: str, founder_email: str, uid: str) -> str:
    """One extracted transcript private to the founder: a meeting node and one commitment the meeting
    raised (a `raised_in` edge written by an org-wide event, its text an org fact). Returns its id."""
    meeting, item, ev, tid = (f"node_mtg_{uid}", f"node_cmt_{uid}", f"evt_mtg_{uid}", f"tr_{uid}")
    with _engine().begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, visibility_scope) values (:e, :o, 'conn', "
            "'gmail', 'message', :e, :e, '{}'::jsonb, :at, 'org')"),
            {"e": ev, "o": org, "at": NOW - timedelta(hours=2)})
        for node, typ, key, name in ((meeting, "meeting", f"gcal:{meeting}", "Board review prep"),
                                     (item, "commitment", f"commitment:{item}", "send the board deck")):
            c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, canonical_key, "
                           "display_name) values (:n, 1, :o, :t, :k, :d)"),
                      {"n": node, "o": org, "t": typ, "k": key, "d": name})
        c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, from_node_id, "
                       "to_node_id, created_by_event_id) values (:v, :e, :o, 'raised_in', :f, :t, :ev)"),
                  {"v": f"ev_{uid}", "e": f"e_{uid}", "o": org, "f": item, "t": meeting, "ev": ev})
        for field, value in (("commitment.text", "send the board deck"), ("commitment.status", "open")):
            fid = uuid.uuid4().hex[:12]
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, "
                "visibility_scope, created_by_event_id) values (:v, :f, :o, :s, :field, cast(:val as jsonb), "
                "'org', :ev)"),
                {"v": "fv_" + fid, "f": "f_" + fid, "o": org, "s": item, "field": field,
                 "val": json.dumps(value), "ev": ev})
        c.execute(text(
            "insert into transcripts (transcript_id, org_id, source, source_ref, provider, status, scope, "
            "meeting_node_id, title, principals, meeting, event_ids, content_hash) values (:t, :o, 'upload', "
            ":t, 'granola', 'extracted', 'attendees', :m, 'Board review prep', cast(:p as text[]), "
            "cast(:mj as jsonb), cast(:ev as text[]), 'h1')"),
            {"t": tid, "o": org, "m": meeting, "p": [founder_email.lower()], "ev": [ev],
             "mj": json.dumps({"meeting_node_id": meeting, "title": "Board review prep"})})
    return tid


def _look_alike(org: str, assignee: str, *, card_id: str, builder: str, rule_id: str) -> None:
    """A card the situation writer did NOT write: open, unexpired, on the app surface, no reasoning run,
    a `meeting.followup` capability — differing from the writer's in exactly one clause the door keeps."""
    with _engine().begin() as c:
        c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
                       "eval_time, capability_id) values (:s, :o, :rule, 'n', 99, 'team', now(), "
                       "'meeting.followup')"), {"s": f"sig_{card_id}", "o": org, "rule": rule_id})
        c.execute(text("insert into cards (card_id, signal_id, org_id, assignee, level, urgency_band, headline, "
                       "situation, score, state, expires_at, builder_version, capability_key) values (:k, :s, "
                       ":o, :a, 'observation', 'high', 'look-alike', 'look-alike', 99, 'queued', "
                       "now() + interval '1 day', :b, 'meeting.followup')"),
                  {"k": card_id, "s": f"sig_{card_id}", "o": org, "a": assignee, "b": builder})


def _the_followup_card(org: str) -> dict:
    with _engine().connect() as c:
        rows = c.execute(text(
            "select k.card_id, k.assignee, k.builder_version, s.rule_id, s.capability_id, s.reasoning_run_id "
            "from cards k join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id "
            "where k.org_id = :o and k.capability_key = 'meeting.followup'"), {"o": org}).mappings().all()
    assert len(rows) == 1, rows
    return dict(rows[0])


def test_an_emitted_meeting_followup_is_in_the_queue_and_opens(client):
    from genios_engine.deliver.store import SITUATION_CARD_BUILDER
    from genios_engine.deliver.store import CardStore
    from genios_engine.reason.meetings import passes as MS
    founder = _founder(client)
    org, seat = founder["org_id"], founder["seat_id"]
    _a_meeting_raised_one_item(org, founder["email"], founder["uid"])

    assert MS.emit_followups(_engine(), None, org, now=NOW) == 1
    card = _the_followup_card(org)
    # the premise, read off the row: what emit_situation writes for a follow-up
    assert card["builder_version"] == SITUATION_CARD_BUILDER and card["reasoning_run_id"] is None
    assert card["rule_id"] == card["capability_id"] == MS.FOLLOWUP_CAPABILITY == "meeting.followup"
    assert card["assignee"] == seat

    store = CardStore(URL)
    for kwargs in ({"assignee": seat, "strict_seat": True}, {"assignee": seat}, {"admin": True}):
        queued = [r["card_id"] for r in store.queue(org, record_impressions=False, **kwargs)]
        assert card["card_id"] in queued, (kwargs, queued)
    assert (store.get_authoritative_card(card["card_id"], org) or {}).get("card_id") == card["card_id"]

    # the app's own routes: the queue, and the card the moment's pinned `open_card` opens
    listed = client.get("/cards", headers=H(founder["token"]))
    assert listed.status_code == 200, listed.text
    assert card["card_id"] in [r["card_id"] for r in listed.json()["cards"]]
    opened = client.get(f"/cards/{card['card_id']}", headers=H(founder["token"]))
    assert opened.status_code == 200, opened.text
    assert opened.json()["card_id"] == card["card_id"]
    assert opened.json()["headline"].startswith("Follow-ups from Board review prep")

    # and it can be acted on (deliver/actions reads the same door)
    acted = client.post(f"/cards/{card['card_id']}/action", json={"action": "snooze", "snooze_option": "4h"},
                        headers=H(founder["token"]))
    assert acted.status_code == 200, acted.text
    with _engine().connect() as c:
        assert c.execute(text("select state from cards where card_id = :k"),
                         {"k": card["card_id"]}).scalar() == "snoozed"


def test_the_door_admits_only_what_its_builder_wrote(client):
    from genios_engine.deliver.store import SITUATION_CARD_BUILDER
    from genios_engine.deliver.store import CardStore
    founder = _founder(client)
    org, seat, uid = founder["org_id"], founder["seat_id"], founder["uid"]
    other_builder, rule_not_capability = f"card_other_{uid}", f"card_rule_{uid}"
    _look_alike(org, seat, card_id=other_builder, builder="other.v1", rule_id="meeting.followup")
    _look_alike(org, seat, card_id=rule_not_capability, builder=SITUATION_CARD_BUILDER,
                rule_id="meeting.something_else")
    store = CardStore(URL)
    queued = {r["card_id"] for r in store.queue(org, admin=True, record_impressions=False)}
    for card_id in (other_builder, rule_not_capability):
        assert card_id not in queued, card_id
        assert store.get_authoritative_card(card_id, org) is None, card_id
        res = client.get(f"/cards/{card_id}", headers=H(founder["token"]))
        assert res.status_code == 404, (card_id, res.text)
