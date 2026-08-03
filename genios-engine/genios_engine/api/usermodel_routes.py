"""Governance — Personas / user model (dashboard → Settings → Personas). CRUD over a per-user
persona (voice / decision_policy / process_habits / priorities / relationships / red_lines) plus the
learned-change proposal queue. Ported from genios-brain (core/usermodel) to the engine's raw-SQL +
`get_current_org` conventions. `user_id` is the user's email; the tenant (org_unit) is the JWT org.
The LLM distill pipeline that generates proposals is out of scope — proposals start empty and the
decide route applies whatever a future distiller enqueues.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform.auth import get_current_org
from genios_engine.platform.ids import new_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

# The 6 persona fields → their jsonb columns. field_meta is keyed by exactly these names (the UI
# iterates them), each carrying {source, confidence, last_updated}.
FIELDS = ("voice", "decision_policy", "process_habits", "priorities", "relationships", "red_lines")
_COL = {f: f"{f}_jsonb" for f in FIELDS}
_LIST_FIELDS = {"red_lines"}                                    # stored as a json array, not an object
_SELECT = ("id, org_id, user_id, voice_jsonb, decision_policy_jsonb, process_habits_jsonb, "
           "priorities_jsonb, relationships_jsonb, red_lines_jsonb, field_meta_jsonb, "
           "created_at, updated_at")


def _j(v, default=None):
    if v is None:
        return default if default is not None else {}
    return v if isinstance(v, (dict, list)) else json.loads(v)


def _persona(r) -> dict:
    return {
        "user_id": r.user_id, "org_unit": r.org_id,
        "voice": _j(r.voice_jsonb), "decision_policy": _j(r.decision_policy_jsonb),
        "process_habits": _j(r.process_habits_jsonb), "priorities": _j(r.priorities_jsonb),
        "relationships": _j(r.relationships_jsonb), "red_lines": _j(r.red_lines_jsonb, []),
        "field_meta": _j(r.field_meta_jsonb),
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _fetch(c, org: str, user_id: str):
    return c.execute(text(f"select {_SELECT} from user_models where org_id=:o and user_id=:u"),
                     {"o": org, "u": user_id}).first()


@router.get("/v1/usermodel/{user_id}")
def get_profile(user_id: str, org_id: str = Depends(get_current_org)) -> dict:
    with _graph.engine.connect() as c:
        r = _fetch(c, org_id, user_id)
    if r is None:
        raise HTTPException(404, {"error": "not_found", "message": "no profile for this user yet"})
    return _persona(r)


class SeedRequest(BaseModel):
    user_id: str
    voice: dict | None = None
    decision_policy: dict | None = None
    process_habits: dict | None = None
    priorities: dict | None = None
    relationships: dict | None = None
    red_lines: list | None = None


@router.post("/v1/usermodel/seed", status_code=201)
def seed(body: SeedRequest, org_id: str = Depends(get_current_org)) -> dict:
    now = datetime.now(timezone.utc)
    provided = {"voice": body.voice, "decision_policy": body.decision_policy,
                "process_habits": body.process_habits, "priorities": body.priorities,
                "relationships": body.relationships, "red_lines": body.red_lines}
    values = {f: (provided[f] if provided[f] is not None else ([] if f in _LIST_FIELDS else {}))
              for f in FIELDS}
    field_meta = {f: {"source": "seeded", "confidence": 0.5, "last_updated": now.isoformat()}
                  for f in FIELDS}
    with _graph.engine.begin() as c:
        c.execute(text(
            "insert into user_models (id, org_id, user_id, voice_jsonb, decision_policy_jsonb, "
            "process_habits_jsonb, priorities_jsonb, relationships_jsonb, red_lines_jsonb, "
            "field_meta_jsonb) values (:i,:o,:u,cast(:v as jsonb),cast(:dp as jsonb),"
            "cast(:ph as jsonb),cast(:pr as jsonb),cast(:rel as jsonb),cast(:rl as jsonb),"
            "cast(:fm as jsonb)) on conflict (org_id, user_id) do update set "
            "voice_jsonb=excluded.voice_jsonb, decision_policy_jsonb=excluded.decision_policy_jsonb, "
            "process_habits_jsonb=excluded.process_habits_jsonb, priorities_jsonb=excluded.priorities_jsonb, "
            "relationships_jsonb=excluded.relationships_jsonb, red_lines_jsonb=excluded.red_lines_jsonb, "
            "field_meta_jsonb=excluded.field_meta_jsonb, updated_at=now()"),
            {"i": new_id("usm"), "o": org_id, "u": body.user_id,
             "v": json.dumps(values["voice"]), "dp": json.dumps(values["decision_policy"]),
             "ph": json.dumps(values["process_habits"]), "pr": json.dumps(values["priorities"]),
             "rel": json.dumps(values["relationships"]), "rl": json.dumps(values["red_lines"]),
             "fm": json.dumps(field_meta)})
        r = _fetch(c, org_id, body.user_id)
    return _persona(r)


class UpdateFieldRequest(BaseModel):
    field: str
    new_value: object = None


@router.patch("/v1/usermodel/{user_id}/field")
def patch_field(user_id: str, body: UpdateFieldRequest, org_id: str = Depends(get_current_org)) -> dict:
    if body.field not in FIELDS:
        raise HTTPException(422, {"error": "invalid_field", "message": f"field must be one of {list(FIELDS)}"})
    now = datetime.now(timezone.utc)
    col = _COL[body.field]
    with _graph.engine.begin() as c:
        r = _fetch(c, org_id, user_id)
        if r is None:
            raise HTTPException(404, {"error": "not_found", "message": "no profile for this user yet"})
        meta = _j(r.field_meta_jsonb)
        meta[body.field] = {"source": "seeded", "confidence": 1.0, "last_updated": now.isoformat()}
        c.execute(text(
            f"update user_models set {col}=cast(:val as jsonb), field_meta_jsonb=cast(:fm as jsonb), "
            "updated_at=now() where org_id=:o and user_id=:u"),
            {"val": json.dumps(body.new_value), "fm": json.dumps(meta), "o": org_id, "u": user_id})
        r = _fetch(c, org_id, user_id)
    return _persona(r)


@router.delete("/v1/usermodel/{user_id}", status_code=204)
def delete_profile(user_id: str, org_id: str = Depends(get_current_org)) -> Response:
    with _graph.engine.begin() as c:
        c.execute(text("delete from user_model_proposals where org_id=:o and user_id=:u"),
                  {"o": org_id, "u": user_id})
        c.execute(text("delete from user_models where org_id=:o and user_id=:u"),
                  {"o": org_id, "u": user_id})
    return Response(status_code=204)


@router.get("/v1/usermodel/{user_id}/proposals")
def list_proposals(user_id: str, org_id: str = Depends(get_current_org)) -> list:
    with _graph.engine.connect() as c:
        rows = c.execute(text(
            "select id, field, current_value_jsonb, proposed_value_jsonb, signal_count, rationale, "
            "created_at from user_model_proposals where org_id=:o and user_id=:u and status='pending' "
            "order by created_at desc"), {"o": org_id, "u": user_id}).fetchall()
    return [{"id": r.id, "field": r.field, "current_value": _j(r.current_value_jsonb),
             "proposed_value": _j(r.proposed_value_jsonb), "signal_count": int(r.signal_count or 0),
             "rationale": r.rationale, "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows]


class ProposalDecision(BaseModel):
    decision: str          # "approve" | "reject"
    actor: str | None = None


@router.post("/v1/usermodel/proposals/{proposal_id}/decide")
def decide_proposal(proposal_id: str, body: ProposalDecision,
                    org_id: str = Depends(get_current_org)) -> dict:
    if body.decision not in ("approve", "reject"):
        raise HTTPException(422, {"error": "invalid_decision", "message": "decision must be approve|reject"})
    now = datetime.now(timezone.utc)
    with _graph.engine.begin() as c:
        p = c.execute(text("select user_id, field, proposed_value_jsonb, status from "
                           "user_model_proposals where org_id=:o and id=:i"),
                      {"o": org_id, "i": proposal_id}).first()
        if p is None:
            raise HTTPException(404, {"error": "not_found", "message": "proposal not found"})
        if p.status != "pending":
            raise HTTPException(409, {"error": "already_decided", "message": f"already {p.status}"})
        status = "approved" if body.decision == "approve" else "rejected"
        if status == "approved" and p.field in _COL:
            meta_row = _fetch(c, org_id, p.user_id)
            if meta_row is not None:
                meta = _j(meta_row.field_meta_jsonb)
                meta[p.field] = {"source": "learned", "confidence": 0.8, "last_updated": now.isoformat()}
                c.execute(text(
                    f"update user_models set {_COL[p.field]}=cast(:val as jsonb), "
                    "field_meta_jsonb=cast(:fm as jsonb), updated_at=now() where org_id=:o and user_id=:u"),
                    {"val": json.dumps(_j(p.proposed_value_jsonb)), "fm": json.dumps(meta),
                     "o": org_id, "u": p.user_id})
        c.execute(text("update user_model_proposals set status=:s, decided_by=:by, decided_at=:t "
                       "where org_id=:o and id=:i"),
                  {"s": status, "by": body.actor, "t": now, "o": org_id, "i": proposal_id})
    return {"id": proposal_id, "status": status, "decided_by": body.actor, "decided_at": now.isoformat()}
