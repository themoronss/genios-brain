"""Device API + capture policy — the hermetic half (no database).

The routes are the real routers; the stores are `tests/device_fakes.py`, which apply the same pure
decisions as the Postgres stores. `tests/test_device_api_pg.py` runs the SQL.

What these pin (contract: docs/plans/SCREEN_INTEL_P1_BUILD.md §3):
  * RFC 8628: pending → slow_down → approved → consumed; denied; expired; single use;
  * the user code alphabet, hashing, and the approval error vocabulary (404 / 410 / 409);
  * `gn_live_` keys and pre-session JWTs are refused by every device and seat endpoint;
  * revoke → the next heartbeat is 401 `DEVICE_REVOKED` (even on an expired token) and the
    device's sessions are revoked;
  * uploads are idempotent (the same body 3× → 1 row), encrypted, and re-checked server-side:
    org disabled, seat off, paused, app not allowed, sensitive URL / app, private window;
  * presence writes only on change or every 30 s; an old app gets 426;
  * the policy merge: a seat only narrows the org; the sensitive list cannot be removed; a
    30-URL sensitive-domain suite.
"""
from __future__ import annotations

import gzip
import json
import re
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from tests.device_fakes import MemoryCaptureStore, MemoryDeviceStore, World

from genios_engine.api import capture_routes, device_routes
from genios_engine.platform import audit, auth
from genios_engine.platform import capture_policy as P
from genios_engine.platform import devices as D
from genios_engine.platform.auth import (MEMBER_SCOPES, ROLE_MEMBER, AuthCtx, hash_key,
                                         jwt_decode, jwt_encode, seat_role)
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt

ORG = "org_dev"
GRANT = "urn:ietf:params:oauth:grant-type:device_code"
NOW = datetime.now(timezone.utc)


# ── harness ───────────────────────────────────────────────────────────────────────────────────
def _fake_verify(w: World, token: str) -> AuthCtx:
    """`auth.verify_bearer` over the in-memory world — same outcomes as `auth._session_ctx`
    (which `tests/test_seat_identity.py` pins against its own fakes)."""
    if token.startswith("gn_live_"):
        return AuthCtx(org_id=ORG, actor_id="org_primary_key", scopes=None, source="legacy")
    payload = jwt_decode(token, get_settings().jwt_secret)
    if not payload:
        raise HTTPException(401, {"code": "SESSION_EXPIRED"})
    sid = payload.get("sid")
    if not sid:                                     # a pre-session token: the owner, no session
        return AuthCtx(org_id=payload["org_id"], actor_id="founder@acme.test", scopes=None,
                       source="jwt", seat_id="seat_owner", role="owner",
                       email="founder@acme.test")
    s = w.sessions.get(sid)
    seat = w.seats.get((s["org_id"], s["seat_id"])) if s else None
    if s is None or s["revoked_at"] is not None or not seat or not seat["active"]:
        raise HTTPException(401, {"code": "TOKEN_REVOKED"})
    role = seat_role(seat["email"], seat["role"], w.orgs[s["org_id"]]["email"])
    return AuthCtx(org_id=s["org_id"], actor_id=seat["email"],
                   scopes=None if role != ROLE_MEMBER else sorted(MEMBER_SCOPES), source="jwt",
                   seat_id=s["seat_id"], role=role, email=seat["email"], session_id=sid)


@pytest.fixture
def world(monkeypatch):
    w = World()
    w.add_org(ORG, "founder@acme.test")
    w.add_seat(ORG, "seat_owner", "founder@acme.test", role="admin")
    w.add_seat(ORG, "seat_ops", "ops@acme.test", role="admin")
    w.add_seat(ORG, "seat_rep", "rep@acme.test", role="member")
    w.add_seat(ORG, "seat_other", "other@acme.test", role="member")
    dstore, cstore = MemoryDeviceStore(w), MemoryCaptureStore(w)
    monkeypatch.setattr(D, "stores", lambda: (dstore, cstore))
    monkeypatch.setattr(auth, "check_kill_switch", lambda: None)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    monkeypatch.setattr(auth, "verify_bearer", lambda tok: _fake_verify(w, tok))
    monkeypatch.setattr(get_settings(), "dashboard_url", "https://app.genios.test")
    w.audit = []
    monkeypatch.setattr(audit, "record",
                        lambda org, action, **kw: w.audit.append((org, action, kw)))
    return w


@pytest.fixture
def client(world):
    app = FastAPI()
    app.include_router(device_routes.router)
    app.include_router(capture_routes.router)
    return TestClient(app)


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _seat(w: World, seat_id: str) -> str:
    return w.open(ORG, seat_id).access_token


def _issue(client) -> dict:
    res = client.post("/v1/devices/code", json={
        "client_id": "genios-desktop", "device_name": "Rep's MacBook", "platform": "macos",
        "os_version": "15.1", "app_version": "0.1.0"})
    assert res.status_code == 200, res.text
    return res.json()


def _poll(client, device_code: str):
    return client.post("/v1/devices/token", json={"grant_type": GRANT, "device_code": device_code})


def _rewind_poll(w: World, device_code: str, seconds: float = 10) -> None:
    row = w.codes[hash_key(device_code)]
    if row["last_polled_at"] is not None:
        row["last_polled_at"] -= timedelta(seconds=seconds)


def _sign_in(client, w: World, seat_id: str = "seat_rep") -> dict:
    code = _issue(client)
    ok = client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                     headers=H(_seat(w, seat_id)))
    assert ok.status_code == 200, ok.text
    res = _poll(client, code["device_code"])
    assert res.status_code == 200, res.text
    return res.json()


def _enable(w: World, seat_id: str = "seat_rep", **org) -> None:
    cstore = MemoryCaptureStore(w)
    cstore.save_org_policy(ORG, {"enabled": True, **org}, updated_by="seat_owner")
    cstore.save_seat_settings(ORG, seat_id, {"enabled": True})


def _session(key="li:conv:abc:2026-09-17T10", wm=37, app="linkedin",
             url="https://www.linkedin.com/messaging/thread/abc/", **extra) -> dict:
    return {"session_key": key, "thread_key": "li:conv:abc", "app": app, "title": "Priya Shah",
            "participants": [{"name": "Priya Shah",
                              "linkedin_url": "https://www.linkedin.com/in/priyashah"},
                             {"self": True}],
            "context_messages": [{"sender": "Priya Shah", "ts": "2026-09-16T18:02:00+05:30",
                                  "text": "Can we talk pricing?"}],
            "messages": [{"fp": "sha256:1", "sender": "self", "ts": "2026-09-17T10:41:40+05:30",
                          "text": "Let's schedule a meeting tomorrow", "is_outgoing": True}],
            "message_watermark": wm, "captured_at": "2026-09-17T10:42:03+05:30", "url": url,
            "bundle_id": "com.google.Chrome", **extra}


