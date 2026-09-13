"""Verify API — SCREEN_INTEL_P4 §3.3 (frozen).

  GET  /v1/discrepancies?status=open            device or seat   discrepancies the seat may see
  POST /v1/discrepancies/{id}/resolve           device or seat   accept | keep | snooze

A seat never sees (nor settles) a discrepancy with a side learned from another seat's private
evidence — `reason/verify/store.visible`, the same filter `GET /context/discrepancies` applies.
Resolving is audit-logged. NEVER CREDIT-CHARGED (D6).
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from genios_engine.api.device_routes import _err
from genios_engine.api.moment_routes import principal
from genios_engine.platform import devices as D
from genios_engine.reason.moments.common import viewer_key
from genios_engine.reason.verify import store as V

router = APIRouter(tags=["verify"])


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: Literal["accept", "keep", "snooze"]
    snooze_days: int = Field(default=7, ge=1, le=V.MAX_SNOOZE_DAYS)


@router.get("/v1/discrepancies")
def list_discrepancies(request: Request, status: str = Query(default="open"),
                       limit: int = Query(default=50, ge=1, le=200)):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    if status not in V.STATUSES:
        return _err(422, "INVALID_STATUS", f"status must be one of {', '.join(V.STATUSES)}")
    with cstore.engine.connect() as c:
        found = V.list_for_viewer(c, org_id=p.org_id, viewer=viewer_key(p.email), status=status,
                                  limit=limit)
    return {"discrepancies": [V.public(r) for r in found]}


@router.post("/v1/discrepancies/{discrepancy_id}/resolve")
def resolve_discrepancy(discrepancy_id: str, body: ResolveRequest, request: Request):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    from genios_engine.context.graph_store import GraphStore
    try:
        return V.resolve(cstore.engine, GraphStore(engine=cstore.engine), org_id=p.org_id,
                         discrepancy_id=discrepancy_id, viewer=viewer_key(p.email),
                         seat_id=p.seat_id, action=body.action, snooze_days=body.snooze_days)
    except V.ResolveError as e:
        return _err(e.status, e.code, e.message)


__all__ = ["router"]
