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

    # Count contacts and interactions
    stats = db.execute(
        text(
            """
            SELECT 
                COUNT(DISTINCT c.id) as contacts_count,
                COUNT(i.id) as interactions_count
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
        """
        ),
        {"org_id": org_id},
    ).fetchone()

    # Count unstaged contacts (ingestion in progress)
    unstaged = db.execute(
        text(
            """
            SELECT COUNT(*) FROM contacts 
            WHERE org_id = :org_id 
            AND (relationship_stage IS NULL OR relationship_stage = 'unknown')
        """
        ),
        {"org_id": org_id},
    ).fetchone()[0]

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


@router.get("/api/org/{org_id}/brain/activity")
def get_brain_activity(org_id: str, db: Session = Depends(get_db)):
    """Brain activity status for graph header — polled every 30s. Read-only, not toggles."""
    try:
        # Reactive: emails/interactions ingested in last 15 min
        reactive = db.execute(
            text("SELECT COUNT(*) FROM interactions WHERE org_id = :oid AND created_at > NOW() - INTERVAL '15 minutes'"),
            {"oid": org_id},
        ).scalar() or 0

        # Proactive: insights generated today
        proactive = db.execute(
            text("SELECT COUNT(*) FROM insights WHERE org_id = :oid AND generated_at > CURRENT_DATE AND is_dismissed = FALSE"),
            {"oid": org_id},
        ).scalar() or 0

        # Totals
        total_contacts = db.execute(
            text("SELECT COUNT(*) FROM contacts WHERE org_id = :oid AND relationship_stage IS NOT NULL"),
            {"oid": org_id},
        ).scalar() or 0

        total_interactions = db.execute(
            text("SELECT COUNT(*) FROM interactions WHERE org_id = :oid"),
            {"oid": org_id},
        ).scalar() or 0

        # Graph sync status
        last_sync = db.execute(
            text("SELECT MIN(last_synced_at) FROM oauth_tokens WHERE org_id = :oid"),
            {"oid": org_id},
        ).scalar()

        graph_status = "live"
        if not last_sync:
            graph_status = "syncing"

        return {
            "reactive_signal_count": reactive,
            "proactive_insight_count": proactive,
            "predictive_alert_count": 0,
            "graph_status": graph_status,
            "total_contacts": total_contacts,
            "total_interactions": total_interactions,
        }
    except Exception as e:
        return {
            "reactive_signal_count": 0,
            "proactive_insight_count": 0,
            "predictive_alert_count": 0,
            "graph_status": "error",
            "total_contacts": 0,
            "total_interactions": 0,
        }


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
    """Export all contacts and relationship data as CSV."""
    contacts = db.execute(
        text("""
            SELECT
                id, name, email, company, entity_type,
                relationship_stage, last_interaction_at,
                interaction_count, sentiment_avg,
                freshness_score, confidence_score, consistency_score,
                authority_score, context_score, response_rate,
                avg_response_time_hours, is_bidirectional, community_id
            FROM contacts
            WHERE org_id = :org_id
              AND relationship_stage IS NOT NULL AND relationship_stage != 'unknown'
            ORDER BY interaction_count DESC
        """),
        {"org_id": org_id},
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "name", "email", "company", "entity_type",
        "relationship_stage", "last_interaction_at",
        "interaction_count", "sentiment_avg",
        "freshness_score", "confidence_score", "consistency_score",
        "authority_score", "context_score", "response_rate",
        "avg_response_time_hours", "is_bidirectional", "community_id",
    ])
    for c in contacts:
        writer.writerow([
            str(c[0]), c[1] or "", c[2] or "", c[3] or "", c[4] or "",
            c[5] or "", c[6].isoformat() if c[6] else "",
            c[7] or 0, round(float(c[8] or 0), 3),
            round(float(c[9] or 0), 3), round(float(c[10] or 0), 3),
            round(float(c[11] or 0), 3), round(float(c[12] or 0), 3),
            round(float(c[13] or 0), 3),
            round(float(c[14] or 0), 3) if c[14] else "",
            round(float(c[15] or 0), 1) if c[15] else "",
            str(c[16]).lower() if c[16] is not None else "false",
            c[17] or "",
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
    """
    Edge click detail — per PDF spec §6.
    When you click an edge between your org and a person, shows:
    - All email threads in that relationship, sorted by date
    - Sentiment trajectory
    - Topic clustering
    - Response time analysis
    - Last 3 thread summaries
    """
    # All interactions for this contact
    interactions = db.execute(
        text("""
            SELECT subject, summary, sentiment, intent, topics,
                interaction_at, direction, interaction_type, weight_score,
                signal_score, reply_time_hours, mentioned_people
            FROM interactions
            WHERE contact_id = :contact_id AND org_id = :org_id
            ORDER BY interaction_at DESC
            LIMIT 50
        """),
        {"contact_id": contact_id, "org_id": org_id}
    ).fetchall()

    # Sentiment trajectory
    sentiment_trajectory = [
        {
            "date": r[5].isoformat() if r[5] else None,
            "sentiment": float(r[2] or 0),
            "direction": r[6],
        } for r in interactions
    ]

    # Topic clustering
    topic_counts = {}
    for r in interactions:
        for t in (r[4] or []):
            topic_counts[t] = topic_counts.get(t, 0) + 1
    top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Response time analysis
    reply_times = [float(r[10]) for r in interactions if r[10] and r[10] > 0]
    avg_reply_time = round(sum(reply_times) / len(reply_times), 1) if reply_times else None
    reply_speed = "fast" if avg_reply_time and avg_reply_time < 4 else "moderate" if avg_reply_time and avg_reply_time < 24 else "slow" if avg_reply_time else "unknown"

    # Last 3 thread summaries
    last_threads = [
        {
            "subject": r[0], "summary": r[1],
            "sentiment": float(r[2] or 0), "direction": r[6],
            "date": r[5].isoformat() if r[5] else None,
        } for r in interactions[:3]
    ]

    # PDF spec §6: company-level aggregation — who else at that company
    contact_row = db.execute(
        text("SELECT company, company_domain FROM contacts WHERE id = :id AND org_id = :org_id"),
        {"id": contact_id, "org_id": org_id}
    ).fetchone()

    company_name = contact_row[0] if contact_row else None
    company_domain = contact_row[1] if contact_row else None

    company_contacts = []
    if company_domain:
        cc_rows = db.execute(
            text("""
                SELECT name, email, entity_type, sentiment_avg, interaction_count
                FROM contacts
                WHERE org_id = :org_id AND company_domain = :domain
                AND id != :contact_id
                AND entity_type != 'self'
                AND (is_archived = FALSE OR is_archived IS NULL)
                ORDER BY interaction_count DESC
                LIMIT 5
            """),
            {"org_id": org_id, "domain": company_domain, "contact_id": contact_id}
        ).fetchall()
        company_contacts = [
            {
                "name": r[0], "email": r[1], "entity_type": r[2],
                "sentiment_avg": float(r[3] or 0), "interaction_count": r[4] or 0,
            } for r in cc_rows
        ]

    # Response time breakdown
    fast_count = sum(1 for t in reply_times if t < 4)
    moderate_count = sum(1 for t in reply_times if 4 <= t < 24)
    slow_count = sum(1 for t in reply_times if t >= 24)

    return {
        "contact_id": contact_id,
        "contact_name": contact_row[0] if contact_row else None,
        "company": company_name,
        "total_interactions": len(interactions),
        "sentiment_trajectory": sentiment_trajectory,
        "topic_clusters": [{"topic": t[0], "count": t[1]} for t in top_topics],
        "response_time": {
            "avg_hours": avg_reply_time,
            "fast": fast_count,
            "moderate": moderate_count,
            "slow": slow_count,
        },
        "last_3_threads": last_threads,
        "company_contacts": company_contacts,
    }


@router.get("/api/org/{org_id}/company/{domain}")
def get_company_aggregate(org_id: str, domain: str, db: Session = Depends(get_db)):
    """
    Company node view — per PDF spec §6.
    When you click a company node edge, shows:
    - Who else at that company is in your graph
    - Aggregate sentiment across all contacts at that company
    - Whether you have multiple open commitments with same org
    """
    contacts = db.execute(
        text("""
            SELECT id, name, email, entity_type, relationship_stage,
                sentiment_avg, interaction_count, last_interaction_at,
                is_bidirectional, confidence_score
            FROM contacts
            WHERE org_id = :org_id AND company_domain = :domain
            AND relationship_stage IS NOT NULL AND relationship_stage != 'unknown'
            ORDER BY interaction_count DESC
        """),
        {"org_id": org_id, "domain": domain.lower()}
    ).fetchall()

    if not contacts:
        raise HTTPException(status_code=404, detail=f"No contacts found at domain {domain}")

    # Aggregate sentiment
    sentiments = [float(c[5] or 0) for c in contacts]
    avg_sentiment = round(sum(sentiments) / len(sentiments), 2) if sentiments else 0

    # Open commitments across all contacts at this company
    contact_ids = [str(c[0]) for c in contacts]
    commitments = db.execute(
        text("""
            SELECT cm.commit_text, cm.owner, cm.due_date, cm.status, c.name
            FROM commitments cm
            JOIN contacts c ON cm.contact_id = c.id
            WHERE cm.contact_id = ANY(:contact_ids)
            AND cm.status IN ('OPEN', 'OVERDUE', 'SOFT')
            ORDER BY cm.due_date ASC NULLS LAST
        """),
        {"contact_ids": contact_ids}
    ).fetchall()

    return {
        "domain": domain,
        "company_name": contacts[0][2].split("@")[1].split(".")[0].title() if contacts else domain,
        "total_contacts": len(contacts),
        "aggregate_sentiment": avg_sentiment,
        "contacts": [
            {
                "id": str(c[0]), "name": c[1], "email": c[2],
                "entity_type": c[3], "relationship_stage": c[4],
                "sentiment_avg": float(c[5] or 0),
                "interaction_count": c[6],
                "last_interaction_at": c[7].isoformat() if c[7] else None,
                "is_bidirectional": bool(c[8]),
            } for c in contacts
        ],
        "open_commitments": [
            {
                "text": r[0], "owner": r[1],
                "due_date": r[2].strftime("%Y-%m-%d") if r[2] else None,
                "status": r[3], "contact_name": r[4],
            } for r in commitments
        ],
    }


@router.get("/api/org/{org_id}/graph/filter/topic")
def filter_graph_by_topic(org_id: str, topic: str, db: Session = Depends(get_db)):
    """
    Topic-based graph filtering — per PDF spec §10.
    Type a topic → filter graph to show only nodes where that topic appeared.
    """
    contacts = db.execute(
        text("""
            SELECT DISTINCT c.id, c.name, c.email, c.company,
                c.relationship_stage, c.entity_type, c.interaction_count,
                c.sentiment_avg, c.last_interaction_at
            FROM contacts c
            JOIN interactions i ON i.contact_id = c.id AND i.org_id = c.org_id
            WHERE c.org_id = :org_id
            AND :topic = ANY(i.topics)
            AND c.relationship_stage IS NOT NULL AND c.relationship_stage != 'unknown'
            ORDER BY c.interaction_count DESC
        """),
        {"org_id": org_id, "topic": topic}
    ).fetchall()

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