def _generic(key="doc:crm.acme.test/deals/42:2026-09-17T10", wm=3,
             url="https://crm.acme.test/deals/42", bundle_id="com.google.Chrome",
             **extra) -> dict:
    """A generic-reader session (§3.7 `screen_doc` blocks in place of messages)."""
    return {"session_key": key, "thread_key": "doc:crm.acme.test/deals/42", "app": "generic",
            "title": "Acme — Deal",
            "blocks": [{"fp": "sha256:a", "role": "heading", "text": "Acme renewal"},
                       {"fp": "sha256:b", "role": "kv", "label": "Stage",
                        "value": "Negotiation"},
                       {"fp": "sha256:c", "role": "table", "header": ["Invoice", "Due", "Status"],
                        "rows": [["INV-9", "2026-09-20", "Unpaid"]]},
                       {"fp": "sha256:d", "role": "message", "sender": "Priya", "ts": None,
                        "text": "Can you send the invoice?", "is_outgoing": False}],
            "message_watermark": wm, "captured_at": "2026-09-17T10:42:03+05:30", "url": url,
            "bundle_id": bundle_id, **extra}


def _upload(client, token: str, sessions: list, **env):
    return client.post("/v1/sessions", json={"schema_version": 1, "sessions": sessions, **env},
                       headers=H(token))


def _beat(client, token: str, **over):
    body = {"app_version": "0.1.0", "policy_version": None, "focus_app": "linkedin",
            "bundle_id": "com.google.Chrome", "dnd": False, "idle": False, **over}
    return client.post("/v1/presence", json=body, headers=H(token))


# ── §3.1 codes ────────────────────────────────────────────────────────────────────────────────
def test_a_code_is_issued_in_the_contract_shape_and_stored_only_as_hashes(client, world):
    body = _issue(client)
    assert set(body) == {"device_code", "user_code", "verification_uri",
                         "verification_uri_complete", "expires_in", "interval"}
    assert re.fullmatch(r"[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}", body["user_code"])
    assert body["verification_uri"] == "https://app.genios.test/device"
    assert body["verification_uri_complete"] == (
        f"https://app.genios.test/device?user_code={body['user_code']}")
    assert (body["expires_in"], body["interval"]) == (600, 5)
    assert len(body["device_code"]) >= 43                     # 32 random bytes, urlsafe
    (row_hash, row), = world.codes.items()
    assert row_hash == hash_key(body["device_code"])
    assert row["user_code_hash"] == hash_key(body["user_code"].replace("-", ""))
    assert body["device_code"] not in json.dumps(row, default=str)


def test_the_user_code_alphabet_has_nothing_a_person_misreads():
    codes = {D.new_user_code() for _ in range(3000)}
    assert not any(ch in c for c in codes for ch in "0O1I")
    assert all(len(c) == 8 for c in codes)
    assert D.normalize_user_code("abcd-efgh") == "ABCDEFGH"
    assert D.normalize_user_code(" abcd efgh ") == "ABCDEFGH"
    assert D.normalize_user_code("ABCD-EFG0") is None             # 0 is never issued
    assert D.normalize_user_code("ABCD-EFG") is None
    assert D.format_user_code("ABCDEFGH") == "ABCD-EFGH"


def test_a_code_request_names_the_desktop_client_and_a_known_platform(client):
    bad = client.post("/v1/devices/code", json={"client_id": "evil", "platform": "macos"})
    assert bad.status_code == 400 and bad.json()["error"] == "invalid_client"
    bad = client.post("/v1/devices/code", json={"client_id": "genios-desktop",
                                                "platform": "amiga"})
    assert bad.status_code == 400 and bad.json()["error"] == "invalid_request"


def test_code_requests_are_rate_limited_per_ip(client, monkeypatch):
    counts: dict[str, int] = {}

    class _Cache:
        def incr_window(self, key, ttl):
            counts[key] = counts.get(key, 0) + 1
            return counts[key]

    monkeypatch.setattr(device_routes, "get_cache", lambda: _Cache())
    for _ in range(20):
        _issue(client)
    res = client.post("/v1/devices/code", json={"client_id": "genios-desktop",
                                                "platform": "macos"})
    assert res.status_code == 429 and res.json()["error"] == "slow_down"
    assert list(counts) == ["devcode:ip:testclient"]


def test_no_dashboard_url_in_production_is_a_503_not_a_guessed_link(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "dashboard_url", "")
    monkeypatch.setattr(get_settings(), "env", "production")
    res = client.post("/v1/devices/code", json={"client_id": "genios-desktop",
                                                "platform": "macos"})
    assert res.status_code == 503 and res.json()["error"] == "temporarily_unavailable"


# ── §3.1 the RFC 8628 sequence ────────────────────────────────────────────────────────────────
def test_pending_then_slow_down_then_approved_then_consumed(client, world):
    code = _issue(client)
    first = _poll(client, code["device_code"])
    assert (first.status_code, first.json()) == (400, {"error": "authorization_pending"})
    fast = _poll(client, code["device_code"])
    assert (fast.status_code, fast.json()) == (400, {"error": "slow_down"})
    _rewind_poll(world, code["device_code"])
    assert _poll(client, code["device_code"]).json() == {"error": "authorization_pending"}

    seat = _seat(world, "seat_rep")
    view = client.get(f"/v1/devices/code/{code['user_code'].lower()}", headers=H(seat))
    assert view.status_code == 200, view.text
    assert view.json()["status"] == "pending" and view.json()["device_name"] == "Rep's MacBook"
    assert set(view.json()) == {"user_code", "device_name", "platform", "os_version",
                                "app_version", "requested_at", "expires_at", "status"}
    ok = client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                     headers=H(seat))
    assert ok.status_code == 200 and ok.json()["ok"] is True
    device_id = ok.json()["device_id"]
    assert device_id.startswith("dev_")
    assert client.get(f"/v1/devices/code/{code['user_code']}",
                      headers=H(seat)).json()["status"] == "approved"

    _rewind_poll(world, code["device_code"])
    res = _poll(client, code["device_code"])
    assert res.status_code == 200, res.text
    tok = res.json()
    assert tok["device_id"] == device_id and tok["seat_id"] == "seat_rep"
    assert tok["refresh_token"] and tok["access_token"] == tok["token"]
    assert res.headers["cache-control"] == "no-store"
    claims = jwt_decode(tok["access_token"], get_settings().jwt_secret)
    assert world.sessions[claims["sid"]]["device_id"] == device_id      # session opened for it
    assert world.devices[device_id]["seat_id"] == "seat_rep"
    assert [a[1] for a in world.audit] == ["device_registered"]

    again = _poll(client, code["device_code"])                          # single use
    assert (again.status_code, again.json()) == (400, {"error": "expired_token"})


def test_a_denied_code_answers_access_denied(client, world):
    code = _issue(client)
    res = client.post("/v1/devices/approve", json={"user_code": code["user_code"],
                                                   "approve": False},
                      headers=H(_seat(world, "seat_rep")))
    assert res.status_code == 200 and res.json() == {"ok": True}
    assert _poll(client, code["device_code"]).json() == {"error": "access_denied"}
    assert client.get(f"/v1/devices/code/{code['user_code']}",
                      headers=H(_seat(world, "seat_rep"))).json()["status"] == "denied"


