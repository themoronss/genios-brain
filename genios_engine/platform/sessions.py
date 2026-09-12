"""Seat sessions — a short-lived access JWT plus a rotating, revocable refresh token.

The dashboard JWT used to be the whole session: stateless, seven days, owner scope, and nothing a
logout or a departing teammate could take back. With one login per SEAT that is no longer
acceptable — deactivating a member has to end their access now, not in a week.

So a sign-in opens a row in `auth_sessions` (migration 0137) and hands back two things:

  * an ACCESS token — the same HS256 JWT the engine always verified, now carrying
    `{org_id, seat_id, email, role, sid, typ, iat, exp}` and living `access_token_ttl_seconds`.
    `verify_bearer` checks its `sid` against the session row on every request (the lookup that
    replaced the old `select 1 from orgs`), so a revoked session or an inactive seat stops working
    immediately, not when the token happens to expire;
  * a REFRESH token — opaque (`grt_…`), stored only as its SHA-256. Every refresh rotates it: the
    new hash replaces the old on the session and the old one is filed in
    `auth_refresh_rotations`. Presenting a token that was already rotated means two parties hold
    the same session, and there is no way to tell the thief from the owner — so the whole session
    is revoked and both have to sign in again.

Tokens minted before this module (no `sid`) still verify: `verify_bearer` resolves them to the
owner's seat. Their only difference is the one they always had — logout cannot revoke them.
"""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.auth import hash_key, jwt_encode, seat_role
from genios_engine.platform.config import get_settings
from genios_engine.platform.ids import new_id

REFRESH_PREFIX = "grt_"
ACCESS_TOKEN_TYPE = "access"

#: Refresh failures, as the `code` the API returns. Every one of them means "sign in again".
INVALID_REFRESH = "INVALID_REFRESH"
REFRESH_REUSED = "REFRESH_REUSED"
SESSION_REVOKED = "SESSION_REVOKED"
SESSION_EXPIRED = "SESSION_EXPIRED"
SEAT_INACTIVE = "SEAT_INACTIVE"
ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"

#: How long a dead session row is kept before the seat's next sign-in deletes it. Housekeeping
#: rides on sign-in rather than a periodic task (the Celery broker is quota-limited).
_DEAD_SESSION_RETENTION = timedelta(days=7)


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    session_id: str
    expires_in: int
    refresh_expires_in: int
    org_id: str
    seat_id: str
    email: str | None
    role: str

    def as_response(self) -> dict:
        """The token half of every sign-in response. `token` stays because every existing client
        reads it; `access_token` is the same value under its standard name."""
        return {"token": self.access_token, "access_token": self.access_token,
                "refresh_token": self.refresh_token, "token_type": "bearer",
                "expires_in": self.expires_in, "refresh_expires_in": self.refresh_expires_in,
                "session_id": self.session_id, "seat_id": self.seat_id, "role": self.role}


@dataclass(frozen=True)
class RefreshOutcome:
    """A refresh either yields tokens or names why not. It never raises: a reuse has to COMMIT
    the revocation it caused, and an exception inside the caller's transaction would roll it back."""
    tokens: SessionTokens | None = None
    error: str | None = None


def _ttls() -> tuple[int, int]:
    s = get_settings()
    return (max(60, int(s.access_token_ttl_seconds)),
            max(3600, int(s.refresh_token_ttl_seconds)))


def mint_access_token(*, org_id: str, seat_id: str, email: str | None, role: str,
                      session_id: str, now: float | None = None) -> str:
    access_ttl, _ = _ttls()
    at = time.time() if now is None else now
    return jwt_encode({"org_id": org_id, "seat_id": seat_id, "email": email, "role": role,
                       "sid": session_id, "typ": ACCESS_TOKEN_TYPE, "iat": int(at),
                       "exp": at + access_ttl}, get_settings().jwt_secret)


def _new_refresh() -> tuple[str, str]:
    raw = REFRESH_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_key(raw)


def _device(device_id: str | None) -> str | None:
    d = (device_id or "").strip()
    return d[:200] or None


def open_session(conn, *, org_id: str, seat_id: str, email: str | None, role: str,
                 device_id: str | None = None) -> SessionTokens:
    """Open a session for a seat that has just proved who it is. Runs in the caller's transaction."""
    access_ttl, refresh_ttl = _ttls()
    now = datetime.now(timezone.utc)
    sid = new_id("ses")
    raw, hashed = _new_refresh()
    conn.execute(text(
        "delete from auth_sessions where org_id=:o and seat_id=:s and expires_at < :cut"),
        {"o": org_id, "s": seat_id, "cut": now - _DEAD_SESSION_RETENTION})
    conn.execute(text(
        "insert into auth_sessions (session_id, org_id, seat_id, device_id, refresh_hash, "
        "created_at, last_used_at, expires_at) values (:sid,:o,:s,:d,:h,:now,:now,:exp)"),
        {"sid": sid, "o": org_id, "s": seat_id, "d": _device(device_id), "h": hashed,
         "now": now, "exp": now + timedelta(seconds=refresh_ttl)})
    return SessionTokens(
        access_token=mint_access_token(org_id=org_id, seat_id=seat_id, email=email, role=role,
                                       session_id=sid),
        refresh_token=raw, session_id=sid, expires_in=access_ttl, refresh_expires_in=refresh_ttl,
        org_id=org_id, seat_id=seat_id, email=email, role=role)


