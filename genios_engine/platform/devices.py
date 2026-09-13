"""Devices — the desktop app's sign-in (RFC 8628 device authorization grant), its registration,
its revocation, and turning a device's access token back into the device it speaks for.

THE FLOW. The app asks for a code (`issue_code`), shows `ABCD-EFGH`, and polls (`exchange`). The
person opens `/device` on the dashboard, already signed in as their seat, and approves
(`decide`) — that approval is what binds the code to an org and a seat and reserves the
`device_id`. The next poll exchanges the code, ONCE, for a `devices` row and an ordinary seat
session opened with that `device_id` (`sessions.open_session`), so refresh, logout and seat
deactivation all work on a device exactly as on the dashboard.

WHAT IS STORED. Only SHA-256 of the device code and of the user code. The device code is 32
random bytes; the user code is 8 characters from an alphabet without 0/O/1/I (nothing a person
misreads) and lives 10 minutes.

THE STATE MACHINE is pure (`poll_outcome`, `decide_transition`, `device_ctx_from_row`) and both
stores — Postgres here, the in-memory double in `tests/device_fakes.py` — apply it, so the
hermetic tests exercise the real decisions and the real-Postgres tests exercise the SQL.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import text

from genios_engine.platform import auth
from genios_engine.platform.auth import hash_key, jwt_decode, seat_role
from genios_engine.platform.config import get_settings
from genios_engine.platform.ids import new_id
from genios_engine.platform.sessions import SessionTokens, open_session

USER_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"      # no 0 / O / 1 / I
USER_CODE_LENGTH = 8
CODE_TTL_SECONDS = 600
POLL_INTERVAL_SECONDS = 5
#: A poll this soon after the previous one is "too fast" → `slow_down`. One second of tolerance
#: under the interval, so a client sleeping exactly 5 s is never punished for timer jitter.
SLOW_DOWN_BELOW_SECONDS = POLL_INTERVAL_SECONDS - 1.0

# RFC 8628 §3.5 token-endpoint errors — the only four the contract (§3.1) names.
AUTHORIZATION_PENDING = "authorization_pending"
SLOW_DOWN = "slow_down"
ACCESS_DENIED = "access_denied"
EXPIRED_TOKEN = "expired_token"
APPROVED = "approved"

# Device-token failures, as the `code` the API returns.
DEVICE_REVOKED = "DEVICE_REVOKED"
DEVICE_TOKEN_REQUIRED = "DEVICE_TOKEN_REQUIRED"
TOKEN_REVOKED = "TOKEN_REVOKED"
SESSION_EXPIRED = "SESSION_EXPIRED"
ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"


# ── codes ─────────────────────────────────────────────────────────────────────────────────────
def new_user_code() -> str:
    return "".join(secrets.choice(USER_CODE_ALPHABET) for _ in range(USER_CODE_LENGTH))


def new_device_code() -> str:
    return secrets.token_urlsafe(32)                            # 32 random bytes


def format_user_code(code: str) -> str:
    return f"{code[:4]}-{code[4:]}"


def normalize_user_code(raw: str | None) -> str | None:
    """What a person typed → the canonical 8 characters, or None. Case, dashes and spaces are
    forgiven; a character outside the alphabet is not (it cannot be one we issued)."""
    s = "".join(ch for ch in (raw or "").upper() if ch.isalnum())
    if len(s) != USER_CODE_LENGTH or any(ch not in USER_CODE_ALPHABET for ch in s):
        return None
    return s


def _aware(dt):
    if isinstance(dt, datetime) and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _iso(dt) -> str | None:
    dt = _aware(dt)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if dt else None


def poll_outcome(row: dict | None, now: datetime) -> str:
    """What one poll of the token endpoint answers, from the code row alone. An unknown or
    already-exchanged code answers `expired_token`: in both cases the only useful thing the app
    can do is start over, and the contract's four errors are all it has to handle."""
    if row is None or row.get("consumed_at") is not None:
        return EXPIRED_TOKEN
    if _aware(row["expires_at"]) <= now:
        return EXPIRED_TOKEN
    if row.get("denied_at") is not None:
        return ACCESS_DENIED
    if row.get("approved_at") is not None:
        return APPROVED
    last = _aware(row.get("last_polled_at"))
    if last is not None and (now - last).total_seconds() < SLOW_DOWN_BELOW_SECONDS:
        return SLOW_DOWN
    return AUTHORIZATION_PENDING


