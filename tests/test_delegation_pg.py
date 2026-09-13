"""P6 group A (Act core) against real Postgres — SCREEN_INTEL_P6_BUILD §3, §7:

  1. propose: invalid params 422 writes nothing; idempotent; not-your-moment 403; private evidence
     never reaches the request; no approval → no outbox row; edit = `supersedes` (old → cancelled
     in the same transaction; only a proposed one); the pinned GET list shape.
  2. two concurrent approvals → ONE outbox row; the act pump sends within seconds; a failed attempt
     retries on the short ladder with the SAME bytes and the same delegation id.
  3. reject / expired proposal → nothing sent; the ladder gives up → delegation `failed` + event.
  4. result intake: wrong agent / no agent 404, recorded once, repeat 200, conflict 409, not
     dispatched 409, moment_feedback 'acted', moment.updated; credits ledger unchanged.
  5. handoff → 202 proposal only; a card's result lands a card_events 'agent.result'; the P5 prep
     carries the `delegate` action when an agent runs `email.reschedule`.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_p6_a \\
        pytest tests/test_delegation_pg.py -q
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
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

RES, RA = "email.reschedule", "task.reassign"
_ORGS: list[str] = []
PINNED = {"delegation_id", "state", "play", "params", "instruction", "headline", "agent_id",
          "agent_name", "moment_id", "card_id", "supersedes", "proposed_at", "approved_by",
          "approved_at", "result"}


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Stub:
    """Stands in for group B's `send_action(body, cfg, *, delegation_id)`. `script[dlg]` = the
    outcomes to return in order (True = ok, str = a failure detail); default ok."""

    def __init__(self):
        self.calls: list[tuple[bytes, dict, str]] = []
        self.script: dict[str, list] = {}
        self._lock = threading.Lock()

    def __call__(self, body: bytes, cfg, *, delegation_id: str, **_kw):
        from genios_engine.deliver.channels.base import ChannelResult
        with self._lock:
            self.calls.append((body, dict(cfg), delegation_id))
            seq = self.script.get(delegation_id)
            res = seq.pop(0) if seq else True
        return ChannelResult(ok=True) if res is True else ChannelResult(ok=False, detail=str(res))

    def for_(self, delegation_id: str) -> list[bytes]:
        with self._lock:
            return [b for b, _, d in self.calls if d == delegation_id]


@pytest.fixture(scope="module")
def stub():
    from genios_engine.deliver import outbox
    s = Stub()
    old = outbox._send_action
    outbox._send_action = lambda: s
    yield s
    outbox._send_action = old


@pytest.fixture(scope="module")
def client(stub):
    from genios_engine.api import (account_routes, auth_routes, delegation_routes,
                                   intelligence_routes, moment_routes)
    app = FastAPI()
    for module in (auth_routes, account_routes, moment_routes, delegation_routes,
                   intelligence_routes):
        app.include_router(module.router)
    settings = get_settings()
    old = settings.dashboard_url
    settings.dashboard_url = "https://app.genios.test"
    yield TestClient(app, base_url="https://api.genios.test")
    settings.dashboard_url = old
    from genios_engine.deliver import act_pump
    from genios_engine.platform.realtime import stop_realtime
    act_pump.stop()
    stop_realtime()
    for org in _ORGS:
        try:
            with _engine().begin() as c:
                c.execute(text("delete from orgs where id=:o"), {"o": org})
        except Exception:      # noqa: BLE001 — the scratch database is dropped after the run
            pass


# ── a workspace: owner (admin) + two members; two agents; a moment with private evidence ─────
def _join(client, owner: dict, name: str) -> dict:
    email = f"{name}_{uuid.uuid4().hex[:8]}@act.test"
    inv = client.post(f"/api/org/{owner['org_id']}/members/invite",
                      json={"email": email, "role": "member"}, headers=H(owner["token"]))
    assert inv.status_code == 200, inv.text
    acc = client.post(f"/invites/{inv.json()['invite_token']}/accept",
                      json={"email": email, "name": name, "password": "member-pass-1"})
    assert acc.status_code == 200, acc.text
    return {**acc.json(), "email": email}


def _agent(c, org: str, agent_id: str, name: str, *, plays, default: bool) -> str:
    raw = "gn_live_" + uuid.uuid4().hex
    c.execute(text(
        "insert into agent_registry (id, org_id, agent_id, key_hash, allowed_actions, name, "
        "status, webhook_url, webhook_secret, is_default) values (:i, :o, :a, :kh, "
        "cast(:acts as text[]), :n, 'active', 'https://agent.act.test/hook', 'gnwh_s', :d)"),
        {"i": "agt_" + uuid.uuid4().hex[:10], "o": org, "a": agent_id,
         "kh": hash_key("gn_live_registry_" + uuid.uuid4().hex), "acts": list(plays), "n": name,
         "d": default})
    c.execute(text(
        "insert into api_keys (id, org_id, key_hash, key_prefix, name, agent_id, scopes, "
        "is_active) values (:i, :o, :h, :p, :n, :a, cast(:sc as text[]), true)"),
        {"i": "key_" + uuid.uuid4().hex[:10], "o": org, "h": hash_key(raw), "p": raw[:12],
         "n": agent_id, "a": agent_id, "sc": ["actions.result"]})
    return raw


def _credits(c, org: str) -> tuple:
    return tuple(c.execute(text(
        "select count(*), coalesce(sum(amount), 0) from credit_ledger where org_id = :o"),
        {"o": org}).first())


@pytest.fixture(scope="module")
def ws(client):
    uid = uuid.uuid4().hex[:8]
    email = f"founder_{uid}@act.test"
    res = client.post("/auth/register", json={"name": "Founder", "password": "founder-pass-1",
                                              "email": email, "company": f"Act {uid}"})
    assert res.status_code == 200, res.text
    owner = {**res.json(), "email": email}
    org = owner["org_id"]
    _ORGS.append(org)
    with _engine().begin() as c:                      # the trial plan allows one seat
        c.execute(text("update orgs set subscription_tier='startup' where id=:o"), {"o": org})
    member, other = _join(client, owner, "member"), _join(client, owner, "other")
    private_node, mtg = f"node_priv_{uid}", f"node_mtg_{uid}"
    with _engine().begin() as c:
        seats = {r.e: r.seat_id for r in c.execute(text(
            "select lower(email) as e, seat_id from org_seats where org_id = :o"), {"o": org})}
        hermes = _agent(c, org, "hermes", "Hermes", plays=[RES, RA, "email.follow_up_draft"],
                        default=True)
        stranger = _agent(c, org, "openclaw", "OpenClaw", plays=[RES], default=False)
        for node, typ, key in ((private_node, "person", f"priv_{uid}@acme.test"),
                               (mtg, "meeting", f"gcal:evt_{uid}")):
            c.execute(text("insert into graph_nodes (node_id, version, org_id, node_type, "
                           "canonical_key, display_name) values (:n, 1, :o, :t, :k, :d)"),
                      {"n": node, "o": org, "t": typ, "k": key, "d": typ})
        c.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "value, visibility_scope, visibility_principals) values (:v, :f, :o, :s, "
            "'relationship.stance', cast(:val as jsonb), 'private', cast(:who as text[]))"),
            {"v": "fv_" + uid, "f": "f_" + uid, "o": org, "s": private_node,
             "val": json.dumps("SECRET"), "who": [member["email"].lower()]})
        moment = f"mom_act_{uid}"
        c.execute(text(
            "insert into moments (moment_id, org_id, seat_id, origin, kind, priority, "
            "capability_id, capability_version, headline, evidence, display, expires_at) values "
            "(:m, :o, :s, 'server', 'advice', 'high', 'moment.meeting_prep', '1', :h, "
            "cast(:e as jsonb), true, now() + interval '1 hour')"),
            {"m": moment, "o": org, "s": seats[member["email"].lower()],
             "h": "Acme review in 15 min",
             "e": json.dumps([{"node_id": private_node, "field": "relationship.stance",
                               "source": "graph"},
                              {"node_id": mtg, "field": "meeting.start_at", "source": "graph"}])})
        credits = _credits(c, org)
    return {"org": org, "owner": owner, "member": member, "other": other, "moment": moment,
            "seats": seats, "hermes": hermes, "stranger": stranger, "private": private_node,
            "mtg": mtg, "uid": uid, "credits": credits}


def _params(tag: str) -> dict:
    return {"meeting_ref": {"provider": "google", "event_id": "evt_1"},
            "attendees": ["priya@acme.test"], "current_start": "2026-09-14T10:00:00Z",
            "proposed_windows": [{"start": "2026-09-15T10:00:00Z", "end": "2026-09-15T10:30:00Z"}],
            "message_draft": f"Could we move? ({tag})", "timezone": "UTC"}


def _propose(client, ws, tag: str, *, seat="member", **extra):
    return client.post("/v1/delegations", json={"moment_id": ws["moment"], "play": RES,
                                                "params": _params(tag), **extra},
                       headers=H(ws[seat]["token"]))


def _q(sql: str, **kw):
    with _engine().connect() as c:
        return c.execute(text(sql), kw).first()


def _outbox(d: str):
    return _q("select count(*) as n, max(status) as status, max(attempts) as attempts, "
              "max(next_attempt_at) as na from delivery_outbox where delegation_id = :d", d=d)


def _events(org: str, d: str) -> list[str]:
    with _engine().connect() as c:
        return [r.st for r in c.execute(text(
            "select payload->'delegation'->>'state' as st from realtime_events where org_id = :o "
            "and kind = 'moment.updated' and payload->'delegation'->>'id' = :d order by seq"),
            {"o": org, "d": d})]


def _wait(pred, timeout: float = 6.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.1)
    return False


def _seat(ws, who: str) -> tuple[str, str]:
    email = ws[who]["email"]
    return ws["seats"][email.lower()], email


def _approve_direct(ws, d: str, who: str = "member"):
    from genios_engine.executive import delegation as DLG
    seat, email = _seat(ws, who)
    with _engine().begin() as c:
        return DLG.approve_and_enqueue(c, org_id=ws["org"], delegation_id=d,
                                       approver_seat_id=seat, approver_email=email, at=_now(),
                                       result_base_url="https://api.genios.test")


# ── 1 ─────────────────────────────────────────────────────────────────────────────────────────
def test_propose_validates_is_idempotent_and_supersedes(client, ws, stub):
    org = ws["org"]

    def count():
        return _q("select count(*) as n from agent_delegations where org_id = :o", o=org).n

    bad = client.post("/v1/delegations", json={
        "moment_id": ws["moment"], "play": RES, "params": {**_params("x"), "extra": 1}},
        headers=H(ws["member"]["token"]))
    assert bad.status_code == 422 and bad.json()["code"] == "INVALID_PARAMS", bad.text
    assert any("unknown field" in e for e in bad.json()["errors"])
    assert client.post("/v1/delegations", json={"moment_id": ws["moment"], "play": "rm.rf",
                                                "params": {}},
                       headers=H(ws["member"]["token"])).status_code == 422
    assert client.post("/v1/delegations", json={"play": RES, "params": _params("x")},
                       headers=H(ws["member"]["token"])).status_code == 422
    assert _propose(client, ws, "one", seat="other").status_code == 403      # not their moment
    assert count() == 0                                                       # nothing written

    first = _propose(client, ws, "one")
    assert first.status_code == 201, first.text
    body = first.json()
    assert set(body) == {"delegation_id", "state", "instruction", "agent_id"}
    assert body["state"] == "proposed" and body["agent_id"] == "hermes"       # the default agent
    again = _propose(client, ws, "one")
    assert again.status_code == 201 and again.json()["delegation_id"] == body["delegation_id"]
    assert count() == 1
    d1 = body["delegation_id"]
    instr = _q("select instruction from agent_delegations where delegation_id = :d",
               d=d1).instruction
    ev_nodes = {e["node_id"] for e in instr["context"]["evidence"]}
    assert ws["private"] not in ev_nodes and ws["mtg"] in ev_nodes           # P2 visibility
    assert "SECRET" not in json.dumps(instr)
    assert _events(org, d1) == ["proposed"]

    # no approval → no outbox row, and a drain pass sends nothing
    from genios_engine.deliver import outbox as OB
    OB.drain_actions(_engine())
    assert _outbox(d1).n == 0 and stub.for_(d1) == []

    # edit = a new proposal naming `supersedes`: the old one is cancelled in the same transaction
    edit = _propose(client, ws, "two", supersedes=d1)
    assert edit.status_code == 201, edit.text
    d2 = edit.json()["delegation_id"]
    old = _q("select state, superseded_by from agent_delegations where delegation_id = :d", d=d1)
    assert (old.state, old.superseded_by) == ("cancelled", d2)
    assert _events(org, d1) == ["proposed", "cancelled"]
    # only a proposed delegation can be superseded; the refused edit writes nothing
    refused = _propose(client, ws, "three", supersedes=d1)
    assert refused.status_code == 409 and refused.json()["code"] == "NOT_EDITABLE"
    assert count() == 2

    items = client.get("/v1/delegations", params={"moment_id": ws["moment"]},
                       headers=H(ws["member"]["token"])).json()["delegations"]
    by_id = {i["delegation_id"]: i for i in items}
    assert set(by_id) == {d1, d2}
    assert PINNED <= set(by_id[d2])                                            # pinned §3.3 shape
    assert by_id[d2]["supersedes"] == d1 and by_id[d1]["supersedes"] is None
    assert by_id[d2]["headline"] == "Acme review in 15 min"
    assert by_id[d2]["agent_name"] == "Hermes" and by_id[d2]["result"] is None
    assert by_id[d2]["state"] == "proposed" and by_id[d1]["state"] == "cancelled"
    assert client.get("/v1/delegations", params={"state": "proposed"},
                      headers=H(ws["other"]["token"])).json()["delegations"] == []


# ── 2 ─────────────────────────────────────────────────────────────────────────────────────────
def test_concurrent_approvals_one_row_pump_sends_fast_and_retries_same_bytes(client, ws, stub):
    from genios_engine.deliver import act_pump
    from genios_engine.deliver import outbox as OB
    d = _propose(client, ws, "concurrent").json()["delegation_id"]
    stub.script[d] = ["503 Service Unavailable", True]
    gate, results = threading.Barrier(2), []

    def click(who):
        gate.wait()
        results.append(_approve_direct(ws, d, who))
    threads = [threading.Thread(target=click, args=(w,)) for w in ("member", "owner")]
    [t.start() for t in threads]
    [t.join(10) for t in threads]
    assert [r["state"] for r in results] == ["dispatched", "dispatched"]
    assert _outbox(d).n == 1                                                   # ONE outbox row
    row = _q("select approved_by, approver_seat_id, request_sha256 from agent_delegations "
             "where delegation_id = :d", d=d)
    assert row.approved_by in (ws["member"]["email"], ws["owner"]["email"])

    started = time.monotonic()
    act_pump.kick(_engine())                                                   # as the route does
    assert _wait(lambda: (_outbox(d).attempts or 0) >= 1), "pump never attempted the send"
    assert time.monotonic() - started < 5                                      # seconds, not 6 h
    after = _outbox(d)
    assert after.status == "queued"
    wait_s = (after.na - _now()).total_seconds()
    assert 3 < wait_s <= 10.5                                                  # short ladder: 10 s
    OB.drain_actions(_engine(), eval_time=_now() + timedelta(seconds=11))
    sent = stub.for_(d)
    assert len(sent) == 2 and sent[0] == sent[1]                               # the SAME bytes
    assert all(dd == d for _, _, dd in stub.calls if dd == d)
    assert hashlib.sha256(sent[0]).hexdigest() == row.request_sha256
    doc = json.loads(sent[0])
    assert doc["delegation_id"] == d and doc["approved_by"] == row.approved_by
    assert doc["result_url"] == f"https://api.genios.test/v1/delegations/{d}/result"
    assert ws["private"] not in json.dumps(doc["context"])
    final = _outbox(d)
    assert (final.status, final.attempts) == ("delivered", 2)
    assert "dispatched" in _events(ws["org"], d)
    act_pump.stop()


# ── 3 ─────────────────────────────────────────────────────────────────────────────────────────
def test_reject_and_expiry_send_nothing_and_the_ladder_gives_up(client, ws, stub):
    from genios_engine.deliver import act_pump
    from genios_engine.deliver import outbox as OB
    act_pump.stop()
    tok = H(ws["member"]["token"])
    r = _propose(client, ws, "rejected").json()["delegation_id"]
    no = client.post(f"/v1/delegations/{r}/reject", json={"reason": "wrong time"}, headers=tok)
    assert no.status_code == 200 and no.json()["state"] == "rejected"
    late = client.post(f"/v1/delegations/{r}/approve", headers=tok)
    assert late.status_code == 200 and late.json()["state"] == "rejected"      # repeat → current
    x = _propose(client, ws, "expired").json()["delegation_id"]
    with _engine().begin() as c:
        c.execute(text("update agent_delegations set proposed_at = now() - interval '25 hours' "
                       "where delegation_id = :d"), {"d": x})
    exp = client.post(f"/v1/delegations/{x}/approve", headers=tok)
    assert exp.status_code == 200 and exp.json()["state"] == "expired"
    assert client.post(f"/v1/delegations/{x}/approve", headers=H(ws["other"]["token"])
                       ).status_code == 403
    OB.drain_actions(_engine())
    for d in (r, x):
        assert _outbox(d).n == 0 and stub.for_(d) == []
    assert _events(ws["org"], r)[-1] == "rejected" and _events(ws["org"], x)[-1] == "expired"

    # the act ladder: 10 s, 30 s, 2 min, 10 min — then give up: outbox failed_terminal, the
    # delegation `failed` with the last error, and the person told (moment.updated)
    g = _propose(client, ws, "gives-up").json()["delegation_id"]
    assert _approve_direct(ws, g)["state"] == "dispatched"
    stub.script[g] = ["timeout"] * 5
    at, gaps = _now(), []
    for _ in range(5):
        OB.drain_actions(_engine(), eval_time=at)
        ob = _outbox(g)
        if ob.status == "queued":
            gaps.append(round((ob.na - at).total_seconds()))
            at = ob.na + timedelta(seconds=1)
    assert gaps == [10, 30, 120, 600]
    assert _outbox(g).status == "failed_terminal" and len(stub.for_(g)) == 5
    assert len(set(stub.for_(g))) == 1                                         # same bytes x5
    dead = _q("select state, result from agent_delegations where delegation_id = :d", d=g)
    assert dead.state == "failed" and dead.result["source"] == "genios"
    assert "timeout" in dead.result["detail"]["error"]
    assert _events(ws["org"], g)[-1] == "failed"


# ── 4 ─────────────────────────────────────────────────────────────────────────────────────────
def test_result_intake_named_agent_once_with_conflict(client, ws, stub):
    tok = H(ws["member"]["token"])
    d = _propose(client, ws, "result").json()["delegation_id"]
    pending = _propose(client, ws, "never-approved").json()["delegation_id"]
    ok = client.post(f"/v1/delegations/{d}/approve", headers=tok)
    assert ok.status_code == 200 and ok.json() == {"delegation_id": d, "state": "dispatched"}
    assert client.post(f"/v1/delegations/{d}/approve", headers=tok).json()["state"] == "dispatched"
    assert _wait(lambda: _outbox(d).status == "delivered")                     # pump, via route
    approved = _q("select approved_by, approver_seat_id from agent_delegations "
                  "where delegation_id = :d", d=d)
    assert approved.approved_by == ws["member"]["email"]                       # the clicker
    assert approved.approver_seat_id == _seat(ws, "member")[0]

    done = {"status": "succeeded", "completed_at": "2026-09-13T10:00:00Z",
            "detail": {"provider_ref": "evt_1", "summary": "Moved to Tue 10:00"}}
    wrong = client.post(f"/v1/delegations/{d}/result", json=done, headers=H(ws["stranger"]))
    assert wrong.status_code == 404
    assert client.post(f"/v1/delegations/{d}/result", json=done,
                       headers=H(ws["owner"]["token"])).status_code == 404      # no agent
    first = client.post(f"/v1/delegations/{d}/result", json=done, headers=H(ws["hermes"]))
    assert first.status_code == 200 and first.json() == {"delegation_id": d, "state": "succeeded",
                                                         "recorded": True}
    repeat = client.post(f"/v1/delegations/{d}/result", json=done, headers=H(ws["hermes"]))
    assert repeat.status_code == 200 and repeat.json()["recorded"] is False
    clash = client.post(f"/v1/delegations/{d}/result", json={**done, "status": "failed"},
                        headers=H(ws["hermes"]))
    assert clash.status_code == 409 and clash.json()["code"] == "result_conflict"
    early = client.post(f"/v1/delegations/{pending}/result", json=done, headers=H(ws["hermes"]))
    assert early.status_code == 409 and early.json()["code"] == "not_dispatched"
    assert _q("select count(*) as n from moment_feedback where moment_id = :m and "
              "action = 'acted'", m=ws["moment"]).n == 1
    assert _events(ws["org"], d)[-1] == "succeeded"
    assert _events(ws["org"], d).count("succeeded") == 1                       # recorded once
    item = next(i for i in client.get("/v1/delegations", headers=tok).json()["delegations"]
                if i["delegation_id"] == d)
    assert item["result"] == {"status": "succeeded", "summary": "Moved to Tue 10:00",
                              "provider_ref": "evt_1", "completed_at": "2026-09-13T10:00:00Z"}
    with _engine().connect() as c:
        assert _credits(c, ws["org"]) == ws["credits"]                        # never charged


# ── 5 ─────────────────────────────────────────────────────────────────────────────────────────
def test_handoff_is_a_proposal_card_result_and_prep_delegate(client, ws, stub):
    from genios_engine.executive import delegation as DLG
    from genios_engine.reason.meetings import prep as MP
    from genios_engine.reason.team.emit import emit_situation
    org, uid = ws["org"], ws["uid"]
    member_seat = _seat(ws, "member")[0]
    card_id, _ = emit_situation(
        _engine(), None, org, kind="team", key=f"deadline_at_risk:act_{uid}", seat_id=member_seat,
        subject_node_ids=[ws["private"]], headline="Anisha is away — ISO pack due Fri",
        body="Shalini can cover.", actions=[], evidence=[], ttl_seconds=900, digest=f"d_{uid}")
    params = {"task_ref": {"provider": "linear", "id": "LIN-42"},
              "from_seat_email": ws["member"]["email"], "to_seat_email": ws["other"]["email"],
              "note": "cover while away"}
    owner = H(ws["owner"]["token"])
    assert client.post(f"/v1/insights/{card_id}/handoff", json={"draft": "just do it"},
                       headers=owner).status_code == 422                       # no free-form
    assert client.post(f"/v1/insights/{card_id}/handoff",
                       json={"play": RA, "params": {**params, "send": True}},
                       headers=owner).status_code == 422
    res = client.post(f"/v1/insights/{card_id}/handoff", json={"play": RA, "params": params},
                      headers=owner)
    assert res.status_code == 202, res.text
    d = res.json()["delegation_id"]
    assert res.json()["state"] == "proposed" and _outbox(d).n == 0            # proposal only
    assert _approve_direct(ws, d, "owner")["state"] == "dispatched"
    with _engine().begin() as c:
        outcome, state = DLG.record_agent_result(
            c, org_id=org, delegation_id=d, agent_id="hermes", status="succeeded",
            detail={"summary": "Reassigned"}, completed_at=None, at=_now())
    assert (outcome, state) == ("recorded", "succeeded")
    ev = _q("select actor_id, detail from card_events where card_id = :c and kind = 'agent.result'",
            c=card_id)
    assert ev.actor_id == "hermes" and ev.detail["delegation_id"] == d

    start = _now() + timedelta(minutes=15)
    att = MP.Attendance(meeting_node_id=ws["mtg"], me="me", attendees=(), title="Acme review",
                        start_at=start, end_at=start + timedelta(minutes=30))
    with _engine().connect() as c:
        action = MP.delegate_reschedule(c, org_id=org, att=att, now=_now())
        content = MP.with_delegate(c, org_id=org, att=att, now=_now(),
                                   content={"actions": [MP.open_meeting_action(ws["mtg"])]})
    assert action["id"] == "delegate" and action["payload"]["agent_id"] == "hermes"
    assert action["payload"]["params"]["meeting_ref"] == {"provider": "google",
                                                          "event_id": f"evt_{uid}"}
    assert [a["id"] for a in content["actions"]] == ["open_meeting", "delegate"]
    with _engine().connect() as c:
        assert _credits(c, org) == ws["credits"]
