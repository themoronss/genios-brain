"""Hot-lane API — SCREEN_INTEL_P3_BUILD.md §2.1–2.4, §2.6 (frozen + pinned 2026-09-13).

  GET  /v1/seats/me/slice?since=<version>        device token   the seat's graph slice
  POST /v1/moments/evaluate                       device token   server moments (P-02), no LLM
  POST /v1/moments                                device token   device-local moments (P-01/P-18)
  POST /v1/moments/{moment_id}/feedback           device or seat
  GET  /v1/moments?limit&before&kind              device or seat the seat's own history

NEVER CREDIT-CHARGED (D6). Every handler is a few statements on the process's one pool (session
pooler 8+4): auth is one, the slice ~9, an evaluate ~10 including the persist transaction.
"""
from __future__ import annotations

import gzip
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from genios_engine.api.device_routes import _bearer, _err
from genios_engine.contracts.moments import KINDS, DeviceMoment, EvaluateRequest, FeedbackRequest
from genios_engine.platform import capture_policy as P
from genios_engine.platform import devices as D
from genios_engine.platform.auth import check_org_kill, jwt_decode, verify_bearer
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger
from genios_engine.reason.moments import guards as G
from genios_engine.reason.moments import recall as R
from genios_engine.reason.moments import slice as S
from genios_engine.reason.moments import store as M
from genios_engine.reason.moments.common import viewer_key

router = APIRouter(tags=["moments"])
_log = get_logger("genios.moments")
_NO_CONTENT = 204


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Principal:
    org_id: str
    seat_id: str
    device_id: str | None          # None = a signed-in seat (dashboard), not a device
    email: str | None
    expires_at: float | None       # the access token's `exp` (epoch seconds)


def _exp(token: str | None) -> float | None:
    payload = jwt_decode(token or "", get_settings().jwt_secret, verify_exp=False) if token else None
    try:
        return float(payload["exp"]) if payload and payload.get("exp") else None
    except (TypeError, ValueError):
        return None


def principal(request: Request, dstore, *, device_only: bool = False):
    """A device token → its seat + device. Otherwise (device_only=False) a signed-in seat's
    session token. API keys are refused either way: they have no seat. Returns a Principal or the
    JSONResponse refusing it; auth HTTPExceptions propagate."""
    token = _bearer(request)
    try:
        ctx = D.resolve_device_token(token, dstore)
        request.state.org_id = ctx.org_id
        return Principal(ctx.org_id, ctx.seat_id, ctx.device_id, ctx.email, _exp(token))
    except D.DeviceAuthError as e:
        if (device_only or e.code != D.DEVICE_TOKEN_REQUIRED or not token
                or token.startswith("gn_")):
            return _err(e.status, e.code, e.message)
    ctx = verify_bearer(token)
    if not ctx.seat_id:
        return _err(403, "SEAT_REQUIRED", "A signed-in seat is required.")
    check_org_kill(ctx.org_id)
    request.state.org_id = ctx.org_id
    return Principal(ctx.org_id, ctx.seat_id, None, ctx.email, _exp(token))


# ── §2.1 slice ────────────────────────────────────────────────────────────────────────────────
@router.get("/v1/seats/me/slice")
def get_slice(request: Request, since: int | None = Query(default=None, ge=0)):
    dstore, cstore = D.stores()
    p = principal(request, dstore, device_only=True)
    if isinstance(p, JSONResponse):
        return p
    doc = S.build(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, email=p.email, since=since)
    body = S.encode(doc)
    headers = {"Cache-Control": "no-store", "Vary": "Accept-Encoding"}
    if "gzip" in (request.headers.get("accept-encoding") or "").lower():
        return Response(gzip.compress(body, 5), media_type="application/json",
                        headers={**headers, "Content-Encoding": "gzip"})
    return Response(body, media_type="application/json", headers=headers)


# ── §2.2 evaluate ─────────────────────────────────────────────────────────────────────────────
def _stored(c, *, moment_id: str, org_id: str, seat_id: str) -> dict | None:
    r = c.execute(text(
        "select m.*, null as feedback from moments m where m.moment_id = :m "
        "and m.org_id = :o and m.seat_id = :s"),
        {"m": moment_id, "o": org_id, "s": seat_id}).mappings().first()
    if r is None:
        return None
    out = M.moment_out(r)
    keys = ("moment_id", "kind", "priority", "headline", "body", "actions", "evidence",
            "ttl_seconds", "capability_id", "capability_version", "display", "reason")
    return {k: out[k] for k in keys}


def _seat_emails(c, org_id: str) -> frozenset[str]:
    return frozenset(r.e for r in c.execute(text(
        "select lower(email) as e from org_seats where org_id = :o and email is not null"),
        {"o": org_id}))