def rotate_session(conn, refresh_token: str | None, *,
                   device_id: str | None = None) -> RefreshOutcome:
    """Exchange a refresh token for a new access + refresh pair, or say why not.

    The session row is locked by its CURRENT hash. Two concurrent refreshes with the same token
    serialise on that lock; the loser re-reads, no longer matches, finds its hash in the rotation
    ledger and revokes the session — reuse is reuse regardless of who got there first.
    """
    if not refresh_token or not refresh_token.startswith(REFRESH_PREFIX):
        return RefreshOutcome(error=INVALID_REFRESH)
    hashed = hash_key(refresh_token)
    now = datetime.now(timezone.utc)
    row = conn.execute(text(
        "select session_id, org_id, seat_id, expires_at, revoked_at from auth_sessions "
        "where refresh_hash=:h for update"), {"h": hashed}).first()
    if row is None:
        reused = conn.execute(text(
            "select session_id from auth_refresh_rotations where refresh_hash=:h"),
            {"h": hashed}).first()
        if reused is None:
            return RefreshOutcome(error=INVALID_REFRESH)
        _revoke(conn, reused.session_id, "refresh_reuse", now)
        return RefreshOutcome(error=REFRESH_REUSED)
    if row.revoked_at is not None:
        return RefreshOutcome(error=SESSION_REVOKED)
    if row.expires_at <= now:
        return RefreshOutcome(error=SESSION_EXPIRED)
    seat = conn.execute(text(
        "select s.email, s.role, s.active, o.email as org_email, o.plan_status "
        "from org_seats s join orgs o on o.id = s.org_id "
        "where s.org_id=:o and s.seat_id=:s"), {"o": row.org_id, "s": row.seat_id}).first()
    if seat is None or not seat.active:
        _revoke(conn, row.session_id, "seat_inactive", now)
        return RefreshOutcome(error=SEAT_INACTIVE)
    if (seat.plan_status or "") == "suspended":
        return RefreshOutcome(error=ACCOUNT_SUSPENDED)
    raw, new_hash = _new_refresh()
    conn.execute(text(
        "insert into auth_refresh_rotations (refresh_hash, org_id, session_id, rotated_at) "
        "values (:h,:o,:sid,:now) on conflict (refresh_hash) do nothing"),
        {"h": hashed, "o": row.org_id, "sid": row.session_id, "now": now})
    conn.execute(text(
        "update auth_sessions set refresh_hash=:nh, last_used_at=:now, "
        "device_id=coalesce(:d, device_id) where session_id=:sid"),
        {"nh": new_hash, "now": now, "d": _device(device_id), "sid": row.session_id})
    role = seat_role(seat.email, seat.role, seat.org_email)
    access_ttl, _ = _ttls()
    return RefreshOutcome(tokens=SessionTokens(
        access_token=mint_access_token(org_id=row.org_id, seat_id=row.seat_id, email=seat.email,
                                       role=role, session_id=row.session_id),
        refresh_token=raw, session_id=row.session_id, expires_in=access_ttl,
        refresh_expires_in=max(0, int((row.expires_at - now).total_seconds())),
        org_id=row.org_id, seat_id=row.seat_id, email=seat.email, role=role))


def _revoke(conn, session_id: str, reason: str, now: datetime) -> bool:
    return conn.execute(text(
        "update auth_sessions set revoked_at=:now, revoked_reason=:r "
        "where session_id=:sid and revoked_at is null"),
        {"now": now, "r": reason, "sid": session_id}).rowcount > 0


def revoke_session(conn, session_id: str | None, *, org_id: str | None = None,
                   reason: str = "logout") -> bool:
    """Revoke one session. `org_id`, when given, must match — a token from one tenant can never
    end a session of another."""
    if not session_id:
        return False
    if org_id is not None:
        owned = conn.execute(text(
            "select 1 from auth_sessions where session_id=:sid and org_id=:o"),
            {"sid": session_id, "o": org_id}).first()
        if owned is None:
            return False
    return _revoke(conn, session_id, reason, datetime.now(timezone.utc))


def revoke_by_refresh(conn, refresh_token: str | None, *, reason: str = "logout") -> bool:
    """Logout by refresh token — works even after the access token expired. A rotated token names
    its session too, so logging out with a stale copy still ends the session."""
    if not refresh_token or not refresh_token.startswith(REFRESH_PREFIX):
        return False
    hashed = hash_key(refresh_token)
    sid = conn.execute(text("select session_id from auth_sessions where refresh_hash=:h"),
                       {"h": hashed}).scalar()
    if sid is None:
        sid = conn.execute(text(
            "select session_id from auth_refresh_rotations where refresh_hash=:h"),
            {"h": hashed}).scalar()
    return _revoke(conn, sid, reason, datetime.now(timezone.utc)) if sid else False


def revoke_seat_sessions(conn, *, org_id: str, seat_id: str, reason: str,
                         except_session: str | None = None) -> int:
    """End every live session of one seat (deactivation, password change)."""
    return conn.execute(text(
        "update auth_sessions set revoked_at=:now, revoked_reason=:r "
        "where org_id=:o and seat_id=:s and revoked_at is null "
        "and (cast(:keep as text) is null or session_id <> :keep)"),
        {"now": datetime.now(timezone.utc), "r": reason, "o": org_id, "s": seat_id,
         "keep": except_session}).rowcount or 0


__all__ = ["ACCESS_TOKEN_TYPE", "ACCOUNT_SUSPENDED", "INVALID_REFRESH", "REFRESH_PREFIX",
           "REFRESH_REUSED", "RefreshOutcome", "SEAT_INACTIVE", "SESSION_EXPIRED",
           "SESSION_REVOKED", "SessionTokens", "mint_access_token", "open_session",
           "revoke_by_refresh", "revoke_seat_sessions", "revoke_session", "rotate_session"]