def test_an_expired_code_answers_expired_token_and_410(client, world):
    code = _issue(client)
    world.codes[hash_key(code["device_code"])]["expires_at"] = NOW - timedelta(seconds=1)
    assert _poll(client, code["device_code"]).json() == {"error": "expired_token"}
    seat = _seat(world, "seat_rep")
    assert client.get(f"/v1/devices/code/{code['user_code']}",
                      headers=H(seat)).json()["status"] == "expired"
    res = client.post("/v1/devices/approve", json={"user_code": code["user_code"],
                                                   "approve": True}, headers=H(seat))
    assert res.status_code == 410 and res.json()["code"] == "CODE_EXPIRED"


def test_an_unknown_device_code_or_grant_type_is_refused(client):
    assert _poll(client, "nope").json() == {"error": "expired_token"}
    res = client.post("/v1/devices/token", json={"grant_type": "password", "device_code": "x"})
    assert res.status_code == 400 and res.json() == {"error": "unsupported_grant_type"}


def test_approval_errors_follow_the_pinned_vocabulary(client, world):
    seat = _seat(world, "seat_rep")
    unknown = client.post("/v1/devices/approve", json={"user_code": "ABCD-EFGH", "approve": True},
                          headers=H(seat))
    assert unknown.status_code == 404 and unknown.json()["code"] == "CODE_NOT_FOUND"
    assert client.get("/v1/devices/code/ABCD-EFGH", headers=H(seat)).status_code == 404
    assert client.get("/v1/devices/code/NOT-ACODE", headers=H(seat)).status_code == 404

    code = _issue(client)
    client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                headers=H(seat))
    for approve in (True, False):                     # already approved → 409 either way
        res = client.post("/v1/devices/approve", json={"user_code": code["user_code"],
                                                       "approve": approve}, headers=H(seat))
        assert res.status_code == 409
        assert (res.json()["code"], res.json()["status"]) == ("CODE_ALREADY_APPROVED", "approved")
    # another seat of the same org never learns the code exists
    other = client.post("/v1/devices/approve", json={"user_code": code["user_code"],
                                                     "approve": True},
                        headers=H(_seat(world, "seat_other")))
    assert other.status_code == 404
    assert client.get(f"/v1/devices/code/{code['user_code']}",
                      headers=H(_seat(world, "seat_other"))).status_code == 404
    _poll(client, code["device_code"])                                  # consume it
    used = client.post("/v1/devices/approve", json={"user_code": code["user_code"],
                                                    "approve": True}, headers=H(seat))
    assert used.status_code == 409 and used.json()["status"] == "approved"

    denied = _issue(client)
    client.post("/v1/devices/approve", json={"user_code": denied["user_code"], "approve": False},
                headers=H(seat))
    res = client.post("/v1/devices/approve", json={"user_code": denied["user_code"],
                                                   "approve": True}, headers=H(seat))
    assert res.status_code == 409
    assert (res.json()["code"], res.json()["status"]) == ("CODE_ALREADY_DENIED", "denied")


def test_a_seat_deactivated_between_approval_and_exchange_gets_no_device(client, world):
    code = _issue(client)
    client.post("/v1/devices/approve", json={"user_code": code["user_code"], "approve": True},
                headers=H(_seat(world, "seat_rep")))
    world.seats[(ORG, "seat_rep")]["active"] = False
    assert _poll(client, code["device_code"]).json() == {"error": "access_denied"}
    assert world.devices == {}


# ── who may call what ─────────────────────────────────────────────────────────────────────────
def _presession_jwt() -> str:
    return jwt_encode({"org_id": ORG, "email": "founder@acme.test", "exp": time.time() + 600},
                      get_settings().jwt_secret)


@pytest.mark.parametrize("method,path,body", [
    ("get", "/v1/devices", None),
    ("get", "/v1/devices/code/ABCD-EFGH", None),
    ("post", "/v1/devices/approve", {"user_code": "ABCD-EFGH", "approve": True}),
    ("delete", "/v1/devices/dev_x", None),
    ("get", "/v1/capture/policy", None),
    ("put", "/v1/capture/policy", {"enabled": True}),
    ("put", "/v1/capture/settings", {"enabled": True}),
    ("post", "/v1/capture/pause", {"minutes": 5}),
])
def test_seat_endpoints_refuse_org_keys_and_presession_tokens(client, method, path, body):
    kw = {"json": body} if body is not None else {}
    assert getattr(client, method)(path, **kw).status_code == 401
    key = getattr(client, method)(path, headers=H("gn_live_primarykey"), **kw)
    assert key.status_code == 403
    legacy = getattr(client, method)(path, headers=H(_presession_jwt()), **kw)
    assert legacy.status_code == 403
    assert legacy.json()["detail"]["code"] == "SEAT_SESSION_REQUIRED"


@pytest.mark.parametrize("path,body", [
    ("/v1/presence", {"app_version": "0.1.0", "dnd": False, "idle": False}),
    ("/v1/sessions", {"schema_version": 1, "sessions": []}),
])
def test_device_endpoints_refuse_keys_presession_and_dashboard_tokens(client, world, path, body):
    none = client.post(path, json=body)
    assert none.status_code == 401 and none.json()["code"] == "MISSING_TOKEN"
    for token in ("gn_live_primarykey", _presession_jwt(), _seat(world, "seat_rep")):
        res = client.post(path, json=body, headers=H(token))
        assert res.status_code == 403, (token[:12], res.text)
        assert res.json()["code"] == "DEVICE_TOKEN_REQUIRED"


def test_a_session_label_that_names_another_seats_device_is_not_that_device(client, world):
    dev = _sign_in(client, world, "seat_rep")
    # a session of seat_other that CLAIMS rep's device id (a free-text login label) is refused
    forged = world.open(ORG, "seat_other", device_id=dev["device_id"])
    res = _beat(client, forged.access_token)
    assert res.status_code == 403 and res.json()["code"] == "DEVICE_TOKEN_REQUIRED"


# ── list / revoke ─────────────────────────────────────────────────────────────────────────────
def test_devices_are_listed_per_seat_and_per_org_for_admins(client, world):
    rep = _sign_in(client, world, "seat_rep")
    ops = _sign_in(client, world, "seat_ops")
    own = client.get("/v1/devices", headers=H(_seat(world, "seat_rep"))).json()
    assert [d["device_id"] for d in own] == [rep["device_id"]]
    assert set(own[0]) == {"device_id", "seat_id", "seat_email", "device_name", "platform",
                           "os_version", "app_version", "last_seen_at", "created_at",
                           "revoked_at"}
    assert own[0]["seat_email"] == "rep@acme.test" and own[0]["revoked_at"] is None
    everyone = client.get("/v1/devices?scope=org", headers=H(_seat(world, "seat_ops"))).json()
    assert {d["device_id"] for d in everyone} == {rep["device_id"], ops["device_id"]}
    assert client.get("/v1/devices?scope=org",
                      headers=H(_seat(world, "seat_rep"))).status_code == 403


