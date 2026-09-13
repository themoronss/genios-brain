"""Device API — P1 screen capture (contracts: docs/plans/SCREEN_INTEL_P1_BUILD.md §3.1, §3.3, §3.4).

  §3.1  POST /v1/devices/code · POST /v1/devices/token          public (RFC 8628)
        GET  /v1/devices/code/{user_code} · POST /v1/devices/approve · GET /v1/devices ·
        DELETE /v1/devices/{device_id}                           signed-in seat
  §3.3  POST /v1/sessions                                         device token
  §3.4  POST /v1/presence                                         device token

A "device token" is a seat access token whose session was opened by the device-code exchange —
`platform/devices.resolve_device_token` refuses anything else, including `gn_live_` keys and
pre-session JWTs. Every handler here is a handful of statements on the process's one pool: the
session pooler is 8+4 connections and a heartbeat arrives every 10 s per device.
"""
from __future__ import annotations

import json
import zlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from genios_engine.contracts.device import (CLIENT_ID, DEVICE_CODE_GRANT, PLATFORMS,
                                            SCHEMA_VERSION, DeviceApproveRequest,
                                            DeviceCodeRequest, DeviceTokenRequest,
                                            PresenceHeartbeat, ScreenSession, SessionUpload)
from genios_engine.platform import capture_policy as P
from genios_engine.platform import devices as D
from genios_engine.platform.auth import AuthCtx, require_seat
from genios_engine.platform.cache import get_cache
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import encrypt
from genios_engine.platform.logging import get_logger

router = APIRouter(tags=["devices"])
_log = get_logger("genios.devices")

MAX_UPLOAD_BYTES = 256 * 1024             # on the wire (§3.3)
MAX_DECODED_BYTES = 1024 * 1024           # after gunzip — a zip-bomb bound, not a second quota
_CODE_REQUESTS_PER_IP = 20                # per 10 minutes
_CODE_LOOKUPS_PER_SEAT = 30               # per 5 minutes (GET code + approve)
_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt) -> str | None:
    return D._iso(dt)


def _err(http_status: int, code: str, message: str, **extra) -> JSONResponse:
    """`{code, message}` at the top level (the §3.4 shape the device reads) AND under `detail`
    (the shape every dashboard client already reads from an HTTPException)."""
    body = {"code": code, "message": message, **extra}
    return JSONResponse(status_code=http_status, content={**body, "detail": body})


def _oauth_error(error: str, description: str | None = None, status: int = 400) -> JSONResponse:
    body = {"error": error}
    if description:
        body["error_description"] = description
    return JSONResponse(status_code=status, content=body, headers=_NO_STORE)


def _throttled(key: str, limit: int, window_s: int) -> bool:
    """Fixed-window counter in the cache. Fails OPEN (as `/auth/login` does): no Redis, or a
    Redis error, never locks a customer out."""
    try:
        return get_cache().incr_window(key, window_s) > limit
    except Exception:                    # noqa: BLE001
        return False


def _client_ip(request: Request) -> str | None:
    ip = request.headers.get("do-connecting-ip")           # DigitalOcean App Platform
    if not ip:
        fwd = request.headers.get("x-forwarded-for") or ""
        ip = fwd.split(",")[0].strip() or None
    if not ip and request.client is not None:
        ip = request.client.host
    return (ip or "")[:64] or None


def _verification_base() -> str | None:
    s = get_settings()
    base = (s.dashboard_url or "").strip().rstrip("/")
    if not base and (s.env or "").lower() in ("dev", "test", "local"):
        base = "http://localhost:3000"
    return base or None


def require_session_seat(ctx: AuthCtx = Depends(require_seat)) -> AuthCtx:
    """A seat signed in through a session. Refuses org API keys (no seat — `require_seat`) and
    pre-session JWTs (no `sid`): neither can be revoked per device, so neither may approve,
    list or revoke one."""
    if ctx.source != "jwt" or not ctx.session_id:
        raise HTTPException(403, {"code": "SEAT_SESSION_REQUIRED",
                                  "message": "Sign in again to manage devices and capture."})
    return ctx


