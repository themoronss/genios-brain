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
    entity_type: str = None,  # Optional filter: investor, customer, etc.
    db: Session = Depends(get_db)
):
    """
    Get relationship graph data for visualization — many-to-many topology.

    Each connected Gmail account is a separate node. Contacts link to the
    specific account(s) they interacted with. CC cross-edges link contacts
    who share the same email thread.
    """

    # Segment type mapping: entity_type → continent ID for graph visualization
    _TYPE_TO_SEGMENT = {
        "investor": "investors", "lead": "investors",
        "customer": "customers",
        "partner": "partners",
        "vendor": "vendors",
        "team": "team",
    }

    # Build WHERE clause for optional entity_type filter
    entity_filter = ""
    params: dict = {"org_id": org_id}
    if entity_type and entity_type != "all":
        entity_filter = "AND entity_type = :entity_type"
        params["entity_type"] = entity_type

    # Determine segment lock boundary for this org's plan tier
    from app.plan_enforcer import get_org_plan as _get_plan
    _plan = _get_plan(db, org_id)
    _max_clusters = _plan["config"]["max_clusters"]

    # Get ordered segment IDs — segments beyond max_clusters are locked
    _seg_rows = db.execute(
        text("SELECT id FROM graph_segments WHERE org_id = :org_id ORDER BY created_at ASC"),
        {"org_id": org_id},
    ).fetchall()
    _locked_seg_ids = {str(r[0]) for i, r in enumerate(_seg_rows) if i >= _max_clusters}

    # Get all contacts (with optional entity_type filter)
    contacts = db.execute(
        text(
            f"""
            SELECT
                id, name, email, company, relationship_stage,
                sentiment_avg, interaction_count, last_interaction_at, entity_type,
                COALESCE(human_score, 0.5) AS human_score,
                confidence_score, community_id, size_score, is_bidirectional,
                freshness_score, context_score, sentiment_trend,
                response_rate, avg_response_time_hours,
                segment_id, clm_state
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage IS NOT NULL
            AND relationship_stage != 'unknown'
            {entity_filter}
            ORDER BY interaction_count DESC
        """
        ),
        params,
    ).fetchall()

    # ── Email account nodes (one per connected Gmail / Calendar) ───────────
    account_rows = db.execute(
        text("SELECT DISTINCT COALESCE(account_email, 'default') FROM oauth_tokens WHERE org_id = :org_id AND account_email NOT LIKE 'gcal:%'"),
        {"org_id": org_id},
    ).fetchall()
    account_emails = {r[0].lower().strip(): r[0] for r in account_rows}

    # Fallback: if no Gmail tokens, derive hub email from orgs table or calendar interactions
    if not account_emails:
        org_email_row = db.execute(
            text("SELECT email FROM orgs WHERE id = :oid"),
            {"oid": org_id},
        ).fetchone()
        if org_email_row and org_email_row.email:
            fallback = org_email_row.email.strip()
            account_emails = {fallback.lower(): fallback}

    nodes = []
    contact_id_set = set()
    contact_id_to_acct = {}

    for c in contacts:
        contact_email_lower = (c.email or "").lower().strip()
        
        # If this contact is ACTUALLY one of our connected accounts, merge them!
        if contact_email_lower in account_emails:
            contact_id_to_acct[str(c.id)] = f"acct_{account_emails[contact_email_lower]}"
            # Keep it in the set so edges to it are still processed
            contact_id_set.add(str(c.id))
        else:
            days_ago = (datetime.now(timezone.utc) - c.last_interaction_at).days if c.last_interaction_at else 999
            is_locked = str(c.segment_id) in _locked_seg_ids if c.segment_id else False
            nodes.append({
                "id": str(c.id),
                "name": c.name or c.email,
                "company": c.company,
                "relationship_stage": c.relationship_stage,
                "last_interaction_days": days_ago,
                "sentiment_avg": float(c.sentiment_avg or 0),
                "interaction_count": c.interaction_count,
                "email": c.email,
                "entity_type": c.entity_type or "other",
                "segment_type": _TYPE_TO_SEGMENT.get(c.entity_type or "", "operations"),
                "human_score": float(c.human_score),
                "confidence_score": float(c.confidence_score or 0),
                "community_id": c.community_id,
                "size_score": float(c.size_score or 0),
                "is_bidirectional": bool(c.is_bidirectional) if c.is_bidirectional is not None else False,
                "freshness_score": float(c.freshness_score or 0),
                "context_score": float(c.context_score or 0),
                "clm_state": c.clm_state or "active",
                "sentiment_trend": c.sentiment_trend,
                "response_rate": float(c.response_rate or 0),
                "avg_response_time_hours": float(c.avg_response_time_hours or 0),
                "locked": is_locked,
            })
            contact_id_set.add(str(c.id))
    for acct_lower, acct_original in account_emails.items():
        nodes.insert(0, {
            "id": f"acct_{acct_original}",
            "name": acct_original,
            "company": None,
            "relationship_stage": "ACTIVE",
            "last_interaction_days": 0,
            "sentiment_avg": 1.0,
            "interaction_count": 0,
            "email": acct_original,
            "entity_type": "self",
        })

    # ── Link 1: Account → Contact edges (many-to-many) ────────────────────
    links = []
    acct_edges = db.execute(
        text("""
            SELECT COALESCE(i.account_email, 'default') AS acct,
                   i.contact_id,
                   COUNT(*) AS cnt,
                   c.sentiment_trend,
                   c.is_bidirectional,
                   MODE() WITHIN GROUP (ORDER BY COALESCE(i.source, 'gmail')) AS predominant_source
            FROM interactions i
            JOIN contacts c ON i.contact_id = c.id
            WHERE i.org_id = :org_id
            GROUP BY i.account_email, i.contact_id, c.sentiment_trend, c.is_bidirectional
        """),
        {"org_id": org_id},
    ).fetchall()

    # Map interaction source to edge_type
    _source_to_edge = {
        "gmail": "email", "calendar": "meeting", "drive": "shared_with",
        "slack": "email", "hubspot": "email",
    }

    for edge in acct_edges:
        source_acct = f"acct_{edge[0]}"
        raw_contact_id = str(edge[1])
        interaction_count = edge[2]

        if raw_contact_id in contact_id_set:
            target = contact_id_to_acct.get(raw_contact_id, raw_contact_id)

            if source_acct != target:
                predominant = edge[5] if len(edge) > 5 else "gmail"
                links.append({
                    "source": source_acct,
                    "target": target,
                    "strength": min(interaction_count / 10.0, 1.0),
                    "interaction_count": interaction_count,
                    "sentiment_trend": edge[3],
                    "is_bidirectional": bool(edge[4]) if edge[4] is not None else False,
                    "link_type": _source_to_edge.get(predominant, "email"),
                })

    # ── Link 2: Contact ↔ Contact cross-edges (CC + calendar co-attendees) ──
    cc_pairs = db.execute(
        text("""
            SELECT contact_a, contact_b, SUM(cnt) as cnt FROM (
                -- Email CC co-occurrence
                SELECT i1.contact_id as contact_a, i2.contact_id as contact_b, COUNT(*) as cnt
                FROM interactions i1
                JOIN interactions i2
                    ON i1.gmail_message_id = i2.gmail_message_id
                    AND i1.contact_id < i2.contact_id
                WHERE i1.org_id = :org_id AND i2.org_id = :org_id
                    AND i1.gmail_message_id IS NOT NULL
                GROUP BY i1.contact_id, i2.contact_id

                UNION ALL

                -- Calendar co-attendee edges
                SELECT i1.contact_id as contact_a, i2.contact_id as contact_b, COUNT(*) as cnt
                FROM interactions i1
                JOIN interactions i2
                    ON i1.calendar_event_id = i2.calendar_event_id
                    AND i1.contact_id < i2.contact_id
                WHERE i1.org_id = :org_id AND i2.org_id = :org_id
                    AND i1.calendar_event_id IS NOT NULL
                GROUP BY i1.contact_id, i2.contact_id
            ) combined
            GROUP BY contact_a, contact_b
            HAVING SUM(cnt) >= 1
        """),
        {"org_id": org_id},
    ).fetchall()

    for pair in cc_pairs:
        raw_a, raw_b = str(pair[0]), str(pair[1])
        if raw_a in contact_id_set and raw_b in contact_id_set:
            source = contact_id_to_acct.get(raw_a, raw_a)
            target = contact_id_to_acct.get(raw_b, raw_b)
            
            if source != target:
                links.append({
                    "source": source,
                    "target": target,
                    "strength": min(float(pair[2]) / 5.0, 1.0),
                    "interaction_count": int(pair[2]),
                    "sentiment_trend": None,
                    "is_bidirectional": True,
                    "link_type": "cc_shared",
                })

    # ── Company nodes + WORKS_AT edges ──────────────────────────────────
    company_rows = db.execute(
        text("""
            SELECT co.id, co.name, co.domain, co.category, co.interaction_count
            FROM companies co
            WHERE co.org_id = :org_id
              AND EXISTS (SELECT 1 FROM contacts c WHERE c.company_id = co.id AND c.org_id = :org_id)
        """),
        {"org_id": org_id},
    ).fetchall()

    company_id_set = set()
    for co in company_rows:
        co_id = f"company_{co.id}"
        company_id_set.add(co_id)
        nodes.append({
            "id": co_id,
            "name": co.name or co.domain,
            "company": None,
            "relationship_stage": "ACTIVE",
            "last_interaction_days": 0,
            "sentiment_avg": 0,
            "interaction_count": co.interaction_count or 0,
            "email": None,
            "entity_type": "company",
            "human_score": 1.0,
            "confidence_score": 0.8,
            "community_id": None,
            "size_score": 0.5,
            "is_bidirectional": False,
            "freshness_score": 0.5,
            "context_score": 0.5,
            "sentiment_trend": None,
            "response_rate": 0,
            "avg_response_time_hours": 0,
            "locked": False,
            "domain": co.domain,
            "category": co.category,
        })

    # WORKS_AT edges: contact → company
    works_at_rows = db.execute(
        text("""
            SELECT c.id as contact_id, c.company_id
            FROM contacts c
            WHERE c.org_id = :org_id AND c.company_id IS NOT NULL
        """),
        {"org_id": org_id},
    ).fetchall()

    for wa in works_at_rows:
        contact_id = str(wa.contact_id)
        company_node_id = f"company_{wa.company_id}"
        if contact_id in contact_id_set and company_node_id in company_id_set:
            target = contact_id_to_acct.get(contact_id, contact_id)
            links.append({
                "source": target,
                "target": company_node_id,
                "strength": 0.3,
                "interaction_count": 0,
                "sentiment_trend": None,
                "is_bidirectional": False,
                "link_type": "works_at",
            })

    # ── Entity type counts for filter buttons ───────────────────────────
    type_counts_rows = db.execute(
        text("""
            SELECT COALESCE(entity_type, 'other'), COUNT(*)
            FROM contacts
            WHERE org_id = :org_id
              AND relationship_stage IS NOT NULL AND relationship_stage != 'unknown'
            GROUP BY entity_type
        """),
        {"org_id": org_id},
    ).fetchall()
    entity_type_counts = {row[0]: row[1] for row in type_counts_rows}

    # Communities for graph visualization
    communities = db.execute(
        text("SELECT community_id, color, node_count FROM communities WHERE org_id = :org_id ORDER BY node_count DESC"),
        {"org_id": org_id}
    ).fetchall()

    # Connected tools — derive from oauth_tokens + sync tables
    connected_tools = []
    if db.execute(text("SELECT 1 FROM oauth_tokens WHERE org_id = :org_id AND account_email NOT LIKE '%:%' LIMIT 1"), {"org_id": org_id}).fetchone():
        connected_tools.append("gmail")
    if db.execute(text("SELECT 1 FROM calendar_sync_state WHERE org_id = :org_id LIMIT 1"), {"org_id": org_id}).fetchone():
        connected_tools.append("gcal")
    if db.execute(text("SELECT 1 FROM slack_workspaces WHERE org_id = :org_id LIMIT 1"), {"org_id": org_id}).fetchone():
        connected_tools.append("slack")
    if db.execute(text("SELECT 1 FROM notion_connections WHERE org_id = :org_id LIMIT 1"), {"org_id": org_id}).fetchone():
        connected_tools.append("notion")

    return {
        "nodes": nodes,
        "links": links,
        "entity_type_counts": entity_type_counts,
        "communities": [{"community_id": c[0], "color": c[1], "node_count": c[2]} for c in communities],
        "connected_tools": connected_tools,
    }