def test_revoke_ends_the_device_its_sessions_and_its_next_heartbeat(client, world):
    dev = _sign_in(client, world, "seat_rep")
    assert _beat(client, dev["access_token"]).status_code == 200
    # another member cannot revoke it; an admin can; its own seat can
    assert client.delete(f"/v1/devices/{dev['device_id']}",
                         headers=H(_seat(world, "seat_other"))).status_code == 403
    assert client.delete("/v1/devices/dev_nope",
                         headers=H(_seat(world, "seat_rep"))).status_code == 404
    res = client.delete(f"/v1/devices/{dev['device_id']}", headers=H(_seat(world, "seat_rep")))
    assert res.status_code == 204 and res.content == b""
    assert world.devices[dev["device_id"]]["revoked_at"] is not None
    sessions = [s for s in world.sessions.values() if s["device_id"] == dev["device_id"]]
    assert sessions and all(s["revoked_at"] is not None for s in sessions)   # refresh is dead
    assert world.leases == {}

    beat = _beat(client, dev["access_token"])
    assert beat.status_code == 401
    assert beat.json()["code"] == "DEVICE_REVOKED"                   # top level, per §3.4
    assert beat.json()["detail"]["code"] == "DEVICE_REVOKED"
    up = _upload(client, dev["access_token"], [_session()])
    assert up.status_code == 401 and up.json()["code"] == "DEVICE_REVOKED"
    # even an EXPIRED token is told the device is revoked — that is what makes the app wipe
    claims = jwt_decode(dev["access_token"], get_settings().jwt_secret)
    stale = jwt_encode({**claims, "exp": time.time() - 60}, get_settings().jwt_secret)
    assert _beat(client, stale).json()["code"] == "DEVICE_REVOKED"
    # revoking again is still 204 and audits nothing new
    again = client.delete(f"/v1/devices/{dev['device_id']}", headers=H(_seat(world, "seat_ops")))
    assert again.status_code == 204
    assert [a[1] for a in world.audit].count("device_revoked") == 1


def test_an_expired_token_on_a_live_device_asks_for_a_refresh(client, world):
    dev = _sign_in(client, world)
    claims = jwt_decode(dev["access_token"], get_settings().jwt_secret)
    stale = jwt_encode({**claims, "exp": time.time() - 60}, get_settings().jwt_secret)
    res = _beat(client, stale)
    assert res.status_code == 401 and res.json()["code"] == "SESSION_EXPIRED"


def test_a_deactivated_seat_is_refused_on_its_device_token(client, world):
    dev = _sign_in(client, world)
    world.seats[(ORG, "seat_rep")]["active"] = False
    res = _beat(client, dev["access_token"])
    assert res.status_code == 401 and res.json()["code"] == "TOKEN_REVOKED"


# ── §3.4 presence ─────────────────────────────────────────────────────────────────────────────
def test_presence_writes_only_on_change_or_every_thirty_seconds(client, world):
    _enable(world)
    dev = _sign_in(client, world)
    first = _beat(client, dev["access_token"])
    assert first.status_code == 200, first.text
    body = first.json()
    assert set(body) == {"revoked", "policy_version", "policy_changed",
                         "min_supported_app_version", "server_time"}
    assert body["revoked"] is False and body["policy_changed"] is True
    version = body["policy_version"]
    assert world.presence_writes == 1

    same = _beat(client, dev["access_token"], policy_version=version)
    assert same.json()["policy_changed"] is False
    assert world.presence_writes == 2                  # policy_version itself changed on the row
    _beat(client, dev["access_token"], policy_version=version)
    _beat(client, dev["access_token"], policy_version=version)
    assert world.presence_writes == 2                  # nothing changed → no write
    _beat(client, dev["access_token"], policy_version=version, dnd=True)
    assert world.presence_writes == 3                  # a field changed
    lease = next(iter(world.leases.values()))
    lease["updated_at"] -= timedelta(seconds=31)
    _beat(client, dev["access_token"], policy_version=version, dnd=True)
    assert world.presence_writes == 4                  # the row went stale
    # a policy change reaches the device as a changed version
    MemoryCaptureStore(world).save_org_policy(ORG, {"allowed_apps": ["gmail"]},
                                              updated_by="seat_owner")
    changed = _beat(client, dev["access_token"], policy_version=version, dnd=True).json()
    assert changed["policy_changed"] is True and changed["policy_version"] != version


def test_presence_does_not_record_focus_before_opt_in_or_on_a_sensitive_app(client, world):
    dev = _sign_in(client, world)
    _beat(client, dev["access_token"])
    lease = next(iter(world.leases.values()))
    assert (lease["focus_app"], lease["bundle_id"]) == (None, None)     # not opted in
    _enable(world)
    _beat(client, dev["access_token"], focus_app="term", bundle_id="com.apple.Terminal")
    lease = next(iter(world.leases.values()))
    assert (lease["focus_app"], lease["bundle_id"]) == (None, None)
    _beat(client, dev["access_token"])
    lease = next(iter(world.leases.values()))
    assert (lease["focus_app"], lease["bundle_id"]) == ("linkedin", "com.google.Chrome")


@pytest.mark.parametrize("version", ["0.0.9", "garbage", ""])
def test_an_app_below_the_minimum_version_gets_426(client, world, version):
    dev = _sign_in(client, world)
    res = _beat(client, dev["access_token"], app_version=version)
    assert res.status_code == 426
    assert res.json()["code"] == "APP_UPDATE_REQUIRED"
    assert res.json()["min_supported_app_version"] == "0.1.0"


def test_version_parsing():
    assert P.version_tuple("0.1.0") == (0, 1, 0)
    assert P.version_tuple("v1.2.3-beta.4") == (1, 2, 3)
    assert P.version_tuple("2") == (2, 0, 0)
    assert P.version_tuple("x") is None
    assert P.version_tuple("0.10.0") > P.version_tuple("0.9.9")


# ── §3.3 session upload ───────────────────────────────────────────────────────────────────────
def test_the_same_upload_three_times_is_one_row(client, world):
    _enable(world)
    dev = _sign_in(client, world)
    bodies = [_upload(client, dev["access_token"], [_session()]) for _ in range(3)]
    assert [b.status_code for b in bodies] == [200, 200, 200]
    assert bodies[0].json() == {"accepted": ["li:conv:abc:2026-09-17T10"], "duplicate": [],
                                "rejected": []}
    for b in bodies[1:]:
        assert b.json() == {"accepted": [], "duplicate": ["li:conv:abc:2026-09-17T10"],
                            "rejected": []}
    assert len(world.deltas) == 1
    (key, row), = world.deltas.items()
    assert key == (ORG, dev["device_id"], "li:conv:abc:2026-09-17T10", 37)
    assert row["status"] == "held" and row["seat_id"] == "seat_rep" and row["message_count"] == 1
    # encrypted at rest: the text is not in the stored bytes, and it decrypts to what was sent
    assert b"schedule a meeting" not in row["payload_enc"]
    sealed = json.loads(decrypt(row["payload_enc"], get_settings().crypto_key))
    assert sealed["messages"][0]["text"] == "Let's schedule a meeting tomorrow"
    assert sealed["messages"][0]["fp"] == "sha256:1"                  # unknown fields kept
    # a later watermark of the same session is a new delta, not an overwrite
    later = _upload(client, dev["access_token"], [_session(wm=38)]).json()
    assert later["accepted"] == ["li:conv:abc:2026-09-17T10"] and len(world.deltas) == 2


