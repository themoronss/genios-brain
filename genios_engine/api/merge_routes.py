"""Merge queue — a thin compatibility surface over the v2 identity system.

The dashboard's older /v1/merge/{org}/queue* endpoints map onto the engine's identity
proposals (merge_proposals + context.merge). No separate merge logic or `contacts` table is
reintroduced: this adapter just reshapes identity proposals into the queue shape the dashboard
expects, and routes decisions to apply_merge / reject_merge. Two honest gaps vs the old backend:
`match_score` is synthesized (the resolver treats similarity as a finder, not an authority), and
`defer` has no backing state so it leaves the proposal open.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from genios_engine.context.merge import apply_merge, open_proposals, reject_merge
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def _degree(conn, org_id: str, node_id: str) -> int:
    return int(conn.execute(text(
        "select count(*) from graph_edges where org_id=:o and valid_to is null "
        "and (from_node_id=:n or to_node_id=:n)"), {"o": org_id, "n": node_id}).scalar() or 0)


def _score(evidence) -> float:
    """The queue UI shows a score; identity proposals don't rank by similarity, so synthesize
    a stable one from the evidence when present, else a neutral default."""
    if isinstance(evidence, dict):
        for key in ("score", "match_score", "confidence"):
            val = evidence.get(key)
            if isinstance(val, (int, float)):
                return round(float(val) if val <= 1 else float(val) / 100.0, 2)
    return 0.85


def _card(node_id, name, key) -> dict:
    return {"id": node_id, "name": name or node_id, "email": key, "company": None}


@router.get("/v1/merge/{org_id}/queue")
def merge_queue(org_id: str, status: str = "pending", limit: int = 20,
                org: str = Depends(_org)) -> dict:
    with _store().engine.connect() as conn:
        proposals = open_proposals(conn, org_id=org, limit=limit)
    queue = [{
        "id": p["id"],
        "match_score": _score(p.get("evidence")),
        "match_reason": p.get("reason") or "possible_duplicate",
        "status": "open",
        "created_at": p.get("created_at").isoformat() if p.get("created_at") else None,
        "contact_a": _card(p["left_node_id"], p.get("left_name"), p.get("left_key")),
        "contact_b": _card(p["right_node_id"], p.get("right_name"), p.get("right_key")),
    } for p in proposals]
    return {"queue": queue, "candidates": queue, "count": len(queue)}


def _load_proposal(conn, org_id: str, merge_id: str):
    row = conn.execute(text(
        "select left_node_id, right_node_id, reason, status from merge_proposals "
        "where org_id=:o and id=:id"), {"o": org_id, "id": merge_id}).first()
    if row is None:
        raise HTTPException(404, "no such merge candidate")
    return row


@router.post("/v1/merge/{org_id}/queue/{merge_id}/merge")
def execute_merge(org_id: str, merge_id: str, org: str = Depends(_org)) -> dict:
    with _store().engine.begin() as conn:
        prop = _load_proposal(conn, org, merge_id)
        if prop.status != "open":
            raise HTTPException(409, {"error": "already_decided", "status": prop.status})
        # survivor = the more-connected node keeps its id (everything downstream refers to it).
        left_deg = _degree(conn, org, prop.left_node_id)
        right_deg = _degree(conn, org, prop.right_node_id)
        survivor, merged = ((prop.left_node_id, prop.right_node_id)
                            if left_deg >= right_deg
                            else (prop.right_node_id, prop.left_node_id))
        try:
            result = apply_merge(conn, org_id=org, survivor_node_id=survivor,
                                 merged_node_id=merged,
                                 reason=f"human_confirmed:{merge_id}", proposal_id=merge_id)
        except ValueError as e:
            raise HTTPException(422, {"error": "merge_failed", "message": str(e)}) from e
    return {"status": "merged", "kept": survivor, "archived": merged,
            "repairs": result.get("repairs")}


@router.post("/v1/merge/{org_id}/queue/{merge_id}/reject")
def reject(org_id: str, merge_id: str, org: str = Depends(_org)) -> dict:
    with _store().engine.begin() as conn:
        _load_proposal(conn, org, merge_id)
        done = reject_merge(conn, org_id=org, proposal_id=merge_id)
    if not done:
        raise HTTPException(409, {"error": "already_decided"})
    return {"status": "rejected"}


@router.post("/v1/merge/{org_id}/queue/{merge_id}/defer")
def defer(org_id: str, merge_id: str, org: str = Depends(_org)) -> dict:
    # No deferred state in the identity model — the proposal simply stays open for later.
    with _store().engine.connect() as conn:
        _load_proposal(conn, org, merge_id)
    return {"status": "deferred", "note": "left open for later review"}