def code_status(row: dict, now: datetime) -> str:
    """pending | approved | denied | expired — what the `/device` page shows."""
    if row.get("denied_at") is not None:
        return "denied"
    if row.get("approved_at") is not None:
        return "approved"
    if _aware(row["expires_at"]) <= now:
        return "expired"
    return "pending"


class DeviceError(Exception):
    """A refused approval — carried to the route as an HTTP status, a stable `code` and (for a
    code that was already decided) the `status` it is in."""

    def __init__(self, status: int, code: str, message: str, *, state: str | None = None) -> None:
        super().__init__(message)
        self.status, self.code, self.message, self.state = status, code, message, state


def decide_transition(row: dict | None, *, org_id: str, seat_id: str, approve: bool,
                      now: datetime) -> tuple[dict, dict]:
    """(column updates, response) for a seat approving or denying a code.

    Contract (§3.2, pinned 2026-09-13): unknown → 404, expired → 410, already approved / denied /
    consumed → 409 carrying the code's `status`. A code decided by ANOTHER seat is reported as
    not found, so a code is never a way to learn about someone else's device."""
    if row is None:
        raise DeviceError(404, "CODE_NOT_FOUND", "That code is not valid.")
    bound = row.get("org_id") is not None
    if bound and (row.get("org_id"), row.get("seat_id")) != (org_id, seat_id):
        raise DeviceError(404, "CODE_NOT_FOUND", "That code is not valid.")
    if row.get("consumed_at") is not None:
        raise DeviceError(409, "CODE_ALREADY_USED", "This device is already signed in.",
                          state="approved")
    if row.get("approved_at") is not None:
        raise DeviceError(409, "CODE_ALREADY_APPROVED", "This device was already approved.",
                          state="approved")
    if row.get("denied_at") is not None:
        raise DeviceError(409, "CODE_ALREADY_DENIED",
                          "This sign-in was denied. Start again on the app.", state="denied")
    if _aware(row["expires_at"]) <= now:
        raise DeviceError(410, "CODE_EXPIRED", "This code has expired. Start again on the app.",
                          state="expired")
    if approve:
        device_id = new_id("dev")
        return ({"org_id": org_id, "seat_id": seat_id, "device_id": device_id,
                 "approved_at": now}, {"ok": True, "device_id": device_id})
    return {"org_id": org_id, "seat_id": seat_id, "denied_at": now}, {"ok": True}


def seat_may_register(seat: dict | None) -> bool:
    return bool(seat and seat.get("active") and (seat.get("plan_status") or "") != "suspended")


@dataclass(frozen=True)
class IssuedCode:
    device_code: str
    user_code: str                        # canonical, no dash
    expires_in: int = CODE_TTL_SECONDS
    interval: int = POLL_INTERVAL_SECONDS


@dataclass(frozen=True)
class Exchange:
    error: str | None = None
    tokens: SessionTokens | None = None
    device_id: str | None = None
    device_name: str | None = None
    platform: str | None = None


# ── resolving a device's access token ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class DeviceCtx:
    org_id: str
    seat_id: str
    device_id: str
    session_id: str
    email: str | None = None
    role: str | None = None