def test_a_body_repeating_one_session_counts_it_once(client, world):
    _enable(world)
    dev = _sign_in(client, world)
    res = _upload(client, dev["access_token"], [_session(), _session()]).json()
    assert res == {"accepted": ["li:conv:abc:2026-09-17T10"],
                   "duplicate": ["li:conv:abc:2026-09-17T10"], "rejected": []}


@pytest.mark.parametrize("session,reason", [
    (_session(url="https://accounts.google.com/v3/signin/identifier"), "domain_blocked"),
    (_session(url="https://netbanking.hdfcbank.com/netbanking/"), "domain_blocked"),
    (_session(url="https://www.linkedin.com/login"), "domain_blocked"),
    (_session(bundle_id="com.1password.1password"), "app_blocked"),
    (_session(private_window=True), "private_window"),
    (_session(app="spotify"), "app_not_allowed"),
    (_generic(url="https://accounts.google.com/signin"), "domain_blocked"),
    (_generic(bundle_id="com.apple.Terminal", url=None), "app_blocked"),
])
def test_what_the_device_should_never_have_sent_is_rejected_server_side(client, world,
                                                                        session, reason):
    _enable(world)
    dev = _sign_in(client, world)
    res = _upload(client, dev["access_token"], [session]).json()
    assert res["rejected"] == [{"session_key": session["session_key"], "reason": reason}]
    assert res["accepted"] == [] and world.deltas == {}


def test_org_disabled_seat_off_and_seat_paused_are_rejected(client, world):
    dev = _sign_in(client, world)
    cstore = MemoryCaptureStore(world)
    assert _upload(client, dev["access_token"], [_session()]).json()["rejected"][0]["reason"] \
        == "capture_disabled"                                   # no policy row = off
    cstore.save_org_policy(ORG, {"enabled": True}, updated_by="seat_owner")
    assert _upload(client, dev["access_token"], [_session()]).json()["rejected"][0]["reason"] \
        == "seat_capture_disabled"
    cstore.save_seat_settings(ORG, "seat_rep", {"enabled": True,
                                                "paused_until": NOW + timedelta(hours=1)})
    assert _upload(client, dev["access_token"], [_session()]).json()["rejected"][0]["reason"] \
        == "paused"
    cstore.save_seat_settings(ORG, "seat_rep", {"paused_until": NOW - timedelta(seconds=1)})
    assert _upload(client, dev["access_token"], [_session()]).json()["accepted"]
    cstore.save_org_policy(ORG, {"enabled": False}, updated_by="seat_owner")
    assert _upload(client, dev["access_token"], [_session(wm=99)]).json()["rejected"][0][
        "reason"] == "capture_disabled"


def test_a_malformed_session_does_not_block_the_rest_of_the_queue(client, world):
    _enable(world)
    dev = _sign_in(client, world)
    bad = {"session_key": "broken", "app": "linkedin"}                  # no watermark
    res = _upload(client, dev["access_token"], [bad, _session()]).json()
    assert res["rejected"] == [{"session_key": "broken", "reason": "invalid_session"}]
    assert res["accepted"] == ["li:conv:abc:2026-09-17T10"]


def test_gzip_size_encoding_schema_and_identity_are_enforced(client, world):
    _enable(world)
    dev = _sign_in(client, world)
    raw = json.dumps({"schema_version": 1, "sessions": [_session()]}).encode()
    gz = client.post("/v1/sessions", content=gzip.compress(raw),
                     headers={**H(dev["access_token"]), "Content-Encoding": "gzip",
                              "Content-Type": "application/json"})
    assert gz.status_code == 200 and gz.json()["accepted"] == ["li:conv:abc:2026-09-17T10"]
    big = client.post("/v1/sessions", content=b"x" * (256 * 1024 + 1),
                      headers={**H(dev["access_token"]), "Content-Type": "application/json"})
    assert big.status_code == 413 and big.json()["code"] == "PAYLOAD_TOO_LARGE"
    bomb = gzip.compress(b" " * (2 * 1024 * 1024))                       # tiny on the wire
    assert client.post("/v1/sessions", content=bomb,
                       headers={**H(dev["access_token"]),
                                "Content-Encoding": "gzip"}).status_code == 413
    assert client.post("/v1/sessions", content=b"not gzip",
                       headers={**H(dev["access_token"]),
                                "Content-Encoding": "gzip"}).json()["code"] == "INVALID_GZIP"
    assert client.post("/v1/sessions", content=raw,
                       headers={**H(dev["access_token"]),
                                "Content-Encoding": "br"}).status_code == 415
    assert client.post("/v1/sessions", content=b"{nope",
                       headers=H(dev["access_token"])).json()["code"] == "INVALID_JSON"
    v2 = _upload(client, dev["access_token"], [], schema_version=2)
    assert v2.status_code == 422 and v2.json()["code"] == "UNSUPPORTED_SCHEMA_VERSION"
    other = _upload(client, dev["access_token"], [_session()], device_id="dev_someone_else")
    assert other.status_code == 403 and other.json()["code"] == "DEVICE_MISMATCH"
    seat = _upload(client, dev["access_token"], [_session()], seat_id="seat_other")
    assert seat.status_code == 403 and seat.json()["code"] == "SEAT_MISMATCH"
    same = _upload(client, dev["access_token"], [_session(wm=40)],
                   device_id=dev["device_id"], seat_id="seat_rep")
    assert same.status_code == 200 and same.json()["accepted"]


def test_without_a_crypto_key_nothing_is_stored(client, world, monkeypatch):
    _enable(world)
    dev = _sign_in(client, world)
    monkeypatch.setattr(get_settings(), "crypto_key", "")
    res = _upload(client, dev["access_token"], [_session()])
    assert res.status_code == 503 and res.json()["code"] == "CAPTURE_STORE_UNAVAILABLE"
    assert world.deltas == {}


# ── §3.2 capture policy API ───────────────────────────────────────────────────────────────────
_DOC_KEYS = {"policy_version", "min_supported_app_version", "sensitive_defaults", "org", "seat",
             "effective"}


