"""
Auto-segment assignment at ingest time.

Maps entity_type (from category_detector) → graph_segments row.
Creates the segment if it doesn't exist yet for the org.
Writes segment_id + adds to segment_members join table.

Architecture rule: segment is written at node creation time.
Subscription only gates the query filter. Upgrade = instant reveal.
"""

import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Map category_detector output → standard cluster_type names
_TYPE_TO_CLUSTER = {
    "investor": "Investor",
    "vendor": "Vendor",
    "customer": "Customer",
    "team": "Team",
    "admin": "Admin",
    "partner": "Investor",   # partners often co-invest
    "advisor": "Investor",
    "lead": "Customer",
    "candidate": "Team",
    "media": "Other",
    "other": "Other",
}


def _get_or_create_segment(db, org_id: str, cluster_type: str) -> str | None:
    """Find segment by cluster_type for this org, or auto-create it."""
    row = db.execute(
        text("""
            SELECT id FROM graph_segments
            WHERE org_id = :org_id AND cluster_type = :ctype
            LIMIT 1
        """),
        {"org_id": org_id, "ctype": cluster_type},
    ).fetchone()

    if row:
        return str(row[0])

    # Auto-create the segment
    try:
        result = db.execute(
            text("""
                INSERT INTO graph_segments (org_id, name, cluster_type, created_at)
                VALUES (:org_id, :name, :ctype, NOW())
                RETURNING id
            """),
            {"org_id": org_id, "name": cluster_type, "ctype": cluster_type},
        ).fetchone()
        if result:
            logger.info(f"Auto-created segment '{cluster_type}' for org {org_id[:8]}")
            return str(result[0])
    except Exception as e:
        # Likely race condition — another thread created it
        logger.debug(f"Segment auto-create conflict (expected): {e}")
        row = db.execute(
            text("""
                SELECT id FROM graph_segments
                WHERE org_id = :org_id AND cluster_type = :ctype
                LIMIT 1
            """),
            {"org_id": org_id, "ctype": cluster_type},
        ).fetchone()
        return str(row[0]) if row else None

    return None


def auto_assign_segment(db, org_id: str, contact_id: str, entity_type: str):
    """
    Auto-assign a contact to the matching segment based on entity_type.
    Skips if contact already has a manual segment assignment.
    """
    if not contact_id or not entity_type:
        return

    # Check if already manually assigned — never override manual
    existing = db.execute(
        text("""
            SELECT segment_id, segment_source FROM contacts
            WHERE id = :cid AND org_id = :org_id
        """),
        {"cid": contact_id, "org_id": org_id},
    ).fetchone()

    if existing and existing[1] == "manual":
        return  # Manual override — don't touch

    cluster_type = _TYPE_TO_CLUSTER.get(entity_type.lower(), "Other")
    segment_id = _get_or_create_segment(db, org_id, cluster_type)

    if not segment_id:
        return

    # Skip if already assigned to this same segment
    if existing and str(existing[0]) == segment_id:
        return

    # Write segment_id on the contact row
    try:
        db.execute(
            text("""
                UPDATE contacts
                SET segment_id = :sid, segment_source = 'auto'
                WHERE id = :cid AND org_id = :org_id
            """),
            {"sid": segment_id, "cid": contact_id, "org_id": org_id},
        )
    except Exception as e:
        logger.debug(f"Segment field update failed: {e}")

    # Also ensure membership in segment_members join table
    try:
        db.execute(
            text("""
                INSERT INTO segment_members (segment_id, contact_id, added_at)
                VALUES (:sid, :cid, NOW())
                ON CONFLICT (segment_id, contact_id) DO NOTHING
            """),
            {"sid": segment_id, "cid": contact_id},
        )
    except Exception as e:
        logger.debug(f"Segment member insert failed: {e}")
