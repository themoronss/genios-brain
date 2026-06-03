from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.api.deps import get_db, verify_api_key
from datetime import datetime, timezone
import csv
import io

router = APIRouter()


@router.get("/api/org/{org_id}/status")
def get_org_status(org_id: str, db: Session = Depends(get_db)):
    """Get organization ingestion status."""

    # Check if Gmail connected (include new sync columns)
    oauth = db.execute(
        text(
            """SELECT last_synced_at, sync_status, sync_total, sync_processed, sync_error 
               FROM oauth_tokens WHERE org_id = :org_id"""
        ),
        {"org_id": org_id},
    ).fetchone()

    # v2 thin-pipe: counts from graph_nodes + facts (v1 contacts/interactions dropped).
    stats = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM graph_nodes
                   WHERE org_id = :org_id AND type = 'entity') AS contacts_count,
                (SELECT COUNT(*) FROM facts
                   WHERE org_id = :org_id)                     AS interactions_count
            """
        ),
        {"org_id": org_id},
    ).fetchone()

    # 'Unstaged' was a v1 relationship-stage concept that doesn't exist in v2.
    # Entities are 'staged' as soon as they're emitted; treat unstaged as 0.
    unstaged = 0

    contacts_count = stats.contacts_count or 0
    interactions_count = stats.interactions_count or 0
    ingestion_complete = contacts_count > 0 and unstaged == 0

    progress = (
        100
        if ingestion_complete
        else (int((contacts_count - unstaged) / max(contacts_count, 1) * 100))
    )

    # Sync progress from DB
    sync_status = "idle"
    sync_total = 0
    sync_processed = 0
    sync_error = None
    if oauth:
        sync_status = oauth.sync_status or "idle"
        sync_total = oauth.sync_total or 0
        sync_processed = oauth.sync_processed or 0
        sync_error = oauth.sync_error

    return {
        "gmail_connected": oauth is not None,
        "last_sync": oauth.last_synced_at if oauth else None,
        "contacts_count": contacts_count,
        "interactions_count": interactions_count,
        "ingestion_complete": ingestion_complete,
        "ingestion_progress": progress,
        "sync_status": sync_status,
        "sync_total": sync_total,
        "sync_processed": sync_processed,
        "sync_error": sync_error,
    }


@router.get("/api/org/{org_id}/graph")
def get_graph_data(
    org_id: str,
    entity_type: str = None,
    db: Session = Depends(get_db),
):
    """Per g-i-1 plan: graph view rendered from v2 graph_nodes + graph_edges.

    No more v1 contacts/interactions joins. Wired through core.graph.views.
    """
    from core.foundations.db import get_session as _v2s
    from core.graph.views import graph_d3 as _v2_graph_d3

    with _v2s() as s:
        return _v2_graph_d3(s, org_id=org_id, entity_type=entity_type)


@router.get("/api/org/{org_id}/contacts")
def get_contacts(
    org_id: str,
    limit: int = 100,
    offset: int = 0,
    entity_type: str = None,  # accepted for back-compat; ignored in v2 view
    db: Session = Depends(get_db),
):
    """Per g-i-1: contacts list is now the v2 graph view (entity-type nodes).

    No more reads from v1 `contacts` table. Wired through core.graph.views.
    """
    from core.foundations.db import get_session as _v2s
    from core.graph.views import list_contacts as _v2_list_contacts

    with _v2s() as s:
        return _v2_list_contacts(s, org_id=org_id, limit=limit, offset=offset)


# brain/activity moved to app/api/routes/brain_activity.py (v2-native — derives
# from decisions + facts + cursors instead of v1 interactions/contacts/oauth_tokens).


@router.get("/v1/graph/stats")
def get_graph_stats(db: Session = Depends(get_db), org_id: str = Depends(verify_api_key)):
    """Graph health check — confirms graph is ready for context calls."""
    stats = db.execute(
        text("""
            SELECT
                COUNT(DISTINCT c.id) as total_nodes,
                COUNT(DISTINCT i.id) as total_edges,
                o.graph_quality_score,
                o.brain_status,
                MAX(ot.last_synced_at) as last_sync
            FROM orgs o
            LEFT JOIN contacts c ON c.org_id = o.id
                AND c.relationship_stage IS NOT NULL AND c.relationship_stage != 'unknown'
            LEFT JOIN interactions i ON i.org_id = o.id
            LEFT JOIN oauth_tokens ot ON ot.org_id = o.id
            WHERE o.id = :org_id
            GROUP BY o.id, o.graph_quality_score, o.brain_status
        """),
        {"org_id": org_id}
    ).fetchone()

    if not stats:
        return {"ready": False, "total_nodes": 0, "total_edges": 0, "quality_score": 0, "brain_status": "building", "last_sync": None}

    total_nodes = stats[0] or 0
    return {
        "ready": total_nodes > 0,
        "total_nodes": total_nodes,
        "total_edges": stats[1] or 0,
        "quality_score": float(stats[2] or 0),
        "brain_status": stats[3] or "building",
        "last_sync": stats[4].isoformat() if stats[4] else None,
    }


PLAN_LIMITS = {
    "hustler": 3000,
    "startup": 10000,
    "enterprise": 999999,
}

@router.get("/dashboard/metrics")
def get_dashboard_metrics(org_id: str, db: Session = Depends(get_db)):
    """Per g-i-1 plan: composite metrics from v2 graph_nodes + facts + edges.

    Same SHAPE as v1 endpoint so dashboard renders unchanged.
    """
    from core.foundations.db import get_session as _v2s
    from core.graph.views import dashboard_metrics as _v2_metrics

    with _v2s() as s:
        return _v2_metrics(s, org_id=org_id)


@router.get("/api/org/{org_id}/graph/export")
def export_graph_csv(org_id: str, db: Session = Depends(get_db)):
    """Export entities + edges as CSV (v2 thin-pipe schema)."""
    rows = db.execute(
        text("""
            SELECT n.id, n.canonical_name, n.type,
                   COALESCE(n.attributes->>'company', '')        AS company,
                   COALESCE(n.attributes->>'relationship_stage', 'active') AS stage,
                   n.last_seen,
                   (SELECT COUNT(*) FROM graph_edges e
                      WHERE e.org_id = n.org_id AND (e.from_node = n.id OR e.to_node = n.id)) AS edge_count,
                   (SELECT COUNT(*) FROM facts f
                      WHERE f.org_id = n.org_id AND f.subject = n.canonical_name) AS fact_count
            FROM graph_nodes n
            WHERE n.org_id = :org_id AND n.type = 'entity'
            ORDER BY edge_count DESC
        """),
        {"org_id": org_id},
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "type", "company", "relationship_stage",
        "last_seen", "edge_count", "fact_count",
    ])
    for r in rows:
        writer.writerow([
            str(r[0]), r[1] or "", r[2] or "", r[3] or "", r[4] or "",
            r[5].isoformat() if r[5] else "",
            int(r[6] or 0), int(r[7] or 0),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=genios_graph_{org_id[:8]}.csv"},
    )


@router.get("/api/org/{org_id}/network-health")
def get_network_health(org_id: str, db: Session = Depends(get_db)):
    """Per g-i-1 plan: high-level health from v2 graph state."""
    from core.foundations.db import get_session as _v2s
    from core.graph.views import network_health as _v2_nh

    with _v2s() as s:
        return _v2_nh(s, org_id=org_id)


@router.get("/api/org/{org_id}/edge/{contact_id}")
def get_edge_detail(org_id: str, contact_id: str, db: Session = Depends(get_db)):
    """Entity detail panel — facts + edges from v2 graph schema.

    v1 returned thread-level email metadata (sentiment trajectory, reply-time
    bins, last-3-threads). v2 doesn't store per-message data (thin pipe by
    design), so we return the structurally-equivalent shape sourced from
    facts + edges instead.
    """
    node = db.execute(
        text("""
            SELECT id, canonical_name, type, attributes, last_seen
            FROM graph_nodes WHERE id = :id AND org_id = :org_id
        """),
        {"id": contact_id, "org_id": org_id},
    ).fetchone()
    if not node:
        raise HTTPException(status_code=404, detail="Contact not found")

    attrs = node[3] if isinstance(node[3], dict) else {}
    name = node[1]
    company = attrs.get("company")

    facts = db.execute(
        text("""
            SELECT predicate, object, confidence, created_at
            FROM facts WHERE org_id = :org_id AND subject = :name
            ORDER BY created_at DESC LIMIT 50
        """),
        {"org_id": org_id, "name": name},
    ).fetchall()

    edges = db.execute(
        text("""
            SELECT type, weight, asserted_at,
                   CASE WHEN from_node = :nid THEN to_node ELSE from_node END AS other_id
            FROM graph_edges
            WHERE org_id = :org_id AND (from_node = :nid OR to_node = :nid)
            ORDER BY asserted_at DESC LIMIT 50
        """),
        {"org_id": org_id, "nid": contact_id},
    ).fetchall()

    topic_counts: dict[str, int] = {}
    last_threads = []
    for predicate, obj, conf, ts in facts:
        if predicate == "interested_in":
            topic_counts[obj] = topic_counts.get(obj, 0) + 1
        if len(last_threads) < 3:
            last_threads.append({
                "subject": predicate,
                "summary": str(obj)[:200],
                "sentiment": float(conf or 0),
                "direction": "fact",
                "date": ts.isoformat() if ts else None,
            })
    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "contact_id": contact_id,
        "contact_name": name,
        "company": company,
        "total_interactions": len(edges),
        "sentiment_trajectory": [],
        "topic_clusters": [{"topic": t[0], "count": t[1]} for t in top_topics],
        "response_time": {"avg_hours": None, "fast": 0, "moderate": 0, "slow": 0},
        "last_3_threads": last_threads,
        "company_contacts": [],
    }


@router.get("/api/org/{org_id}/company/{domain}")
def get_company_aggregate(org_id: str, domain: str, db: Session = Depends(get_db)):
    """Company aggregate — entities whose company attribute matches the domain."""
    rows = db.execute(
        text("""
            SELECT n.id, n.canonical_name, n.attributes, n.last_seen,
                   (SELECT COUNT(*) FROM graph_edges e
                      WHERE e.org_id = n.org_id AND (e.from_node = n.id OR e.to_node = n.id)) AS edge_count
            FROM graph_nodes n
            WHERE n.org_id = :org_id
              AND n.type = 'entity'
              AND (LOWER(COALESCE(n.attributes->>'company', '')) LIKE :pat
                OR LOWER(COALESCE(n.attributes->>'company_domain', '')) = :dom)
            ORDER BY edge_count DESC
        """),
        {"org_id": org_id, "pat": f"%{domain.lower()}%", "dom": domain.lower()},
    ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No contacts found at domain {domain}")

    return {
        "domain": domain,
        "company_name": rows[0][2].get("company") if isinstance(rows[0][2], dict) else domain,
        "total_contacts": len(rows),
        "aggregate_sentiment": 0.0,
        "contacts": [
            {
                "id": str(r[0]),
                "name": r[1],
                "email": (r[2] or {}).get("email") if isinstance(r[2], dict) else None,
                "entity_type": "person",
                "relationship_stage": (r[2] or {}).get("relationship_stage") if isinstance(r[2], dict) else "active",
                "sentiment_avg": 0.0,
                "interaction_count": int(r[4] or 0),
                "last_interaction_at": r[3].isoformat() if r[3] else None,
                "is_bidirectional": False,
            } for r in rows
        ],
        "open_commitments": [],
    }


@router.get("/api/org/{org_id}/graph/filter/topic")
def filter_graph_by_topic(org_id: str, topic: str, db: Session = Depends(get_db)):
    """Entities whose facts include this topic (object match on 'interested_in')."""
    rows = db.execute(
        text("""
            SELECT DISTINCT n.id, n.canonical_name, n.attributes, n.last_seen
            FROM graph_nodes n
            JOIN facts f ON f.org_id = n.org_id AND f.subject = n.canonical_name
            WHERE n.org_id = :org_id
              AND n.type = 'entity'
              AND (LOWER(f.object) LIKE :topic OR f.predicate = :topic_raw)
        """),
        {"org_id": org_id, "topic": f"%{topic.lower()}%", "topic_raw": topic},
    ).fetchall()

    contacts = [
        (r[0], r[1], (r[2] or {}).get("email"), (r[2] or {}).get("company"),
         (r[2] or {}).get("relationship_stage", "active"), "person", 0, 0.0, r[3])
        for r in rows
    ]

    return {
        "topic": topic,
        "total_contacts": len(contacts),
        "contacts": [
            {
                "id": str(c[0]), "name": c[1], "email": c[2], "company": c[3],
                "relationship_stage": c[4], "entity_type": c[5] or "other",
                "interaction_count": c[6], "sentiment_avg": float(c[7] or 0),
                "last_interaction_at": c[8].isoformat() if c[8] else None,
            } for c in contacts
        ],
    }


