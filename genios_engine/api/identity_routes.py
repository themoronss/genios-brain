"""L2 · Identity review — where a human rules on "are these two the same thing?".

The resolver never merges. It records that two nodes claim the same key and stops. That
is only a safe design if someone can actually see the queue and decide — otherwise
proposals accumulate silently and the duplicates stay duplicated.

Merging is destructive (it rewrites who every fact and edge is about), so it is a POST
by a human, it is transactional, and it is undoable.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.context.merge import (apply_merge, open_proposals, reject_merge,
                                          reverse_merge)
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_log = get_logger("genios.identity")
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


class MergeIn(BaseModel):
    survivor_node_id: str          # keeps its id, key and history
    merged_node_id: str


@router.get("/api/org/{org_id}/identity/proposals")
def list_proposals(org_id: str, limit: int = 50, org: str = Depends(_org)) -> dict:
    """Open duplicate candidates, newest first, with both sides' names and keys."""
    with _store().engine.connect() as conn:
        proposals = open_proposals(conn, org_id=org, limit=limit)
    return {"proposals": proposals, "count": len(proposals)}


@router.post("/api/org/{org_id}/identity/proposals/{proposal_id}/merge")
def merge_proposal(org_id: str, proposal_id: str, body: MergeIn,
                   org: str = Depends(_org)) -> dict:
    """Confirm two nodes are one entity, and fold one into the other.

    The survivor is chosen by the caller rather than guessed: which node keeps its id
    decides what every existing delivery card and reasoning trace still resolves to.
    """
    with _store().engine.begin() as conn:
        proposal = conn.execute(text(
            "select left_node_id, right_node_id, status from merge_proposals "
            "where org_id=:o and id=:id"), {"o": org, "id": proposal_id}).first()
        if proposal is None:
            raise HTTPException(404, "no such proposal")
        if proposal.status != "open":
            raise HTTPException(409, {"error": "already_decided", "status": proposal.status})
        pair = {proposal.left_node_id, proposal.right_node_id}
        if {body.survivor_node_id, body.merged_node_id} != pair:
            raise HTTPException(422, {
                "error": "nodes_do_not_match_proposal",
                "message": "survivor and merged must be the two nodes this proposal names",
                "proposal_nodes": sorted(pair)})
        try:
            result = apply_merge(conn, org_id=org, survivor_node_id=body.survivor_node_id,
                                 merged_node_id=body.merged_node_id,
                                 reason=f"human_confirmed:{proposal_id}",
                                 proposal_id=proposal_id)
        except ValueError as e:
            raise HTTPException(422, {"error": "merge_failed", "message": str(e)}) from e

    from genios_engine.platform.audit import record
    record(org, "entities_merged", actor_type="user", target_type="node",
           target_id=body.survivor_node_id,
           metadata={"merged": body.merged_node_id, "proposal": proposal_id,
                     "repairs": result["repairs"]})
    return result


@router.post("/api/org/{org_id}/identity/proposals/{proposal_id}/reject")
def reject_proposal(org_id: str, proposal_id: str, org: str = Depends(_org)) -> dict:
    """Two different things that happen to share a name. Recorded permanently, so the
    next email about either one does not re-raise the same question."""
    with _store().engine.begin() as conn:
        if not reject_merge(conn, org_id=org, proposal_id=proposal_id):
            raise HTTPException(404, "no open proposal with that id")
    return {"proposal_id": proposal_id, "status": "rejected"}


@router.post("/api/org/{org_id}/identity/merges/{merge_id}/reverse")
def undo_merge(org_id: str, merge_id: str, org: str = Depends(_org)) -> dict:
    """Undo a merge that turned out to be wrong.

    The graph is restored from the snapshot taken at merge time — the merged entity
    reopens and its facts, observations, aliases and edges go back to it. Correlations
    and situations are DROPPED rather than restored: they are derived, and recomputing
    them from the graph we just put back is both cheaper and more correct than
    reconstructing rows the merge deleted. They return on the next L2 refresh.
    """
    with _store().engine.begin() as conn:
        try:
            result = reverse_merge(conn, org_id=org, merge_id=merge_id)
        except ValueError as e:
            raise HTTPException(404, {"error": "cannot_reverse", "message": str(e)}) from e

    from genios_engine.platform.audit import record
    record(org, "entity_merge_reversed", actor_type="user", target_type="node",
           target_id=result["reopened_node"], metadata={"merge_id": merge_id})
    return result


@router.get("/api/org/{org_id}/identity/merges")
def list_merges(org_id: str, limit: int = 50, org: str = Depends(_org)) -> dict:
    """Merge history — what was folded into what, and whether it has been reversed."""
    with _store().engine.connect() as conn:
        rows = conn.execute(text(
            "select id, survivor_node_id, merged_node_id, reason, reversed, created_at "
            "from merge_history where org_id=:o order by created_at desc limit :lim"),
            {"o": org, "lim": limit}).mappings().all()
    return {"merges": [dict(r) for r in rows]}
