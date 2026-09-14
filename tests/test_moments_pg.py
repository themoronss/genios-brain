"""P3 hot lane against real Postgres — the scenarios the build plan names (§5):

  1. the slice respects a private fact (seat 2 never sees seat 1's private fact or private touch),
     versions, deltas, and the slice.delta event a graph write emits;
  2. P-02 evaluate for a known counterparty, in shadow mode (display:false) and then shown, with
     `moments_display` round-tripping through the capture policy API;
  3. rate limits cap, reminders are exempt, DND suppresses; device moments are idempotent;
     feedback (incl. `useful`) reaches moment_feedback + L6's inbox; history shape (§2.6 pinned);
  4. SSE delivers moment.new live and replays with Last-Event-ID; revocation ends the stream.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_p3_a \\
        pytest tests/test_moments_pg.py -q
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.platform.auth import hash_key
from genios_engine.platform.config import get_settings

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

GRANT = "urn:ietf:params:oauth:grant-type:device_code"
_ORGS: list[str] = []
NOW = datetime.now(timezone.utc)


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import (account_routes, auth_routes, capture_routes, device_routes,
                                   moment_routes)
    app = FastAPI()
    for module in (auth_routes, account_routes, device_routes, capture_routes, moment_routes):
        app.include_router(module.router)
    settings = get_settings()
    old = settings.dashboard_url
    settings.dashboard_url = "https://app.genios.test"
    yield TestClient(app)
    settings.dashboard_url = old
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


# ── a workspace: owner + member, each with a signed-in device ──────────────────────────────────
def _register(client) -> dict:
    uid = uuid.uuid4().hex[:8]
    email = f"founder_{uid}@moments.test"
    res = client.post("/auth/register", json={"name": "Founder", "password": "founder-pass-1",
                                              "email": email, "company": f"Acme {uid}"})
    assert res.status_code == 200, res.text
    body = res.json()
    _ORGS.append(body["org_id"])
    with _engine().begin() as c:
        c.execute(text("update orgs set subscription_tier='startup' where id=:o"),
                  {"o": body["org_id"]})
    return {**body, "email": email}


def _join(client, owner: dict) -> dict:
    email = f"member_{uuid.uuid4().hex[:8]}@moments.test"
    inv = client.post(f"/api/org/{owner['org_id']}/members/invite",
                      json={"email": email, "role": "member"}, headers=H(owner["token"]))
    assert inv.status_code == 200, inv.text
    acc = client.post(f"/invites/{inv.json()['invite_token']}/accept",
                      json={"email": email, "name": "Member", "password": "member-pass-1"})
    assert acc.status_code == 200, acc.text
    return {**acc.json(), "email": email}


def _sign_in(client, seat: dict) -> dict:
    code = client.post("/v1/devices/code", json={
        "client_id": "genios-desktop", "device_name": "MacBook", "platform": "macos",
        "os_version": "15.1", "app_version": "0.1.0"}).json()
    ok = client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                     headers=H(seat["token"]))
    assert ok.status_code == 200, ok.text
    res = client.post("/v1/devices/token", json={"grant_type": GRANT,
                                                 "device_code": code["device_code"]})
    assert res.status_code == 200, res.text
    return res.json()


def _workspace(client, *, capture: bool = True) -> dict:
    owner = _register(client)
    member = _join(client, owner)
    ws = {"org": owner["org_id"], "owner": owner, "member": member,
          "owner_dev": _sign_in(client, owner), "member_dev": _sign_in(client, member)}
    if capture:
        r = client.put("/v1/capture/policy", json={"enabled": True}, headers=H(owner["token"]))
        assert r.status_code == 200, r.text
        for seat in (owner, member):
            r = client.put("/v1/capture/settings", json={"enabled": True},
                           headers=H(seat["token"]))
            assert r.status_code == 200, r.text
    return ws


# ── a small graph: two seats both talk to Priya @ Acme; the owner owes her a proposal ─────────
def _seed(ws: dict) -> dict:
    org = ws["org"]
    o_mail, m_mail = ws["owner"]["email"].lower(), ws["member"]["email"].lower()
    n = {k: f"node_{k}_{uuid.uuid4().hex[:8]}" for k in
         ("me1", "me2", "priya", "acme", "deal", "cmt", "mtg", "ravi")}
    nodes = [(n["me1"], "person", o_mail, "Founder"), (n["me2"], "person", m_mail, "Member"),
             (n["priya"], "person", "priya@acme.test", "Priya Shah"),
             (n["acme"], "company", "acme.test", "Acme Logistics"),
             (n["deal"], "deal", f"hubspot:{n['deal']}", "Acme expansion"),
             (n["cmt"], "commitment", f"cmt:{n['cmt']}", "send the revised proposal"),
             (n["mtg"], "meeting", f"gcal:{n['mtg']}", "Acme review"),
             # known ONLY from seat 1's own screen session: no edge to any seat's node
             (n["ravi"], "person", "ravi@ravico.test", "Ravi Kumar")]
    aliases = [("email", o_mail, n["me1"]), ("email", m_mail, n["me2"]),
               ("email", "priya@acme.test", n["priya"]), ("person_name", "priya shah", n["priya"]),
               ("domain", "acme.test", n["acme"])]
    edges = [("corresponded_with", n["me1"], n["priya"]), ("corresponded_with", n["me2"], n["priya"]),
             ("works_at", n["priya"], n["acme"]), ("about", n["deal"], n["acme"]),
             ("owns", n["me1"], n["cmt"]), ("attended", n["me1"], n["mtg"]),
             ("attended", n["priya"], n["mtg"])]
    start = (NOW + timedelta(days=1)).replace(microsecond=0)
    facts = [(n["deal"], "deal.stage", "negotiation", None, None),
             (n["deal"], "deal.status", "open", None, None),
             (n["cmt"], "commitment.text", "send the revised proposal", None, None),
             (n["cmt"], "commitment.status", "open", None, None),
             (n["cmt"], "commitment.owed_to", "Priya Shah", None, None),
             (n["cmt"], "commitment.due_at", start.isoformat(), None, None),
             (n["mtg"], "meeting.title", "Acme review", None, None),
             (n["mtg"], "meeting.start_at", start.isoformat(), None, None),
             (n["mtg"], "meeting.end_at", (start + timedelta(hours=1)).isoformat(), None, None),
             # seat 1's PRIVATE overlay — learned from their own screen session
             (n["priya"], "person.title", "Secret Buyer", "private", [o_mail])]
    ev_org, ev_priv = f"evt_org_{uuid.uuid4().hex[:8]}", f"evt_priv_{uuid.uuid4().hex[:8]}"
    with _engine().begin() as c:
        for nid, typ, key, name in nodes:
            c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                           "canonical_key, display_name) values (:n, 1, :o, :t, :k, :d)"),
                      {"n": nid, "o": org, "t": typ, "k": key, "d": name})
        for typ, key, nid in aliases:
            c.execute(text("insert into graph_aliases (org_id, alias_type, alias_key, node_id) "
                           "values (:o, :t, :k, :n)"), {"o": org, "t": typ, "k": key, "n": nid})
        for typ, frm, to in edges:
            eid = uuid.uuid4().hex[:12]
            c.execute(text("insert into graph_edges (edge_version_id, edge_id, org_id, edge_type, "
                           "from_node_id, to_node_id) values (:v, :e, :o, :t, :f, :to)"),
                      {"v": "ev_" + eid, "e": "e_" + eid, "o": org, "t": typ, "f": frm, "to": to})
        for subj, field, value, scope, who in facts:
            fid = uuid.uuid4().hex[:12]
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, visibility_scope, visibility_principals) values "
                "(:v, :f, :o, :s, :field, cast(:val as jsonb), :scope, cast(:who as text[]))"),
                {"v": "fv_" + fid, "f": "f_" + fid, "o": org, "s": subj, "field": field,
                 "val": json.dumps(value), "scope": scope or "org", "who": who})
        for ev, scope, who, days in ((ev_org, "org", None, 3), (ev_priv, "private", [o_mail], 1)):
            c.execute(text(
                "insert into source_events (event_id, org_id, connection_id, source, object_type, "
                "source_object_id, dedup_key, actor, occurred_at, visibility_scope, "
                "visibility_principals) values (:e, :o, 'conn', 'screen_session', 'message', :e, "
                ":e, '{}'::jsonb, :at, :scope, cast(:who as text[]))"),
                {"e": ev, "o": org, "at": NOW - timedelta(days=days), "scope": scope, "who": who})
            c.execute(text(
                "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
                "occurred_at, created_by_event_id) values (:i, :o, :s, 'event_presence', :at, :e)"),
                {"i": "obs_" + ev, "o": org, "s": n["priya"], "at": NOW - timedelta(days=days),
                 "e": ev})
        ev_scr = f"evt_scr_{uuid.uuid4().hex[:8]}"
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at, visibility_scope, "
            "visibility_principals) values (:e, :o, :conn, 'screen_session', 'message', :e, :e, "
            "'{}'::jsonb, :at, 'private', cast(:who as text[]))"),
            {"e": ev_scr, "o": org, "conn": f"screen:{ws['owner']['seat_id']}",
             "at": NOW - timedelta(days=2), "who": [o_mail]})
        c.execute(text(
            "insert into graph_observations (observation_id, org_id, subject_node_id, kind, "
            "occurred_at, created_by_event_id) values (:i, :o, :s, 'mention:person', :at, :e)"),
            {"i": "obs_" + ev_scr, "o": org, "s": n["ravi"], "at": NOW - timedelta(days=2),
             "e": ev_scr})
        c.execute(text("insert into graph_source_refs (source_ref_id, org_id, observation_id, "
                       "event_id) values (:r, :o, :i, :e)"),
                  {"r": "ref_" + ev_scr, "o": org, "i": "obs_" + ev_scr, "e": ev_scr})
    return n


def _count(sql: str, **params) -> int:
    with _engine().connect() as c:
        return int(c.execute(text(sql), params).scalar() or 0)


def _enable_display(client, ws, on: bool = True) -> dict:
    r = client.put("/v1/capture/policy", json={"moments_display": on},
                   headers=H(ws["owner"]["token"]))
    assert r.status_code == 200, r.text
    return r.json()


# ── 1 · slice ─────────────────────────────────────────────────────────────────────────────────
def test_slice_is_seat_visible_versioned_and_announced(client):
    ws = _workspace(client, capture=False)
    n = _seed(ws)
    t0 = time.perf_counter()
    one = client.get("/v1/seats/me/slice", headers={**H(ws["owner_dev"]["access_token"]),
                                                     "Accept-Encoding": "gzip"})
    assert one.status_code == 200, one.text
    assert time.perf_counter() - t0 < 0.5
    a = one.json()
    # P4 §3.4: slice v2 — additive `companies[].other_seats` + `recent_changes` in every response;
    # P8 C5: v3 adds `followups` + `removed_followups` (additive)
    assert a["schema_version"] == 3 and a["full"] is True and a["version"] > 0
    assert a["followups"] == [] and a["removed_followups"] == []
    assert isinstance(a["recent_changes"], list)
    assert all(isinstance(co.get("other_seats"), list) for co in a["companies"])
    priya = next(p for p in a["people"] if p["node_id"] == n["priya"])
    assert priya["role"] == "Secret Buyer"                        # the owner's own overlay
    assert priya["company"] == n["acme"] and "priya@acme.test" in priya["aliases"]
    assert priya["summary"] == "you owe: send the revised proposal"
    assert (NOW - datetime.fromisoformat(priya["last_touch_at"].replace("Z", "+00:00"))).days == 1
    assert a["companies"][0]["deal_stage"] == "negotiation"
    assert a["commitments"] == [{"node_id": n["cmt"], "text": "send the revised proposal",
                                 "due_at": a["commitments"][0]["due_at"], "owner": "seat",
                                 "beneficiary": n["priya"], "since": a["commitments"][0]["since"]}]
    assert a["commitments"][0]["since"], "the seat's commitment carries when it was recorded"
    assert a["meetings"][0]["attendees"] == [n["priya"]] and len(a["busy"]) == 1
    ravi = next(p for p in a["people"] if p["node_id"] == n["ravi"])   # screen-only counterparty
    assert (NOW - datetime.fromisoformat(ravi["last_touch_at"].replace("Z", "+00:00"))).days == 2

    two = client.get("/v1/seats/me/slice", headers=H(ws["member_dev"]["access_token"]))
    b = two.json()
    assert "Secret Buyer" not in two.text                         # never in seat 2's slice
    priya2 = next(p for p in b["people"] if p["node_id"] == n["priya"])
    assert priya2["role"] is None
    # seat 1's private screen touch (1 d ago) is not seat 2's; the org touch (3 d ago) is
    assert (NOW - datetime.fromisoformat(priya2["last_touch_at"].replace("Z", "+00:00"))).days == 3
    assert b["commitments"] == [] and b["meetings"] == []
    assert n["ravi"] not in {p["node_id"] for p in b["people"]}        # seat 1's screen stays theirs

    # a seat JWT is not a device: the slice is device-only
    assert client.get("/v1/seats/me/slice", headers=H(ws["owner"]["token"])).status_code == 403

    # delta + the graph-write hook
    v1 = b["version"]
    delta = client.get(f"/v1/seats/me/slice?since={v1}",
                       headers=H(ws["member_dev"]["access_token"])).json()
    assert delta["full"] is False and delta["version"] == v1
    future = client.get(f"/v1/seats/me/slice?since={v1 + 10**9}",
                        headers=H(ws["member_dev"]["access_token"])).json()
    assert future["full"] is True
    from genios_engine.context.graph_store import GraphStore
    with _engine().begin() as c:
        GraphStore(engine=_engine()).bump_version(c, ws["org"])
    with _engine().connect() as c:
        rows = c.execute(text("select seat_id, payload from realtime_events where org_id=:o "
                              "and kind='slice.delta' order by seq"), {"o": ws["org"]}).fetchall()
    assert {r.seat_id for r in rows} == {ws["owner"]["seat_id"], ws["member"]["seat_id"]}
    bumped = client.get(f"/v1/seats/me/slice?since={v1}",
                        headers=H(ws["member_dev"]["access_token"])).json()
    assert bumped["version"] > v1 and bumped["full"] is False
    assert any(r.payload["version"] == bumped["version"] for r in rows)


# ── 2 · P-02 evaluate, shadow → shown ─────────────────────────────────────────────────────────
def _evaluate(client, dev: dict, rid: str | None = None, **over):
    body = {"moment_request_id": rid or uuid.uuid4().hex,
            "surface": {"app": "linkedin", "bundle_id": "com.google.Chrome",
                        "url_domain": "linkedin.com", "thread_key": "li:conv:abc"},
            "participants": [{"name": "Priya Shah", "email": "priya@acme.test"}],
            "features": {"intents": ["schedule"], "dates": [], "entities": []}, **over}
    return client.post("/v1/moments/evaluate", json=body, headers=H(dev["access_token"]))


def test_counterparty_recall_in_shadow_then_shown(client):
    ws = _workspace(client)
    n = _seed(ws)
    t0 = time.perf_counter()
    res = _evaluate(client, ws["member_dev"], rid="req-1")
    assert time.perf_counter() - t0 < 1.2
    assert res.status_code == 200, res.text
    m = res.json()
    assert m["capability_id"] == "moment.counterparty_recall" and m["capability_version"] == "1"
    assert m["headline"].startswith("Priya Shah · Acme Logistics — last touch 3 d ago")
    assert "Secret" not in res.text and "Deal: negotiation" in m["body"]
    assert (m["display"], m["reason"]) == (False, "shadow")                # shadow is the default
    assert _evaluate(client, ws["member_dev"], rid="req-1").json() == m    # retry = same answer
    again = _evaluate(client, ws["member_dev"]).json()          # re-seen in shadow: logged once
    assert (again["display"], again["reason"]) == (False, "shadow")
    assert _count("select count(*) from moments where org_id=:o", o=ws["org"]) == 1

    doc = _enable_display(client, ws)
    assert doc["org"]["moments_display"] is True and doc["effective"]["moments_display"] is True
    got = client.get("/v1/capture/policy", headers=H(ws["member"]["token"])).json()
    assert got["org"]["moments_display"] is True
    assert _count("select count(*) from realtime_events where org_id=:o and kind='policy.updated' "
                  "and seat_id is null", o=ws["org"]) >= 1

    # the shadow-mode twin (same subject, inside its TTL) must NOT block the first real display
    shown = _evaluate(client, ws["member_dev"]).json()
    assert (shown["display"], shown["reason"]) == (True, None)
    dup = _evaluate(client, ws["member_dev"]).json()                        # now it IS a duplicate
    assert (dup["display"], dup["reason"]) == (False, "duplicate")
    assert _count("select count(*) from realtime_events where org_id=:o and seat_id=:s "
                  "and kind='moment.new'", o=ws["org"], s=ws["member"]["seat_id"]) == 1

    mine = _evaluate(client, ws["owner_dev"]).json()                        # seat 1 sees its own
    assert "(Secret Buyer)" in mine["headline"] and "last touch yesterday" in mine["headline"]
    assert mine["body"].startswith("You owe: send the revised proposal (due ")

    nobody = _evaluate(client, ws["member_dev"], participants=[{"email": "x@nowhere.test"}])
    assert nobody.status_code == 204
    blocked = _evaluate(client, ws["member_dev"],
                        surface={"url_domain": "accounts.google.com"})
    assert blocked.status_code == 204
    by_node = _evaluate(client, ws["member_dev"], participants=[],
                        features={"entities": [n["acme"]]})
    assert by_node.status_code == 200 and by_node.json()["headline"].startswith("Acme Logistics")


# ── 3 · rate limits, DND, device moments, feedback, history ───────────────────────────────────
def _device_moment(client, dev, *, kind="advice", headline=None, mid=None, prio="normal"):
    body = {"moment_id": mid or str(uuid.uuid4()), "origin": "device", "kind": kind,
            "priority": prio, "headline": headline or f"Kal 3 PM meeting {uuid.uuid4().hex[:6]}",
            "body": "Voltex audit prep", "actions": [{"id": "dismiss"}],
            "evidence": [{"node_id": "node_mtg", "field": "meeting.start_at", "source": "gcal"}],
            "ttl_seconds": 900, "capability_id": "moment.schedule_conflict",
            "capability_version": "1"}
    return client.post("/v1/moments", json=body, headers=H(dev["access_token"])), body


def test_rate_limits_dnd_feedback_and_history(client):
    ws = _workspace(client)
    _enable_display(client, ws)
    dev = ws["owner_dev"]
    answers = [_device_moment(client, dev)[0].json() for _ in range(7)]
    assert [a["display"] for a in answers] == [True] * 6 + [False]
    assert answers[-1]["reason"] == "rate_limited_hour"
    reminder, rbody = _device_moment(client, dev, kind="reminder", headline="Proposal due at 5")
    assert reminder.json()["display"] is True                           # reminders are never capped
    again, _ = _device_moment(client, dev, kind="reminder", mid=rbody["moment_id"])
    assert again.json() == reminder.json()                             # idempotent on moment_id
    stolen, _ = _device_moment(client, ws["member_dev"], mid=rbody["moment_id"])
    assert stolen.status_code == 409
    assert _count("select count(*) from moments where org_id=:o", o=ws["org"]) == 8

    # DND on the member's device suppresses a non-critical moment, never a critical one
    beat = client.post("/v1/presence", headers=H(ws["member_dev"]["access_token"]), json={
        "app_version": "0.1.0", "policy_version": None, "dnd": True, "idle": False})
    assert beat.status_code == 200, beat.text
    assert _device_moment(client, ws["member_dev"])[0].json()["reason"] == "dnd"
    assert _device_moment(client, ws["member_dev"], prio="critical")[0].json()["display"] is True

    # feedback — device and seat tokens; `useful` pinned 2026-09-13
    first = answers[0]["moment_id"]
    at = datetime.now(timezone.utc).isoformat()
    ok = client.post(f"/v1/moments/{first}/feedback", json={"action": "useful", "at": at},
                     headers=H(dev["access_token"]))
    assert ok.status_code == 200 and ok.json()["recorded"] is True
    again = client.post(f"/v1/moments/{first}/feedback", json={"action": "useful", "at": at},
                        headers=H(dev["access_token"]))
    assert again.json()["recorded"] is False                          # a retry is one row
    web = client.post(f"/v1/moments/{first}/feedback", json={"action": "dismissed"},
                      headers=H(ws["owner"]["token"]))
    assert web.status_code == 200
    assert client.post(f"/v1/moments/{first}/feedback", json={"action": "dismissed"},
                       headers=H(ws["member"]["token"])).status_code == 404   # not their moment
    assert _count("select count(*) from moment_feedback where moment_id=:m", m=first) == 2
    assert _count("select count(*) from learning_event_inbox where org_id=:o "
                  "and payload->>'moment_id' = :m", o=ws["org"], m=first) == 2
    assert _count("select count(*) from realtime_events where org_id=:o and kind='moment.updated'",
                  o=ws["org"]) == 2
    for action in ("shown", "dismissed"):                  # no state change → nothing pushed
        client.post(f"/v1/moments/{first}/feedback", json={"action": action},
                    headers=H(dev["access_token"]))
    assert _count("select count(*) from realtime_events where org_id=:o and kind='moment.updated'",
                  o=ws["org"]) == 2
    # exactly one moment.new per DISPLAYED moment; suppressed ones are never pushed
    displayed = _count("select count(*) from moments where org_id=:o and display", o=ws["org"])
    assert displayed == 8                                  # 6 advice + reminder + critical
    assert _count("select count(*) from realtime_events where org_id=:o and kind='moment.new'",
                  o=ws["org"]) == displayed
    assert _count("select count(distinct payload->>'moment_id') from realtime_events "
                  "where org_id=:o and kind='moment.new'", o=ws["org"]) == displayed

    # history — §2.6 pinned shape, own moments only, cursor, kind filter
    page = client.get("/v1/moments?limit=5", headers=H(ws["owner"]["token"])).json()
    assert set(page) == {"moments", "next_before"} and len(page["moments"]) == 5
    assert page["next_before"] is not None
    rest = client.get("/v1/moments", params={"limit": 50, "before": page["next_before"]},
                      headers=H(ws["owner"]["token"])).json()
    assert len(rest["moments"]) == 3 and rest["next_before"] is None
    everything = page["moments"] + rest["moments"]
    assert next(x for x in everything if x["moment_id"] == first)["feedback"] == "dismissed"
    assert {"created_at", "feedback", "display", "reason", "headline"} <= set(everything[0])
    only = client.get("/v1/moments?kind=reminder", headers=H(ws["owner"]["token"])).json()
    assert [x["kind"] for x in only["moments"]] == ["reminder"]
    member_view = client.get("/v1/moments", headers=H(ws["member"]["token"])).json()
    assert {x["moment_id"] for x in member_view["moments"]}.isdisjoint(
        {x["moment_id"] for x in everything})


# ── 4 · SSE ───────────────────────────────────────────────────────────────────────────────────
def test_sse_delivers_live_and_replays_with_last_event_id(client):
    from genios_engine.api.moment_routes import Principal
    from genios_engine.api.stream_routes import event_stream
    from genios_engine.platform import devices as D

    ws = _workspace(client)
    _enable_display(client, ws)
    dev = ws["member_dev"]
    ctx = D.resolve_device_token(dev["access_token"], D.DeviceStore(_engine()))
    p = Principal(ctx.org_id, ctx.seat_id, ctx.device_id, ctx.email, None)

    async def next_event(gen, timeout: float) -> str:
        async def pull():
            async for frame in gen:
                if not frame.startswith((":", "retry:")):
                    return frame
            return ""
        return await asyncio.wait_for(pull(), timeout)

    async def run():
        live = event_stream(p, engine=_engine(), last_event_id=None, heartbeat_s=0.5, max_s=20)
        assert (await live.__anext__()).startswith("retry:")
        started = time.perf_counter()
        posted = asyncio.create_task(asyncio.to_thread(_device_moment, client, dev))
        frame = await next_event(live, 2.0)
        latency = time.perf_counter() - started
        res, body = await posted
        assert res.json()["display"] is True
        assert frame.startswith("id: ") and "event: moment.new" in frame
        assert body["moment_id"] in frame and latency < 2.0
        seq = int(frame.split("\n", 1)[0][4:])

        replay = event_stream(p, engine=_engine(), last_event_id=seq - 1, heartbeat_s=0.5, max_s=5)
        await replay.__anext__()
        again = await next_event(replay, 2.0)
        assert again == frame                                     # replayed from the outbox
        await replay.aclose()

        revoke = await asyncio.to_thread(client.delete, f"/v1/devices/{ctx.device_id}",
                                         headers=H(ws["member"]["token"]))
        assert revoke.status_code == 204
        last = await next_event(live, 3.0)
        assert "event: device.revoked" in last
        rest = [f async for f in live]
        assert all(f.startswith(":") for f in rest)               # the stream ended
    asyncio.run(run())
    _ = hash_key  # imported for parity with the device suite's helpers