@router.get("/api/org/{org_id}/contacts")
def get_contacts(
    org_id: str,
    limit: int = 100,
    offset: int = 0,
    entity_type: str = None,  # Optional filter
    db: Session = Depends(get_db)
):
    """Get list of contacts, with optional entity_type filter."""

    entity_filter = ""
    params: dict = {"org_id": org_id, "limit": limit, "offset": offset}
    if entity_type and entity_type != "all":
        entity_filter = "AND entity_type = :entity_type"
        params["entity_type"] = entity_type

    contacts = db.execute(
        text(
            f"""
            SELECT
                id, name, email, company,
                relationship_stage, last_interaction_at,
                interaction_count, sentiment_avg, entity_type,
                consistency_score
            FROM contacts
            WHERE org_id = :org_id
            {entity_filter}
            ORDER BY interaction_count DESC
            LIMIT :limit OFFSET :offset
        """
        ),
        params,
    ).fetchall()

    count_params: dict = {"org_id": org_id}
    count_filter = ""
    if entity_type and entity_type != "all":
        count_filter = "AND entity_type = :entity_type"
        count_params["entity_type"] = entity_type

    total = db.execute(
        text(f"SELECT COUNT(*) FROM contacts WHERE org_id = :org_id {count_filter}"),
        count_params,
    ).fetchone()[0]

    return {
        "contacts": [
            {
                "id": str(c.id),
                "name": c.name or c.email,
                "email": c.email,
                "company": c.company,
                "relationship_stage": c.relationship_stage,
                "last_interaction_at": (
                    c.last_interaction_at.isoformat() if c.last_interaction_at else None
                ),
                "interaction_count": c.interaction_count,
                "sentiment_avg": float(c.sentiment_avg or 0),
                "entity_type": c.entity_type or "other",
                "consistency_score": float(c.consistency_score) if c.consistency_score is not None else None,
            }
            for c in contacts
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


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
    """Stats bar data for dashboard."""
    stats = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM contacts WHERE org_id = :org_id AND relationship_stage IS NOT NULL AND relationship_stage != 'unknown') as contacts_count,
                (SELECT COUNT(*) FROM interactions WHERE org_id = :org_id) as interactions_count,
                (SELECT COUNT(*) FROM contacts WHERE org_id = :org_id AND relationship_stage IN ('ACTIVE', 'WARM') AND last_interaction_at >= NOW() - INTERVAL '30 days') as active_relationships,
                (SELECT COUNT(*) FROM context_calls WHERE org_id = :org_id AND (source = 'api' OR source IS NULL)) as api_calls
        """),
        {"org_id": org_id}
    ).fetchone()

    org_data = db.execute(
        text("SELECT aer, graph_quality_score, COALESCE(subscription_tier, 'hustler'), COALESCE(time_saved_hours, 0) FROM orgs WHERE id = :org_id"),
        {"org_id": org_id}
    ).fetchone()

    tier = org_data[2] if org_data else "hustler"
    daily_limit = PLAN_LIMITS.get(tier, 3000)

    # Count only external API calls for quota (exclude dashboard clicks)
    api_calls_today = db.execute(
        text("SELECT COUNT(*) FROM context_calls WHERE org_id = :org_id AND called_at >= CURRENT_DATE AND (source = 'api' OR source IS NULL)"),
        {"org_id": org_id}
    ).scalar() or 0

    internal_calls_today = db.execute(
        text("SELECT COUNT(*) FROM context_calls WHERE org_id = :org_id AND called_at >= CURRENT_DATE AND source = 'dashboard'"),
        {"org_id": org_id}
    ).scalar() or 0

    # Trend data from daily snapshots (last 14 days)
    trends = db.execute(
        text("""
            SELECT snapshot_date, brain_health, aer, time_saved_hours, context_calls_count
            FROM daily_snapshots
            WHERE org_id = :org_id
            ORDER BY snapshot_date DESC
            LIMIT 14
        """),
        {"org_id": org_id}
    ).fetchall()

    trend_brain = [float(r[1] or 0) for r in reversed(trends)]
    trend_aer = [float(r[2] or 0) for r in reversed(trends)]
    trend_time = [float(r[3] or 0) for r in reversed(trends)]
    trend_calls = [int(r[4] or 0) for r in reversed(trends)]

    return {
        "contacts_count": stats[0] or 0,
        "interactions_count": stats[1] or 0,
        "active_relationships_count": stats[2] or 0,
        "context_calls_count": stats[3] or 0,
        "aer": float(org_data[0] or 0) if org_data else 0,
        "graph_quality_score": float(org_data[1] or 0) if org_data else 0,
        "time_saved_hours": float(org_data[3]) if org_data else 0,
        "context_calls_today": api_calls_today,
        "internal_calls_today": internal_calls_today,
        "context_calls_limit": daily_limit,
        "has_agent_calls": api_calls_today > 0,
        "plan": tier.capitalize(),
        "brain_trend": trend_brain,
        "aer_trend": trend_aer,
        "time_trend": trend_time,
        "calls_trend": trend_calls,
    }


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
    """
    Network Health Summary — the "daily briefing" view per PDF spec §7.
    Returns org-level intelligence: total contacts, active now, need follow-up,
    at risk, open commitments, and attention-required items.
    """
    # Core stats
    stats = db.execute(
        text("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE relationship_stage = 'ACTIVE') as active,
                COUNT(*) FILTER (WHERE relationship_stage = 'WARM') as warm,
                COUNT(*) FILTER (WHERE relationship_stage IN ('NEEDS_ATTENTION', 'DORMANT')) as needs_attention,
                COUNT(*) FILTER (WHERE relationship_stage = 'COLD') as cold,
                COUNT(*) FILTER (WHERE relationship_stage = 'AT_RISK') as at_risk
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage IS NOT NULL AND relationship_stage != 'unknown'
            AND (is_archived = FALSE OR is_archived IS NULL)
        """),
        {"org_id": org_id}
    ).fetchone()

    # Overdue commitments
    overdue = db.execute(
        text("""
            SELECT cm.commit_text, c.name, cm.due_date,
                EXTRACT(DAY FROM (NOW() - cm.due_date)) as days_overdue
            FROM commitments cm
            JOIN contacts c ON cm.contact_id = c.id
            WHERE cm.org_id = :org_id
            AND cm.status IN ('OPEN', 'OVERDUE')
            AND cm.due_date < NOW()
            ORDER BY cm.due_date ASC
            LIMIT 10
        """),
        {"org_id": org_id}
    ).fetchall()

    # Contacts needing follow-up (WARM going cold — 20+ days since contact)
    need_follow_up = db.execute(
        text("""
            SELECT id, name, company, entity_type,
                EXTRACT(DAY FROM (NOW() - last_interaction_at)) as days_since
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage = 'WARM'
            AND last_interaction_at < NOW() - INTERVAL '20 days'
            AND (is_archived = FALSE OR is_archived IS NULL)
            ORDER BY last_interaction_at ASC
            LIMIT 10
        """),
        {"org_id": org_id}
    ).fetchall()

    # At-risk contacts
    at_risk_contacts = db.execute(
        text("""
            SELECT id, name, company, entity_type, sentiment_ewma,
                EXTRACT(DAY FROM (NOW() - last_interaction_at)) as days_since
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage = 'AT_RISK'
            AND (is_archived = FALSE OR is_archived IS NULL)
        """),
        {"org_id": org_id}
    ).fetchall()

    # Open commitments summary
    commit_stats = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'OPEN') as open_count,
                COUNT(*) FILTER (WHERE status = 'OVERDUE') as overdue_count
            FROM commitments
            WHERE org_id = :org_id AND status IN ('OPEN', 'OVERDUE')
        """),
        {"org_id": org_id}
    ).fetchone()

    # Recent insights
    insights = db.execute(
        text("""
            SELECT priority, category, title, detail, contact_name, generated_at
            FROM insights
            WHERE org_id = :org_id AND is_dismissed = FALSE
            ORDER BY
                CASE priority WHEN 'P1' THEN 0 WHEN 'P2' THEN 1 ELSE 2 END,
                generated_at DESC
            LIMIT 15
        """),
        {"org_id": org_id}
    ).fetchall()

    return {
        "network_health": {
            "total_contacts": stats[0] or 0,
            "active_now": stats[1] or 0,
            "warm": stats[2] or 0,
            "needs_attention": stats[3] or 0,
            "cold": stats[4] or 0,
            "at_risk": stats[5] or 0,
        },
        "open_commitments": {
            "total": (commit_stats[0] or 0) + (commit_stats[1] or 0),
            "overdue": commit_stats[1] or 0,
        },
        "need_follow_up": [
            {
                "id": str(r[0]), "name": r[1], "company": r[2],
                "entity_type": r[3], "days_since": int(r[4]),
            } for r in need_follow_up
        ],
        "at_risk_contacts": [
            {
                "id": str(r[0]), "name": r[1], "company": r[2],
                "entity_type": r[3], "sentiment_ewma": round(float(r[4] or 0), 2),
                "days_since": int(r[5]),
            } for r in at_risk_contacts
        ],
        "overdue_commitments": [
            {
                "text": r[0], "contact_name": r[1],
                "due_date": r[2].strftime("%Y-%m-%d") if r[2] else None,
                "days_overdue": int(r[3]),
            } for r in overdue
        ],
        "attention_required": [
            {
                "priority": r[0], "category": r[1], "title": r[2],
                "detail": r[3], "contact_name": r[4],
                "generated_at": r[5].isoformat() if r[5] else None,
            } for r in insights
        ],
    }


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


