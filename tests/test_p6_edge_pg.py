"""P6 group B against real Postgres (SCREEN_INTEL_P6_BUILD.md §3.6, §3.7, §7):

  1. An agent key bound to a seat: initialize + tools/list + tools/call over POST /mcp.
  2. Seat 2's key cannot see seat 1's private facts (seat 1's own key can; the overlay wins).
  3. Unbound key → SEAT_REQUIRED on seat tools; no mcp.read → 403; unknown seat → 422; archived → 401.
  4. Registration SSRF refusals: 10.0.0.1, 169.254.169.254, http://evil in prod, a hostname that
     resolves to a private address, localhost outside dev.
  5. propose_action through the lazily-imported proposer (stubbed) with the bound seat; a seat
     session (owner JWT) reads over MCP too.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_p6_b \\
        pytest tests/test_p6_edge_pg.py -q
"""
from __future__ import annotations

import json
import os
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

SECRET = "SECRET-SEAT1-PRIVATE-STANCE"
_ORGS: list[str] = []


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import agent_mgmt_routes, auth_routes
    from genios_engine.mcp import server
    app = FastAPI()
    for module in (auth_routes, agent_mgmt_routes, server):
        app.include_router(module.router)
    yield TestClient(app)
    for org in _ORGS:
        try:
            with _engine().begin() as c:
                c.execute(text("delete from orgs where id=:o"), {"o": org})
        except Exception:      # noqa: BLE001 — the scratch database is dropped after the run
            pass


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def rpc(client, token, method, params=None, rid=1):
    msg = {"jsonrpc": "2.0", "id": rid, "method": method, **({"params": params} if params else {})}
    return client.post("/mcp", json=msg, headers=H(token))


def call(client, token, name, arguments=None):
    return rpc(client, token, "tools/call", {"name": name, "arguments": arguments or {}}).json()


@pytest.fixture(scope="module")
def ws(client):
    uid = uuid.uuid4().hex[:8]
    owner = f"owner_{uid}@acme.test"
    res = client.post("/auth/register", json={"name": "Owner", "password": "founder-pass-1",
                                              "email": owner, "company": f"Acme {uid}"})
    assert res.status_code == 200, res.text
    body = res.json()
    org = body["org_id"]
    _ORGS.append(org)
    seats = {"alice": f"seat_ali_{uid}", "bob": f"seat_bob_{uid}"}
    mails = {"alice": f"alice_{uid}@acme.test", "bob": f"bob_{uid}@acme.test"}
    node = f"node_carol_{uid}"
    with _engine().begin() as c:
        for k in seats:
            c.execute(text("insert into org_seats (org_id, seat_id, email, role, active) "
                           "values (:o, :s, :e, 'member', true)"),
                      {"o": org, "s": seats[k], "e": mails[k]})
        c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                       "canonical_key, display_name) values (:n, 1, :o, 'person', :k, :d)"),
                  {"n": node, "o": org, "k": f"carol_{uid}@client.test", "d": f"Carol Diaz {uid}"})

        def fact(field, value, *, scope="org", who=None):
            fid = uuid.uuid4().hex[:12]
            c.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, visibility_scope, visibility_principals) values (:v, :f, :o, :s, "
                ":field, cast(:val as jsonb), :scope, cast(:who as text[]))"),
                {"v": "fv_" + fid, "f": "f_" + fid, "o": org, "s": node, "field": field,
                 "val": json.dumps(value), "scope": scope, "who": who})
        fact("person.title", "VP Operations")
        fact("relationship.stance", "neutral")                                   # org version
        fact("relationship.stance", SECRET, scope="private", who=[mails["alice"]])  # alice overlay
        fact("person.private_note", SECRET + "-NOTE", scope="private", who=[mails["alice"]])
    return {"org": org, "owner_token": body["token"], "owner_seat": body["seat_id"],
            "seats": seats, "mails": mails, "node": node, "uid": uid}


def _agent(client, ws, name, *, seat=None) -> str:
    aid = f"{name}_{ws['uid']}"
    body = {"agent_id": aid, "name": name}
    if seat:
        body["seat_id"] = seat
    r = client.post("/v1/agents", json=body, headers=H(ws["owner_token"]))
    assert r.status_code == 200, r.text
    return r.json()["key"]


def _bind(client, ws, name, seat):
    return client.patch(f"/v1/agents/{name}_{ws['uid']}/seat", json={"seat_id": seat},
                        headers=H(ws["owner_token"]))


