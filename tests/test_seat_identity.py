"""Seat identity — the hermetic half (no database; `tests/test_seat_identity_pg.py` runs the SQL).

Every teammate signs in as their own SEAT. What these pin, each at the boundary that enforces it:

  * a MEMBER is deny-by-default on every org-wide route (`get_current_org` refuses a scope list)
    and a tenant ADMIN is not the account OWNER;
  * a JWT resolves through its session row — revoked, expired, a deactivated seat or a mismatched
    seat claim are all refused, and the ROLE comes from the seat row, never from the claim;
  * a token minted before seats (no `sid`) still verifies, as the owner's seat;
  * a member's card reads are strict: their assignment and declared responsibilities, never the
    admin queue's unassigned cards;
  * a seat connection is its own Composio user and its own mailbox owner;
  * a personal upload's events are private to the uploading seat.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from genios_engine.api import account_routes, routes, upload_routes
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.connectors.composio_push import ComposioPush, pick_connection
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.contracts.connection import SEAT, WORKSPACE, Connection, composio_user_id_for
from genios_engine.contracts.visibility import PRIVATE, Visibility
from genios_engine.deliver import actions
from genios_engine.platform import auth
from genios_engine.platform.auth import (MEMBER_SCOPES, ROLE_ADMIN, ROLE_MEMBER, ROLE_OWNER,
                                         AuthCtx, get_auth_ctx, get_current_org, jwt_decode,
                                         require_account_owner, require_org_admin, require_owner,
                                         require_seat, require_workspace_user, seat_role)
from genios_engine.platform.sessions import mint_access_token

ORG = "org_seats"
NOW = datetime.now(timezone.utc)

OWNER = AuthCtx(org_id=ORG, actor_id="founder@acme.test", scopes=None, source="jwt",
                seat_id="seat_owner", role=ROLE_OWNER, email="founder@acme.test", session_id="s0")
ADMIN = AuthCtx(org_id=ORG, actor_id="ops@acme.test", scopes=None, source="jwt",
                seat_id="seat_ops", role=ROLE_ADMIN, email="ops@acme.test", session_id="s1")
MEMBER = AuthCtx(org_id=ORG, actor_id="rep@acme.test", scopes=sorted(MEMBER_SCOPES), source="jwt",
                 seat_id="seat_rep", role=ROLE_MEMBER, email="rep@acme.test", session_id="s2")
ORG_KEY = AuthCtx(org_id=ORG, actor_id="org_primary_key", scopes=None, source="legacy")
AGENT_KEY = AuthCtx(org_id=ORG, actor_id="api_key:abc", agent_id="bot",
                    scopes=["cards.read", "cards.act"], source="api_key")


@pytest.fixture(autouse=True)
def _no_kill(monkeypatch):
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    monkeypatch.setattr(routes, "check_org_kill", lambda org_id: None)


def _refused(dep, ctx, status=403):
    with pytest.raises(HTTPException) as exc:
        dep(ctx)
    assert exc.value.status_code == status


# ── roles and dependencies ───────────────────────────────────────────────────────────────────
def test_the_owner_is_identified_by_address_not_by_the_seat_row():
    assert seat_role("Founder@Acme.test", "member", "founder@acme.test") == ROLE_OWNER
    assert seat_role("ops@acme.test", "admin", "founder@acme.test") == ROLE_ADMIN
    assert seat_role("rep@acme.test", "member", "founder@acme.test") == ROLE_MEMBER
    assert seat_role("rep@acme.test", None, None) == ROLE_MEMBER      # unknown role → least power


def test_a_member_is_refused_by_every_org_wide_dependency():
    for dep in (get_current_org, require_owner, require_org_admin, require_account_owner):
        _refused(dep, MEMBER)
    assert require_seat(MEMBER) is MEMBER
    assert require_workspace_user(MEMBER) is MEMBER
    assert MEMBER.sees_org_queue is False


def test_a_tenant_admin_is_not_the_account_owner():
    assert get_current_org(ADMIN) == ORG
    assert require_owner(ADMIN) is ADMIN              # owner-LEVEL: agents, keys, decisions
    assert require_org_admin(ADMIN) is ADMIN           # manages the team
    assert ADMIN.sees_org_queue is True
    _refused(require_account_owner, ADMIN)             # but cannot erase or delete the account
    assert require_account_owner(OWNER) is OWNER
    assert require_account_owner(ORG_KEY) is ORG_KEY   # an owner-level org key keeps its reach


def test_scoped_keys_stay_exactly_where_they_were():
    _refused(require_workspace_user, AGENT_KEY)
    _refused(require_seat, ORG_KEY)
    _refused(require_org_admin, AGENT_KEY)
    assert AGENT_KEY.sees_org_queue is False
    assert ORG_KEY.sees_org_queue is True


# ── the JWT resolver ─────────────────────────────────────────────────────────────────────────
class _Conn:
    def __init__(self, row):
        self.row, self.calls = row, 0

    def execute(self, *_a, **_kw):
        self.calls += 1
        return SimpleNamespace(first=lambda: self.row)


class _Eng:
    def __init__(self, row):
        self.conn = _Conn(row)

    @contextmanager
    def connect(self):
        yield self.conn


def _verify(monkeypatch, claims, row):
    eng = _Eng(row)
    monkeypatch.setattr(auth, "_engine", lambda: eng)
    monkeypatch.setattr(auth, "check_kill_switch", lambda: None)
    return auth.verify_bearer(auth.jwt_encode(claims, auth.get_settings().jwt_secret)), eng.conn


def _session_row(**over):
    row = dict(seat_id="seat_rep", revoked_at=None, expires_at=NOW + timedelta(days=1),
               email="rep@acme.test", role="member", active=True, org_email="founder@acme.test")
    row.update(over)
    return SimpleNamespace(**row)


def _claims(**over):
    c = {"org_id": ORG, "seat_id": "seat_rep", "email": "rep@acme.test", "role": "admin",
         "sid": "ses_1", "typ": "access", "exp": time.time() + 600}
    c.update(over)
    return c


def test_a_token_minted_before_seats_still_verifies_as_the_owner(monkeypatch):
    ctx, conn = _verify(monkeypatch,
                        {"org_id": ORG, "email": "founder@acme.test", "exp": time.time() + 600},
                        SimpleNamespace(id=ORG, seat_id="seat_owner"))
    assert (ctx.role, ctx.seat_id, ctx.scopes, ctx.session_id) == (ROLE_OWNER, "seat_owner", None, None)
    assert ctx.actor_id == "founder@acme.test"         # audit identity unchanged
    assert conn.calls == 1                             # one round trip, as before


def test_the_role_comes_from_the_seat_not_from_the_claim(monkeypatch):
    ctx, conn = _verify(monkeypatch, _claims(role="admin"), _session_row(role="member"))
    assert ctx.role == ROLE_MEMBER and ctx.seat_id == "seat_rep" and ctx.session_id == "ses_1"
    assert set(ctx.scopes) == MEMBER_SCOPES
    assert conn.calls == 1
    _refused(get_current_org, ctx)


@pytest.mark.parametrize("row", [
    None,                                                  # no such session
    _session_row(revoked_at=NOW),                          # logged out / reuse-revoked
    _session_row(expires_at=NOW - timedelta(seconds=1)),   # session past its absolute lifetime
    _session_row(active=False),                            # the seat was deactivated
    _session_row(active=None),                             # the seat row is gone
    _session_row(seat_id="seat_other"),                    # the claim names another seat
])
def test_a_dead_session_is_refused_on_the_next_request(monkeypatch, row):
    with pytest.raises(HTTPException) as exc:
        _verify(monkeypatch, _claims(), row)
    assert exc.value.status_code == 401


def test_a_seat_claim_without_a_session_is_not_a_token_we_minted(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _verify(monkeypatch, {"org_id": ORG, "seat_id": "seat_owner", "exp": time.time() + 60},
                SimpleNamespace(id=ORG, seat_id="seat_owner"))
    assert exc.value.status_code == 401


def test_only_an_access_token_opens_the_api(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _verify(monkeypatch, _claims(typ="refresh"), _session_row())
    assert exc.value.status_code == 401


def test_the_access_token_carries_the_seat_and_is_short_lived():
    tok = mint_access_token(org_id=ORG, seat_id="seat_rep", email="rep@acme.test",
                            role=ROLE_MEMBER, session_id="ses_9")
    claims = jwt_decode(tok, auth.get_settings().jwt_secret)
    assert {k: claims[k] for k in ("org_id", "seat_id", "email", "role", "sid", "typ")} == {
        "org_id": ORG, "seat_id": "seat_rep", "email": "rep@acme.test", "role": ROLE_MEMBER,
        "sid": "ses_9", "typ": "access"}
    assert claims["exp"] - claims["iat"] <= auth.get_settings().access_token_ttl_seconds + 1


# ── per-seat connections ─────────────────────────────────────────────────────────────────────
def test_a_seat_connection_is_its_own_composio_user():
    assert composio_user_id_for("org_1") == "org_1"
    assert composio_user_id_for("org_1", "seat_a") == "org_1:seat_a"
    assert Connection(org_id="org_1", seat_id="seat_a").ownership_type == SEAT
    assert Connection(org_id="org_1").ownership_type == WORKSPACE
    with pytest.raises(ValueError):
        Connection(org_id="org_1", ownership_type=SEAT)          # a seat connection names its seat


def test_a_push_lands_on_the_connection_whose_user_it_names():
    ws = Connection(connection_id="ws", org_id="org_1", composio_user_id="org_1")
    a = Connection(connection_id="a", org_id="org_1", seat_id="seat_a",
                   composio_user_id="org_1:seat_a")
    b = Connection(connection_id="b", org_id="org_1", seat_id="seat_b",
                   composio_user_id="org_1:seat_b")
    gcal = Connection(connection_id="cal", org_id="org_1", composio_user_id="org_1",
                      source_type="gcal")

    def push(uid, st="gmail"):
        return pick_connection([ws, a, b, gcal], ComposioPush(user_id=uid, source_type=st, data={}))

    assert push("org_1:seat_b") is b
    assert push("org_1") is ws
    assert push("org_1", "gcal") is gcal
    assert push("org_1:seat_c") is None
    assert push("org_1:seat_a", None) is a                       # legacy envelope: label alone


def test_a_seat_connection_owns_the_seat_mailbox(monkeypatch):
    class _Scalar:
        @contextmanager
        def connect(self):
            yield SimpleNamespace(execute=lambda *_a, **_k: SimpleNamespace(
                scalar=lambda: "rep@acme.test"))

    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_Scalar()))
    monkeypatch.setattr(routes, "_mailbox_owner_for", lambda org_id: "founder@acme.test")
    seat = Connection(org_id=ORG, seat_id="seat_rep", composio_user_id=f"{ORG}:seat_rep")
    assert routes._mailbox_owner_for_connection(seat) == "rep@acme.test"
    assert routes._mailbox_owner_for_connection(Connection(org_id=ORG)) == "founder@acme.test"


def test_a_seat_gmail_never_reads_the_pinned_shared_account(monkeypatch):
    from genios_engine.capture.connectors import composio as composio_mod
    from genios_engine.platform import wiring
    built = []
    monkeypatch.setattr(composio_mod, "ComposioGmailConnector",
                        lambda **kw: built.append(kw) or SimpleNamespace(**kw))
    monkeypatch.setattr(wiring, "get_settings", lambda: SimpleNamespace(
        use_real_composio=True, composio_api_key="k", composio_gmail_account="ca_shared"))
    monkeypatch.setattr(wiring, "make_ocr", lambda org_id=None: None)
    wiring.make_connector_for(Connection(org_id=ORG, composio_user_id=ORG))
    wiring.make_connector_for(Connection(org_id=ORG, seat_id="seat_rep",
                                         composio_user_id=f"{ORG}:seat_rep"))
    assert built[0]["user_id"] == ORG and built[0]["connected_account_id"] == "ca_shared"
    assert built[1]["user_id"] == f"{ORG}:seat_rep" and built[1]["connected_account_id"] is None


def test_whose_connection_comes_from_the_credential():
    assert routes._connect_principal(MEMBER, "seat") == (ORG, "seat_rep")
    assert routes._connect_principal(OWNER, None) == (ORG, None)
    for ctx, scope, status in ((MEMBER, "workspace", 403), (ORG_KEY, "seat", 403),
                               (OWNER, "everyone", 422)):
        with pytest.raises(HTTPException) as exc:
            routes._connect_principal(ctx, scope)
        assert exc.value.status_code == status


# ── visibility ───────────────────────────────────────────────────────────────────────────────
def _upload_chunk(visibility=None):
    return RawObject(source="upload", object_type="document_chunk",
                     source_object_id="upl_x:chunk_0", occurred_at=NOW,
                     actor_type="internal_user", actor_email="rep@acme.test",
                     raw={"body": "our renewal terms"}, visibility=visibility)


def test_a_personal_upload_is_private_to_its_seat():
    ev = to_source_event(_upload_chunk(Visibility(scope=PRIVATE, principals=["rep@acme.test"],
                                                  derived_from="upload:personal:seat_rep")),
                         org_id=ORG, connection_id="upload")
    assert ev.visibility.scope == PRIVATE
    assert ev.visibility.can_view("rep@acme.test")
    assert not ev.visibility.can_view("founder@acme.test")
    assert not ev.visibility.can_view("ops@acme.test")
    company = to_source_event(_upload_chunk(), org_id=ORG, connection_id="upload")
    assert company.visibility.scope == "org" and company.visibility.can_view("ops@acme.test")


def test_a_member_mailbox_is_visible_to_its_participants_and_that_member():
    raw = RawObject(source="gmail", object_type="message", source_object_id="m1",
                    occurred_at=NOW, actor_email="buyer@client.test",
                    recipients=("rep@acme.test",))
    ev = to_source_event(raw, org_id=ORG, connection_id="con_seat", mailbox_owner="rep@acme.test")
    assert set(ev.visibility.principals) == {"buyer@client.test", "rep@acme.test"}
    assert not ev.visibility.can_view("founder@acme.test")


# ── member card reads ────────────────────────────────────────────────────────────────────────
class _Store:
    def __init__(self, cards=None, reaches=False):
        self.cards, self.calls = cards or {}, []
        self.engine = _Eng(SimpleNamespace() if reaches else None)

    def queue(self, org_id, **kw):
        self.calls.append(kw)
        return []

    def history(self, org_id, **kw):
        self.calls.append(kw)
        return []

    def get_card(self, card_id):
        return self.cards.get(card_id)

    def timeline(self, org_id, card_id):
        return []


def _client(monkeypatch, store, ctx, router=routes.router):
    monkeypatch.setattr(routes, "_card_store", store)
    monkeypatch.setattr(routes, "_graph", object())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    return TestClient(app)


def test_a_member_queue_is_strictly_their_seat(monkeypatch):
    store = _Store()
    c = _client(monkeypatch, store, MEMBER)
    assert c.get("/cards", params={"assignee": "seat_other"}).status_code == 200
    assert c.get("/cards/history").status_code == 200
    assert c.get("/digest").status_code == 200
    queue, history, digest = store.calls
    assert queue == {"assignee": "seat_rep", "admin": False, "viewer": "seat_rep",
                     "strict_seat": True}
    assert history["assignee"] == "seat_rep" and history["strict_seat"] is True
    assert digest["assignee"] == "seat_rep" and digest["strict_seat"] is True


def test_the_owner_and_an_agent_key_read_what_they_always_read(monkeypatch):
    store = _Store()
    _client(monkeypatch, store, OWNER).get("/cards", params={"assignee": "seat_rep"})
    _client(monkeypatch, store, AGENT_KEY).get("/cards")
    owner, agent = store.calls
    assert owner == {"assignee": "seat_rep", "admin": True, "viewer": "founder@acme.test"}
    assert agent == {"assignee": "api_key:abc", "admin": False, "viewer": "api_key:abc"}


def _card(card_id, assignee):
    return {"card_id": card_id, "signal_id": "sig", "org_id": ORG, "assignee": assignee,
            "state": "acted", "expires_at": NOW + timedelta(days=1)}


@pytest.mark.parametrize("assignee, reaches, status", [
    ("seat_rep", False, 200),       # assigned to the member
    ("seat_other", True, 200),      # a declared responsibility names the member
    ("seat_other", False, 403),     # another seat's card
    (None, False, 403),             # unassigned = the admin queue, not the member's
])
def test_a_member_reads_one_card_only_if_it_reaches_their_seat(monkeypatch, assignee, reaches,
                                                               status):
    store = _Store({"c1": _card("c1", assignee)}, reaches=reaches)
    assert _client(monkeypatch, store, MEMBER).get("/cards/c1/timeline").status_code == status


def test_a_member_cannot_act_on_a_card_that_is_not_theirs(monkeypatch):
    seen = []
    monkeypatch.setattr(actions, "ingest_action", lambda **kw: seen.append(kw) or {"ok": True})
    monkeypatch.setattr(routes, "_member_reaches", lambda ctx, card_id: card_id == "mine")
    c = _client(monkeypatch, _Store(), MEMBER)
    assert c.post("/cards/theirs/action", json={"action": "snooze"}).status_code == 403
    assert seen == []
    assert c.post("/cards/mine/action", json={"action": "snooze"}).status_code == 200
    assert seen[0]["allow_any_assignee"] is True and seen[0]["actor"] == "rep@acme.test"


# ── org-wide surfaces a member never reaches ─────────────────────────────────────────────────
def test_team_management_and_erasure_need_the_right_role(monkeypatch):
    member = _client(monkeypatch, _Store(), MEMBER, account_routes.router)
    assert member.get(f"/api/org/{ORG}/members").status_code == 403
    assert member.post(f"/api/org/{ORG}/members/invite",
                       json={"email": "x@acme.test"}).status_code == 403
    admin = _client(monkeypatch, _Store(), ADMIN, account_routes.router)
    assert admin.delete(f"/api/org/{ORG}/account").status_code == 403
    assert admin.post(f"/api/org/{ORG}/reset").status_code == 403
    assert admin.post(f"/api/org/{ORG}/apikey/regenerate").status_code == 403


def test_the_integrations_status_of_a_seat_is_its_own(monkeypatch):
    c = _client(monkeypatch, _Store(), MEMBER)
    assert c.get("/integrations/status", params={"scope": "workspace"}).status_code == 403
    assert c.get("/integrations/status", params={"scope": "seat"}).json() == {}   # no Composio
    redirect = _client(monkeypatch, _Store(), MEMBER).get(
        "/auth/gmail/connect", params={"org_id": ORG, "scope": "seat"})
    assert redirect.status_code == 401                 # a seat connect must prove who it is


# ── upload scope ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ctx, data, status, code", [
    (ORG_KEY, {"scope": "personal"}, 403, "seat_required"),
    (MEMBER, {"scope": "company", "tag": "policy"}, 403, "admin_required"),
    (MEMBER, {"scope": "everyone"}, 422, "invalid_scope"),
])
def test_upload_scope_is_decided_before_anything_is_stored(monkeypatch, ctx, data, status, code):
    monkeypatch.setattr(upload_routes, "_graph", None)
    app = FastAPI()
    app.include_router(upload_routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: ctx
    res = TestClient(app).post(f"/api/org/{ORG}/upload", data=data,
                               files={"file": ("notes.txt", b"renewal terms", "text/plain")})
    assert res.status_code == status
    assert res.json()["detail"]["error"] == code
