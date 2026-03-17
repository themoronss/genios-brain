from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import SessionLocal
from datetime import datetime, timezone

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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

    # Build WHERE clause for optional entity_type filter
    entity_filter = ""
    params: dict = {"org_id": org_id}
    if entity_type and entity_type != "all":
        entity_filter = "AND entity_type = :entity_type"
        params["entity_type"] = entity_type

    # Get all contacts (with optional entity_type filter)
    contacts = db.execute(
        text(
            f"""
            SELECT
                id, name, email, company, relationship_stage,
                sentiment_avg, interaction_count, last_interaction_at, entity_type,
                COALESCE(human_score, 0.5) AS human_score
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

    # ── Email account nodes (one per connected Gmail) ─────────────────────
    account_rows = db.execute(
        text("SELECT DISTINCT COALESCE(account_email, 'default') FROM oauth_tokens WHERE org_id = :org_id"),
        {"org_id": org_id},
    ).fetchall()
    account_emails = {r[0].lower().strip(): r[0] for r in account_rows}

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
                "human_score": float(c.human_score),
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
                   COUNT(*) AS cnt
            FROM interactions i
            WHERE i.org_id = :org_id
            GROUP BY i.account_email, i.contact_id
        """),
        {"org_id": org_id},
    ).fetchall()

    for edge in acct_edges:
        source_acct = f"acct_{edge[0]}"
        raw_contact_id = str(edge[1])
        
        if raw_contact_id in contact_id_set:
            # Map contact_id to acct_ node if they were merged
            target = contact_id_to_acct.get(raw_contact_id, raw_contact_id)
            
            # Don't draw self-loops (e.g. acct_X talking to acct_X, which shouldn't happen but just in case)
            if source_acct != target:
                links.append({
                    "source": source_acct,
                    "target": target,
                    "strength": min(edge[2] / 10.0, 1.0),
                    "link_type": "primary",
                })

    # ── Link 2: Contact ↔ Contact cross-edges (CC many-to-many) ───────────
    cc_pairs = db.execute(
        text("""
            SELECT i1.contact_id, i2.contact_id, COUNT(*)
            FROM interactions i1
            JOIN interactions i2
                ON i1.gmail_message_id = i2.gmail_message_id
                AND i1.contact_id < i2.contact_id
            WHERE i1.org_id = :org_id AND i2.org_id = :org_id
            GROUP BY i1.contact_id, i2.contact_id
            HAVING COUNT(*) >= 1
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
                    "strength": min(pair[2] / 5.0, 1.0),
                    "link_type": "cc_shared",
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

    return {
        "nodes": nodes,
        "links": links,
        "entity_type_counts": entity_type_counts,
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
                interaction_count, sentiment_avg, entity_type
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
            }
            for c in contacts
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
