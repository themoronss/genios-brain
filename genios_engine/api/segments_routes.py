"""Graph segments — named, typed groups of contacts (person/company graph nodes).

Ported from the v1 backend and adapted to the v2 graph model: a "contact" is a current
graph_node of type person/company, not a legacy `contacts` row. Membership lives in
segment_members; the frontend's /v1/segment* paths are preserved so the dashboard is unchanged.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.ids import new_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

VALID_CLUSTER_TYPES = ("Investor", "Customer", "Team", "Vendor", "Admin", "Other")
_VALID_SYNC_HOURS = (6, 12, 18, 24)
# Plan → max segments. Kept generous; refined when plan enforcement is unified.
_MAX_CLUSTERS = {"trial": 1, "early": 3, "hustler": 3, "startup": 10, "enterprise": 100}


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def _plan(conn, org_id: str) -> str:
    row = conn.execute(text("select subscription_tier from orgs where id=:o"),
                       {"o": org_id}).first()
    return (row[0] if row and row[0] else "trial").lower()


def _validated_sync_interval(plan: str, value: int | None) -> int | None:
    if plan == "trial":
        return None                          # trial is manual-only
    if value is None:
        return None
    return value if value in _VALID_SYNC_HOURS else 6


def _iso(value) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else None)


def _format(row, member_count: int) -> dict:
    return {
        "id": row["id"], "name": row["name"], "cluster_type": row["cluster_type"],
        "config": row["config"] or {}, "sync_interval_hours": row["sync_interval_hours"],
        "last_synced_at": _iso(row["last_synced_at"]), "created_at": _iso(row["created_at"]),
        "member_count": member_count,
    }


def _member_count(conn, segment_id: str) -> int:
    return int(conn.execute(text("select count(*) from segment_members where segment_id=:s"),
                            {"s": segment_id}).scalar() or 0)


class CreateSegment(BaseModel):
    name: str
    cluster_type: str
    config: dict = {}
    sync_interval_hours: int | None = None


class UpdateSegment(BaseModel):
    name: str | None = None
    cluster_type: str | None = None
    config: dict | None = None
    sync_interval_hours: int | None = None


class AddMembers(BaseModel):
    contact_ids: list[str]


class ContactSegment(BaseModel):
    segment_id: str | None = None


def _known_nodes(conn, org_id: str, ids: list[str]) -> list[str]:
    """Only the ids that are current person/company graph nodes for this org."""
    if not ids:
        return []
    rows = conn.execute(text(
        "select distinct node_id from graph_nodes where org_id=:o and valid_to is null "
        "and node_type in ('person','company') and node_id = any(cast(:ids as text[]))"),
        {"o": org_id, "ids": list(ids)}).scalars().all()
    return [str(r) for r in rows]


@router.get("/v1/segments")
def list_segments(org: str = Depends(get_current_org)) -> dict:
    with _store().engine.begin() as conn:
        plan = _plan(conn, org)
        rows = conn.execute(text(
            "select s.*, (select count(*) from segment_members m where m.segment_id=s.id) mc "
            "from graph_segments s where s.org_id=:o order by s.created_at desc"),
            {"o": org}).mappings().all()
    segments = [_format(r, int(r["mc"])) for r in rows]
    return {"segments": segments, "count": len(segments),
            "max_allowed": _MAX_CLUSTERS.get(plan, 3), "plan_tier": plan}


@router.post("/v1/segment", status_code=201)
def create_segment(body: CreateSegment, org: str = Depends(get_current_org)) -> dict:
    name = (body.name or "").strip()
    if len(name) < 2:
        raise HTTPException(400, "name must be at least 2 characters")
    if body.cluster_type not in VALID_CLUSTER_TYPES:
        raise HTTPException(400, f"cluster_type must be one of {VALID_CLUSTER_TYPES}")
    with _store().engine.begin() as conn:
        plan = _plan(conn, org)
        count = int(conn.execute(text("select count(*) from graph_segments where org_id=:o"),
                                 {"o": org}).scalar() or 0)
        if count >= _MAX_CLUSTERS.get(plan, 3):
            raise HTTPException(403, {"code": "PLAN_LIMIT",
                                      "message": f"segment limit reached for {plan} plan"})
        sid = new_id("seg")
        interval = _validated_sync_interval(plan, body.sync_interval_hours)
        conn.execute(text(
            "insert into graph_segments (id,org_id,name,cluster_type,config,sync_interval_hours) "
            "values (:id,:o,:n,:ct,cast(:cfg as jsonb),:si)"),
            {"id": sid, "o": org, "n": name, "ct": body.cluster_type,
             "cfg": json.dumps(body.config or {}), "si": interval})
        row = conn.execute(text("select * from graph_segments where id=:id"),
                           {"id": sid}).mappings().first()
    return _format(row, 0)


@router.put("/v1/segment/{segment_id}")
def update_segment(segment_id: str, body: UpdateSegment,
                   org: str = Depends(get_current_org)) -> dict:
    sets, params = [], {"id": segment_id, "o": org}
    if body.name is not None:
        if len(body.name.strip()) < 2:
            raise HTTPException(400, "name must be at least 2 characters")
        sets.append("name=:n"); params["n"] = body.name.strip()
    if body.cluster_type is not None:
        if body.cluster_type not in VALID_CLUSTER_TYPES:
            raise HTTPException(400, f"cluster_type must be one of {VALID_CLUSTER_TYPES}")
        sets.append("cluster_type=:ct"); params["ct"] = body.cluster_type
    if body.config is not None:
        sets.append("config=cast(:cfg as jsonb)"); params["cfg"] = json.dumps(body.config)
    with _store().engine.begin() as conn:
        if body.sync_interval_hours is not None:
            sets.append("sync_interval_hours=:si")
            params["si"] = _validated_sync_interval(_plan(conn, org), body.sync_interval_hours)
        if sets:
            conn.execute(text(f"update graph_segments set {','.join(sets)} "
                              "where id=:id and org_id=:o"), params)
        row = conn.execute(text("select * from graph_segments where id=:id and org_id=:o"),
                           {"id": segment_id, "o": org}).mappings().first()
        if row is None:
            raise HTTPException(404, "segment not found")
        return _format(row, _member_count(conn, segment_id))


@router.delete("/v1/segment/{segment_id}")
def delete_segment(segment_id: str, org: str = Depends(get_current_org)) -> dict:
    with _store().engine.begin() as conn:
        deleted = conn.execute(text(
            "delete from graph_segments where id=:id and org_id=:o returning id"),
            {"id": segment_id, "o": org}).first()
    if deleted is None:
        raise HTTPException(404, "segment not found")
    return {"deleted": True, "id": segment_id}


@router.get("/v1/segment/{segment_id}/members")
def list_members(segment_id: str, org: str = Depends(get_current_org)) -> dict:
    with _store().engine.begin() as conn:
        if conn.execute(text("select 1 from graph_segments where id=:id and org_id=:o"),
                        {"id": segment_id, "o": org}).first() is None:
            raise HTTPException(404, "segment not found")
        rows = conn.execute(text(
            "select m.node_id, m.source, m.added_at, "
            "  (select n.display_name from graph_nodes n where n.org_id=m.org_id "
            "   and n.node_id=m.node_id and n.valid_to is null limit 1) as name, "
            "  (select n.node_type from graph_nodes n where n.org_id=m.org_id "
            "   and n.node_id=m.node_id and n.valid_to is null limit 1) as type "
            "from segment_members m where m.segment_id=:s order by m.added_at desc"),
            {"s": segment_id}).mappings().all()
    members = [{"contact_id": r["node_id"], "name": r["name"], "type": r["type"],
                "source": r["source"], "added_at": _iso(r["added_at"])} for r in rows]
    return {"segment_id": segment_id, "members": members, "count": len(members)}


@router.post("/v1/segment/{segment_id}/members")
def add_members(segment_id: str, body: AddMembers,
                org: str = Depends(get_current_org)) -> dict:
    with _store().engine.begin() as conn:
        if conn.execute(text("select 1 from graph_segments where id=:id and org_id=:o"),
                        {"id": segment_id, "o": org}).first() is None:
            raise HTTPException(404, "segment not found")
        valid = _known_nodes(conn, org, body.contact_ids)
        added = 0
        for node_id in valid:
            added += int(bool(conn.execute(text(
                "insert into segment_members (org_id,segment_id,node_id,source,added_by) "
                "values (:o,:s,:n,'manual','user') on conflict do nothing returning node_id"),
                {"o": org, "s": segment_id, "n": node_id}).first()))
    return {"added": added, "segment_id": segment_id}


@router.delete("/v1/segment/{segment_id}/members/{contact_id}")
def remove_member(segment_id: str, contact_id: str,
                  org: str = Depends(get_current_org)) -> dict:
    with _store().engine.begin() as conn:
        if conn.execute(text("select 1 from graph_segments where id=:id and org_id=:o"),
                        {"id": segment_id, "o": org}).first() is None:
            raise HTTPException(404, "segment not found")
        conn.execute(text("delete from segment_members where segment_id=:s and node_id=:n"),
                     {"s": segment_id, "n": contact_id})
    return {"removed": True, "segment_id": segment_id, "contact_id": contact_id}


@router.post("/v1/segment/{segment_id}/sync")
def sync_segment(segment_id: str, org: str = Depends(get_current_org)) -> dict:
    now = datetime.now(timezone.utc)
    with _store().engine.begin() as conn:
        updated = conn.execute(text(
            "update graph_segments set last_synced_at=:t where id=:id and org_id=:o returning id"),
            {"t": now, "id": segment_id, "o": org}).first()
    if updated is None:
        raise HTTPException(404, "segment not found")
    return {"synced": True, "segment_id": segment_id, "synced_at": now.isoformat()}


@router.put("/v1/contacts/{contact_id}/segment")
def set_contact_segment(contact_id: str, body: ContactSegment,
                        org: str = Depends(get_current_org)) -> dict:
    with _store().engine.begin() as conn:
        if not _known_nodes(conn, org, [contact_id]):
            raise HTTPException(404, "contact not found")
        # override: the contact belongs to exactly the chosen segment (manual), or none.
        conn.execute(text("delete from segment_members where org_id=:o and node_id=:n"),
                     {"o": org, "n": contact_id})
        if body.segment_id:
            if conn.execute(text("select 1 from graph_segments where id=:id and org_id=:o"),
                            {"id": body.segment_id, "o": org}).first() is None:
                raise HTTPException(404, "segment not found")
            conn.execute(text(
                "insert into segment_members (org_id,segment_id,node_id,source,added_by) "
                "values (:o,:s,:n,'manual','user') on conflict do nothing"),
                {"o": org, "s": body.segment_id, "n": contact_id})
    return {"contact_id": contact_id, "segment_id": body.segment_id, "segment_source": "manual"}
