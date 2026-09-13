"""P6 §3.6 MCP protocol surface — hermetic (auth stubbed; no database)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.mcp import server as S

BOUND = S.Caller("org_1", "seat_1", "a@x.test", "member", "hermes")
UNBOUND = S.Caller("org_1", None, None, None, "hermes")


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(S.router)
    return TestClient(app)


@pytest.fixture
def as_caller(monkeypatch):
    def use(caller):
        monkeypatch.setattr(S, "_authenticate", lambda request: caller)
        monkeypatch.setattr(S, "_audit", lambda *a, **k: None)
    return use


def rpc(client, method, params=None, rid=1, **headers):
    msg = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        msg["params"] = params
    return client.post("/mcp", json=msg, headers=headers)


def test_get_and_delete_are_405(client):
    for r in (client.get("/mcp"), client.delete("/mcp")):
        assert r.status_code == 405 and r.headers["allow"] == "POST"


def test_no_credential_is_401(client):
    r = rpc(client, "initialize")
    assert r.status_code == 401 and r.json()["code"] == "AUTH_REQUIRED"
    assert "Bearer" in r.headers["www-authenticate"]


def test_initialize_negotiates_the_protocol(client, as_caller):
    as_caller(BOUND)
    res = rpc(client, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "t", "version": "1"}}).json()["result"]
    assert res["protocolVersion"] == "2025-06-18"
    assert res["capabilities"] == {"tools": {"listChanged": False}}
    assert res["serverInfo"]["name"] == "genios"
    assert rpc(client, "initialize", {"protocolVersion": "2099-01-01"}).json()["result"][
        "protocolVersion"] == S.PROTOCOL_VERSION
    assert rpc(client, "ping").json()["result"] == {}


def test_framing_errors(client, as_caller):
    as_caller(BOUND)
    assert client.post("/mcp", content=b"{not json").json()["error"]["code"] == S.PARSE_ERROR
    r = client.post("/mcp", json=[{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
    assert r.status_code == 400 and r.json()["error"]["code"] == S.INVALID_REQUEST
    assert client.post("/mcp", json={"id": 1, "method": "ping"}).status_code == 400
    note = client.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.status_code == 202 and note.content == b""
    assert rpc(client, "resources/list").json()["error"]["code"] == S.METHOD_NOT_FOUND
    bad_version = rpc(client, "ping", **{"MCP-Protocol-Version": "1999-01-01"})
    assert bad_version.status_code == 400
    assert rpc(client, "ping", **{"MCP-Protocol-Version": "2025-06-18"}).status_code == 200


def test_tools_list_names_and_schemas(client, as_caller):
    as_caller(BOUND)
    tools = rpc(client, "tools/list").json()["result"]["tools"]
    names = [t["name"] for t in tools]
    assert names == ["get_context", "list_moments", "list_cards", "get_team_availability",
                     "propose_action"]
    assert "search_graph" not in names       # no seat-filtered search exists — deferred
    for t in tools:
        assert t["inputSchema"]["type"] == "object"
        assert t["annotations"]["readOnlyHint"] is (t["name"] != "propose_action")


def test_unbound_key_gets_seat_required_on_seat_tools(client, as_caller, monkeypatch):
    as_caller(UNBOUND)
    for name in ("get_context", "list_moments", "list_cards", "propose_action"):
        err = rpc(client, "tools/call", {"name": name, "arguments": {"entity": "x"}}).json()["error"]
        assert err["code"] == S.SEAT_REQUIRED and err["data"]["code"] == "SEAT_REQUIRED"
    monkeypatch.setattr(S, "tool_get_team_availability", lambda c, a: {"away": []})
    monkeypatch.setitem(S.TOOLS, "get_team_availability", S.Tool(
        "get_team_availability", "t", "d", {"type": "object"}, lambda c, a: {"away": []},
        seat=False))
    ok = rpc(client, "tools/call", {"name": "get_team_availability"}).json()["result"]
    assert ok["isError"] is False and ok["structuredContent"] == {"away": []}


def test_bad_arguments_and_unknown_tool(client, as_caller):
    as_caller(BOUND)
    assert rpc(client, "tools/call", {"name": "nope"}).json()["error"]["code"] == S.INVALID_PARAMS
    assert rpc(client, "tools/call", {"name": "get_context", "arguments": {}}).json()[
        "error"]["code"] == S.INVALID_PARAMS
    assert rpc(client, "tools/call", {"name": "propose_action", "arguments": {
        "moment_id": "m", "card_id": "c", "play": "task.reassign", "params": {}}}).json()[
        "error"]["code"] == S.INVALID_PARAMS


def test_propose_action_calls_the_proposer_lazily(client, as_caller, monkeypatch):
    as_caller(BOUND)
    monkeypatch.setattr(S, "_proposer", lambda: None)
    err = rpc(client, "tools/call", {"name": "propose_action", "arguments": {
        "moment_id": "mom_1", "play": "email.reschedule", "params": {}}}).json()["error"]
    assert err["data"]["code"] == "NOT_AVAILABLE"

    calls = []

    def create_proposal(engine, **kw):
        calls.append(kw)
        if kw["params"].get("bad"):
            raise ValueError("params invalid for email.reschedule")
        return {"delegation_id": "dlg_1", "state": "proposed", "instruction": "…",
                "agent_id": "hermes"}
    monkeypatch.setattr(S, "_proposer", lambda: create_proposal)
    monkeypatch.setattr(S, "_engine", lambda: object())
    res = rpc(client, "tools/call", {"name": "propose_action", "arguments": {
        "moment_id": "mom_1", "play": "email.reschedule", "params": {"a": 1}}}).json()["result"]
    assert res["isError"] is False and res["structuredContent"]["state"] == "proposed"
    assert calls[0]["seat_id"] == "seat_1" and calls[0]["moment_id"] == "mom_1"
    assert calls[0]["card_id"] is None and calls[0]["via"] == "mcp"
    bad = rpc(client, "tools/call", {"name": "propose_action", "arguments": {
        "card_id": "card_1", "play": "email.reschedule", "params": {"bad": 1}}}).json()["result"]
    assert bad["isError"] is True and bad["structuredContent"]["error"]["code"] == "INVALID_PROPOSAL"