class DeviceAuthError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def device_ctx_from_row(payload: dict, row: dict | None, *, now: datetime,
                        token_expired: bool) -> DeviceCtx:
    """A verified token + its session/device row → the device, or why not.

    Order matters. A REVOKED device is reported as such even on an expired token — that answer
    only takes access away, and it is the one signal that tells the app to wipe its local store,
    so it must not be hidden behind "please refresh" (whose refresh would then fail anyway)."""
    if row is None:
        raise DeviceAuthError(401, TOKEN_REVOKED, "Session no longer valid.")
    if (not row.get("device_id") or not row.get("device_exists")
            or row.get("device_seat_id") != row.get("seat_id")):
        raise DeviceAuthError(403, DEVICE_TOKEN_REQUIRED,
                              "This endpoint needs a registered device's sign-in.")
    if row.get("device_revoked_at") is not None:
        raise DeviceAuthError(401, DEVICE_REVOKED, "This device was signed out.")
    if token_expired:
        raise DeviceAuthError(401, SESSION_EXPIRED, "Please refresh the session.")
    if (row.get("revoked_at") is not None or _aware(row["expires_at"]) <= now
            or not row.get("seat_active") or row.get("seat_id") != payload.get("seat_id")):
        raise DeviceAuthError(401, TOKEN_REVOKED, "Session no longer valid.")
    if (row.get("plan_status") or "") == "suspended":
        raise DeviceAuthError(403, ACCOUNT_SUSPENDED, "This workspace is suspended.")
    return DeviceCtx(org_id=str(payload["org_id"]), seat_id=row["seat_id"],
                     device_id=row["device_id"], session_id=str(payload["sid"]),
                     email=row.get("email"),
                     role=seat_role(row.get("email"), row.get("role"), row.get("org_email")))


def resolve_device_token(token: str | None, store) -> DeviceCtx:
    """Bearer → DeviceCtx. Refuses `gn_live_` org keys and pre-session JWTs (no `sid`) before
    touching the database; one query otherwise."""
    if not token:
        raise DeviceAuthError(401, "MISSING_TOKEN", "Missing bearer credential.")
    if token.startswith("gn_") or token.count(".") != 2:
        raise DeviceAuthError(403, DEVICE_TOKEN_REQUIRED,
                              "API keys cannot act as a device. Sign the app in.")
    auth.check_kill_switch()
    payload = jwt_decode(token, get_settings().jwt_secret, verify_exp=False)
    if (not payload or not payload.get("org_id")
            or payload.get("typ") not in (None, "access")):
        raise DeviceAuthError(401, SESSION_EXPIRED, "Please sign in again.")
    if not payload.get("sid"):
        raise DeviceAuthError(403, DEVICE_TOKEN_REQUIRED,
                              "This sign-in predates devices. Sign the app in again.")
    exp = payload.get("exp")
    expired = bool(exp) and time.time() > float(exp)
    row = store.session_row(str(payload["org_id"]), str(payload["sid"]))
    ctx = device_ctx_from_row(payload, row, now=datetime.now(timezone.utc),
                              token_expired=expired)
    auth.check_org_kill(ctx.org_id)
    return ctx


# ── Postgres store ────────────────────────────────────────────────────────────────────────────
_CODE_COLS = ("org_id, seat_id, device_id, device_name, platform, os_version, app_version, "
              "created_at, expires_at, approved_at, denied_at, consumed_at, last_polled_at")
_UPDATABLE = {"org_id", "seat_id", "device_id", "approved_at", "denied_at", "consumed_at",
              "last_polled_at"}


def _set_clause(updates: dict) -> str:
    bad = set(updates) - _UPDATABLE
    if bad:
        raise ValueError(f"not an updatable code column: {sorted(bad)}")
    return ", ".join(f"{k} = :{k}" for k in updates)