def test_1_bound_agent_key_speaks_mcp(client, ws):
    key = _agent(client, ws, "hermes")
    b = _bind(client, ws, "hermes", ws["seats"]["alice"])
    assert b.status_code == 200 and "mcp.read" in b.json()["allowed_actions"], b.text
    init = rpc(client, key, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                           "clientInfo": {"name": "hermes", "version": "1"}})
    assert init.status_code == 200 and init.json()["result"]["protocolVersion"] == "2025-06-18"
    tools = [t["name"] for t in rpc(client, key, "tools/list").json()["result"]["tools"]]
    assert set(tools) == {"get_context", "list_moments", "list_cards", "get_team_availability",
                          "propose_action"}
    for name, args, key_ in (("list_moments", {"limit": 5}, "moments"), ("list_cards", {}, "cards"),
                             ("get_team_availability", {}, "away")):
        res = call(client, key, name, args)["result"]
        assert res["isError"] is False and isinstance(res["structuredContent"][key_], list), res
    got = call(client, key, "get_context", {"entity": ws["node"]})["result"]["structuredContent"]
    assert got["found"] and got["entity"]["facts"]["person.title"]["value"] == "VP Operations"
    with _engine().connect() as c:           # the call is on the agent's audit trail
        n = c.execute(text("select count(*) from agent_events where org_id=:o and agent_id=:a "
                           "and action_taken like 'mcp.%'"),
                      {"o": ws["org"], "a": f"hermes_{ws['uid']}"}).scalar()
    assert n >= 4


def test_2_seat2_key_cannot_see_seat1_private_facts(client, ws):
    alice = _agent(client, ws, "alice_agent", seat=ws["seats"]["alice"])
    bob = _agent(client, ws, "bob_agent", seat=ws["seats"]["bob"])
    mine = call(client, alice, "get_context", {"entity": ws["node"]})["result"]
    facts = mine["structuredContent"]["entity"]["facts"]
    assert facts["relationship.stance"] == {**facts["relationship.stance"], "value": SECRET,
                                            "private": True}, "the owner's overlay wins its field"
    assert facts["person.private_note"]["value"] == SECRET + "-NOTE"
    theirs = call(client, bob, "get_context", {"entity": f"Carol Diaz {ws['uid']}"})["result"]
    assert theirs["structuredContent"]["found"], theirs
    bob_facts = theirs["structuredContent"]["entity"]["facts"]
    assert bob_facts["relationship.stance"]["value"] == "neutral"
    assert "person.private_note" not in bob_facts
    assert SECRET not in json.dumps(theirs), "no trace of seat 1's private facts, in any field"


def test_3_unbound_scopeless_unknown_and_archived(client, ws):
    key = _agent(client, ws, "openclaw", seat=ws["seats"]["bob"])
    assert _bind(client, ws, "openclaw", None).status_code == 200          # unbind keeps mcp.read
    err = call(client, key, "get_context", {"entity": ws["node"]})["error"]
    assert err["data"]["code"] == "SEAT_REQUIRED"
    assert call(client, key, "get_team_availability")["result"]["isError"] is False
    fresh = _agent(client, ws, "n8n")                       # never bound → no mcp.read
    r = rpc(client, fresh, "tools/list")
    assert r.status_code == 403 and r.json()["code"] == "SCOPE_REQUIRED"
    assert _bind(client, ws, "n8n", "seat_nobody").status_code == 422
    client.delete(f"/v1/agents/openclaw_{ws['uid']}", headers=H(ws["owner_token"]))
    assert rpc(client, key, "tools/list").status_code == 401


def test_4_registration_refuses_ssrf_targets(client, ws, monkeypatch):
    from genios_engine.platform import egress
    from genios_engine.platform.config import get_settings

    def create(name, url):
        return client.post("/v1/agents", json={"agent_id": f"{name}_{ws['uid']}",
                                               "webhook_url": url}, headers=H(ws["owner_token"]))
    for name, url, code in (("p1", "https://10.0.0.1/hook", "private_address"),
                            ("p2", "https://169.254.169.254/latest/meta-data", "metadata_address")):
        r = create(name, url)
        assert r.status_code == 422 and r.json()["detail"]["code"] == code, r.text
    monkeypatch.setattr(egress, "_system_resolver", lambda host, port: ["10.9.8.7"])
    r = create("p3", "https://hooks.rebind.test/x")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "private_address"
    settings = get_settings()
    monkeypatch.setattr(settings, "env", "prod")
    for name, url, code in (("p4", "http://evil.example/hook", "https_required"),
                            ("p5", "http://localhost:8080/hook", "loopback_address")):
        r = create(name, url)
        assert r.status_code == 422 and r.json()["detail"]["code"] == code, r.text
    with _engine().connect() as c:           # nothing was registered
        assert c.execute(text("select count(*) from agent_registry where org_id=:o and "
                              "agent_id like 'p_\\_%'"), {"o": ws["org"]}).scalar() == 0
    monkeypatch.setattr(settings, "env", "dev")
    ok = create("p6", "http://localhost:8080/hook")
    assert ok.status_code == 200 and ok.json()["webhook_secret"].startswith("gnwh_")
    w = client.patch(f"/v1/agents/p6_{ws['uid']}/webhook",
                     json={"webhook_url": "https://169.254.169.254/"}, headers=H(ws["owner_token"]))
    assert w.status_code == 422