# ── §3.1 device sign-in ──────────────────────────────────────────────────────────────────────
@router.post("/v1/devices/code")
def device_code(body: DeviceCodeRequest, request: Request):
    if body.client_id != CLIENT_ID:
        return _oauth_error("invalid_client", "unknown client_id")
    platform = body.platform.strip().lower()
    if platform not in PLATFORMS:
        return _oauth_error("invalid_request", f"platform must be one of {sorted(PLATFORMS)}")
    ip = _client_ip(request)
    if ip and _throttled(f"devcode:ip:{ip}", _CODE_REQUESTS_PER_IP, 600):
        return _oauth_error("slow_down", "too many sign-in codes requested; try again later",
                            status=429)
    base = _verification_base()
    if base is None:
        _log.error("device sign-in requested but GENIOS_DASHBOARD_URL is not set")
        return _oauth_error("temporarily_unavailable",
                            "device sign-in is not configured on this server", status=503)
    dstore, _ = D.stores()
    issued = dstore.issue_code(device_name=(body.device_name or "").strip() or None,
                               platform=platform, os_version=body.os_version,
                               app_version=body.app_version, requested_ip=ip)
    shown = D.format_user_code(issued.user_code)
    return JSONResponse(content={
        "device_code": issued.device_code, "user_code": shown,
        "verification_uri": f"{base}/device",
        "verification_uri_complete": f"{base}/device?user_code={shown}",
        "expires_in": issued.expires_in, "interval": issued.interval}, headers=_NO_STORE)


@router.post("/v1/devices/token")
def device_token(body: DeviceTokenRequest):
    if body.grant_type != DEVICE_CODE_GRANT:
        return _oauth_error("unsupported_grant_type")
    dstore, _ = D.stores()
    out = dstore.exchange(body.device_code)
    if out.error:
        return _oauth_error(out.error)
    t = out.tokens
    from genios_engine.platform.audit import record
    record(t.org_id, "device_registered", actor_type="user", actor_id=t.email or t.seat_id,
           target_type="device", target_id=out.device_id,
           metadata={"seat_id": t.seat_id, "platform": out.platform,
                     "device_name": out.device_name})
    return JSONResponse(content={"device_id": out.device_id, "org_id": t.org_id,
                                 "email": t.email, **t.as_response()}, headers=_NO_STORE)


def _code_or_404(user_code: str, ctx: AuthCtx) -> str:
    if _throttled(f"devcode:seat:{ctx.org_id}:{ctx.seat_id}", _CODE_LOOKUPS_PER_SEAT, 300):
        raise HTTPException(429, {"code": "TOO_MANY_ATTEMPTS",
                                  "message": "Too many codes tried. Wait a few minutes."})
    uc = D.normalize_user_code(user_code)
    if uc is None:
        raise HTTPException(404, {"code": "CODE_NOT_FOUND", "message": "That code is not valid."})
    return uc


@router.get("/v1/devices/code/{user_code}")
def get_device_code(user_code: str, ctx: AuthCtx = Depends(require_session_seat)) -> dict:
    uc = _code_or_404(user_code, ctx)
    dstore, _ = D.stores()
    row = dstore.get_code(uc)
    if row is None or (row.get("org_id") is not None
                       and (row["org_id"], row["seat_id"]) != (ctx.org_id, ctx.seat_id)):
        raise HTTPException(404, {"code": "CODE_NOT_FOUND", "message": "That code is not valid."})
    return {"user_code": D.format_user_code(uc), "device_name": row.get("device_name"),
            "platform": row.get("platform"), "os_version": row.get("os_version"),
            "app_version": row.get("app_version"), "requested_at": _iso(row.get("created_at")),
            "expires_at": _iso(row.get("expires_at")), "status": D.code_status(row, _now())}


@router.post("/v1/devices/approve")
def approve_device(body: DeviceApproveRequest, ctx: AuthCtx = Depends(require_session_seat)):
    """404 unknown · 410 expired · 409 `{code, status}` already approved / denied / consumed
    (contract §3.2, pinned 2026-09-13)."""
    uc = _code_or_404(body.user_code, ctx)
    dstore, _ = D.stores()
    try:
        return dstore.decide(uc, org_id=ctx.org_id, seat_id=ctx.seat_id, approve=body.approve)
    except D.DeviceError as e:
        extra = {"status": e.state} if e.state else {}
        return _err(e.status, e.code, e.message, **extra)


def _device_out(r: dict) -> dict:
    return {"device_id": r["device_id"], "seat_id": r["seat_id"],
            "seat_email": r.get("seat_email"), "device_name": r.get("device_name"),
            "platform": r.get("platform"), "os_version": r.get("os_version"),
            "app_version": r.get("app_version"), "last_seen_at": _iso(r.get("last_seen_at")),
            "created_at": _iso(r.get("created_at")), "revoked_at": _iso(r.get("revoked_at"))}