class DeviceStore:
    """Every device-side SQL statement; each public method is one short transaction."""

    def __init__(self, engine) -> None:
        self.engine = engine

    def issue_code(self, *, device_name: str | None, platform: str, os_version: str | None,
                   app_version: str | None, requested_ip: str | None,
                   now: datetime | None = None) -> IssuedCode:
        now = now or datetime.now(timezone.utc)
        with self.engine.begin() as c:
            # housekeeping rides on issuing (no periodic task): codes dead for a day go
            c.execute(text("delete from device_auth_codes where expires_at < :cut"),
                      {"cut": now - timedelta(days=1)})
            for _ in range(5):
                user_code, device_code = new_user_code(), new_device_code()
                hit = c.execute(text(
                    "insert into device_auth_codes (device_code_hash, user_code_hash, "
                    "device_name, platform, os_version, app_version, requested_ip, created_at, "
                    "expires_at) values (:dh, :uh, :n, :p, :ov, :av, :ip, :now, :exp) "
                    "on conflict do nothing returning device_code_hash"),
                    {"dh": hash_key(device_code), "uh": hash_key(user_code), "n": device_name,
                     "p": platform, "ov": os_version, "av": app_version, "ip": requested_ip,
                     "now": now, "exp": now + timedelta(seconds=CODE_TTL_SECONDS)}).first()
                if hit is not None:
                    return IssuedCode(device_code=device_code, user_code=user_code)
        raise RuntimeError("could not allocate a unique user code")

    def exchange(self, device_code: str, *, now: datetime | None = None) -> Exchange:
        """One poll. A pending poll still WRITES (`last_polled_at` — that is how `slow_down` is
        measured), so the caller must commit before answering; this method never raises."""
        now = now or datetime.now(timezone.utc)
        h = hash_key(device_code or "")
        with self.engine.begin() as c:
            r = c.execute(text(f"select {_CODE_COLS} from device_auth_codes "
                               "where device_code_hash = :h for update"), {"h": h}).mappings().first()
            row = dict(r) if r is not None else None
            outcome = poll_outcome(row, now)
            if outcome in (AUTHORIZATION_PENDING, SLOW_DOWN):
                c.execute(text("update device_auth_codes set last_polled_at = :now "
                               "where device_code_hash = :h"), {"now": now, "h": h})
                return Exchange(error=outcome)
            if outcome != APPROVED:
                return Exchange(error=outcome)
            seat = c.execute(text(
                "select s.email, s.role, s.active, o.email as org_email, o.plan_status "
                "from org_seats s join orgs o on o.id = s.org_id "
                "where s.org_id = :o and s.seat_id = :s"),
                {"o": row["org_id"], "s": row["seat_id"]}).mappings().first()
            seat = dict(seat) if seat is not None else None
            if not seat_may_register(seat):
                c.execute(text("update device_auth_codes set denied_at = :now "
                               "where device_code_hash = :h"), {"now": now, "h": h})
                return Exchange(error=ACCESS_DENIED)
            c.execute(text(
                "insert into devices (device_id, org_id, seat_id, device_name, platform, "
                "os_version, app_version, created_at, last_seen_at) "
                "values (:d, :o, :s, :n, :p, :ov, :av, :now, :now) "
                "on conflict (device_id) do nothing"),
                {"d": row["device_id"], "o": row["org_id"], "s": row["seat_id"],
                 "n": row["device_name"], "p": row["platform"], "ov": row["os_version"],
                 "av": row["app_version"], "now": now})
            tokens = open_session(c, org_id=row["org_id"], seat_id=row["seat_id"],
                                  email=seat["email"],
                                  role=seat_role(seat["email"], seat["role"], seat["org_email"]),
                                  device_id=row["device_id"])
            c.execute(text("update device_auth_codes set consumed_at = :now, "
                           "last_polled_at = :now where device_code_hash = :h"),
                      {"now": now, "h": h})
        return Exchange(tokens=tokens, device_id=row["device_id"],
                        device_name=row["device_name"], platform=row["platform"])

    def get_code(self, user_code: str) -> dict | None:
        with self.engine.connect() as c:
            r = c.execute(text(f"select {_CODE_COLS} from device_auth_codes "
                               "where user_code_hash = :h"), {"h": hash_key(user_code)}
                          ).mappings().first()
        return dict(r) if r is not None else None

    def decide(self, user_code: str, *, org_id: str, seat_id: str, approve: bool,
               now: datetime | None = None) -> dict:
        now = now or datetime.now(timezone.utc)
        h = hash_key(user_code)
        with self.engine.begin() as c:
            r = c.execute(text(f"select {_CODE_COLS} from device_auth_codes "
                               "where user_code_hash = :h for update"), {"h": h}).mappings().first()
            updates, out = decide_transition(dict(r) if r is not None else None, org_id=org_id,
                                             seat_id=seat_id, approve=approve, now=now)
            if updates:
                c.execute(text(f"update device_auth_codes set {_set_clause(updates)} "
                               "where user_code_hash = :h"), {**updates, "h": h})
        return out

    def list_devices(self, org_id: str, seat_id: str | None = None) -> list[dict]:
        with self.engine.connect() as c:
            rows = c.execute(text(
                "select d.device_id, d.seat_id, s.email as seat_email, d.device_name, "
                "d.platform, d.os_version, d.app_version, d.last_seen_at, d.created_at, "
                "d.revoked_at from devices d left join org_seats s "
                "on s.org_id = d.org_id and s.seat_id = d.seat_id "
                "where d.org_id = :o and (cast(:s as text) is null or d.seat_id = :s) "
                "order by d.revoked_at nulls first, d.created_at desc limit 500"),
                {"o": org_id, "s": seat_id}).mappings().all()
        return [dict(r) for r in rows]

    def device(self, org_id: str, device_id: str) -> dict | None:
        with self.engine.connect() as c:
            r = c.execute(text("select device_id, org_id, seat_id, revoked_at from devices "
                               "where org_id = :o and device_id = :d"),
                          {"o": org_id, "d": device_id}).mappings().first()
        return dict(r) if r is not None else None

    def revoke(self, org_id: str, device_id: str, *, revoked_by: str | None) -> bool:
        """Revoke the device, every session opened for it, and its presence. False when it was
        already revoked (idempotent)."""
        now = datetime.now(timezone.utc)
        with self.engine.begin() as c:
            n = c.execute(text(
                "update devices set revoked_at = :now, revoked_by = :by "
                "where org_id = :o and device_id = :d and revoked_at is null"),
                {"now": now, "by": revoked_by, "o": org_id, "d": device_id}).rowcount or 0
            c.execute(text(
                "update auth_sessions set revoked_at = :now, revoked_reason = 'device_revoked' "
                "where org_id = :o and device_id = :d and revoked_at is null"),
                {"now": now, "o": org_id, "d": device_id})
            c.execute(text("delete from presence_leases where org_id = :o and device_id = :d"),
                      {"o": org_id, "d": device_id})
        return n > 0

    def session_row(self, org_id: str, session_id: str) -> dict | None:
        """The session, its seat, its org and its device — ONE statement."""
        with self.engine.connect() as c:
            r = c.execute(text(
                "select a.seat_id, a.device_id, a.revoked_at, a.expires_at, "
                "s.active as seat_active, s.email, s.role, o.email as org_email, o.plan_status, "
                "d.seat_id as device_seat_id, d.revoked_at as device_revoked_at, "
                "(d.device_id is not null) as device_exists "
                "from auth_sessions a join orgs o on o.id = a.org_id "
                "left join org_seats s on s.org_id = a.org_id and s.seat_id = a.seat_id "
                "left join devices d on d.org_id = a.org_id and d.device_id = a.device_id "
                "where a.session_id = :sid and a.org_id = :o"),
                {"sid": session_id, "o": org_id}).mappings().first()
        return dict(r) if r is not None else None