def test_5_propose_action_and_seat_session(client, ws, monkeypatch):
    from genios_engine.mcp import server
    calls = []

    def create_proposal(engine, **kw):
        calls.append(kw)
        return {"delegation_id": "dlg_test", "state": "proposed", "instruction": "Reschedule",
                "agent_id": kw["agent_id"]}
    monkeypatch.setattr(server, "_proposer", lambda: create_proposal)
    key = _agent(client, ws, "crew", seat=ws["seats"]["alice"])
    res = call(client, key, "propose_action", {"moment_id": "mom_x", "play": "email.reschedule",
                                               "params": {"timezone": "UTC"}})["result"]
    assert res["structuredContent"]["state"] == "proposed"
    assert calls[0]["seat_id"] == ws["seats"]["alice"] and calls[0]["org_id"] == ws["org"]
    assert calls[0]["seat_email"] == ws["mails"]["alice"]
    # a seat session reads over MCP as its own seat (the owner sees no member's private overlay)
    got = call(client, ws["owner_token"], "get_context", {"entity": ws["node"]})["result"]
    assert got["structuredContent"]["found"] and SECRET not in json.dumps(got)
    assert call(client, ws["owner_token"], "list_cards")["result"]["isError"] is False


def test_6_agent_with_plays_is_selectable_and_may_post_results(client, ws):
    """The P6 gate's registration: scope.allowed_actions → agent_registry.allowed_actions (what
    executive/plays.select_agent reads) and the key gets actions.result (+ mcp.read, seat-bound)."""
    from genios_engine.platform.auth import verify_bearer
    plays = ["email.reschedule", "task.reassign", "email.follow_up_draft"]
    aid = f"gate_{ws['uid']}"
    bad = client.post("/v1/agents", json={"agent_id": aid, "scope": {"allowed_actions": ["x.y"]}},
                      headers=H(ws["owner_token"]))
    assert bad.status_code == 422 and bad.json()["detail"]["error"] == "unknown_play"
    r = client.post("/v1/agents", json={"agent_id": aid, "name": "Gate",
                                        "scope": {"allowed_actions": plays},
                                        "webhook_url": "https://93.184.215.14/genios/action",
                                        "seat_id": ws["seats"]["alice"]}, headers=H(ws["owner_token"]))
    assert r.status_code == 200, r.text
    ctx = verify_bearer(r.json()["key"])
    assert ctx.has_scope("actions.result") and ctx.has_scope("mcp.read")
    select = ("select agent_id from agent_registry where org_id = :o and status = 'active' "
              "and :p = any(allowed_actions) and coalesce(webhook_url, '') <> ''")  # plays.py:198
    with _engine().connect() as c:
        for p in plays:
            assert aid in {x.agent_id for x in c.execute(text(select), {"o": ws["org"], "p": p})}
    u = client.patch(f"/v1/agents/{aid}/scope", json={"scope": {"allowed_actions": ["task.reassign"]}},
                     headers=H(ws["owner_token"]))
    assert u.status_code == 200 and "email.reschedule" not in u.json()["allowed_actions"]
    with _engine().connect() as c:
        assert not list(c.execute(text(select), {"o": ws["org"], "p": "email.reschedule"}))
        scopes = c.execute(text("select scopes from api_keys where org_id=:o and agent_id=:a "
                                "and is_active"), {"o": ws["org"], "a": aid}).scalar()
    assert "task.reassign" in scopes and "actions.result" in scopes and "mcp.read" in scopes
    none = client.patch(f"/v1/agents/{aid}/scope", json={"scope": {"allowed_actions": []}},
                        headers=H(ws["owner_token"]))
    assert "actions.result" not in none.json()["allowed_actions"]