def test_the_default_policy_is_off_and_carries_the_sensitive_defaults(client, world):
    doc = client.get("/v1/capture/policy", headers=H(_seat(world, "seat_rep"))).json()
    assert set(doc) == _DOC_KEYS
    # D2 revised (plan §3.7): every dedicated reader on, and the generic reader on — capture as a
    # whole still waits for the org switch and the seat's own opt-in.
    assert doc["org"] == {"enabled": False,
                          "allowed_apps": ["gmail", "whatsapp", "linkedin", "slack", "outlook",
                                           "gcal"],
                          "blocked_domains": [], "generic_web_allowed": True,
                          "draft_assist_allowed": False, "retention_days": 90,
                          # P3 (pinned 2026-09-13): shadow mode by default; per-seat caps
                          "moments_display": False, "moments_max_per_hour": 6,
                          "moments_max_per_day": 30}
    assert doc["seat"] == {"enabled": False, "draft_assist": False, "generic_web": True,
                           "paused_until": None, "blocked_apps": [], "blocked_domains": []}
    assert doc["effective"]["generic_web"] is True
    assert doc["effective"]["capture_on"] is False
    assert "accounts.google.com" in doc["sensitive_defaults"]
    assert set(doc["sensitive_defaults"]) <= set(doc["effective"]["blocked_domains"])
    assert "app.genios.test" in doc["sensitive_defaults"]              # GeniOS itself
    assert re.fullmatch(r"[0-9a-f]{12}", doc["policy_version"])


def test_only_an_admin_changes_the_org_half_and_it_is_audited(client, world):
    rep, owner = _seat(world, "seat_rep"), _seat(world, "seat_owner")
    assert client.put("/v1/capture/policy", json={"enabled": True},
                      headers=H(rep)).status_code == 403
    res = client.put("/v1/capture/policy", headers=H(owner), json={
        "enabled": True, "allowed_apps": ["Gmail", "slack"], "retention_days": 30,
        "blocked_domains": ["https://crm.acme.test/deals", "*.internal.acme.test"]})
    assert res.status_code == 200, res.text
    doc = res.json()
    assert set(doc) == _DOC_KEYS
    assert doc["org"]["enabled"] is True and doc["org"]["allowed_apps"] == ["gmail", "slack"]
    assert doc["org"]["blocked_domains"] == ["crm.acme.test", "*.internal.acme.test"]
    assert doc["org"]["retention_days"] == 30
    assert ("capture_policy_changed" in [a[1] for a in world.audit])
    # the admin's list replaces the admin's list — it can never remove a sensitive default
    cleared = client.put("/v1/capture/policy", json={"blocked_domains": []},
                         headers=H(owner)).json()
    assert cleared["org"]["blocked_domains"] == []
    assert "accounts.google.com" in cleared["effective"]["blocked_domains"]
    assert client.put("/v1/capture/policy", json={"allowed_apps": ["tiktok"]},
                      headers=H(owner)).status_code == 422
    assert client.put("/v1/capture/policy", json={"blocked_domains": ["bad domain!"]},
                      headers=H(owner)).status_code == 422
    assert client.put("/v1/capture/policy", json={"retention_days": 0},
                      headers=H(owner)).status_code == 422


def test_a_seat_opts_in_pauses_and_resumes(client, world):
    owner, rep = _seat(world, "seat_owner"), _seat(world, "seat_rep")
    client.put("/v1/capture/policy", json={"enabled": True}, headers=H(owner))
    on = client.put("/v1/capture/settings", json={"enabled": True, "blocked_apps": ["slack"]},
                    headers=H(rep))
    assert on.status_code == 200 and set(on.json()) == _DOC_KEYS
    doc = on.json()
    assert doc["effective"]["capture_on"] is True
    assert doc["effective"]["apps"] == ["gcal", "gmail", "linkedin", "outlook",
                                        "whatsapp"]                    # the seat narrowed it
    assert [a[1] for a in world.audit][-1] == "seat_capture_enabled"
    version = doc["policy_version"]

    paused = client.post("/v1/capture/pause", json={"minutes": 30}, headers=H(rep)).json()
    assert set(paused) == _DOC_KEYS
    assert paused["effective"]["capture_on"] is False and paused["effective"]["paused_until"]
    assert paused["policy_version"] != version
    resumed = client.post("/v1/capture/pause", json={"minutes": 0}, headers=H(rep)).json()
    assert resumed["seat"]["paused_until"] is None and resumed["effective"]["capture_on"] is True
    assert resumed["policy_version"] == version
    until = (NOW + timedelta(hours=2)).isoformat()
    assert client.post("/v1/capture/pause", json={"until": until},
                       headers=H(rep)).json()["effective"]["paused_until"]
    past = (NOW - timedelta(hours=2)).isoformat()
    assert client.post("/v1/capture/pause", json={"until": past},
                       headers=H(rep)).json()["seat"]["paused_until"] is None
    assert client.post("/v1/capture/pause", json={}, headers=H(rep)).status_code == 422

    off = client.put("/v1/capture/settings", json={"enabled": False}, headers=H(rep)).json()
    assert off["effective"]["capture_on"] is False
    assert [a[1] for a in world.audit][-1] == "seat_capture_disabled"
    # a no-op write audits nothing
    n = len(world.audit)
    client.put("/v1/capture/settings", json={"enabled": False}, headers=H(rep))
    assert len(world.audit) == n


# ── the policy merge ──────────────────────────────────────────────────────────────────────────
def test_a_seat_only_ever_narrows_the_org():
    org = P.OrgPolicy(enabled=True, allowed_apps=("gmail", "linkedin"), generic_web_allowed=False,
                      draft_assist_allowed=True, blocked_domains=("crm.acme.test",))
    seat = P.SeatSettings(enabled=True, generic_web=True, draft_assist=True,
                          blocked_apps=("linkedin",), blocked_domains=("news.acme.test",))
    eff = P.effective_policy(org, seat, now=NOW)
    assert eff["apps"] == ["gmail"]
    assert eff["generic_web"] is False                  # the seat wanted it; the org said no
    assert eff["draft_assist"] is True
    assert {"crm.acme.test", "news.acme.test", "accounts.google.com"} <= set(
        eff["blocked_domains"])
    assert P.effective_policy(org, P.SeatSettings(), now=NOW)["capture_on"] is False
    assert P.effective_policy(P.OrgPolicy(), seat, now=NOW)["capture_on"] is False


def test_the_version_is_stable_and_moves_when_a_pause_runs_out():
    org, seat = P.OrgPolicy(enabled=True), P.SeatSettings(enabled=True)
    v = P.policy_version(P.effective_policy(org, seat, now=NOW))
    assert v == P.policy_version(P.effective_policy(org, seat, now=NOW + timedelta(days=3)))
    paused = P.SeatSettings(enabled=True, paused_until=NOW + timedelta(minutes=5))
    during = P.policy_version(P.effective_policy(org, paused, now=NOW))
    after = P.policy_version(P.effective_policy(org, paused, now=NOW + timedelta(minutes=6)))
    assert during != v and after == v


def test_presence_write_rule():
    fields = {"dnd": False, "idle": False}
    assert P.should_write_presence(None, fields, now=NOW)
    fresh = {"dnd": False, "idle": False, "updated_at": NOW - timedelta(seconds=10)}
    assert not P.should_write_presence(fresh, fields, now=NOW)
    assert P.should_write_presence(fresh, {"dnd": True, "idle": False}, now=NOW)
    stale = {**fresh, "updated_at": NOW - timedelta(seconds=30)}
    assert P.should_write_presence(stale, fields, now=NOW)