@router.post("/v1/moments/evaluate")
def evaluate(body: EvaluateRequest, request: Request):
    started = time.perf_counter()
    dstore, cstore = D.stores()
    p = principal(request, dstore, device_only=True)
    if isinstance(p, JSONResponse):
        return p
    if body.device_id and body.device_id != p.device_id:
        return _err(403, "DEVICE_MISMATCH", "The body names a different device than the token.")
    if body.seat_id and body.seat_id != p.seat_id:
        return _err(403, "SEAT_MISMATCH", "The body names a different seat than the token.")
    now = _now()
    org, seat, _ = cstore.load(p.org_id, p.seat_id)
    eff = P.effective_policy(org, seat, now=now)
    s = body.surface
    # A moment is about what is on screen: nothing is evaluated while capture is off or paused,
    # nor on a surface the privacy gate blocks (banking, SSO, password managers …).
    if not eff["capture_on"] or P.is_blocked(s.url_domain, s.bundle_id, eff):
        return Response(status_code=_NO_CONTENT)
    engine = cstore.engine
    viewer = viewer_key(p.email)
    moment_id = M.server_moment_id(p.seat_id, body.moment_request_id)
    chosen = None
    with engine.connect() as c:
        prior = _stored(c, moment_id=moment_id, org_id=p.org_id, seat_id=p.seat_id)
        if prior is not None:                 # a retried request answers what the first did
            return prior
        subjects, me = R.resolve(c, org_id=p.org_id, participants=body.participants,
                                 entities=body.features.entities, seat_email=p.email)
        if not subjects:
            return Response(status_code=_NO_CONTENT)
        seat_emails = _seat_emails(c, p.org_id)
        for subj in subjects[:3]:
            version = R.subject_version(c, org_id=p.org_id, node_ids=[subj.node_id])
            # "last touch N d ago" changes daily, so the day is part of the trigger.
            trig = M.trigger_digest(R.CAPABILITY_ID, subj.node_id, now.date().isoformat())
            key = M.cache_key(seat_id=p.seat_id, capability_id=R.CAPABILITY_ID,
                              subject_ids=[subj.node_id], trigger=trig, subject_version=version)
            hit = M.cached(c, key, now)
            if hit is not None and hit.get("displayed"):      # only a SHOWN twin is a duplicate
                return {**M._public(hit), "display": False, "reason": G.DUPLICATE}
            content = R.compose(R.read(c, org_id=p.org_id, subject=subj, me=me, viewer=viewer,
                                       seat_emails=seat_emails, now=now), now=now)
            if content is not None:
                chosen = (subj, key, content)
                break
    if chosen is None:
        return Response(status_code=_NO_CONTENT)
    subj, key, content = chosen
    try:
        out = M.persist(engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="server", moment={"moment_id": moment_id, **content},
                        subject_ids=[subj.node_id], now=now, key=key)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    _log.info("moment evaluated org=%s seat=%s cap=%s display=%s reason=%s ms=%.0f", p.org_id,
              p.seat_id, R.CAPABILITY_ID, out["display"], out["reason"],
              (time.perf_counter() - started) * 1000)
    return out


# ── §2.3 device-local moments ─────────────────────────────────────────────────────────────────
@router.post("/v1/moments")
def post_device_moment(body: DeviceMoment, request: Request):
    dstore, cstore = D.stores()
    p = principal(request, dstore, device_only=True)
    if isinstance(p, JSONResponse):
        return p
    subjects = body.subject_node_ids or [e["node_id"] for e in body.evidence
                                         if isinstance(e, dict) and isinstance(e.get("node_id"), str)]
    moment = body.model_dump(exclude={"origin", "subject_node_ids"})
    # Identical advice within its TTL is shown once. A reminder is time-triggered and never
    # deduplicated (a snoozed reminder re-fires on purpose).
    key = None if body.kind == "reminder" else M.cache_key(
        seat_id=p.seat_id, capability_id=body.capability_id, subject_ids=subjects,
        trigger=M.trigger_digest(body.kind, body.headline, body.body), subject_version="device")
    try:
        out = M.persist(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, device_id=p.device_id,
                        origin="device", moment=moment, subject_ids=subjects, key=key)
    except M.MomentConflict:
        return _err(409, "MOMENT_ID_CONFLICT", "That moment id belongs to another seat.")
    return {"moment_id": body.moment_id, "display": out["display"], "reason": out["reason"]}


# ── §2.4 feedback ─────────────────────────────────────────────────────────────────────────────
@router.post("/v1/moments/{moment_id}/feedback")
def post_feedback(moment_id: str, body: FeedbackRequest, request: Request):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    at = body.at or _now()
    at = at if at.tzinfo else at.replace(tzinfo=timezone.utc)
    res = M.record_feedback(cstore.engine, org_id=p.org_id, seat_id=p.seat_id,
                            actor=viewer_key(p.email), moment_id=moment_id, action=body.action,
                            reason=body.reason, at=at)
    if res is None:
        return _err(404, "MOMENT_NOT_FOUND", "No such moment for this seat.")
    return res


# ── §2.6 history ──────────────────────────────────────────────────────────────────────────────
@router.get("/v1/moments")
def list_moments(request: Request, limit: int = Query(default=50, ge=1, le=200),
                 before: datetime | None = None, kind: str | None = None):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    if kind is not None and kind not in KINDS:
        return _err(422, "INVALID_KIND", f"kind must be one of {', '.join(KINDS)}")
    if before is not None and before.tzinfo is None:
        before = before.replace(tzinfo=timezone.utc)
    return M.history(cstore.engine, org_id=p.org_id, seat_id=p.seat_id, limit=limit,
                     before=before, kind=kind)


__all__ = ["Principal", "principal", "router"]
