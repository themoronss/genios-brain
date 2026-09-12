"""Seat identity against real Postgres — the HTTP routes, the sessions, the SQL.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://…/scratch pytest tests/test_seat_identity_pg.py

Skips without a scratch database. Every test registers its own workspace through `/auth/register`
and drives the real routers over HTTP; the stores behind them are the production objects the route
modules built at import (pointed at the scratch database by `tests/conftest.py`).
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from genios_engine.platform import auth

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
pytestmark = [pytest.mark.pg,
              pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")]

NOW = datetime.now(timezone.utc)
_ORGS: list[str] = []


def _engine():
    from genios_engine.platform.db import get_engine
    return get_engine(URL)


@pytest.fixture(scope="module")
def client():
    from genios_engine.api import (account_routes, auth_routes, home_routes, intelligence_routes,
                                   routes, upload_routes, workspace_routes)
    app = FastAPI()
    for module in (auth_routes, account_routes, routes, upload_routes, workspace_routes,
                   intelligence_routes, home_routes):
        app.include_router(module.router)
    yield TestClient(app)
    for org in _ORGS:
        try:
            with _engine().begin() as c:
                c.execute(text("delete from connections where org_id=:o"), {"o": org})
                c.execute(text("delete from orgs where id=:o"), {"o": org})
        except Exception:      # noqa: BLE001 — the scratch database is dropped after the run
            pass


def H(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register(client, tier: str = "startup") -> dict:
    uid = uuid.uuid4().hex[:8]
    email = f"founder_{uid}@seat.test"
    res = client.post("/auth/register", json={"name": "Founder", "email": email,
                                              "password": "founder-pass-1",
                                              "company": f"Acme {uid}"})
    assert res.status_code == 200, res.text
    body = res.json()
    _ORGS.append(body["org_id"])
    with _engine().begin() as c:
        c.execute(text("update orgs set subscription_tier=:t where id=:o"),
                  {"t": tier, "o": body["org_id"]})
    return body


def _invite(client, owner: dict, email: str, role: str = "member"):
    return client.post(f"/api/org/{owner['org_id']}/members/invite",
                       json={"email": email, "role": role}, headers=H(owner["token"]))


def _join(client, owner: dict, role: str = "member", password: str = "member-pass-1") -> dict:
    email = f"{role}_{uuid.uuid4().hex[:8]}@seat.test"
    res = _invite(client, owner, email, role)
    assert res.status_code == 200, res.text
    acc = client.post(f"/invites/{res.json()['invite_token']}/accept",
                      json={"email": email, "name": role.title(), "password": password})
    assert acc.status_code == 200, acc.text
    return {**acc.json(), "password": password}


# ── invite → accept → login → refresh → logout ──────────────────────────────────────────────
def test_the_whole_seat_lifecycle(client):
    owner = _register(client)
    org = owner["org_id"]
    assert owner["role"] == "owner" and owner["seat_id"] == "seat_owner"
    assert owner["token"] == owner["access_token"] and owner["refresh_token"].startswith("grt_")
    assert owner["api_key"].startswith("gn_live_")                     # the old fields remain

    email = f"rep_{uuid.uuid4().hex[:8]}@seat.test"
    inv = _invite(client, owner, email)
    assert inv.status_code == 200, inv.text
    token = inv.json()["invite_token"]
    assert inv.json()["email"] == email and inv.json()["expires_at"]

    public = client.get(f"/invites/{token}").json()
    assert public == {"org_name": public["org_name"], "email": email, "role": "member",
                      "expires_at": public["expires_at"], "expired": False, "accepted": False}
    assert public["org_name"].startswith("Acme")
    assert client.get("/invites/ginv_nope").status_code == 404

    bad = client.post(f"/invites/{token}/accept",
                      json={"email": "someone.else@seat.test", "name": "X", "password": "pw-123456"})
    assert bad.status_code == 403 and bad.json()["detail"]["code"] == "EMAIL_MISMATCH"
    assert client.post(f"/invites/{token}/accept",
                       json={"email": email, "name": "Rep", "password": "short"}).status_code == 400

    joined = client.post(f"/invites/{token}/accept",
                         json={"email": email.upper(), "name": "Rep", "password": "member-pass-1",
                               "device_id": "mac-1"})
    assert joined.status_code == 200, joined.text
    member = joined.json()
    assert member["role"] == "member" and member["seat_id"].startswith("seat_")
    assert member["org_id"] == org and member["refresh_token"].startswith("grt_")
    again = client.post(f"/invites/{token}/accept",
                        json={"email": email, "name": "Rep", "password": "member-pass-1"})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "INVITE_USED"

    # ONE identity: the login row and the routing row share the seat id.
    with _engine().connect() as c:
        seat = c.execute(text("select email, role, active from org_seats where org_id=:o "
                              "and seat_id=:s"), {"o": org, "s": member["seat_id"]}).first()
        m = c.execute(text("select seat_id, pass_hash, status from org_members where org_id=:o "
                           "and email=:e"), {"o": org, "e": email}).first()
    assert (seat.email, seat.role, seat.active) == (email, "member", True)
    assert m.seat_id == member["seat_id"] and m.status == "active"
    assert m.pass_hash.startswith("pbkdf2$")                          # the owner's scheme

    me = client.get("/auth/me", headers=H(member["token"])).json()
    assert (me["role"], me["seat_id"], me["email"]) == ("member", member["seat_id"], email)
    assert client.get(f"/api/org/{org}/members", headers=H(member["token"])).status_code == 403
    assert client.get(f"/api/org/{org}/home-summary", headers=H(member["token"])).status_code == 403

    login = client.post("/auth/login", json={"email": email, "password": "member-pass-1"})
    assert login.status_code == 200, login.text
    session = login.json()
    assert (session["org_id"], session["seat_id"], session["role"]) == (org, member["seat_id"],
                                                                        "member")
    assert client.post("/auth/login", json={"email": email, "password": "nope-nope"}).status_code == 401

    refreshed = client.post("/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert refreshed.status_code == 200, refreshed.text
    fresh = refreshed.json()
    assert fresh["session_id"] == session["session_id"]
    assert fresh["refresh_token"] != session["refresh_token"]
    assert client.get("/auth/me", headers=H(fresh["token"])).status_code == 200

    out = client.post("/auth/logout", json={"refresh_token": fresh["refresh_token"]},
                      headers=H(fresh["token"]))
    assert out.json() == {"ok": True, "revoked": True}
    assert client.get("/auth/me", headers=H(fresh["token"])).status_code == 401
    assert client.post("/auth/refresh",
                       json={"refresh_token": fresh["refresh_token"]}).status_code == 401
    # the accept-time session is a different device and is untouched by that logout
    assert client.get("/auth/me", headers=H(member["token"])).status_code == 200


def test_reusing_a_rotated_refresh_token_revokes_the_session(client):
    owner = _register(client)
    member = _join(client, owner)
    first = client.post("/auth/refresh", json={"refresh_token": member["refresh_token"]}).json()
    stolen = client.post("/auth/refresh", json={"refresh_token": member["refresh_token"]})
    assert stolen.status_code == 401 and stolen.json()["detail"]["code"] == "REFRESH_REUSED"
    # the whole session is gone — the legitimate holder's new pair included
    assert client.get("/auth/me", headers=H(first["token"])).status_code == 401
    after = client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert after.status_code == 401 and after.json()["detail"]["code"] == "SESSION_REVOKED"


def test_an_expired_invite_is_refused(client):
    owner = _register(client)
    email = f"late_{uuid.uuid4().hex[:8]}@seat.test"
    token = _invite(client, owner, email).json()["invite_token"]
    with _engine().begin() as c:
        c.execute(text("update org_invites set expires_at=now() - interval '1 minute' "
                       "where org_id=:o and email=:e"), {"o": owner["org_id"], "e": email})
    assert client.get(f"/invites/{token}").json()["expired"] is True
    res = client.post(f"/invites/{token}/accept",
                      json={"email": email, "name": "Late", "password": "member-pass-1"})
    assert res.status_code == 410 and res.json()["detail"]["code"] == "INVITE_EXPIRED"


def test_role_changes_and_deactivation_take_effect_on_the_next_request(client):
    owner = _register(client)
    org = owner["org_id"]
    member = _join(client, owner)
    listed = client.get(f"/api/org/{org}/members", headers=H(owner["token"])).json()
    row = next(m for m in listed["members"] if m.get("seat_id") == member["seat_id"])
    assert listed["members"][0]["role"] == "owner" and listed["members"][0]["seat_id"] == "seat_owner"

    promoted = client.patch(f"/api/org/{org}/members/{row['id']}", json={"role": "admin"},
                            headers=H(owner["token"]))
    assert promoted.status_code == 200, promoted.text
    assert client.get("/auth/me", headers=H(member["token"])).json()["role"] == "admin"
    assert client.get(f"/api/org/{org}/members", headers=H(member["token"])).status_code == 200
    # a tenant admin still cannot erase the workspace
    assert client.post(f"/api/org/{org}/reset", headers=H(member["token"])).status_code == 403
    assert client.patch(f"/api/org/{org}/members/owner", json={"role": "member"},
                        headers=H(owner["token"])).status_code == 400

    gone = client.post(f"/api/org/{org}/members/{row['id']}/deactivate", headers=H(owner["token"]))
    assert gone.status_code == 200 and gone.json()["sessions_revoked"] >= 1
    assert client.get("/auth/me", headers=H(member["token"])).status_code == 401
    assert client.post("/auth/refresh",
                       json={"refresh_token": member["refresh_token"]}).status_code == 401
    assert client.post("/auth/login", json={"email": member["email"],
                                            "password": member["password"]}).status_code == 401
    with _engine().connect() as c:
        assert c.execute(text("select active from org_seats where org_id=:o and seat_id=:s"),
                         {"o": org, "s": member["seat_id"]}).scalar() is False


def test_a_member_changes_their_own_password_not_the_owners(client):
    owner = _register(client)
    org = owner["org_id"]
    member = _join(client, owner)
    other = client.post("/auth/login", json={"email": member["email"],
                                             "password": member["password"]}).json()
    res = client.post(f"/api/org/{org}/password/change",
                      json={"current_password": member["password"],
                            "new_password": "member-pass-2"}, headers=H(member["token"]))
    assert res.status_code == 200 and res.json()["other_sessions_revoked"] >= 1
    assert client.get("/auth/me", headers=H(other["token"])).status_code == 401
    assert client.get("/auth/me", headers=H(member["token"])).status_code == 200
    assert client.post("/auth/login", json={"email": member["email"],
                                            "password": "member-pass-2"}).status_code == 200
    assert client.post("/auth/login", json={"email": owner["email"],
                                            "password": "founder-pass-1"}).status_code == 200


# ── backward compatibility ───────────────────────────────────────────────────────────────────
def test_an_owner_token_minted_before_seats_keeps_working(client):
    owner = _register(client)
    org = owner["org_id"]
    legacy = auth.jwt_encode({"org_id": org, "email": owner["email"],
                              "exp": time.time() + 600}, auth.get_settings().jwt_secret)
    me = client.get("/auth/me", headers=H(legacy)).json()
    assert (me["role"], me["seat_id"], me["session_id"], me["scopes"]) == (
        "owner", "seat_owner", None, None)
    assert client.get(f"/api/org/{org}/members", headers=H(legacy)).status_code == 200
    assert client.post("/auth/logout", headers=H(legacy)).json() == {"ok": True, "revoked": False}
    assert client.get("/auth/me", headers=H(legacy)).status_code == 200    # stateless, as before
    # the primary API key minted at signup is untouched by any of this
    key = client.get("/auth/me", headers=H(owner["api_key"])).json()
    assert key["source"] == "api_key" and key["seat_id"] is None


def test_one_address_in_two_workspaces_must_pick_one(client):
    a, b = _register(client), _register(client)
    email = f"shared_{uuid.uuid4().hex[:8]}@seat.test"
    for owner in (a, b):
        tok = _invite(client, owner, email).json()["invite_token"]
        assert client.post(f"/invites/{tok}/accept", json={
            "email": email, "name": "Shared", "password": "shared-pass-1"}).status_code == 200
    res = client.post("/auth/login", json={"email": email, "password": "shared-pass-1"})
    assert res.status_code == 409
    assert {o["org_id"] for o in res.json()["detail"]["orgs"]} == {a["org_id"], b["org_id"]}
    picked = client.post("/auth/login", json={"email": email, "password": "shared-pass-1",
                                              "org_id": b["org_id"]})
    assert picked.status_code == 200 and picked.json()["org_id"] == b["org_id"]


# ── one seat limit ───────────────────────────────────────────────────────────────────────────
def test_the_seat_limit_is_the_plans_and_counts_pending_invites(client):
    trial = _register(client, tier="trial")                             # 1 seat: the owner's
    res = _invite(client, trial, f"x_{uuid.uuid4().hex[:6]}@seat.test")
    assert res.status_code == 409 and "seat limit" in res.text

    owner = _register(client, tier="startup")                          # 5 seats
    org = owner["org_id"]
    tokens = []
    for i in range(4):
        r = _invite(client, owner, f"p{i}_{uuid.uuid4().hex[:6]}@seat.test")
        assert r.status_code == 200, r.text
        tokens.append(r.json())
    assert _invite(client, owner, f"p5_{uuid.uuid4().hex[:6]}@seat.test").status_code == 409
    # the seat-seeding route counts the same way — the hardcoded table is gone
    assert client.post("/seats", json={"seat_id": "seat_extra", "email": "e@seat.test"},
                       headers=H(owner["token"])).status_code == 409
    listed = client.get(f"/api/org/{org}/members", headers=H(owner["token"])).json()
    assert (listed["seat_limit"], listed["seats_used"]) == (5, 5)
    # re-sending an invite does not count it twice
    assert _invite(client, owner, tokens[0]["email"]).status_code == 200

    # accepting re-checks: a plan that shrank since the invite was sent is honoured
    with _engine().begin() as c:
        c.execute(text("update orgs set subscription_tier='trial' where id=:o"), {"o": org})
    late = client.post(f"/invites/{tokens[1]['invite_token']}/accept",
                       json={"email": tokens[1]["email"], "name": "P", "password": "member-pass-1"})
    assert late.status_code == 409 and late.json()["detail"]["code"] == "SEAT_LIMIT"


# ── seat-scoped card reads ───────────────────────────────────────────────────────────────────
def _seed_card(org, card_id, assignee):
    with _engine().begin() as c:
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, assignee, level, urgency_band, "
            "headline, situation, score, state, created_at, expires_at, surfaces) "
            "values (:id, :sig, :o, :a, 'prescriptive', 'high', :h, 'situation', 60, 'acted', "
            ":created, :expires, :surfaces)"),
            {"id": card_id, "sig": f"sig_{card_id}", "o": org, "a": assignee,
             "h": f"headline {card_id}", "created": NOW - timedelta(days=1),
             "expires": NOW + timedelta(days=5), "surfaces": ["app"]})


def test_a_member_sees_only_the_cards_routed_to_their_seat(client):
    owner = _register(client)
    org = owner["org_id"]
    a, b = _join(client, owner), _join(client, owner)
    ids = {k: f"{org}_{k}" for k in ("a", "b", "unrouted", "shared")}
    _seed_card(org, ids["a"], a["seat_id"])
    _seed_card(org, ids["b"], b["seat_id"])
    _seed_card(org, ids["unrouted"], None)
    _seed_card(org, ids["shared"], b["seat_id"])
    with _engine().begin() as c:                    # A covers the region the shared card names
        c.execute(text("insert into card_recipients (org_id, card_id, seat_id, accountability, "
                       "scope_kind, scope_key, source, owner_seat) values (:o,:c,:s,'covers',"
                       "'region','APAC','admin_declared',:own)"),
                  {"o": org, "c": ids["shared"], "s": a["seat_id"], "own": b["seat_id"]})

    def history(tok):
        res = client.get("/cards/history", headers=H(tok))
        assert res.status_code == 200, res.text
        return {r["card_id"] for r in res.json()["cards"]}

    assert history(a["token"]) == {ids["a"], ids["shared"]}
    assert history(b["token"]) == {ids["b"], ids["shared"]}
    assert history(owner["token"]) == set(ids.values())

    def timeline(tok, key):
        return client.get(f"/cards/{ids[key]}/timeline", headers=H(tok)).status_code

    assert (timeline(a["token"], "a"), timeline(a["token"], "shared")) == (200, 200)
    assert (timeline(a["token"], "b"), timeline(a["token"], "unrouted")) == (403, 403)
    assert timeline(owner["token"], "b") == 200
    assert client.post(f"/cards/{ids['b']}/action", json={"action": "snooze"},
                       headers=H(a["token"])).status_code == 403

    # every member-facing feed runs its seat filter against real SQL
    for path in ("/cards", "/digest", "/v1/insights", "/v1/insights?state=resolved",
                 f"/api/org/{org}/morning-brief", "/v1/morning-brief"):
        res = client.get(path, headers=H(a["token"]))
        assert res.status_code == 200, (path, res.text)
        assert ids["b"] not in res.text and ids["unrouted"] not in res.text, path
    assert client.get(f"/api/org/{org}/morning-brief",
                      headers=H(a["token"])).json().get("nags", []) == []

    # an admin reads the whole queue, promoted mid-session
    row = next(m for m in client.get(f"/api/org/{org}/members",
                                     headers=H(owner["token"])).json()["members"]
               if m.get("seat_id") == b["seat_id"])
    client.patch(f"/api/org/{org}/members/{row['id']}", json={"role": "admin"},
                 headers=H(owner["token"]))
    assert history(b["token"]) == set(ids.values())


# ── per-seat connections ─────────────────────────────────────────────────────────────────────
def test_a_seat_connection_is_stored_routed_and_owns_its_mailbox(client, monkeypatch):
    from genios_engine.api import routes
    from genios_engine.capture.connections.store import PostgresConnectionStore
    from genios_engine.capture.connectors.composio_push import ComposioPush, pick_connection
    owner = _register(client)
    org = owner["org_id"]
    member = _join(client, owner)
    seat = member["seat_id"]

    started = threading.Event()
    pulls = []
    monkeypatch.setattr(routes, "_sync_connection",
                        lambda conn, mode, limit: (pulls.append(conn.connection_id), started.set()))
    routes._adopt_completed_oauth(org, [{"source_type": "gmail", "status": "ACTIVE"}],
                                  seat_id=seat)
    assert started.wait(5)
    routes._adopt_completed_oauth(org, [{"source_type": "gmail", "status": "ACTIVE"}],
                                  seat_id=seat)                    # a second poll pulls nothing
    assert pulls == [f"con_{org}_{seat}_gmail"]
    # the member's Gmail did not make the workspace Gmail look adopted
    routes._mirror_connection(org, "gmail")

    store = PostgresConnectionStore(URL)
    mine = {c.connection_id: c for c in store.list_active() if c.org_id == org}
    ws, personal = mine[f"con_{org}_gmail"], mine[f"con_{org}_{seat}_gmail"]
    assert (ws.seat_id, ws.ownership_type, ws.composio_user_id) == (None, "workspace", org)
    assert (personal.seat_id, personal.ownership_type, personal.composio_user_id) == (
        seat, "seat", f"{org}:{seat}")

    everyone = store.list_active()
    assert pick_connection(everyone, ComposioPush(f"{org}:{seat}", "gmail", {})).connection_id \
        == personal.connection_id
    assert pick_connection(everyone, ComposioPush(org, "gmail", {})).connection_id \
        == ws.connection_id
    assert routes._mailbox_owner_for_connection(personal) == member["email"]
    assert routes._mailbox_owner_for_connection(ws) == owner["email"]
    assert routes._org_tool_connection(org, "gmail").connection_id == ws.connection_id

    with pytest.raises(IntegrityError), _engine().begin() as c:
        c.execute(text("insert into connections (connection_id, org_id, ownership_type) "
                       "values (:c, :o, 'seat')"), {"c": f"con_bad_{uuid.uuid4().hex[:6]}", "o": org})

    assert client.get("/integrations/status", params={"scope": "workspace"},
                      headers=H(member["token"])).status_code == 403
    assert client.get("/integrations/status", params={"scope": "seat"},
                      headers=H(member["token"])).status_code == 200


# ── personal uploads ─────────────────────────────────────────────────────────────────────────
def test_a_personal_upload_is_invisible_to_every_other_seat(client, monkeypatch, tmp_path):
    from genios_engine.api import upload_routes
    from genios_engine.contracts.visibility import Visibility
    monkeypatch.setattr(upload_routes, "UPLOAD_DIR", tmp_path)
    owner = _register(client)
    org = owner["org_id"]
    a, b = _join(client, owner), _join(client, owner)
    doc = b"ACCOUNT PLAN\nNorthwind renewal: push for a two-year term at the current price."

    def upload(tok, scope, tag=None, body=doc):
        data = {"scope": scope, **({"tag": tag} if tag else {})}
        return client.post(f"/api/org/{org}/upload", data=data, headers=H(tok),
                           files={"file": ("plan.txt", body, "text/plain")})

    mine = upload(a["token"], "personal")
    assert mine.status_code == 200, mine.text
    file_id = mine.json()["file_id"]
    assert mine.json()["scope"] == "personal"
    # the same bytes from another seat are that seat's own private copy, not a "duplicate"
    theirs = upload(b["token"], "personal")
    assert theirs.status_code == 200 and theirs.json()["file_id"] != file_id
    assert not theirs.json().get("duplicate")

    def listed(tok):
        return {u["id"]: u for u in client.get(f"/api/org/{org}/uploads",
                                               headers=H(tok)).json()["uploads"]}

    assert listed(a["token"])[file_id]["scope"] == "personal"
    assert file_id not in listed(b["token"]) and file_id not in listed(owner["token"])
    for tok in (b["token"], owner["token"]):
        assert client.delete(f"/api/org/{org}/uploads/{file_id}", headers=H(tok)).status_code == 404

    with _engine().connect() as c:
        rows = c.execute(text(
            "select visibility_scope, visibility_principals from source_events "
            "where org_id=:o and dedup_key like :p"),
            {"o": org, "p": f"upload:document_chunk:{file_id}:%"}).all()
    assert rows, "the personal upload captured no events"
    for r in rows:
        vis = Visibility(scope=r.visibility_scope, principals=list(r.visibility_principals))
        assert vis.scope == "private" and vis.principals == [a["email"]]
        assert vis.can_view(a["email"])
        assert not vis.can_view(b["email"]) and not vis.can_view(owner["email"])

    shared = upload(b["token"], "company", body=b"Team handbook: replies within one day.")
    assert shared.status_code == 200 and shared.json()["scope"] == "company"
    assert shared.json()["file_id"] in listed(a["token"])
    assert upload(a["token"], "company", tag="policy").status_code == 403    # canon needs admin
    assert client.delete(f"/api/org/{org}/uploads/{shared.json()['file_id']}",
                         headers=H(a["token"])).status_code == 403
    assert client.delete(f"/api/org/{org}/uploads/{file_id}",
                         headers=H(a["token"])).status_code == 200