def test_the_poll_state_machine_on_its_own():
    row = {"expires_at": NOW + timedelta(minutes=5), "approved_at": None, "denied_at": None,
           "consumed_at": None, "last_polled_at": None}
    assert D.poll_outcome(row, NOW) == D.AUTHORIZATION_PENDING
    assert D.poll_outcome({**row, "last_polled_at": NOW - timedelta(seconds=2)}, NOW) \
        == D.SLOW_DOWN
    assert D.poll_outcome({**row, "last_polled_at": NOW - timedelta(seconds=4.5)}, NOW) \
        == D.AUTHORIZATION_PENDING                         # timer jitter is not punished
    assert D.poll_outcome({**row, "approved_at": NOW}, NOW) == D.APPROVED
    assert D.poll_outcome({**row, "denied_at": NOW}, NOW) == D.ACCESS_DENIED
    assert D.poll_outcome({**row, "consumed_at": NOW, "approved_at": NOW}, NOW) \
        == D.EXPIRED_TOKEN
    assert D.poll_outcome({**row, "expires_at": NOW}, NOW) == D.EXPIRED_TOKEN
    assert D.poll_outcome(None, NOW) == D.EXPIRED_TOKEN


# ── §3.5 the sensitive list: one list, 30+ URLs ─────────────────────────────────────────────
SENSITIVE_SUITE = [
    # banking / payments / brokerage
    ("https://netbanking.hdfcbank.com/netbanking/", True),
    ("https://www.icicibank.com/personal-banking", True),
    ("https://retail.onlinesbi.sbi/retail/login.htm", True),
    ("https://www.paypal.com/myaccount/summary", True),
    ("https://dashboard.stripe.com/payments", True),
    ("https://dashboard.razorpay.com/app/dashboard", True),
    ("https://kite.zerodha.com/dashboard", True),
    ("https://secure.chase.com/web/auth/dashboard", True),
    # password managers
    ("https://my.1password.com/vaults", True),
    ("https://vault.bitwarden.com/#/vault", True),
    ("https://lastpass.com/vault/", True),
    ("https://app.dashlane.com/", True),
    # SSO / 2FA / OAuth
    ("https://accounts.google.com/v3/signin/identifier?continue=x", True),
    ("https://login.microsoftonline.com/common/oauth2/v2.0/authorize", True),
    ("https://acme.okta.com/app/UserHome", True),
    ("https://acme.us.auth0.com/u/login", True),
    ("https://github.com/login/oauth/authorize?client_id=x", True),
    ("https://www.linkedin.com/login", True),
    ("https://slack.com/signin", True),
    ("https://app.example.com/o/oauth2/auth", True),
    # HR / payroll / health
    ("https://acme.bamboohr.com/employees/", True),
    ("https://wd5.myworkday.com/acme/d/home.htmld", True),
    ("https://app.gusto.com/payroll", True),
    ("https://www.practo.com/consult", True),
    ("https://mychart.example-health.org/MyChart/", True),
    # GeniOS itself, browser internals
    ("https://thegenios.com/dashboard", True),
    ("https://app.genios.test/cards", True),
    ("chrome://password-manager/passwords", True),
    # what capture is FOR — must stay capturable
    ("https://mail.google.com/mail/u/0/#inbox", False),
    ("https://www.linkedin.com/messaging/thread/2-abc/", False),
    ("https://app.slack.com/client/T01/C02", False),
    ("https://www.linkedin.com/in/loginov/", False),            # a surname, not a login page
    ("https://outlook.office.com/mail/", False),
    ("https://calendar.google.com/calendar/u/0/r", False),
    ("https://web.whatsapp.com/", False),
    ("https://www.linkedin.com/company/hdfc-life/", False),
    ("https://news.ycombinator.com/item?id=1", False),
]


def test_the_sensitive_suite_has_at_least_thirty_urls():
    assert len(SENSITIVE_SUITE) >= 30
    assert sum(1 for _, b in SENSITIVE_SUITE if b) >= 25


@pytest.mark.parametrize("url,blocked", SENSITIVE_SUITE)
def test_the_sensitive_domain_suite(world, url, blocked):
    eff = P.effective_policy(P.OrgPolicy(enabled=True), P.SeatSettings(enabled=True), now=NOW)
    assert P.is_blocked(url, None, eff) is blocked
    # the same answer the upload gate gives
    reason = P.check_session(P.OrgPolicy(enabled=True), P.SeatSettings(enabled=True),
                             app="linkedin", url=url, bundle_id=None, private_window=False,
                             now=NOW)
    assert (reason == "domain_blocked") is blocked


@pytest.mark.parametrize("bundle,blocked", [
    ("com.apple.Terminal", True), ("com.googlecode.iterm2", True),
    ("com.microsoft.VSCode", True), ("com.jetbrains.intellij", True),
    ("com.1password.1password", True), ("com.apple.keychainaccess", True),
    ("ai.genios.desktop", True),
    ("com.google.Chrome", False), ("com.tinyspeck.slackmacgap", False),
    ("net.whatsapp.WhatsApp", False), (None, False),
])
def test_sensitive_apps_by_bundle_id(bundle, blocked):
    assert P.bundle_blocked(bundle) is blocked
    assert P.is_blocked(None, bundle, {}) is blocked


def test_an_org_or_seat_pattern_blocks_too():
    eff = P.effective_policy(P.OrgPolicy(enabled=True, blocked_domains=("crm.acme.test",)),
                             P.SeatSettings(enabled=True, blocked_domains=("*.hr.acme.test",
                                                                           "/payroll")),
                             now=NOW)
    assert P.is_blocked("https://crm.acme.test/deal/1", None, eff)
    assert P.is_blocked("https://people.hr.acme.test/", None, eff)
    assert P.is_blocked("https://tools.acme.test/payroll/run", None, eff)
    assert not P.is_blocked("https://tools.acme.test/pipeline", None, eff)
    assert P.normalize_patterns(["HTTPS://WWW.Example.COM/path", "/Login", "*bank*"]) == [
        "example.com", "/login", "*bank*"]
    with pytest.raises(ValueError):
        P.normalize_patterns(["not a domain"])


# ── D2 revised (plan §3.7): every app is read ───────────────────────────────────────────────
def _on(world, **org):
    """Only the two master switches — every other capture setting stays at its default."""
    cstore = MemoryCaptureStore(world)
    cstore.save_org_policy(ORG, {"enabled": True, **org}, updated_by="seat_owner")
    cstore.save_seat_settings(ORG, "seat_rep", {"enabled": True})
    return cstore


