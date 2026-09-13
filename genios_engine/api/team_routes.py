"""Team API — SCREEN_INTEL_P4_BUILD.md §3.2 (frozen + pinned 2026-09-13).

  GET  /v1/team/away?from&to    device or seat          [{seat_id, name, start, end, kind}]
  POST /v1/team/milestones      owner / admin session   the created milestone item
  GET  /v1/team/milestones      device or seat          [{milestone_id, title, due_at, owner_seat_id,
                                                          owner_name, scope_kind, scope_key, done,
                                                          pending, away, away_names}]

Away is who + when only: never a leave reason (a `sick` window is reported as `leave`; the site
shows "Away"). Readiness counts are computed on read (reason/team/readiness.py) — nothing stale is
stored. NEVER CREDIT-CHARGED.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from genios_engine.api.device_routes import _bearer, _err
from genios_engine.api.moment_routes import principal
from genios_engine.context.correlation_people import commitment_links, load_directory
from genios_engine.platform import devices as D
from genios_engine.platform.auth import check_org_kill, verify_bearer
from genios_engine.platform.ids import new_id
from genios_engine.reason.team.away import team_away
from genios_engine.reason.team.readiness import (counts, load_milestones, load_tasks,
                                                 milestone_out, normalize_task_filter)

router = APIRouter(tags=["team"])

DEFAULT_AWAY_DAYS = 14
MAX_AWAY_DAYS = 180
_CREATORS = ("owner", "admin")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MilestoneIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime
    owner_seat_id: str = Field(min_length=1, max_length=200)
    scope_kind: str | None = Field(default=None, max_length=100)
    scope_key: str | None = Field(default=None, max_length=200)
    task_filter: dict | None = None


@router.get("/v1/team/away")
def get_away(request: Request, from_: date | None = Query(default=None, alias="from"),
             to: date | None = Query(default=None)):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    start = from_ or _now().date()
    end = to or start + timedelta(days=DEFAULT_AWAY_DAYS)
    if end < start:
        return _err(422, "INVALID_RANGE", "`to` must not be before `from`.")
    if (end - start).days > MAX_AWAY_DAYS:
        return _err(422, "RANGE_TOO_LONG", f"At most {MAX_AWAY_DAYS} days per request.")
    with cstore.engine.connect() as c:
        return team_away(c, p.org_id, start=start, end=end)


def _items(conn, org_id: str, *, milestone_id: str | None = None) -> list[dict]:
    now = _now()
    directory = load_directory(conn, org_id)
    links = commitment_links(conn, org_id, directory)
    tasks = None
    out = []
    for m in load_milestones(conn, org_id, milestone_id=milestone_id):
        if m.query and tasks is None:
            tasks = load_tasks(conn, org_id)
        c = counts(conn, org_id, m, now=now, directory=directory, links=links, tasks=tasks)
        out.append(milestone_out(m, c, directory))
    return out


@router.get("/v1/team/milestones")
def list_milestones(request: Request):
    dstore, cstore = D.stores()
    p = principal(request, dstore)
    if isinstance(p, JSONResponse):
        return p
    with cstore.engine.connect() as c:
        return _items(c, p.org_id)


@router.post("/v1/team/milestones")
def create_milestone(request: Request, body: MilestoneIn):
    token = _bearer(request)
    if not token:
        return _err(401, "AUTH_REQUIRED", "Sign in to create a milestone.")
    ctx = verify_bearer(token)
    if not ctx.seat_id or ctx.role not in _CREATORS:
        return _err(403, "OWNER_OR_ADMIN_REQUIRED",
                    "Only a workspace owner or admin can create milestones.")
    check_org_kill(ctx.org_id)
    try:
        task_filter = normalize_task_filter(body.task_filter)
    except ValueError as e:
        return _err(422, "INVALID_TASK_FILTER", str(e))
    kind = (body.scope_kind or "").strip() or None
    key = (body.scope_key or "").strip() or None
    if (kind is None) != (key is None):
        return _err(422, "INVALID_SCOPE", "Give both scope_kind and scope_key, or neither.")
    due = body.due_at if body.due_at.tzinfo else body.due_at.replace(tzinfo=timezone.utc)
    _, cstore = D.stores()
    mid = new_id("mst")
    with cstore.engine.begin() as c:
        seat = c.execute(text("select 1 from org_seats where org_id = :o and seat_id = :s "
                              "and active"), {"o": ctx.org_id, "s": body.owner_seat_id}).first()
        if seat is None:
            return _err(422, "UNKNOWN_SEAT", "owner_seat_id is not an active seat of this workspace.")
        import json
        c.execute(text(
            "insert into team_milestones (milestone_id, org_id, title, due_at, owner_seat_id, "
            "scope_kind, scope_key, task_filter, created_by) values (:m, :o, :t, :d, :s, :k, "
            ":key, cast(:f as jsonb), :by)"),
            {"m": mid, "o": ctx.org_id, "t": body.title.strip(), "d": due,
             "s": body.owner_seat_id, "k": kind, "key": key,
             "f": json.dumps(task_filter or {}), "by": ctx.seat_id})
    with cstore.engine.connect() as c:
        items = _items(c, ctx.org_id, milestone_id=mid)
    return items[0] if items else {"milestone_id": mid}
