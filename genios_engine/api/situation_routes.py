"""L2 · Situations — the read surface reasoning uses instead of the graph.

The Reasoning Engine should not wake up and ask for nodes and edges. It should ask for
the active situations relevant to what it is doing. That shift — from traversing a graph
to reading bounded, assembled situations — is what keeps reasoning about thinking rather
than about rebuilding context on every question.

Confidence comes back as a VECTOR, not one number, because a caller needs to know WHY it
is low. "82% overall, 12% identity" tells you to go resolve a duplicate. "82%" tells you
nothing you can act on.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.context.situations import active_situations, resolve_situation
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


class ResolveIn(BaseModel):
    note: str | None = None


def _shape(row: dict) -> dict:
    """One situation, with confidence kept as its dimensions."""
    return {
        "situation_id": row["situation_id"],
        "type": row["situation_type"],
        "domain": row["domain"],
        "status": row["status"],
        "about": {"node_id": row["anchor_node_id"], "name": row["anchor_name"],
                  "type": row["anchor_type"]},
        "evidence_events": row["event_count"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "confidence": {
            "overall": row["confidence_overall"],
            "evidence": row["confidence_evidence"],
            "freshness": row["confidence_freshness"],
            "consistency": row["confidence_consistency"],
            "identity": row["confidence_identity"],
        },
        # Completeness, reported apart from confidence on purpose: not knowing a close
        # date does not make the stage we DO know less true.
        "coverage": row["coverage"],
        "missing": row["missing"] or [],
    }


@router.get("/api/org/{org_id}/situations")
def list_situations(org_id: str, domain: str | None = None, limit: int = 100,
                    org: str = Depends(_org)) -> dict:
    """Active situations, most-confident first.

    Ordering is by how SURE we are, which is not the same as how much something matters.
    Which situation deserves action is a decision, and this layer does not make decisions.
    """
    with _store().engine.connect() as conn:
        rows = active_situations(conn, org_id=org, domain=domain, limit=limit)
    return {"situations": [_shape(r) for r in rows], "count": len(rows),
            "ordering": "confidence_desc",
            "note": "ordered by confidence, not priority — ranking is a decision made downstream"}


@router.get("/api/org/{org_id}/situations/{situation_id}")
def get_situation(org_id: str, situation_id: str, org: str = Depends(_org)) -> dict:
    """One situation with its evidence — the events that built it, newest first."""
    with _store().engine.connect() as conn:
        row = conn.execute(text(
            "select s.*, n.display_name as anchor_name, n.node_type as anchor_type, "
            "       c.event_count "
            "from context_situations s "
            "join context_correlations c on c.org_id = s.org_id "
            "     and c.correlation_id = s.correlation_id "
            "left join graph_nodes n on n.org_id = s.org_id "
            "     and n.node_id = s.anchor_node_id and n.valid_to is null "
            "where s.org_id = :o and s.situation_id = :sid"),
            {"o": org, "sid": situation_id}).mappings().first()
        if row is None:
            raise HTTPException(404, "no such situation")
        evidence = conn.execute(text(
            "select se.event_id, se.source, se.object_type, se.occurred_at, m.joined_via "
            "from context_correlation_members m "
            "join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
            "where m.org_id = :o and m.correlation_id = :cid "
            "order by se.occurred_at desc nulls last limit 100"),
            {"o": org, "cid": row["correlation_id"]}).mappings().all()

    shaped = _shape(dict(row))
    # `inputs` is the arithmetic behind the score. A confidence number nobody can account
    # for is a number nobody should act on.
    shaped["confidence"]["inputs"] = row["inputs"]
    shaped["evidence"] = [dict(e) for e in evidence]
    return shaped


@router.post("/api/org/{org_id}/situations/{situation_id}/resolve")
def mark_resolved(org_id: str, situation_id: str, body: ResolveIn,
                  org: str = Depends(_org)) -> dict:
    """Mark a situation handled.

    It reopens by itself when new evidence arrives. Marking something handled is a
    statement about the past, not a promise about the future — when the customer writes
    again it is open again, because a situation that stays closed through new activity
    actively hides work.
    """
    with _store().engine.begin() as conn:
        if not resolve_situation(conn, org_id=org, situation_id=situation_id,
                                 note=body.note):
            raise HTTPException(404, "no such open situation")
    return {"situation_id": situation_id, "status": "resolved",
            "reopens_on_new_evidence": True}


@router.post("/api/org/{org_id}/situations/backfill")
def run_backfill(org_id: str, limit: int | None = None, org: str = Depends(_org)) -> dict:
    """Apply Layer 2 to history that was already in the graph before it existed.

    Aliases are claimed inside node creation and correlation runs inside the L2 drain, so
    both only fire when an event ARRIVES. Without this, a tenant with months of history
    would see none of it: no duplicate detection on existing entities, no situations for
    anything that happened before today. The features would look broken while being
    correctly implemented — which is worse than missing, because nobody knows where to
    look.

    Safe to re-run: aliases are insert-or-ignore, membership is idempotent, and
    situations are rebuilt from scratch each time. `limit` caps the events processed so a
    large tenant can be backfilled in passes.
    """
    from genios_engine.context.backfill import backfill_layer2
    return backfill_layer2(_store(), org, limit=limit)


@router.get("/api/org/{org_id}/graph/health")
def graph_health(org_id: str, org: str = Depends(_org)) -> dict:
    """Is our picture of the enterprise still trustworthy?

    Returned as a vector with `overall` as the MINIMUM of the measured dimensions — a
    graph with flawless evidence and 40% broken edges is not "70% healthy", it is a graph
    you cannot traverse. Dimensions with nothing behind them are marked unmeasured rather
    than scored zero, so a new tenant is never reported as broken.

    Read-only. Nothing here repairs anything: an unattended auto-fix turns a small
    inconsistency into silent data loss.
    """
    from genios_engine.context.health import compute_health
    health = compute_health(_store(), org, persist=False)
    return {"overall": health.overall, "dimensions": health.dimensions,
            "measured": health.measured, "metrics": health.metrics,
            "issues": health.issues}


@router.get("/api/org/{org_id}/graph/health/history")
def graph_health_history(org_id: str, limit: int = 30, org: str = Depends(_org)) -> dict:
    """Health over time. The trend is the signal — one number says little, the same
    number falling over three weeks says something broke."""
    with _store().engine.connect() as conn:
        rows = conn.execute(text(
            "select computed_at, overall, dimensions, issues from graph_health "
            "where org_id = :o order by computed_at desc limit :lim"),
            {"o": org, "lim": limit}).mappings().all()
    return {"history": [dict(r) for r in rows]}


@router.get("/api/org/{org_id}/projections")
def list_projections(org_id: str, org: str = Depends(_org)) -> dict:
    """The lenses this tenant actually has, discovered from its data.

    Nothing here declares a domain. Add one upstream and its lens appears immediately —
    `registered: false` simply means it is present in the data but nobody has described
    it yet, which is a normal state while a domain is being introduced, not an error.
    """
    from genios_engine.context.projections import available_projections
    with _store().engine.connect() as conn:
        projections = available_projections(conn, org_id=org)
    return {"projections": projections, "count": len(projections)}


@router.get("/api/org/{org_id}/projections/{domain}")
def get_projection(org_id: str, domain: str, active_only: bool = True,
                   include_boundary: bool = True, org: str = Depends(_org)) -> dict:
    """One lens over the graph.

    Boundary edges — relationships that leave the lens — are returned SEPARATELY rather
    than dropped. A view that silently omits them claims the entity has no other
    relationships, which is a lie the view has no way of admitting to because it looks
    complete.
    """
    from genios_engine.context.projections import boundary_edges, projection_members
    with _store().engine.connect() as conn:
        projection = projection_members(conn, org_id=org, domain=domain,
                                        active_only=active_only)
        boundary = (boundary_edges(conn, org_id=org, node_ids=projection.node_ids)
                    if include_boundary else [])
    return {"domain": projection.domain, "display_name": projection.display_name,
            "registered": projection.registered,
            "situations": projection.situation_count,
            "node_ids": list(projection.node_ids),
            "node_count": len(projection.node_ids),
            # Reported so a capped lens is never mistaken for a complete one.
            "total_members": projection.total_members,
            "truncated": projection.truncated,
            "boundary_edges": boundary,
            "note": "a lens narrows retrieval, never evaluation — reasoning still sees "
                    "every entity"}


@router.get("/api/org/{org_id}/projections/_/unclassified")
def unclassified(org_id: str, limit: int = 200, org: str = Depends(_org)) -> dict:
    """Entities that fall through every lens.

    A first-class query, not a diagnostic afterthought: without it a projection system is
    a way to lose things quietly. A non-empty result is normal — and it is the first place
    to look when a new domain has just been introduced.
    """
    from genios_engine.context.projections import unprojected_nodes
    with _store().engine.connect() as conn:
        result = unprojected_nodes(conn, org_id=org, limit=limit)
    return {**result, "count": len(result["nodes"]),
            "note": "not an error — these are simply not reached by any situation yet"}