@router.get("/v1/devices")
def list_devices(scope: str | None = None,
                 ctx: AuthCtx = Depends(require_session_seat)) -> list[dict]:
    dstore, _ = D.stores()
    if scope == "org":
        if not ctx.is_org_admin:
            raise HTTPException(403, "workspace admin required")
        rows = dstore.list_devices(ctx.org_id)
    elif scope in (None, "", "seat", "own"):
        rows = dstore.list_devices(ctx.org_id, ctx.seat_id)
    else:
        raise HTTPException(422, "scope must be 'org' or omitted")
    return [_device_out(r) for r in rows]


@router.delete("/v1/devices/{device_id}", status_code=204)
def revoke_device(device_id: str, ctx: AuthCtx = Depends(require_session_seat)) -> Response:
    """204 whether or not it was already revoked (pinned 2026-09-13); 404 / 403 otherwise."""
    dstore, _ = D.stores()
    row = dstore.device(ctx.org_id, device_id)
    if row is None:
        raise HTTPException(404, {"code": "DEVICE_NOT_FOUND", "message": "No such device."})
    if row["seat_id"] != ctx.seat_id and not ctx.is_org_admin:
        raise HTTPException(403, "only the device's own seat or a workspace admin can revoke it")
    revoked = dstore.revoke(ctx.org_id, device_id, revoked_by=ctx.seat_id)
    if revoked:
        from genios_engine.platform.audit import record
        record(ctx.org_id, "device_revoked", actor_type="user", actor_id=ctx.email or ctx.seat_id,
               target_type="device", target_id=device_id, metadata={"seat_id": row["seat_id"]})
    return Response(status_code=204)


# ── device-token endpoints ───────────────────────────────────────────────────────────────────
def _bearer(request: Request) -> str | None:
    h = request.headers.get("authorization") or ""
    return h[7:].strip() if h[:7].lower() == "bearer " else None


def _device(request: Request, dstore):
    """DeviceCtx, or the JSONResponse that refuses it (401 DEVICE_REVOKED keeps its top-level
    `code`, which an HTTPException would bury under `detail`)."""
    try:
        return D.resolve_device_token(_bearer(request), dstore)
    except D.DeviceAuthError as e:
        return _err(e.status, e.code, e.message)


def _too_old(app_version: str | None) -> JSONResponse | None:
    if P.app_version_supported(app_version):
        return None
    need = P.min_supported_app_version()
    return _err(426, "APP_UPDATE_REQUIRED", f"This app version is no longer supported ({need}+).",
                min_supported_app_version=need)


# §3.4 presence ------------------------------------------------------------------------------
@router.post("/v1/presence")
def presence(body: PresenceHeartbeat, request: Request):
    dstore, cstore = D.stores()
    ctx = _device(request, dstore)
    if isinstance(ctx, JSONResponse):
        return ctx
    old = _too_old(body.app_version)
    if old is not None:
        return old
    now = _now()
    org, seat, lease = cstore.load(ctx.org_id, ctx.seat_id, ctx.device_id)
    eff = P.effective_policy(org, seat, now=now)
    version = P.policy_version(eff)
    # What someone is focused on is recorded only once they opted into capture, and never the
    # name of a sensitive app (a password manager in focus is itself a disclosure).
    focus_ok = eff["capture_on"] and not P.bundle_blocked(body.bundle_id)
    fields = {"focus_app": body.focus_app if focus_ok else None,
              "bundle_id": body.bundle_id if focus_ok else None,
              "dnd": bool(body.dnd), "idle": bool(body.idle), "app_version": body.app_version,
              "policy_version": body.policy_version}
    if P.should_write_presence(lease, fields, now=now):
        cstore.write_presence(org_id=ctx.org_id, seat_id=ctx.seat_id, device_id=ctx.device_id,
                              fields=fields, now=now)
    return {"revoked": False, "policy_version": version,
            "policy_changed": body.policy_version != version,
            "min_supported_app_version": P.min_supported_app_version(),
            "server_time": _iso(now)}


# §3.3 session upload --------------------------------------------------------------------------
class _BodyError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise _BodyError(413, "PAYLOAD_TOO_LARGE", f"Upload bodies are limited to "
                                                   f"{MAX_UPLOAD_BYTES // 1024} KB; split it.")
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > MAX_UPLOAD_BYTES:
            raise _BodyError(413, "PAYLOAD_TOO_LARGE", f"Upload bodies are limited to "
                                                       f"{MAX_UPLOAD_BYTES // 1024} KB; split it.")
    encoding = (request.headers.get("content-encoding") or "").strip().lower()
    if encoding in ("", "identity"):
        return bytes(buf)
    if encoding != "gzip":
        raise _BodyError(415, "UNSUPPORTED_ENCODING", "Only gzip content encoding is accepted.")
    inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = inflater.decompress(bytes(buf), MAX_DECODED_BYTES + 1)
    except zlib.error:
        raise _BodyError(400, "INVALID_GZIP", "The body is not valid gzip.") from None
    if len(out) > MAX_DECODED_BYTES or inflater.unconsumed_tail:
        raise _BodyError(413, "PAYLOAD_TOO_LARGE", "The decompressed body is too large; split it.")
    return out


