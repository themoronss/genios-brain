from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.contracts.events import (AGENT_ACTIONS, AGENT_API_SCOPES,
                                            HUMAN_API_SCOPES, INTELLIGENCE_API_SCOPES)
from genios_engine.platform.auth import (ROLE_OWNER, AuthCtx, get_auth_ctx, hash_password,
                                         invalidate_key_cache, jwt_decode, new_api_key,
                                         require_owner, security, seat_role, verify_password)
from genios_engine.platform.cache import get_cache
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt, encrypt
from genios_engine.platform.db import get_engine
from genios_engine.platform.ids import new_id
from genios_engine.platform.sessions import (ACCOUNT_SUSPENDED, open_session, revoke_by_refresh,
                                             revoke_session, rotate_session)


def _enc_key(raw: str) -> bytes | None:
    """Encrypt a raw key at rest so the owner can reveal/copy it later (auth still uses the hash).
    Best-effort: no crypto key configured → no reveal copy, never blocks minting."""
    ck = get_settings().crypto_key
    if not ck:
        return None
    try:
        return encrypt(raw, ck)
    except Exception:      # noqa: BLE001
        return None

# Auth routes — register/login (dashboard) + scoped API-key minting (agents/integrations). This
# is the parity port of genios-brain/app/api/routes/auth.py, engine-native. org_id is issued
# here and thereafter always derived from the credential (never trusted from a request body).
#
# Every sign-in (register, login, invite accept, refresh) now opens or rotates a SEAT SESSION
# (platform/sessions.py): a short-lived access JWT under `token` / `access_token` plus a rotating
# `refresh_token`. The response keeps every field it had; the session fields are additions.

router = APIRouter(prefix="/auth", tags=["auth"])
GRANTABLE = AGENT_ACTIONS | AGENT_API_SCOPES | HUMAN_API_SCOPES | INTELLIGENCE_API_SCOPES


def _engine():
    s = get_settings()
    if not s.database_url:
        raise HTTPException(503, "auth not available (no database configured)")
    return get_engine(s.database_url)


class Register(BaseModel):
    name: str
    email: str
    password: str
    company: str | None = None      # workspace/company name from signup — was silently dropped before
    device_id: str | None = None    # the desktop app names its install; the dashboard sends nothing


@router.post("/register")
def register(body: Register) -> dict:
    """Create a tenant + its first full-scope gn_live_ key + the owner's seat session. Raw key
    shown ONCE."""
    org_id = new_id("org")
    raw, key_hash, prefix = new_api_key()
    with _engine().begin() as c:
        exists = c.execute(text("select 1 from orgs where lower(email)=lower(:e)"),
                           {"e": body.email}).first()
        if exists:
            raise HTTPException(409, "email already registered")
        # New tenants start on a 15-day trial with its credit allowance already granted —
        # otherwise the credits column defaults to 0 and a fresh trial reads as "out of credits".
        from datetime import datetime, timedelta, timezone
        from genios_engine.platform.billing import TRIAL_DAYS, plan_points
        now = datetime.now(timezone.utc)
        # orgs.name holds the person's full name (used for the sidebar/greeting); orgs.company holds
        # the workspace/company name typed at signup. Both are now persisted — company was dropped
        # before (frontend ignored it and this model had no field for it).
        c.execute(text("insert into orgs (id, name, company, email, pass_hash, api_key_hash, "
                       "subscription_tier, plan_status, credits, plan_started_at, plan_expires_at, "
                       "credit_period_start, credit_period_end) "
                       "values (:id,:n,:co,:e,:p,:kh,'trial','trial',:cr,:now,:exp,:now,:exp)"),
                  {"id": org_id, "n": body.name, "co": (body.company or "").strip()[:120] or None,
                   "e": body.email, "p": hash_password(body.password), "kh": key_hash,
                   "cr": plan_points("trial"), "now": now,
                   "exp": now + timedelta(days=TRIAL_DAYS)})
        # The org's first seat AND its durable pull surface, in the same transaction that creates
        # the org. Without the seat L2 has nobody to exclude from counterparty correlation, L5 has
        # no escalation ladder and L6 has no recipient for any card. Without the surface row
        # `run_distribution` does not enumerate the org at all, so no digest, reminder or push
        # ever leaves the building. None of those layers can tell "this tenant has none" apart
        # from "this tenant has no people", so all of them fail quietly.
        from genios_engine.platform.seats import OWNER_SEAT_ID, provision_org
        provisioned = provision_org(c, org_id)
        seat_id = (provisioned.get("seat") or {}).get("seat_id") or OWNER_SEAT_ID
        c.execute(text("insert into credit_ledger (org_id,kind,amount,balance_after,reason,bucket,"
                       "idempotency_key) values (:o,'reset',:cr,:cr,'trial:signup','credits',:idem)"),
                  {"o": org_id, "cr": plan_points("trial"), "idem": f"trial:{org_id}"})
        c.execute(text("insert into api_keys (id, org_id, key_hash, key_enc, key_prefix, name, scopes) "
                       "values (:id,:o,:kh,:ke,:pfx,'primary',:sc)"),
                  {"id": new_id("key"), "o": org_id, "kh": key_hash, "ke": _enc_key(raw),
                   "pfx": prefix, "sc": sorted(GRANTABLE)})
        tokens = open_session(c, org_id=org_id, seat_id=seat_id, email=body.email,
                              role=ROLE_OWNER, device_id=body.device_id)
    # Signup is the first point of the growth funnel; login already audits, signup did not, so the
    # admin console had no server-side record of *when* an account entered (orgs.created_at alone
    # can't be joined against the activity timeline). Never fatal — record() swallows its errors.
    from genios_engine.platform.audit import record
    record(org_id, "user_signed_up", actor_type="user", actor_id=body.email,
           metadata={"company": (body.company or "").strip()[:120] or None})
    # Server-side signup event: the top of the funnel must be counted where the account is actually
    # created, not where a browser says it was — the client event can be blocked or replayed.
    from genios_engine.platform import analytics
    analytics.capture_with_person(_engine(), org_id, "user_signed_up",
                                  {"company": (body.company or "").strip()[:120] or None})
    return {"org_id": org_id, "name": body.name, "email": body.email,
            "api_key": raw, "key_prefix": prefix, "note": "store api_key now — shown only once",
            **tokens.as_response()}