def test_generic_sessions_native_and_web_are_accepted_by_default(client, world):
    _on(world)
    dev = _sign_in(client, world)
    res = _upload(client, dev["access_token"], [
        _generic(),                                                     # web, via Chrome
        _generic(key="doc:web:1", app="web"),                           # `web` is an alias
        _generic(key="doc:erp:1", url=None, bundle_id="com.acme.erp"),  # a native app, no url
        _session(key="wa:1", app="whatsapp", url=None,                  # every dedicated reader
                 bundle_id="net.whatsapp.WhatsApp")]).json()
    assert res == {"accepted": ["doc:crm.acme.test/deals/42:2026-09-17T10", "doc:web:1",
                                "doc:erp:1", "wa:1"], "duplicate": [], "rejected": []}
    rows = {k[2]: r for k, r in world.deltas.items()}
    assert {rows[k]["app"] for k in ("doc:web:1", "doc:erp:1")} == {"generic"}
    assert rows["doc:erp:1"]["message_count"] == 4                     # the block count
    assert rows["wa:1"]["message_count"] == 1
    sealed = json.loads(decrypt(rows["doc:erp:1"]["payload_enc"], get_settings().crypto_key))
    assert sealed["app"] == "generic" and sealed["messages"] == []
    assert sealed["blocks"][2] == {"fp": "sha256:c", "role": "table",
                                   "header": ["Invoice", "Due", "Status"],
                                   "rows": [["INV-9", "2026-09-20", "Unpaid"]]}
    assert sealed["blocks"][1]["label"] == "Stage"                     # unknown keys kept
    # idempotent exactly like a dedicated session
    again = _upload(client, dev["access_token"], [_generic()]).json()
    assert again["duplicate"] == ["doc:crm.acme.test/deals/42:2026-09-17T10"]


def test_a_dedicated_reader_switched_off_is_reader_disabled(client, world):
    cstore = _on(world, allowed_apps=["gmail", "linkedin"])
    dev = _sign_in(client, world)
    res = _upload(client, dev["access_token"], [
        _session(key="wa:1", app="whatsapp", url=None), _session(key="li:1"),
        _session(key="sp:1", app="spotify")]).json()
    assert res["accepted"] == ["li:1"]
    assert res["rejected"] == [{"session_key": "wa:1", "reason": "reader_disabled"},
                               {"session_key": "sp:1", "reason": "app_not_allowed"}]
    cstore.save_seat_settings(ORG, "seat_rep", {"blocked_apps": ["linkedin"]})
    seat_off = _upload(client, dev["access_token"], [_session(key="li:2")]).json()
    assert seat_off["rejected"] == [{"session_key": "li:2", "reason": "reader_disabled"}]
    # the generic reader is unaffected by which dedicated readers are on
    assert _upload(client, dev["access_token"], [_generic()]).json()["accepted"]


def test_generic_can_still_be_switched_off_by_the_org_or_the_seat(client, world):
    cstore = _on(world, generic_web_allowed=False)
    dev = _sign_in(client, world)
    assert _upload(client, dev["access_token"], [_generic()]).json()["rejected"] == [
        {"session_key": "doc:crm.acme.test/deals/42:2026-09-17T10", "reason": "generic_disabled"}]
    cstore.save_org_policy(ORG, {"generic_web_allowed": True}, updated_by="seat_owner")
    cstore.save_seat_settings(ORG, "seat_rep", {"generic_web": False})
    assert _upload(client, dev["access_token"], [_generic(wm=4)]).json()["rejected"][0][
        "reason"] == "generic_disabled"
    assert _upload(client, dev["access_token"], [_session()]).json()["accepted"]


def _blocks(n: int) -> list:
    return [{"fp": f"sha256:{i}", "role": "text", "text": f"line {i}"} for i in range(n)]


@pytest.mark.parametrize("session,ok", [
    (_generic(bundle_id=None), False),                                  # generic names its app
    (_generic(bundle_id="  "), False),
    (_generic(blocks=[]), False),                                       # blocks[] required
    (_generic(messages=[{"text": "hi"}]), False),                       # never both
    (_session(blocks=_blocks(1)), False),                               # dedicated: no blocks
    (_session(messages=[]), False),                                     # dedicated: messages
    (_generic(blocks=_blocks(500)), True),                              # the block cap …
    (_generic(blocks=_blocks(501)), False),
    (_generic(blocks=[{"role": "table", "header": ["a"],
                       "rows": [["x"]] * 200}]), True),                 # … and the row cap
    (_generic(blocks=[{"role": "table", "header": ["a"], "rows": [["x"]] * 201}]), False),
    (_generic(blocks=[{"text": "no role"}]), False),
])
def test_the_generic_session_shape_and_caps(client, world, session, ok):
    _on(world)
    dev = _sign_in(client, world)
    res = _upload(client, dev["access_token"], [session]).json()
    if ok:
        assert res["accepted"] == [session["session_key"]], res
    else:
        assert res["rejected"] == [{"session_key": session["session_key"],
                                    "reason": "invalid_session"}]


@pytest.mark.parametrize("session,ok", [
    (_generic(context_blocks=_blocks(10)), True),                       # ≤ 10 context blocks
    (_generic(context_blocks=_blocks(11)), False),
    (_generic(blocks=[], context_blocks=_blocks(3)), False),            # blocks[] still required
    (_generic(blocks=_blocks(495), context_blocks=_blocks(5)), True),   # shares the 500 cap
    (_generic(blocks=_blocks(496), context_blocks=_blocks(5)), False),
    (_generic(context_blocks=[{"text": "no role"}]), False),            # same block validation
    (_generic(context_blocks=[{"role": "table", "rows": [["x"]] * 201}]), False),
    (_session(context_blocks=_blocks(1)), False),                       # generic sessions only
])
def test_context_blocks_are_validated_capped_and_generic_only(client, world, session, ok):
    _on(world)
    dev = _sign_in(client, world)
    res = _upload(client, dev["access_token"], [session]).json()
    if ok:
        assert res["accepted"] == [session["session_key"]], res
    else:
        assert res["rejected"] == [{"session_key": session["session_key"],
                                    "reason": "invalid_session"}]


def test_context_blocks_are_sealed_with_the_session_but_not_counted(client, world):
    _on(world)
    dev = _sign_in(client, world)
    ctx = [{"fp": "sha256:ctx", "role": "kv", "label": "Owner", "value": "Priya"}]
    assert _upload(client, dev["access_token"], [_generic(context_blocks=ctx)]).json()["accepted"]
    (row,) = world.deltas.values()
    assert row["message_count"] == 4                  # new/changed blocks only
    sealed = json.loads(decrypt(row["payload_enc"], get_settings().crypto_key))
    assert sealed["context_blocks"] == ctx


def test_the_generic_gate_on_its_own():
    org, seat = P.OrgPolicy(enabled=True), P.SeatSettings(enabled=True)
    for app in ("generic", "web", "GENERIC"):
        assert P.check_session(org, seat, app=app, url=None, bundle_id="com.acme.erp",
                               private_window=False, now=NOW) is None
    assert P.check_session(org, seat, app="generic", url="https://my.1password.com/",
                           bundle_id="com.google.Chrome", private_window=False,
                           now=NOW) == "domain_blocked"
    assert P.check_session(org, seat, app="generic", url=None, bundle_id="com.apple.Terminal",
                           private_window=False, now=NOW) == "app_blocked"
    assert P.check_session(org, seat, app="generic", url=None, bundle_id="com.acme.erp",
                           private_window=True, now=NOW) == "private_window"
