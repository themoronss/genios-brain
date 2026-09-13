"""Delegations — SCREEN_INTEL_P6_BUILD §3.3 (human) + §3.4 (agent result intake), frozen.

  POST /v1/delegations                      seat / device   propose a typed play (201, idempotent)
  POST /v1/delegations/{id}/approve         seat / device   the subject's seat or an org admin
  POST /v1/delegations/{id}/reject          seat / device   {reason}
  GET  /v1/delegations?state=&moment_id=    seat / device   own seat's (an admin: the org's)
  POST /v1/delegations/{id}/result          agent key, scope `actions.result`

GeniOS never writes to a provider: an approval queues the frozen request for the CLIENT'S agent
(`deliver/outbox.py`), which executes it and posts the result here. The approver is the clicking
seat — its email is `approved_by` — never `orgs.email`. Never credit-charged.

Registered in `main.py` by group B.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from genios_engine.api.device_routes import _err
from genios_engine.api.moment_routes import principal
from genios_engine.deliver import act_pump
from genios_engine.executive import delegation as DLG
from genios_engine.platform import devices as D
from genios_engine.platform import realtime
from genios_engine.platform.auth import AuthCtx, require_scope
from genios_engine.platform.config import get_settings

router = APIRouter(tags=["delegations"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ProposeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    moment_id: str | None = None
    card_id: str | None = None
    play: str
    params: dict
    agent_id: str | None = None
    supersedes: str | None = None


class RejectBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class ResultDetail(BaseModel):
    model_config = ConfigDict(extra="allow")
    provider_ref: str | None = None
    summary: str | None = None
    error: str | None = None


class ResultBody(BaseModel):
    status: Literal["succeeded", "failed"]
    detail: ResultDetail = Field(default_factory=ResultDetail)
    completed_at: datetime | None = None


def result_base_url(request: Request) -> str:
    """Where the agent posts its result. GENIOS_PUBLIC_API_URL when set (behind a proxy the
    request's own base URL may name an internal host), else the request's base URL."""
    configured = (getattr(get_settings(), "public_api_url", "") or
                  os.environ.get("GENIOS_PUBLIC_API_URL", ""))
    return (configured or str(request.base_url)).rstrip("/")


def _auth(request: Request):
    dstore, cstore = D.stores()
    return principal(request, dstore), cstore.engine


def _refuse(e: DLG.DelegationError) -> JSONResponse:
    return _err(e.status, e.code, e.message, **e.extra)


@router.post("/v1/delegations", status_code=201)
def create_delegation(body: ProposeBody, request: Request):
    p, engine = _auth(request)
    if isinstance(p, JSONResponse):
        return p
    try:
        out = DLG.create_proposal(engine, org_id=p.org_id, seat_id=p.seat_id, seat_email=p.email,
                                  moment_id=body.moment_id, card_id=body.card_id,
                                  play=body.play, params=body.params, agent_id=body.agent_id,
                                  via="device" if p.device_id else "api",
                                  supersedes=body.supersedes, now=_now())
    except DLG.DelegationError as e:
        return _refuse(e)
    return JSONResponse(status_code=201, content=out)


def _decide(request: Request, delegation_id: str, verb):
    p, engine = _auth(request)
    if isinstance(p, JSONResponse):
        return p
    if not p.email:
        return _err(403, "SEAT_EMAIL_REQUIRED", "The deciding seat has no email to record.")
    try:
        with engine.begin() as c:
            subject = DLG.subject_of(c, p.org_id, delegation_id)
            if subject is None:
                raise DLG.DelegationError(404, "NOT_FOUND", "No such delegation.")
            if not DLG.may_act(c, p.org_id, subject, p.seat_id):
                raise DLG.DelegationError(403, "FORBIDDEN",
                                          "Only its own seat or an org admin can decide this.")
            out = verb(c, p)
    except DLG.DelegationError as e:
        return _refuse(e)
    if out is None:
        return _err(404, "NOT_FOUND", "No such delegation.")
    realtime.wake()
    return out


@router.post("/v1/delegations/{delegation_id}/approve")
def approve_delegation(delegation_id: str, request: Request):
    base = result_base_url(request)
    out = _decide(request, delegation_id, lambda c, p: DLG.approve_and_enqueue(
        c, org_id=p.org_id, delegation_id=delegation_id, approver_seat_id=p.seat_id,
        approver_email=p.email, at=_now(), result_base_url=base))
    if isinstance(out, dict) and out.get("state") == "dispatched":
        act_pump.kick(D.stores()[1].engine)     # after the commit: send within seconds
    return out


@router.post("/v1/delegations/{delegation_id}/reject")
def reject_delegation(delegation_id: str, request: Request, body: RejectBody | None = None):
    reason = body.reason if body else None
    return _decide(request, delegation_id, lambda c, p: DLG.reject(
        c, org_id=p.org_id, delegation_id=delegation_id, actor_email=p.email,
        actor_seat_id=p.seat_id, reason=reason, at=_now()))


@router.get("/v1/delegations")
def list_delegations(request: Request, state: str | None = Query(default=None),
                     moment_id: str | None = Query(default=None),
                     limit: int = Query(default=50, ge=1, le=200)):
    p, engine = _auth(request)
    if isinstance(p, JSONResponse):
        return p
    if state is not None and state not in DLG.STATES:
        return _err(422, "INVALID_STATE", f"state must be one of {list(DLG.STATES)}.")
    with engine.connect() as c:
        admin = DLG.seat_is_org_admin(c, p.org_id, p.seat_id)
        items = DLG.list_delegations(c, p.org_id, seat_id=None if admin else p.seat_id,
                                     state=state, moment_id=moment_id, limit=limit)
    if not act_pump.running():
        act_pump.kick(engine)        # a process restarted with actions queued resumes here
    return {"delegations": items}


@router.post("/v1/delegations/{delegation_id}/result")
def post_result(delegation_id: str, body: ResultBody,
                ctx: AuthCtx = Depends(require_scope("actions.result"))):
    """§3.4. Only the agent the delegation was dispatched to — any other credential (another
    agent, an owner session with no agent) gets 404 and learns nothing."""
    _, cstore = D.stores()
    with cstore.engine.begin() as c:
        outcome, state = DLG.record_agent_result(
            c, org_id=ctx.org_id, delegation_id=delegation_id, agent_id=ctx.agent_id,
            status=body.status, detail=body.detail.model_dump(exclude_none=True),
            completed_at=body.completed_at, at=_now())
    if outcome == "not_found":
        return _err(404, "NOT_FOUND", "No such delegation for this agent.")
    if outcome == "conflict":
        return _err(409, "result_conflict", "A different final result is already recorded.",
                    state=state)
    if outcome == "not_dispatched":
        return _err(409, "not_dispatched", f"The delegation is {state}, not dispatched.",
                    state=state)
    if outcome == "recorded":
        realtime.wake()
    return {"delegation_id": delegation_id, "state": state, "recorded": outcome == "recorded"}


__all__ = ["router", "result_base_url"]