class Login(BaseModel):
    email: str
    password: str
    #: Which workspace, when this address + password opens more than one (an owner who was also
    #: invited to a colleague's workspace). Omit it and a single match signs straight in.
    org_id: str | None = None
    device_id: str | None = None


_LOGIN_ATTEMPTS = 10                     # per email, per window
_LOGIN_WINDOW_SECONDS = 300


def _login_throttle(email: str) -> None:
    """Cap password attempts per email. Passwords are pbkdf2 at 200k iterations, so an online
    guess is slow — but nothing stopped an attacker from running it indefinitely, and a customer's
    whole workspace sits behind one password. Fails OPEN on a cache outage: locking every customer
    out because Redis blinked is the worse failure."""
    try:
        n = get_cache().incr_window(f"login:{email.strip().lower()}", _LOGIN_WINDOW_SECONDS)
    except Exception:                    # noqa: BLE001
        return
    if n > _LOGIN_ATTEMPTS:
        raise HTTPException(429, {"code": "TOO_MANY_ATTEMPTS",
                                  "message": "Too many sign-in attempts. Try again in a few minutes."})


def _workspace_name(row) -> str:
    return (getattr(row, "company", None) or getattr(row, "org_name", None)
            or getattr(row, "name", None) or "")


@router.post("/login")
def login(body: Login) -> dict:
    """Owner OR member sign-in, one form.

    The owner's password lives on `orgs` (as it always has); a member's on their `org_members`
    row, hashed with the same pbkdf2 scheme. The same address can hold both — owner of one
    workspace, invited to another — so every row the password actually OPENS is a candidate, and
    only a verified candidate is ever named back (409 `ORG_SELECTION_REQUIRED` lists them; the
    client re-sends with `org_id`). An address that verifies nowhere learns nothing.
    """
    _login_throttle(body.email)
    with _engine().connect() as c:
        owners = c.execute(text(
            "select id, name, company, pass_hash, plan_status, subscription_tier "
            "from orgs where lower(email)=lower(:e)"), {"e": body.email}).all()
        members = c.execute(text(
            "select m.org_id as id, m.name, m.pass_hash, m.seat_id, o.name as org_name, "
            "o.company, o.plan_status, o.subscription_tier "
            "from org_members m join orgs o on o.id = m.org_id "
            "join org_seats s on s.org_id = m.org_id and s.seat_id = m.seat_id "
            "where lower(m.email)=lower(:e) and m.status='active' and s.active "
            "and m.pass_hash is not null"), {"e": body.email}).all()
    matches = [("owner", r) for r in owners if verify_password(body.password, r.pass_hash)]
    matches += [("member", r) for r in members if verify_password(body.password, r.pass_hash)]
    if body.org_id:
        matches = [m for m in matches if m[1].id == body.org_id]
    if not matches:
        from genios_engine.platform.audit import record as _rec
        known = (owners or members)
        if known:                        # only auditable against a real tenant
            _rec(known[0].id, "login_failed", actor_type="user", actor_id=body.email)
        raise HTTPException(401, "invalid email or password")
    if len(matches) > 1:
        raise HTTPException(409, {"code": "ORG_SELECTION_REQUIRED",
                                  "message": "This sign-in opens more than one workspace.",
                                  "orgs": [{"org_id": r.id, "name": _workspace_name(r)}
                                           for _, r in matches]})
    kind, row = matches[0]
    if row.plan_status == "suspended":
        raise HTTPException(403, {"error": "ACCOUNT_SUSPENDED"})
    with _engine().begin() as c:
        if kind == "owner":
            from genios_engine.platform.seats import OWNER_SEAT_ID, ensure_owner_seat
            seat_id = ensure_owner_seat(c, row.id).get("seat_id") or OWNER_SEAT_ID
            role, name = ROLE_OWNER, row.name
        else:
            seat = c.execute(text(
                "select s.email, s.role, o.email as org_email from org_seats s "
                "join orgs o on o.id = s.org_id where s.org_id=:o and s.seat_id=:s"),
                {"o": row.id, "s": row.seat_id}).first()
            seat_id = row.seat_id
            role = seat_role(seat.email if seat else body.email, seat.role if seat else None,
                             seat.org_email if seat else None)
            name = row.name or body.email
        tokens = open_session(c, org_id=row.id, seat_id=seat_id, email=body.email, role=role,
                              device_id=body.device_id)
    from genios_engine.platform.audit import record
    record(row.id, "user_logged_in", actor_type="user", actor_id=body.email)
    # Login carries the person properties too: it is the most frequent moment we can cheaply
    # refresh an account's plan / paying / internal flags in PostHog.
    from genios_engine.platform import analytics
    analytics.capture_with_person(_engine(), row.id, "user_logged_in")
    return {"org_id": row.id, "name": name, "email": body.email,
            "plan": row.subscription_tier, "org_name": _workspace_name(row),
            **tokens.as_response()}


