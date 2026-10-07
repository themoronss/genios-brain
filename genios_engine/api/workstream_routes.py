"""The founder's files, readable — `GET /v1/workstreams` (STEP-09).

The read model `context/workstreams.files_for` over the signed-in member's tenant: every file with the
kind the company brief gives it, its counterparty, its evidence, its last touch, its open asks and
whose move it is — and every counterparty the brief names, with how much of its mail is filed, the
ones with mail and no file named. Nothing is written, nothing calls a model, and nothing a seat
captured privately is listed (an org-level reader, `context/fact_visibility`).

WHO READS. Anyone the dashboard already lets read the tenant (`get_current_org`), as the company
brief's own read is (`api/company_brief_routes`). A scoped key is refused there, as everywhere.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from genios_engine.context.workstreams import as_dict, files_for
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _engine():
    if _graph is None:
        raise HTTPException(503, "no database")
    return _graph.engine


def _now() -> datetime:
    """The clock is read here, at the request boundary; the read model takes it as a parameter."""
    return datetime.now(timezone.utc)


@router.get("/v1/workstreams")
def list_workstreams(org_id: str = Depends(get_current_org)) -> dict:
    """Every file of the tenant, most recently touched first, with what the founder's brief names."""
    now = _now()
    with _engine().connect() as conn:
        return as_dict(files_for(conn, org_id, now=now), now=now)
