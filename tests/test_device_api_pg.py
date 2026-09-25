"""Device API + capture policy against real Postgres — the routes, the stores, the SQL.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/scratch pytest tests/test_device_api_pg.py

Skips without a scratch database. Every test registers its own workspace through `/auth/register`
and drives the real routers over HTTP (`tests/conftest.py` points them at the scratch database).
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.platform.auth import hash_key, jwt_decode
from genios_engine.platform.capture_policy import DEFAULT_ALLOWED_APPS
from genios_engine.platform.config import get_settings

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

GRANT = "urn:ietf:params:oauth:grant-type:device_code"
_ORGS: list[str] = []


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import account_routes, auth_routes, capture_routes, device_routes
    app = FastAPI()
    for module in (auth_routes, account_routes, device_routes, capture_routes):
        app.include_router(module.router)
    settings = get_settings()
    old = settings.dashboard_url
    settings.dashboard_url = "https://app.genios.test"
    yield TestClient(app)
    settings.dashboard_url = old
    for org in _ORGS:
        try:
            with _engine().begin() as c:
                c.execute(text("delete from orgs where id=:o"), {"o": org})
        except Exception:      # noqa: BLE001 — the scratch database is dropped after the run
            pass


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client) -> dict:
    uid = uuid.uuid4().hex[:8]
    res = client.post("/auth/register", json={"name": "Founder", "password": "founder-pass-1",
                                              "email": f"founder_{uid}@device.test",
                                              "company": f"Acme {uid}"})
    assert res.status_code == 200, res.text
    body = res.json()
    _ORGS.append(body["org_id"])
    with _engine().begin() as c:
        c.execute(text("update orgs set subscription_tier='startup' where id=:o"),
                  {"o": body["org_id"]})
    return body


def _join(client, owner: dict, role: str = "member") -> dict:
    email = f"{role}_{uuid.uuid4().hex[:8]}@device.test"
    inv = client.post(f"/api/org/{owner['org_id']}/members/invite",
                      json={"email": email, "role": role}, headers=H(owner["token"]))
    assert inv.status_code == 200, inv.text
    acc = client.post(f"/invites/{inv.json()['invite_token']}/accept",
                      json={"email": email, "name": role.title(), "password": "member-pass-1"})
    assert acc.status_code == 200, acc.text
    return acc.json()


def _rewind(device_code: str) -> None:
    with _engine().begin() as c:
        c.execute(text("update device_auth_codes set last_polled_at = last_polled_at "
                       "- interval '10 seconds' where device_code_hash = :h"),
                  {"h": hash_key(device_code)})


def _issue(client) -> dict:
    res = client.post("/v1/devices/code", json={
        "client_id": "genios-desktop", "device_name": "MacBook", "platform": "macos",
        "os_version": "15.1", "app_version": "0.1.0"})
    assert res.status_code == 200, res.text
    return res.json()


def _poll(client, device_code: str):
    return client.post("/v1/devices/token", json={"grant_type": GRANT, "device_code": device_code})


def _sign_in(client, seat: dict) -> dict:
    code = _issue(client)
    assert _poll(client, code["device_code"]).json() == {"error": "authorization_pending"}
    assert _poll(client, code["device_code"]).json() == {"error": "slow_down"}
    ok = client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                     headers=H(seat["token"]))
    assert ok.status_code == 200, ok.text
    _rewind(code["device_code"])
    res = _poll(client, code["device_code"])
    assert res.status_code == 200, res.text
    assert _poll(client, code["device_code"]).json() == {"error": "expired_token"}
    return {**res.json(), "code": code}


def _session(key="li:conv:abc:2026-09-17T10", wm=37, **extra) -> dict:
    return {"session_key": key, "thread_key": "li:conv:abc", "app": "linkedin",
            "title": "Priya Shah", "participants": [{"name": "Priya Shah"}, {"self": True}],
            "messages": [{"fp": "sha256:1", "sender": "self", "ts": "2026-09-17T10:41:40+05:30",
                          "text": "Let's schedule a meeting tomorrow", "is_outgoing": True}],
            "message_watermark": wm, "captured_at": "2026-09-17T10:42:03+05:30",
            "url": "https://www.linkedin.com/messaging/thread/abc/",
            "bundle_id": "com.google.Chrome", **extra}


def _beat(client, token: str, **over):
    return client.post("/v1/presence", headers=H(token), json={
        "app_version": "0.1.0", "policy_version": None, "focus_app": "linkedin",
        "bundle_id": "com.google.Chrome", "dnd": False, "idle": False, **over})


def _count(sql: str, **params) -> int:
    with _engine().connect() as c:
        return int(c.execute(text(sql), params).scalar() or 0)


# ── sign-in ─────────────────────────────────────────────────────────────────────────────────
def test_device_sign_in_end_to_end(client):
    owner = _register(client)
    member = _join(client, owner)
    dev = _sign_in(client, member)
    org = owner["org_id"]
    assert dev["seat_id"] == member["seat_id"] and dev["org_id"] == org
    with _engine().connect() as c:
        d = c.execute(text("select seat_id, platform, device_name, revoked_at from devices "
                           "where org_id=:o and device_id=:d"),
                      {"o": org, "d": dev["device_id"]}).first()
        sid = jwt_decode(dev["access_token"], get_settings().jwt_secret)["sid"]
        s = c.execute(text("select device_id from auth_sessions where session_id=:s"),
                      {"s": sid}).first()
        code = c.execute(text("select * from device_auth_codes where device_code_hash=:h"),
                         {"h": hash_key(dev["code"]["device_code"])}).mappings().first()
    assert (d.seat_id, d.platform, d.device_name, d.revoked_at) == (
        member["seat_id"], "macos", "MacBook", None)
    assert s.device_id == dev["device_id"]
    assert code["consumed_at"] is not None and code["org_id"] == org
    raw_user = dev["code"]["user_code"]
    assert code["user_code_hash"] == hash_key(raw_user.replace("-", ""))
    assert raw_user not in json.dumps(dict(code), default=str)        # hashes only
    assert _count("select count(*) from audit_log where org_id=:o and action='device_registered'",
                  o=org) == 1
    # the refresh the desktop app will use works on a device session
    ref = client.post("/auth/refresh", json={"refresh_token": dev["refresh_token"],
                                             "device_id": dev["device_id"]})
    assert ref.status_code == 200, ref.text
    assert _beat(client, ref.json()["access_token"]).status_code == 200


def test_the_exchange_is_single_use_under_concurrency(client):
    from genios_engine.platform import devices as D
    owner = _register(client)
    code = _issue(client)
    client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                headers=H(owner["token"]))
    dstore, _ = D.stores()
    results, barrier = [], threading.Barrier(5)

    def go():
        barrier.wait()
        results.append(dstore.exchange(code["device_code"]))

    threads = [threading.Thread(target=go) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for r in results if r.tokens is not None) == 1
    assert {r.error for r in results if r.tokens is None} == {"expired_token"}
    assert _count("select count(*) from devices where org_id=:o", o=owner["org_id"]) == 1


def test_approval_errors_against_real_rows(client):
    owner = _register(client)
    other = _join(client, owner)
    unknown = client.post("/v1/devices/approve", json={"user_code": "ABCD-EFGH",
                                                       "approve": True},
                          headers=H(owner["token"]))
    assert unknown.status_code == 404
    code = _issue(client)
    client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                headers=H(owner["token"]))
    again = client.post("/v1/devices/approve", json={"user_code": code["user_code"],
                                                     "approve": True},
                        headers=H(owner["token"]))
    assert again.status_code == 409 and again.json()["status"] == "approved"
    assert client.get(f"/v1/devices/code/{code['user_code']}",
                      headers=H(other["token"])).status_code == 404
    late = _issue(client)
    with _engine().begin() as c:
        c.execute(text("update device_auth_codes set expires_at = now() - interval '1 second' "
                       "where device_code_hash = :h"), {"h": hash_key(late["device_code"])})
    assert client.post("/v1/devices/approve", json={"user_code": late["user_code"],
                                                    "approve": True},
                       headers=H(owner["token"])).status_code == 410
    assert _poll(client, late["device_code"]).json() == {"error": "expired_token"}
    no = _issue(client)
    client.post("/v1/devices/approve", json={"user_code": no["user_code"], "approve": False},
                headers=H(owner["token"]))
    assert _poll(client, no["device_code"]).json() == {"error": "access_denied"}


# ── policy + upload + presence ──────────────────────────────────────────────────────────────
def test_policy_upload_replay_and_presence(client):
    owner = _register(client)
    member = _join(client, owner)
    org = owner["org_id"]
    dev = _sign_in(client, member)
    tok = dev["access_token"]

    off = client.post("/v1/sessions", json={"schema_version": 1, "sessions": [_session()]},
                      headers=H(tok)).json()
    assert off["rejected"] == [{"session_key": _session()["session_key"],
                                "reason": "capture_disabled"}]
    assert client.put("/v1/capture/policy", json={"enabled": True},
                      headers=H(member["token"])).status_code == 403
    pol = client.put("/v1/capture/policy", headers=H(owner["token"]), json={
        "enabled": True, "retention_days": 30, "blocked_domains": ["crm.acme.test"]})
    assert pol.status_code == 200, pol.text
    assert pol.json()["org"]["blocked_domains"] == ["crm.acme.test"]
    seat = client.put("/v1/capture/settings", json={"enabled": True},
                      headers=H(member["token"]))
    assert seat.status_code == 200 and seat.json()["effective"]["capture_on"] is True
    doc = client.get("/v1/capture/policy", headers=H(tok)).json()        # the device reads it
    assert doc["policy_version"] == seat.json()["policy_version"]

    body = gzip.compress(json.dumps({"schema_version": 1, "device_id": dev["device_id"],
                                     "seat_id": member["seat_id"],
                                     "sessions": [_session()]}).encode())
    hdrs = {**H(tok), "Content-Encoding": "gzip", "Content-Type": "application/json"}
    replies = [client.post("/v1/sessions", content=body, headers=hdrs) for _ in range(3)]
    assert [r.status_code for r in replies] == [200, 200, 200]
    assert replies[0].json()["accepted"] == [_session()["session_key"]]
    assert replies[1].json()["duplicate"] == replies[2].json()["duplicate"] == [
        _session()["session_key"]]
    assert _count("select count(*) from screen_session_deltas where org_id=:o", o=org) == 1
    with _engine().connect() as c:
        row = c.execute(text("select payload_enc, status, seat_id, app, message_count "
                             "from screen_session_deltas where org_id=:o"), {"o": org}).first()
    from genios_engine.platform.crypto import decrypt
    assert (row.status, row.seat_id, row.app, row.message_count) == (
        "held", member["seat_id"], "linkedin", 1)
    assert b"schedule a meeting" not in bytes(row.payload_enc)
    sealed = json.loads(decrypt(bytes(row.payload_enc), get_settings().crypto_key))
    assert sealed["messages"][0]["text"] == "Let's schedule a meeting tomorrow"

    blocked = client.post("/v1/sessions", headers=H(tok), json={"schema_version": 1, "sessions": [
        _session(key="a", url="https://accounts.google.com/signin"),
        _session(key="b", url="https://crm.acme.test/deal/7"),
        _session(key="c", wm=38)]}).json()
    assert blocked["rejected"] == [{"session_key": "a", "reason": "domain_blocked"},
                                   {"session_key": "b", "reason": "domain_blocked"}]
    assert blocked["accepted"] == ["c"]

    client.post("/v1/capture/pause", json={"minutes": 15}, headers=H(member["token"]))
    assert client.post("/v1/sessions", headers=H(tok), json={
        "schema_version": 1, "sessions": [_session(wm=39)]}).json()["rejected"][0]["reason"] \
        == "paused"
    resumed = client.post("/v1/capture/pause", json={"minutes": 0},
                          headers=H(member["token"])).json()
    assert resumed["seat"]["paused_until"] is None

    # presence: write on first beat, not on an identical second, again on a change
    first = _beat(client, tok, policy_version=resumed["policy_version"])
    assert first.status_code == 200 and first.json()["policy_changed"] is False

    def lease():
        with _engine().connect() as c:
            return c.execute(text("select updated_at, dnd, focus_app from presence_leases "
                                  "where org_id=:o and device_id=:d"),
                             {"o": org, "d": dev["device_id"]}).first()
    one = lease()
    assert one.focus_app == "linkedin"
    _beat(client, tok, policy_version=resumed["policy_version"])
    assert lease().updated_at == one.updated_at
    _beat(client, tok, policy_version=resumed["policy_version"], dnd=True)
    two = lease()
    assert two.dnd is True and two.updated_at > one.updated_at
    assert _beat(client, tok, app_version="0.0.1").status_code == 426
    assert _count("select count(*) from devices where device_id=:d and last_seen_at is not null",
                  d=dev["device_id"]) == 1


# ── revoke / seat removal / retention ───────────────────────────────────────────────────────
def test_revoke_then_presence_401_and_refresh_fails(client):
    owner = _register(client)
    member = _join(client, owner)
    dev = _sign_in(client, member)
    listed = client.get("/v1/devices", headers=H(member["token"])).json()
    assert [d["device_id"] for d in listed] == [dev["device_id"]]
    everyone = client.get("/v1/devices?scope=org", headers=H(owner["token"])).json()
    assert everyone[0]["seat_email"] and everyone[0]["seat_id"] == member["seat_id"]
    assert client.get("/v1/devices?scope=org",
                      headers=H(member["token"])).status_code == 403

    res = client.delete(f"/v1/devices/{dev['device_id']}", headers=H(owner["token"]))
    assert res.status_code == 204
    beat = _beat(client, dev["access_token"])
    assert beat.status_code == 401 and beat.json()["code"] == "DEVICE_REVOKED"
    ref = client.post("/auth/refresh", json={"refresh_token": dev["refresh_token"],
                                             "device_id": dev["device_id"]})
    assert ref.status_code == 401 and ref.json()["detail"]["code"] == "SESSION_REVOKED"
    assert client.get("/v1/capture/policy", headers=H(dev["access_token"])).status_code == 401
    assert client.get("/v1/devices", headers=H(member["token"])).json()[0]["revoked_at"]
    assert client.delete(f"/v1/devices/{dev['device_id']}",
                         headers=H(owner["token"])).status_code == 204
    assert _count("select count(*) from audit_log where org_id=:o and action='device_revoked'",
                  o=owner["org_id"]) == 1
    # the member's DASHBOARD session is untouched by revoking one device
    assert client.get("/v1/devices", headers=H(member["token"])).status_code == 200


def test_removing_a_member_revokes_their_devices_and_shreds_their_capture(client):
    owner = _register(client)
    member = _join(client, owner)
    org = owner["org_id"]
    dev = _sign_in(client, member)
    client.put("/v1/capture/policy", json={"enabled": True}, headers=H(owner["token"]))
    client.put("/v1/capture/settings", json={"enabled": True}, headers=H(member["token"]))
    assert client.post("/v1/sessions", headers=H(dev["access_token"]), json={
        "schema_version": 1, "sessions": [_session()]}).json()["accepted"]
    _beat(client, dev["access_token"])
    with _engine().connect() as c:
        member_id = c.execute(text("select id from org_members where org_id=:o and seat_id=:s"),
                              {"o": org, "s": member["seat_id"]}).scalar()
    res = client.post(f"/api/org/{org}/members/{member_id}/deactivate", headers=H(owner["token"]))
    assert res.status_code == 200, res.text
    assert res.json()["devices_revoked"] == 1
    assert _count("select count(*) from screen_session_deltas where org_id=:o and seat_id=:s",
                  o=org, s=member["seat_id"]) == 0
    assert _count("select count(*) from presence_leases where org_id=:o and seat_id=:s",
                  o=org, s=member["seat_id"]) == 0
    assert _count("select count(*) from seat_capture_settings where org_id=:o and seat_id=:s",
                  o=org, s=member["seat_id"]) == 0
    assert _count("select count(*) from devices where org_id=:o and revoked_at is null",
                  o=org) == 0
    beat = _beat(client, dev["access_token"])
    assert beat.status_code == 401 and beat.json()["code"] == "DEVICE_REVOKED"


def test_retention_deletes_only_what_is_past_each_orgs_horizon(client):
    from genios_engine.platform.capture_policy import CaptureStore
    short, long_ = _register(client), _register(client)
    for owner, days in ((short, 3), (long_, 90)):
        client.put("/v1/capture/policy", json={"enabled": True, "retention_days": days},
                   headers=H(owner["token"]))
        client.put("/v1/capture/settings", json={"enabled": True}, headers=H(owner["token"]))
        dev = _sign_in(client, owner)
        for wm in (1, 2):
            assert client.post("/v1/sessions", headers=H(dev["access_token"]), json={
                "schema_version": 1, "sessions": [_session(wm=wm)]}).json()["accepted"]
        with _engine().begin() as c:          # both orgs: one row 5 days old, one fresh
            c.execute(text("update screen_session_deltas set received_at = now() - "
                           "interval '5 days' where org_id=:o and message_watermark=1"),
                      {"o": owner["org_id"]})
    out = CaptureStore(_engine()).purge_expired(batch=1)
    assert out["screen_session_deltas"] >= 1
    assert _count("select count(*) from screen_session_deltas where org_id=:o",
                  o=short["org_id"]) == 1                     # the 5-day row is past 3 days
    assert _count("select count(*) from screen_session_deltas where org_id=:o",
                  o=long_["org_id"]) == 2                     # 5 days is inside 90


def test_the_reset_route_erases_captured_content_but_keeps_devices_and_policy(client):
    owner = _register(client)
    org = owner["org_id"]
    client.put("/v1/capture/policy", json={"enabled": True}, headers=H(owner["token"]))
    client.put("/v1/capture/settings", json={"enabled": True}, headers=H(owner["token"]))
    dev = _sign_in(client, owner)
    client.post("/v1/sessions", headers=H(dev["access_token"]),
                json={"schema_version": 1, "sessions": [_session()]})
    res = client.post(f"/api/org/{org}/reset", headers=H(owner["token"]))
    assert res.status_code == 200, res.text
    assert _count("select count(*) from screen_session_deltas where org_id=:o", o=org) == 0
    assert _count("select count(*) from devices where org_id=:o", o=org) == 1
    assert _count("select count(*) from capture_policies where org_id=:o", o=org) == 1


def test_account_deletion_cascades_every_capture_table(client):
    owner = _register(client)
    org = owner["org_id"]
    client.put("/v1/capture/policy", json={"enabled": True}, headers=H(owner["token"]))
    client.put("/v1/capture/settings", json={"enabled": True}, headers=H(owner["token"]))
    dev = _sign_in(client, owner)
    client.post("/v1/sessions", headers=H(dev["access_token"]),
                json={"schema_version": 1, "sessions": [_session()]})
    _beat(client, dev["access_token"])
    with _engine().begin() as c:
        c.execute(text("delete from orgs where id=:o"), {"o": org})
    for table in ("devices", "device_auth_codes", "capture_policies", "seat_capture_settings",
                  "screen_session_deltas", "presence_leases"):
        assert _count(f"select count(*) from {table} where org_id=:o", o=org) == 0, table


# ── D2 revised (plan §3.7): every app is read ───────────────────────────────────────────────
def _generic(key="doc:erp:1", wm=1, url=None, bundle_id="com.acme.erp", **extra) -> dict:
    return {"session_key": key, "app": "generic", "title": "Invoices", "url": url,
            "bundle_id": bundle_id, "message_watermark": wm,
            "blocks": [{"fp": "sha256:a", "role": "heading", "text": "Open invoices"},
                       {"fp": "sha256:b", "role": "table", "header": ["Invoice", "Due"],
                        "rows": [["INV-9", "2026-09-20"]]},
                       {"fp": "sha256:c", "role": "kv", "label": "Owner", "value": "Priya"}],
            **extra}


def test_every_app_is_read_by_default_and_each_reader_can_be_switched_off(client):
    owner = _register(client)
    org = owner["org_id"]
    doc = client.get("/v1/capture/policy", headers=H(owner["token"])).json()
    # READ OFF THE CONSTANT, never re-typed. This literal said six apps and `DEFAULT_ALLOWED_APPS`
    # had said seven since `teams` landed, so the assertion failed on a real database for a reason
    # that is not a defect — a wave adding a surface would otherwise have to edit this line, and a
    # wave that forgot would look like a policy regression.
    assert doc["org"]["allowed_apps"] == list(DEFAULT_ALLOWED_APPS)
    assert doc["org"]["generic_web_allowed"] is True and doc["seat"]["generic_web"] is True
    # the column defaults agree with the in-code defaults once a row exists
    client.put("/v1/capture/policy", json={"enabled": True}, headers=H(owner["token"]))
    client.put("/v1/capture/settings", json={"enabled": True}, headers=H(owner["token"]))
    with _engine().connect() as c:
        p = c.execute(text("select allowed_apps, generic_web_allowed from capture_policies "
                           "where org_id=:o"), {"o": org}).first()
        s = c.execute(text("select generic_web from seat_capture_settings where org_id=:o"),
                      {"o": org}).first()
    assert list(p.allowed_apps) == list(DEFAULT_ALLOWED_APPS)
    assert p.generic_web_allowed is True and s.generic_web is True

    dev = _sign_in(client, owner)
    tok = dev["access_token"]
    res = client.post("/v1/sessions", headers=H(tok), json={"schema_version": 1, "sessions": [
        _generic(),                                                    # native: no url
        _generic(key="doc:web:1", app="web", url="https://erp.acme.test/invoices",
                 bundle_id="com.google.Chrome"),                       # `web` = generic
        _generic(key="doc:bank:1", url="https://netbanking.hdfcbank.com/",
                 bundle_id="com.google.Chrome"),
        _generic(key="doc:nobundle:1", bundle_id=None),
        _session(key="wa:1", app="whatsapp", url=None, bundle_id="net.whatsapp.WhatsApp")]}).json()
    assert res["accepted"] == ["doc:erp:1", "doc:web:1", "wa:1"]
    assert res["rejected"] == [{"session_key": "doc:bank:1", "reason": "domain_blocked"},
                               {"session_key": "doc:nobundle:1", "reason": "invalid_session"}]
    with _engine().connect() as c:
        rows = {r.session_key: r for r in c.execute(text(
            "select session_key, app, message_count from screen_session_deltas "
            "where org_id=:o"), {"o": org})}
    assert (rows["doc:erp:1"].app, rows["doc:erp:1"].message_count) == ("generic", 3)
    assert rows["doc:web:1"].app == "generic"
    assert (rows["wa:1"].app, rows["wa:1"].message_count) == ("whatsapp", 1)

    client.put("/v1/capture/policy", json={"allowed_apps": ["gmail"]}, headers=H(owner["token"]))
    off = client.post("/v1/sessions", headers=H(tok), json={"schema_version": 1, "sessions": [
        _session(key="wa:2", app="whatsapp", url=None)]}).json()
    assert off["rejected"] == [{"session_key": "wa:2", "reason": "reader_disabled"}]
    client.put("/v1/capture/settings", json={"generic_web": False}, headers=H(owner["token"]))
    gen = client.post("/v1/sessions", headers=H(tok), json={"schema_version": 1, "sessions": [
        _generic(key="doc:erp:2")]}).json()
    assert gen["rejected"] == [{"session_key": "doc:erp:2", "reason": "generic_disabled"}]


def test_context_blocks_round_trip_through_the_encrypted_payload(client):
    from genios_engine.platform.crypto import decrypt
    owner = _register(client)
    org = owner["org_id"]
    client.put("/v1/capture/policy", json={"enabled": True}, headers=H(owner["token"]))
    client.put("/v1/capture/settings", json={"enabled": True}, headers=H(owner["token"]))
    dev = _sign_in(client, owner)
    ctx = [{"fp": f"sha256:ctx{i}", "role": "text", "text": f"unchanged {i}"} for i in range(10)]
    res = client.post("/v1/sessions", headers=H(dev["access_token"]), json={
        "schema_version": 1, "sessions": [
            _generic(context_blocks=ctx),
            _generic(key="doc:erp:too-many", context_blocks=ctx + ctx[:1])]}).json()
    assert res["accepted"] == ["doc:erp:1"]
    assert res["rejected"] == [{"session_key": "doc:erp:too-many", "reason": "invalid_session"}]
    with _engine().connect() as c:
        row = c.execute(text("select payload_enc, message_count from screen_session_deltas "
                             "where org_id=:o"), {"o": org}).first()
    assert row.message_count == 3
    sealed = json.loads(decrypt(bytes(row.payload_enc), get_settings().crypto_key))
    assert sealed["context_blocks"] == ctx