class Refresh(BaseModel):
    refresh_token: str
    device_id: str | None = None


_REFRESH_MESSAGES = {
    "REFRESH_REUSED": "This session was used from somewhere else and has been signed out.",
    "SEAT_INACTIVE": "Your access to this workspace has been removed.",
    ACCOUNT_SUSPENDED: "This workspace is suspended.",
}


@router.post("/refresh")
def refresh(body: Refresh) -> dict:
    """Rotate a refresh token: a fresh access token AND a fresh refresh token; the presented one
    is dead from this moment. Presenting a token that was already rotated revokes the session."""
    with _engine().begin() as c:
        out = rotate_session(c, body.refresh_token, device_id=body.device_id)
    # The transaction above has COMMITTED before any error is raised: a reuse must stay revoked.
    if out.error:
        raise HTTPException(403 if out.error == ACCOUNT_SUSPENDED else 401,
                            {"code": out.error,
                             "message": _REFRESH_MESSAGES.get(out.error, "Please log in again.")})
    t = out.tokens
    return {"org_id": t.org_id, "email": t.email, **t.as_response()}


class MintKey(BaseModel):
    name: str = "key"
    agent_id: str | None = None
    scopes: list[str]                    # subset of the controlled grant vocabulary


@router.post("/keys")
def mint_key(body: MintKey, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Mint a scoped gn_live_ key for the authenticated tenant. This is the 'pick scope → get
    key → key carries that scope' flow. Raw key returned ONCE."""
    org_id = ctx.org_id
    bad = [s for s in body.scopes if s not in GRANTABLE]
    if bad:
        raise HTTPException(422, f"unknown scopes: {bad}")
    raw, key_hash, prefix = new_api_key()
    kid = new_id("key")
    with _engine().begin() as c:
        c.execute(text("insert into api_keys (id, org_id, key_hash, key_enc, key_prefix, name, agent_id, scopes) "
                       "values (:id,:o,:kh,:ke,:pfx,:n,:aid,:sc)"),
                  {"id": kid, "o": org_id, "kh": key_hash, "ke": _enc_key(raw), "pfx": prefix,
                   "n": body.name, "aid": body.agent_id, "sc": body.scopes})
    return {"id": kid, "api_key": raw, "key_prefix": prefix, "scopes": body.scopes,
            "note": "store api_key now — shown only once"}


@router.get("/keys")
def list_keys(ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _engine().connect() as c:
        # ACTIVE keys only — a revoked key must disappear from the list, otherwise "revoke" looks
        # like it did nothing (the row stayed). `revealable` tells the UI whether a Reveal will work
        # (older keys minted before key_enc have no at-rest copy).
        rows = c.execute(text("select id, key_prefix, name, agent_id, scopes, is_active, "
                              "created_at, last_used_at, (key_enc is not null) as revealable "
                              "from api_keys where org_id=:o and coalesce(is_active, true) "
                              "order by created_at desc"), {"o": org_id}).mappings().all()
    return {"keys": [dict(r) for r in rows]}      # never returns key_hash or the raw key


@router.get("/keys/{key_id}/reveal")
def reveal_key(key_id: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    """Reveal a key's full secret so the owner can copy it again (not only once at creation).
    Owner-gated; decrypts the at-rest copy. Keys minted before this feature have no copy → 409."""
    org_id = ctx.org_id
    with _engine().connect() as c:
        row = c.execute(text("select key_enc, key_prefix from api_keys "
                             "where id=:id and org_id=:o and coalesce(is_active, true)"),
                        {"id": key_id, "o": org_id}).first()
    if row is None:
        raise HTTPException(404, "key not found")
    if not row.key_enc:
        raise HTTPException(409, {"error": "key_not_recoverable",
                                  "message": "This key predates key reveal. Create a new key to get "
                                             "a copyable one.", "key_prefix": row.key_prefix})
    try:
        raw = decrypt(bytes(row.key_enc), get_settings().crypto_key)
    except Exception:      # noqa: BLE001
        raise HTTPException(409, {"error": "key_not_recoverable",
                                  "message": "Stored key could not be decrypted. Create a new key."})
    return {"id": key_id, "api_key": raw, "key_prefix": row.key_prefix}


@router.delete("/keys/{key_id}")
def revoke_key(key_id: str, ctx: AuthCtx = Depends(require_owner)) -> dict:
    org_id = ctx.org_id
    with _engine().begin() as c:
        row = c.execute(text("select key_hash from api_keys where id=:id and org_id=:o"),
                        {"id": key_id, "o": org_id}).first()
        if row is None:
            raise HTTPException(404, "key not found")
        c.execute(text("update api_keys set is_active=false where id=:id"), {"id": key_id})
    invalidate_key_cache(row.key_hash)
    return {"revoked": True, "key_id": key_id}


@router.get("/me")
def whoami(ctx: AuthCtx = Depends(get_auth_ctx)) -> dict:
    return {"org_id": ctx.org_id, "agent_id": ctx.agent_id, "scopes": ctx.scopes,
            "plan_status": ctx.plan_status, "source": ctx.source,
            "seat_id": ctx.seat_id, "role": ctx.role, "email": ctx.email,
            "session_id": ctx.session_id}


class Logout(BaseModel):
    refresh_token: str | None = None


@router.post("/logout")
def logout(body: Logout | None = None,
           creds: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    """Revoke the caller's session — by its access token, its refresh token, or both. Always 200:
    a client signing out must never be stuck on an error. A pre-session token (no `sid`) cannot be
    revoked server-side and reports `revoked: false`; dropping it client-side ends it, as before."""
    s = get_settings()
    if not s.database_url:
        return {"ok": True, "revoked": False}
    revoked = False
    with _engine().begin() as c:
        token = creds.credentials if creds is not None else ""
        if token and token.count(".") == 2 and not token.startswith("gn_"):
            payload = jwt_decode(token, s.jwt_secret, verify_exp=False)
            if payload and payload.get("sid"):
                revoked = revoke_session(c, str(payload["sid"]),
                                         org_id=str(payload.get("org_id") or ""),
                                         reason="logout") or revoked
        if body is not None and body.refresh_token:
            revoked = revoke_by_refresh(c, body.refresh_token, reason="logout") or revoked
    return {"ok": True, "revoked": revoked}
