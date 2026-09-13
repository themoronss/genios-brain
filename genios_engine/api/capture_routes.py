"""Capture policy API — P1 screen capture (contract: docs/plans/SCREEN_INTEL_P1_BUILD.md §3.2).

  GET  /v1/capture/policy     any signed-in seat (dashboard or device) — the merged document
  PUT  /v1/capture/policy     workspace admin — the ORG half
  PUT  /v1/capture/settings   the seat itself — its own opt-in and blocks
  POST /v1/capture/pause      the seat itself — {minutes} or {until}; minutes 0 resumes

Every write answers with the full policy document the GET returns, so a settings page re-renders
from the response and never shows a state the server did not store.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from genios_engine.api.device_routes import require_session_seat
from genios_engine.contracts.device import CapturePause, CapturePolicyUpdate, SeatCaptureUpdate
from genios_engine.platform import capture_policy as P
from genios_engine.platform import devices as D
from genios_engine.platform.auth import AuthCtx

router = APIRouter(tags=["capture"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _document(cstore, ctx: AuthCtx) -> dict:
    org, seat, _ = cstore.load(ctx.org_id, ctx.seat_id)
    return P.policy_document(org, seat, now=_now())


def _clean(changes: dict, *, apps_key: str, domains_key: str) -> dict:
    try:
        if apps_key in changes:
            changes[apps_key] = P.normalize_apps(changes[apps_key])
        if domains_key in changes:
            changes[domains_key] = P.normalize_patterns(changes[domains_key])
    except ValueError as e:
        raise HTTPException(422, {"code": "INVALID_POLICY", "message": str(e)}) from None
    return changes


@router.get("/v1/capture/policy")
def get_policy(ctx: AuthCtx = Depends(require_session_seat)) -> dict:
    _, cstore = D.stores()
    return _document(cstore, ctx)


@router.put("/v1/capture/policy")
def put_policy(body: CapturePolicyUpdate, ctx: AuthCtx = Depends(require_session_seat)) -> dict:
    if not ctx.is_org_admin:
        raise HTTPException(403, "workspace admin required")
    changes = _clean(body.model_dump(exclude_unset=True, exclude_none=True),
                     apps_key="allowed_apps", domains_key="blocked_domains")
    _, cstore = D.stores()
    cstore.save_org_policy(ctx.org_id, changes, updated_by=ctx.seat_id)
    doc = _document(cstore, ctx)
    from genios_engine.platform.audit import record
    record(ctx.org_id, "capture_policy_changed", actor_type="user",
           actor_id=ctx.email or ctx.seat_id, target_type="capture_policy",
           target_id=ctx.org_id,
           metadata={"fields": sorted(changes), "enabled": doc["org"]["enabled"],
                     "allowed_apps": doc["org"]["allowed_apps"],
                     "retention_days": doc["org"]["retention_days"]})
    return doc


@router.put("/v1/capture/settings")
def put_settings(body: SeatCaptureUpdate, ctx: AuthCtx = Depends(require_session_seat)) -> dict:
    changes = _clean(body.model_dump(exclude_unset=True, exclude_none=True),
                     apps_key="blocked_apps", domains_key="blocked_domains")
    _, cstore = D.stores()
    before = _document(cstore, ctx)["seat"]["enabled"] if "enabled" in changes else None
    cstore.save_seat_settings(ctx.org_id, ctx.seat_id, changes)
    doc = _document(cstore, ctx)
    if before is not None and before != doc["seat"]["enabled"]:
        from genios_engine.platform.audit import record
        record(ctx.org_id,
               "seat_capture_enabled" if doc["seat"]["enabled"] else "seat_capture_disabled",
               actor_type="user", actor_id=ctx.email or ctx.seat_id, target_type="seat",
               target_id=ctx.seat_id)
    return doc


@router.post("/v1/capture/pause")
def pause(body: CapturePause, ctx: AuthCtx = Depends(require_session_seat)) -> dict:
    now = _now()
    if body.minutes is not None:
        until = now + timedelta(minutes=body.minutes) if body.minutes > 0 else None
    elif body.until is not None:
        until = body.until if body.until.tzinfo else body.until.replace(tzinfo=timezone.utc)
        until = until if until > now else None
    else:
        raise HTTPException(422, {"code": "INVALID_PAUSE",
                                  "message": "send {minutes} or {until}"})
    _, cstore = D.stores()
    cstore.save_seat_settings(ctx.org_id, ctx.seat_id, {"paused_until": until})
    return _document(cstore, ctx)
