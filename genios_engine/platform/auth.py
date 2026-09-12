from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text

from genios_engine.platform.cache import get_cache, okey
from genios_engine.platform.config import get_settings
from genios_engine.platform.db import get_engine

# Auth & identity — ported from genios-brain/app/api/deps.py, engine-native + stdlib-only (no
# PyJWT/passlib/bcrypt dependency). Two credential families, BOTH resolving org_id server-side:
#   • JWT dashboard session (HS256, from /auth/login) — stateless, full owner scope.
#   • gn_live_… API key — sha256 at rest, Redis-cached 60s, carries a scope grant.
# Law: org_id ALWAYS comes from the credential, NEVER from a query param → tenant isolation.

_API_KEY_CACHE_TTL = 60
_KILL_TTL = 10
_PBKDF2_ITERS = 200_000
security = HTTPBearer(auto_error=False)


# ── base64url + HS256 JWT (stdlib) ─────────────────────────────────────────────────────
def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64u_dec(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def jwt_encode(payload: dict, secret: str) -> str:
    head = _b64u(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64u(json.dumps(payload, separators=(",", ":"), default=str).encode())
    signing = f"{head}.{body}".encode()
    sig = _b64u(hmac.new(secret.encode(), signing, hashlib.sha256).digest())
    return f"{head}.{body}.{sig}"


def jwt_decode(token: str, secret: str, *, verify_exp: bool = True) -> dict | None:
    """Verified claims, or None. `verify_exp=False` is for LOGOUT only: ending a session with an
    access token that has just expired is safe (it can only take access away)."""
    try:
        head, body, sig = token.split(".")
        expected = _b64u(hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64u_dec(body))
        if verify_exp and payload.get("exp") and time.time() > float(payload["exp"]):
            return None
        return payload
    except Exception:
        return None


# ── password hashing (pbkdf2, stdlib) ──────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, _PBKDF2_ITERS)
    return f"pbkdf2${_PBKDF2_ITERS}${salt.hex()}${dk.hex()}"


def verify_password(pw: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("pbkdf2$"):
        return False
    try:
        _, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── API keys ────────────────────────────────────────────────────────────────────────
def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    """Return (raw_key, key_hash, key_prefix). Raw is shown ONCE; only the hash is stored."""
    raw = "gn_live_" + secrets.token_urlsafe(24)
    return raw, hash_key(raw), raw[:12]


# ── seat roles ─────────────────────────────────────────────────────────────────────────
#: The org's owner — the person whose address is `orgs.email`. Their seat row carries `admin`.
ROLE_OWNER = "owner"
#: A tenant admin: full org scope, manages the team. NOT GeniOS staff (that is `require_admin`).
ROLE_ADMIN = "admin"
#: A member: reads and acts on the cards routed to their own seat, and nothing org-wide.
ROLE_MEMBER = "member"
SEAT_ROLES = (ROLE_ADMIN, ROLE_MEMBER)            # what an org_seats / invite row may hold

#: A member session's grant. Every other route resolves the tenant through `get_current_org`,
#: which refuses any credential carrying a scope list — so a member is deny-by-default everywhere
#: except routes that name one of these (and filter to the seat) or that explicitly accept
#: `require_seat` / `require_workspace_user`.
MEMBER_SCOPES = frozenset({"cards.read", "cards.act", "insights.read", "feedback.write"})


def seat_role(seat_email: str | None, role: str | None, org_email: str | None) -> str:
    """A seat's effective role. The owner is identified by ADDRESS (`orgs.email`), not by the seat
    row's role, so a founder's seat that an admin demoted is still the owner's."""
    if seat_email and org_email and seat_email.strip().lower() == org_email.strip().lower():
        return ROLE_OWNER
    return ROLE_ADMIN if (role or "").strip().lower() == ROLE_ADMIN else ROLE_MEMBER


@dataclass
class AuthCtx:
    org_id: str
    agent_id: str | None = None
    actor_id: str | None = None
    scopes: list[str] | None = None      # None = full org scope (owner/admin session / legacy key)
    plan_status: str = "active"
    source: str = "legacy"               # jwt | api_key | legacy
    # Seat identity — JWT sessions only; an API key is issued to an org, not to a person.
    seat_id: str | None = None
    role: str | None = None              # owner | admin | member; None = an API key
    email: str | None = None
    session_id: str | None = None        # None for a pre-session (legacy) JWT

    def has_scope(self, scope: str) -> bool:
        return self.scopes is None or scope in self.scopes

    @property
    def is_member(self) -> bool:
        """A member seat: every card read is filtered to what is routed to `seat_id`."""
        return self.role == ROLE_MEMBER

    @property
    def is_org_admin(self) -> bool:
        """A tenant admin in the TENANT's sense — owner, admin seat, or an owner-level org key."""
        return self.scopes is None and self.role in (None, ROLE_OWNER, ROLE_ADMIN)

    @property
    def sees_org_queue(self) -> bool:
        """Does this credential read the ORG's card queue rather than one person's?

        Two principals do. An owner session (``scopes is None``) always did. The one that did not,
        and should have, is an API key with no personal identity: ``agent_id`` and ``actor_id`` are
        both NULL on a key minted from the dashboard's "API key" button, because a key is issued to
        an ORGANISATION, not to a human.

        The queue filter asked "which person is this?" and got NULL, so it matched cards assigned
        to nobody — and L5 assigns every card to a seat. The desktop app therefore authenticated
        correctly, was authorised correctly, and received an empty list forever. Granting
        ``cards.read`` to a credential that structurally cannot match any card is a scope that
        means nothing.

        A key carries the reach of whoever minted it, and only an owner can mint one. So an
        identity-less key reads the org queue; a key bound to an AGENT still sees only its own lane.

        Test ``agent_id``, never ``actor_id``: the API-key branch above synthesises
        ``actor_id = row.agent_id or f"api_key:{hashed[:12]}"``, so actor_id is NEVER None on this
        path and an ``actor_id is None`` check silently never fires. ``agent_id`` is the only field
        that carries a real principal, because ``api_keys`` has no other identity column. A JWT
        session needs no clause of its own — it always arrives with ``scopes is None``.
        """
        return self.scopes is None or (self.source == "api_key" and self.agent_id is None)


def _engine():
    s = get_settings()
    if not s.database_url:
        raise HTTPException(503, "auth not available (no database configured)")
    return get_engine(s.database_url)


# ── kill switch (Redis-cached, fail-open) ──────────────────────────────────────────────
def check_kill_switch() -> None:
    cache = get_cache()
    cached = cache.get("ff:kill_switch_all")
    if cached == "0":
        raise HTTPException(503, {"error": "SERVICE_UNAVAILABLE", "message": "GeniOS is temporarily offline."})
    if cached == "1":
        return
    try:
        with _engine().connect() as c:
            row = c.execute(text("select enabled from feature_flags where key='kill_switch_all'")).first()
        live = row is None or bool(row.enabled)
        cache.setex("ff:kill_switch_all", _KILL_TTL, "1" if live else "0")
        if not live:
            raise HTTPException(503, {"error": "SERVICE_UNAVAILABLE", "message": "GeniOS is temporarily offline."})
    except HTTPException:
        raise
    except Exception:
        return                       # infra hiccup → fail open, never block on the flag lookup


# ── the resolver ───────────────────────────────────────────────────────────────────────
_TOKEN_REVOKED = {"code": "TOKEN_REVOKED", "message": "Session no longer valid."}


def _session_ctx(payload: dict) -> AuthCtx:
    """A verified JWT → the seat it speaks for. ONE query either way — the same round trip the old
    `select 1 from orgs` existence check already paid.

    * A token with a `sid` (every token minted since 0137) must name a live, unrevoked session
      whose seat is still ACTIVE. The role is read from the seat row, not trusted from the claim,
      so a demotion or a deactivation takes effect on the next request.
    * A token without one predates seats. It was only ever issued to the owner, so it resolves to
      the owner's seat — every existing dashboard session keeps working until it expires.
    """
    from genios_engine.platform.seats import OWNER_SEAT_ID
    org_id = str(payload["org_id"])
    sid = payload.get("sid")
    if not sid:
        if payload.get("seat_id"):          # a seat claim without a session is not one we minted
            raise HTTPException(401, _TOKEN_REVOKED)
        with _engine().connect() as c:
            row = c.execute(text(
                "select o.id, (select s.seat_id from org_seats s where s.org_id = o.id "
                "and lower(s.email) = lower(o.email) and s.active "
                "order by (s.seat_id = :owner) desc, s.seat_id limit 1) as seat_id "
                "from orgs o where o.id = :o"), {"o": org_id, "owner": OWNER_SEAT_ID}).first()
        if row is None:
            raise HTTPException(401, _TOKEN_REVOKED)
        email = payload.get("email")
        return AuthCtx(org_id=org_id, actor_id=str(email or "org_owner"), scopes=None,
                       source="jwt", seat_id=row.seat_id or OWNER_SEAT_ID, role=ROLE_OWNER,
                       email=email)
    with _engine().connect() as c:
        row = c.execute(text(
            "select a.seat_id, a.revoked_at, a.expires_at, s.email, s.role, s.active, "
            "o.email as org_email from auth_sessions a join orgs o on o.id = a.org_id "
            "left join org_seats s on s.org_id = a.org_id and s.seat_id = a.seat_id "
            "where a.session_id = :sid and a.org_id = :o"),
            {"sid": str(sid), "o": org_id}).first()
    if (row is None or row.revoked_at is not None
            or row.expires_at <= datetime.now(timezone.utc) or not row.active
            or row.seat_id != payload.get("seat_id")):
        raise HTTPException(401, _TOKEN_REVOKED)
    role = seat_role(row.email, row.role, row.org_email)
    email = row.email or payload.get("email")
    return AuthCtx(org_id=org_id, actor_id=str(email or row.seat_id),
                   scopes=None if role != ROLE_MEMBER else sorted(MEMBER_SCOPES),
                   source="jwt", seat_id=row.seat_id, role=role, email=email,
                   session_id=str(sid))


def verify_bearer(token: str) -> AuthCtx:
    check_kill_switch()
    s = get_settings()

    # Path 1 — JWT session (seat-bound; checked against its session row on every request)
    if token.count(".") == 2 and not token.startswith("gn_"):
        payload = jwt_decode(token, s.jwt_secret)
        if (not payload or not payload.get("org_id")
                or payload.get("typ") not in (None, "access")):
            raise HTTPException(401, {"code": "SESSION_EXPIRED", "message": "Please log in again."})
        return _session_ctx(payload)

    # Path 2 — gn_live_ API key
    if not token.startswith("gn_live_"):
        raise HTTPException(401, "Invalid credential format")
    hashed = hash_key(token)
    cache = get_cache()
    blob = cache.get_json(f"apikey:{hashed}")
    if blob is not None:
        if blob.get("plan_status") == "invalid":
            raise HTTPException(401, "Invalid API key")
        if blob.get("plan_status") == "suspended":
            raise HTTPException(403, {"error": "ACCOUNT_SUSPENDED"})
        return AuthCtx(org_id=blob["org_id"], agent_id=blob.get("agent_id"),
                       actor_id=blob.get("actor_id") or blob.get("agent_id") or "scoped_api_key",
                       scopes=blob.get("scopes"), plan_status=blob.get("plan_status", "active"),
                       source="api_key")

    with _engine().begin() as c:
        row = c.execute(text(
            "select k.org_id, k.agent_id, k.scopes, o.plan_status from api_keys k "
            "join orgs o on o.id=k.org_id where k.key_hash=:h and k.is_active"),
            {"h": hashed}).first()
        if row is None:      # legacy: org primary key
            row2 = c.execute(text("select id as org_id, plan_status from orgs where api_key_hash=:h"),
                             {"h": hashed}).first()
            if row2 is None:
                cache.set_json(f"apikey:{hashed}", 30, {"org_id": "", "plan_status": "invalid"})
                raise HTTPException(401, "Invalid API key")
            ctx = AuthCtx(org_id=row2.org_id, actor_id="org_primary_key", scopes=None,
                          plan_status=row2.plan_status or "active", source="legacy")
        else:
            c.execute(text("update api_keys set last_used_at=now() where key_hash=:h"), {"h": hashed})
            ctx = AuthCtx(org_id=row.org_id, agent_id=row.agent_id,
                          actor_id=row.agent_id or f"api_key:{hashed[:12]}",
                          scopes=list(row.scopes or []),
                          plan_status=row.plan_status or "active", source="api_key")
    cache.set_json(f"apikey:{hashed}", _API_KEY_CACHE_TTL,
                   {"org_id": ctx.org_id, "agent_id": ctx.agent_id,
                    "actor_id": ctx.actor_id, "scopes": ctx.scopes,
                    "plan_status": ctx.plan_status})
    if ctx.plan_status == "suspended":
        raise HTTPException(403, {"error": "ACCOUNT_SUSPENDED"})
    return ctx


def invalidate_key_cache(key_hash: str) -> None:
    get_cache().delete(f"apikey:{key_hash}")


# ── FastAPI dependencies ───────────────────────────────────────────────────────────────
def get_auth_ctx(request: Request,
                 creds: HTTPAuthorizationCredentials | None = Depends(security)) -> AuthCtx:
    if creds is None or not creds.credentials:
        raise HTTPException(401, "Missing bearer credential")
    ctx = verify_bearer(creds.credentials)
    request.state.auth = ctx
    # The analytics middleware runs after the route and must not re-authenticate; it reads the org
    # this dependency already resolved. Set explicitly (not derived from .auth) so the middleware
    # stays independent of AuthCtx's shape.
    request.state.org_id = ctx.org_id
    request.state.agent_id = ctx.agent_id
    return ctx


_ORG_KILL_TTL = 30


def check_org_kill(org_id: str) -> None:
    """Per-org kill (spec Level C — the tenant's 'stop everything' switch, complementing the global
    kill and the per-source pause). A feature_flags row key='kill_switch:{org}' with enabled=false
    blocks every request for that org (503). Redis-cached (30s), fail-open like the global switch —
    an infra hiccup never blocks a legitimate tenant."""
    if not org_id:
        return
    cache = get_cache()
    ckey = f"ff:kill:{org_id}"
    cached = cache.get(ckey)
    if cached == "1":
        return
    if cached == "0":
        raise HTTPException(503, {"error": "TENANT_PAUSED", "message": "This workspace is paused."})
    try:
        with _engine().connect() as c:
            row = c.execute(text("select enabled from feature_flags where key=:k"),
                            {"k": f"kill_switch:{org_id}"}).first()
        live = row is None or bool(row.enabled)
        cache.setex(ckey, _ORG_KILL_TTL, "1" if live else "0")
        if not live:
            raise HTTPException(503, {"error": "TENANT_PAUSED", "message": "This workspace is paused."})
    except HTTPException:
        raise
    except Exception:
        return                       # infra hiccup → fail open


def get_current_org(ctx: AuthCtx = Depends(get_auth_ctx)) -> str:
    """Resolve an owner tenant for legacy/dashboard routes.

    Scoped credentials are deny-by-default here.  A route intentionally exposed to an agent or
    extension must name its grant with ``require_scope``; otherwise a read-only key could inherit
    every historical dashboard mutation merely because both credentials belong to one tenant.
    """
    if ctx.scopes is not None:
        raise HTTPException(403, "explicit scoped endpoint required for this credential")
    check_org_kill(ctx.org_id)
    return ctx.org_id


def require_scope(scope: str):
    """Dependency factory: 403 unless the credential carries `scope` (owner JWT = all scopes)."""
    def _dep(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
        if not ctx.has_scope(scope):
            raise HTTPException(403, f"scope '{scope}' not granted")
        check_org_kill(ctx.org_id)
        return ctx
    return _dep


def require_owner(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
    """Owner-LEVEL mutation boundary: the owner, a tenant-admin seat, or an owner-level org key.
    Scoped keys and member seats cannot mint or revoke their way to more power."""
    if ctx.scopes is not None:
        raise HTTPException(403, "owner credential required")
    check_org_kill(ctx.org_id)
    return ctx


def require_account_owner(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
    """The account's OWNER only — what no teammate may do on the owner's behalf: erase or delete
    the workspace, rotate the org's primary key, edit the owner's own profile. A tenant admin is
    refused; an owner-level org key (no seat) keeps the reach it always had."""
    if ctx.scopes is not None or ctx.role not in (None, ROLE_OWNER):
        raise HTTPException(403, "workspace owner required")
    check_org_kill(ctx.org_id)
    return ctx


def require_org_admin(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
    """Tenant admin: the owner or an `admin` seat (or an owner-level org key). Manages the team —
    invites, roles, deactivation. Distinct from `require_admin`, which is GeniOS STAFF."""
    if not ctx.is_org_admin:
        raise HTTPException(403, "workspace admin required")
    check_org_kill(ctx.org_id)
    return ctx


def require_seat(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
    """A signed-in seat of any role. API keys have no seat and are refused."""
    if not ctx.seat_id:
        raise HTTPException(403, "a signed-in seat is required")
    check_org_kill(ctx.org_id)
    return ctx


def require_workspace_user(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
    """Anyone who works here: an owner-level credential or any signed-in seat. Scoped API keys are
    refused exactly as `get_current_org` refuses them. A route behind this MUST scope what a member
    sees — that is the whole reason it is not behind `get_current_org`."""
    if ctx.scopes is not None and not ctx.seat_id:
        raise HTTPException(403, "explicit scoped endpoint required for this credential")
    check_org_kill(ctx.org_id)
    return ctx


def superadmin_emails() -> set[str]:
    raw = get_settings().superadmin_emails or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def require_admin(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
    """GeniOS-staff boundary for the cross-org admin console.

    Every other dependency here answers "which tenant is this?"; this one answers "is this us?".
    The admin routes read *all* tenants' spend, revenue and activity, so the check is the narrowest
    in the file — and it is answered from the DEPLOYMENT, not from tenant data:

      • the credential must be an owner JWT (never a scoped API key: a leaked agent key must not
        become a cross-org read), and
      • the email it was issued to must appear in GENIOS_SUPERADMIN_EMAILS.

    Being staff is a fact about us, so granting it must never mean writing to a customer's account
    row. `orgs.is_internal` exists for a different job — excluding our own tenants from reported
    numbers — and is accepted here only as a fallback so an existing internal tenant keeps working.
    """
    if ctx.scopes is not None:
        raise HTTPException(403, "owner credential required")
    allowed = superadmin_emails()
    if allowed and (ctx.actor_id or "").strip().lower() in allowed:
        return ctx
    if ctx.role not in (None, ROLE_OWNER):
        # The `is_internal` fallback below vouches for an internal TENANT, which used to mean its
        # owner — the only person who could sign in. A teammate seat of that tenant is not staff.
        raise HTTPException(403, "admin access required")
    try:
        with _engine().connect() as c:
            row = c.execute(text("select is_internal from orgs where id=:o"),
                            {"o": ctx.org_id}).first()
    except Exception as exc:                             # noqa: BLE001
        # Unlike check_org_kill this fails CLOSED: a database hiccup must never open a cross-org
        # read to a customer tenant.
        raise HTTPException(503, "admin authorization unavailable") from exc
    if row is None or not row.is_internal:
        raise HTTPException(403, "admin access required")
    return ctx


def require_internal(x_internal_token: str | None = Header(None)) -> None:
    """Cron / internal endpoints (cross-org sweep, ingest-all). Requires a shared secret so a
    tenant can't trigger a cross-org run or enumerate which orgs exist. Denies if unset."""
    expected = get_settings().internal_token
    if not expected or x_internal_token != expected:
        raise HTTPException(403, "internal endpoint")


def verify_webhook_hmac(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """HMAC-SHA256 hex over the raw body (same scheme as genios-brain X-Genios-Signature).
    Constant-time compare. Accepts an optional 'sha256=' / 'v1,' prefix on the header."""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    sig = signature.split("=", 1)[-1].split(",", 1)[-1].strip()
    return hmac.compare_digest(sig, expected)


def verify_standard_webhook(raw_body: bytes, *, webhook_id: str | None, timestamp: str | None,
                            signature: str | None, secret: str, tolerance_s: int = 300,
                            now: float | None = None) -> bool:
    """Standard Webhooks — the scheme Composio's current (V3) deliveries are signed with.

    Signed content is `{webhook-id}.{webhook-timestamp}.{raw body}`, HMAC-SHA256 keyed with the
    secret as UTF-8, base64-encoded; the `webhook-signature` header carries one or more
    space-separated `v1,<sig>` (the SDK's `_verify_webhook_signature` computes exactly this).
    `verify_webhook_hmac` above checks a hex digest of the body alone, so every real Composio
    delivery failed it. A timestamp outside ±`tolerance_s` is refused: that is what stops a
    captured delivery from being replayed later with its valid signature.
    """
    import base64
    import time
    if not (webhook_id and timestamp and signature and secret):
        return False
    try:
        sent_at = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(int(time.time() if now is None else now) - sent_at) > tolerance_s:
        return False
    to_sign = f"{webhook_id}.{timestamp}.".encode() + raw_body
    expected = base64.b64encode(hmac.new(secret.encode(), to_sign, hashlib.sha256).digest()).decode()
    return any(hmac.compare_digest(part[3:], expected)
               for part in signature.split() if part.startswith("v1,"))