def revoke_seat_devices(conn, *, org_id: str, seat_id: str, revoked_by: str | None) -> int:
    """Seat removal, in the caller's transaction: every device of the seat is revoked (its
    sessions are ended by `sessions.revoke_seat_sessions` in the same transaction)."""
    return conn.execute(text(
        "update devices set revoked_at = now(), revoked_by = :by "
        "where org_id = :o and seat_id = :s and revoked_at is null"),
        {"by": revoked_by, "o": org_id, "s": seat_id}).rowcount or 0


def stores():
    """(DeviceStore, CaptureStore) on the configured database, or 503. The engine is the
    process's one pooled engine (`db.get_engine` is cached) — no new pool per request."""
    from genios_engine.platform.capture_policy import CaptureStore
    from genios_engine.platform.db import get_engine
    url = get_settings().database_url
    if not url:
        raise HTTPException(503, "device API not available (no database configured)")
    eng = get_engine(url)
    return DeviceStore(eng), CaptureStore(eng)


__all__ = ["ACCESS_DENIED", "APPROVED", "AUTHORIZATION_PENDING", "CODE_TTL_SECONDS",
           "DEVICE_REVOKED", "DEVICE_TOKEN_REQUIRED", "DeviceAuthError", "DeviceCtx",
           "DeviceError", "DeviceStore", "EXPIRED_TOKEN", "Exchange", "IssuedCode",
           "POLL_INTERVAL_SECONDS", "SLOW_DOWN", "USER_CODE_ALPHABET", "code_status",
           "decide_transition", "device_ctx_from_row", "format_user_code", "new_device_code",
           "new_user_code", "normalize_user_code", "poll_outcome", "resolve_device_token",
           "revoke_seat_devices", "seat_may_register", "stores"]