def _ingest(ctx: D.DeviceCtx, envelope: SessionUpload, cstore, key: str) -> dict:
    now = _now()
    org, seat, _ = cstore.load(ctx.org_id, ctx.seat_id)
    # One slot per input session, in input order; filled once the insert says what was new.
    outcome: list[tuple[str, str, str | None]] = []       # (kind, session_key, reason)
    rows: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for raw in envelope.sessions:
        hint = raw.get("session_key") if isinstance(raw, dict) else None
        try:
            s = ScreenSession.model_validate(raw)
        except ValidationError:
            outcome.append(("rejected", str(hint or "")[:300], P.INVALID))
            continue
        reason = P.check_session(org, seat, app=s.app, url=s.url, bundle_id=s.bundle_id,
                                 private_window=s.private_window, now=now)
        if reason:
            outcome.append(("rejected", s.session_key, reason))
            continue
        pair = (s.session_key, s.message_watermark)
        if pair in seen:
            outcome.append(("duplicate", s.session_key, None))
            continue
        seen.add(pair)
        payload = json.dumps(s.model_dump(mode="json"), separators=(",", ":"))
        rows.append({"session_key": s.session_key, "message_watermark": s.message_watermark,
                     "seat_id": ctx.seat_id, "app": s.app.strip().lower(),
                     "thread_key": s.thread_key, "payload_enc": encrypt(payload, key),
                     # a generic session's unit is the block (§3.7)
                     "message_count": (len(s.blocks) if s.app == P.GENERIC_APP
                                       else len(s.messages)),
                     "captured_at": s.captured_at})
        outcome.append(("pending", s.session_key, str(s.message_watermark)))
    inserted = cstore.insert_deltas(rows, org_id=ctx.org_id, device_id=ctx.device_id, now=now)
    accepted, duplicate, rejected = [], [], []
    for kind, skey, extra in outcome:
        if kind == "rejected":
            rejected.append({"session_key": skey, "reason": extra})
        elif kind == "duplicate":
            duplicate.append(skey)
        elif (skey, int(extra)) in inserted:
            accepted.append(skey)
        else:
            duplicate.append(skey)
    return {"accepted": accepted, "duplicate": duplicate, "rejected": rejected}


@router.post("/v1/sessions")
async def upload_sessions(request: Request):
    dstore, cstore = D.stores()
    ctx = await run_in_threadpool(_device, request, dstore)
    if isinstance(ctx, JSONResponse):
        return ctx
    key = get_settings().crypto_key
    if not key:
        # Screen text is never stored in clear. No key → nothing is stored; the device keeps
        # its queue and retries.
        _log.error("screen session upload refused: GENIOS_CRYPTO_KEY is not configured")
        return _err(503, "CAPTURE_STORE_UNAVAILABLE", "Capture storage is not configured.")
    try:
        raw = await _read_body(request)
    except _BodyError as e:
        return _err(e.status, e.code, e.message)
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return _err(400, "INVALID_JSON", "The body is not JSON.")
    try:
        envelope = SessionUpload.model_validate(obj)
    except ValidationError as e:
        return _err(422, "INVALID_UPLOAD", "The upload envelope is malformed.",
                    errors=json.loads(e.json(include_url=False, include_input=False))[:10])
    if envelope.schema_version != SCHEMA_VERSION:
        return _err(422, "UNSUPPORTED_SCHEMA_VERSION",
                    f"schema_version {envelope.schema_version} is not supported "
                    f"(this server speaks {SCHEMA_VERSION}).")
    if envelope.device_id and envelope.device_id != ctx.device_id:
        return _err(403, "DEVICE_MISMATCH", "The body names a different device than the token.")
    if envelope.seat_id and envelope.seat_id != ctx.seat_id:
        return _err(403, "SEAT_MISMATCH", "The body names a different seat than the token.")
    request.state.org_id = ctx.org_id          # the api_call analytics event, as other routes
    return await run_in_threadpool(_ingest, ctx, envelope, cstore, key)
