"""Custom-source field mapping — map an arbitrary source's fields onto the canonical capture shape.

Ported from the v1 backend and adapted to the v2 engine (text ids, v2 connections, engine auth).
Pipeline: introspect (infer field types from samples) -> propose (common-name templates first;
deterministic and free) -> confirm (apply human edits, freeze a versioned row) -> active/list.
The four canonical targets are content (required), timestamp (required), owner, tags. An LLM can
refine proposals but is optional — with no key the template guesses still produce a usable mapping.
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

router = APIRouter(prefix="/v1/mapping")
_graph = make_graph_store()

_CANONICAL = [
    ("content", True, ("body", "content", "text", "message", "description", "note", "summary")),
    ("timestamp", True, ("timestamp", "created_at", "created", "date", "time", "occurred_at",
                         "updated_at", "sent_at")),
    ("owner", False, ("owner", "assignee", "user", "author", "from", "sender", "created_by",
                      "email")),
    ("tags", False, ("tags", "labels", "categories", "topics", "keywords")),
]


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def _infer_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, (list, tuple)):
        return "array"
    if isinstance(value, dict):
        return "object"
    s = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            datetime.strptime(s[:19], fmt)
            return "datetime"
        except ValueError:
            continue
    return "string"


class IntrospectRequest(BaseModel):
    source_type: str
    samples: list[dict] = []
    sql_schema_rows: list[dict] | None = None


def _introspect(source_type: str, samples: list[dict],
                sql_schema_rows: list[dict] | None) -> dict:
    names: dict[str, dict] = {}
    for row in samples or []:
        for name, value in row.items():
            entry = names.setdefault(name, {"name": name, "types": set(), "sample_value": None,
                                            "observed_in": 0, "nulls": 0})
            entry["observed_in"] += 1
            t = _infer_type(value)
            if t == "null":
                entry["nulls"] += 1
            else:
                entry["types"].add(t)
                if entry["sample_value"] is None:
                    entry["sample_value"] = value
    for row in sql_schema_rows or []:                     # schema rows carry name + data_type
        name = row.get("column_name") or row.get("name")
        if name and name not in names:
            names[name] = {"name": name, "types": {str(row.get("data_type") or "string")},
                           "sample_value": None, "observed_in": 0, "nulls": 0}
    n = len(samples or [])
    fields = [{
        "name": e["name"],
        "inferred_type": sorted(e["types"])[0] if e["types"] else "string",
        "sample_value": e["sample_value"],
        "nullable": e["nulls"] > 0 or e["observed_in"] < n,
        "observed_in": e["observed_in"],
    } for e in names.values()]
    return {"source_type": source_type, "sample_size": n, "fields": fields}


def _propose_rows(introspection: dict) -> list[dict]:
    available = [f["name"] for f in introspection["fields"]]
    lowered = {f["name"].lower(): f["name"] for f in introspection["fields"]}
    rows = []
    for canonical, required, hints in _CANONICAL:
        match, confidence = None, 0.0
        for hint in hints:
            if hint in lowered:
                match, confidence = lowered[hint], 0.95 if hint == canonical else 0.8
                break
        if match is None:                                  # loose contains-match fallback
            for low, orig in lowered.items():
                if any(h in low for h in hints):
                    match, confidence = orig, 0.6
                    break
        rows.append({
            "canonical_field": canonical,
            "proposed_source_field": match,
            "proposed_transform": "iso8601" if canonical == "timestamp" and match else "none",
            "proposed_confidence": confidence,
            "available_source_fields": available,
            "is_required": required,
        })
    return rows


@router.post("/introspect")
def introspect(body: IntrospectRequest, org: str = Depends(get_current_org)) -> dict:
    return _introspect(body.source_type, body.samples, body.sql_schema_rows)


@router.post("/propose")
def propose(body: IntrospectRequest, org: str = Depends(get_current_org)) -> dict:
    introspection = _introspect(body.source_type, body.samples, body.sql_schema_rows)
    return {"source_type": body.source_type, "introspection": introspection,
            "rows": _propose_rows(introspection)}


class Edit(BaseModel):
    canonical_field: str
    source_field: str | None = None
    transform: str | None = None
    confidence_override: float | None = None


class ConfirmRequest(BaseModel):
    connection_id: str
    source_type: str
    confirmed_by: str
    samples: list[dict] = []
    sql_schema_rows: list[dict] | None = None
    edits: list[Edit] = []


@router.post("/confirm", status_code=201)
def confirm(body: ConfirmRequest, org: str = Depends(get_current_org)) -> dict:
    introspection = _introspect(body.source_type, body.samples, body.sql_schema_rows)
    field_map = {r["canonical_field"]: {"source_field": r["proposed_source_field"],
                                        "transform": r["proposed_transform"],
                                        "confidence": r["proposed_confidence"]}
                 for r in _propose_rows(introspection)}
    for e in body.edits:                                   # human edits win
        field_map[e.canonical_field] = {
            "source_field": e.source_field,
            "transform": e.transform or ("iso8601" if e.canonical_field == "timestamp" else "none"),
            "confidence": e.confidence_override if e.confidence_override is not None else 1.0}
    for canonical, required, _ in _CANONICAL:
        if required and not (field_map.get(canonical) or {}).get("source_field"):
            raise HTTPException(422, {"error": "missing_required_field",
                                      "message": f"{canonical} must be mapped"})
    confidences = [v.get("confidence", 0) for v in field_map.values() if v.get("source_field")]
    source_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

    with _store().engine.begin() as conn:
        prev = conn.execute(text(
            "select coalesce(max(version),0) from source_mappings where org_id=:o "
            "and connection_id=:c and source_type=:st"),
            {"o": org, "c": body.connection_id, "st": body.source_type}).scalar() or 0
        conn.execute(text("update source_mappings set active=false where org_id=:o "
                          "and connection_id=:c and source_type=:st and active"),
                     {"o": org, "c": body.connection_id, "st": body.source_type})
        mid = new_id("srcmap")
        conn.execute(text(
            "insert into source_mappings (id,org_id,connection_id,source_type,mapping_json,"
            "version,source_confidence,confirmed_by) values "
            "(:id,:o,:c,:st,cast(:mj as jsonb),:v,:sc,:by)"),
            {"id": mid, "o": org, "c": body.connection_id, "st": body.source_type,
             "mj": json.dumps(field_map), "v": int(prev) + 1, "sc": source_confidence,
             "by": body.confirmed_by})
    return {"id": mid, "source_type": body.source_type, "field_map": field_map,
            "confirmed_by": body.confirmed_by, "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "version": int(prev) + 1, "source_confidence": source_confidence}


@router.get("/active")
def get_active(connection_id: str, source_type: str,
               org: str = Depends(get_current_org)) -> dict:
    with _store().engine.connect() as conn:
        row = conn.execute(text(
            "select * from source_mappings where org_id=:o and connection_id=:c "
            "and source_type=:st and active"),
            {"o": org, "c": connection_id, "st": source_type}).mappings().first()
    if row is None:
        raise HTTPException(404, "no active mapping")
    return {"id": row["id"], "source_type": row["source_type"], "field_map": row["mapping_json"],
            "version": row["version"], "confirmed_by": row["confirmed_by"],
            "source_confidence": float(row["source_confidence"] or 0)}


@router.get("/list")
def list_mappings(org: str = Depends(get_current_org)) -> dict:
    with _store().engine.connect() as conn:
        rows = conn.execute(text(
            "select id, connection_id, source_type, version, source_confidence, active, "
            "confirmed_at from source_mappings where org_id=:o and active order by confirmed_at desc"),
            {"o": org}).mappings().all()
    mappings = [{"id": r["id"], "connection_id": r["connection_id"],
                 "source_type": r["source_type"], "version": r["version"],
                 "source_confidence": float(r["source_confidence"] or 0),
                 "confirmed_at": r["confirmed_at"].isoformat() if r["confirmed_at"] else None}
                for r in rows]
    return {"mappings": mappings, "count": len(mappings)}


@router.get("/connections")
def list_connections(org: str = Depends(get_current_org)) -> dict:
    with _store().engine.connect() as conn:
        try:
            rows = conn.execute(text(
                "select connection_id, source_type from connections where org_id=:o"),
                {"o": org}).mappings().all()
        except Exception:
            rows = []
    connections = [{"connection_id": r["connection_id"], "source_type": r["source_type"],
                    "label": f"{r['source_type']} · {r['connection_id']}"} for r in rows]
    return {"connections": connections}
