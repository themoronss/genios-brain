"""
Graph Intelligence Dimensions — per-org nightly summary.

Computes what % of each intelligence dimension is "lit up" based on
connected tools and data quality. Maps to the artifact's 4 dimensions:
  Relationship  — confidence_score (source diversity + volume)
  Authority     — authority_score (directness + organizer patterns)
  State         — freshness_score (temporal awareness)
  Precedent     — consistency_score (historical pattern agreement)
"""

from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def compute_intelligence_dimensions(db, org_id: str) -> dict:
    """
    Compute graph intelligence dimension percentages for an org.
    UPSERTs result into graph_intelligence_dimensions table.

    Returns dict with relationship_pct, authority_pct, state_pct, precedent_pct.
    """
    # Get connected tool sources
    sources_row = db.execute(
        text("""
            SELECT ARRAY_AGG(DISTINCT source) as tools
            FROM interactions
            WHERE org_id = :oid AND source IS NOT NULL
        """),
        {"oid": org_id},
    ).fetchone()
    connected_tools = sources_row[0] if sources_row and sources_row[0] else []

    # Get aggregate scores across non-archived contacts with interactions
    scores = db.execute(
        text("""
            SELECT
                AVG(confidence_score) as avg_confidence,
                AVG(authority_score) as avg_authority,
                AVG(freshness_score) as avg_freshness,
                AVG(consistency_score) as avg_consistency,
                COUNT(*) as contact_count
            FROM contacts
            WHERE org_id = :oid
            AND is_archived = FALSE
            AND EXISTS (SELECT 1 FROM interactions WHERE contact_id = contacts.id)
        """),
        {"oid": org_id},
    ).fetchone()

    if not scores or not scores[4]:
        dims = {
            "relationship_pct": 0.0,
            "authority_pct": 0.0,
            "state_pct": 0.0,
            "precedent_pct": 0.0,
        }
    else:
        # Scale 0-1 scores to 0-100 percentages
        dims = {
            "relationship_pct": round(float(scores[0] or 0) * 100, 1),
            "authority_pct": round(float(scores[1] or 0) * 100, 1),
            "state_pct": round(float(scores[2] or 0) * 100, 1),
            "precedent_pct": round(float(scores[3] or 0) * 100, 1),
        }

    # UPSERT into summary table
    db.execute(
        text("""
            INSERT INTO graph_intelligence_dimensions
                (org_id, relationship_pct, authority_pct, state_pct,
                 precedent_pct, connected_tools, computed_at)
            VALUES
                (:oid, :rel, :auth, :state, :prec, :tools, NOW())
            ON CONFLICT (org_id) DO UPDATE SET
                relationship_pct = EXCLUDED.relationship_pct,
                authority_pct = EXCLUDED.authority_pct,
                state_pct = EXCLUDED.state_pct,
                precedent_pct = EXCLUDED.precedent_pct,
                connected_tools = EXCLUDED.connected_tools,
                computed_at = NOW()
        """),
        {
            "oid": org_id,
            "rel": dims["relationship_pct"],
            "auth": dims["authority_pct"],
            "state": dims["state_pct"],
            "prec": dims["precedent_pct"],
            "tools": connected_tools,
        },
    )

    logger.info(
        f"Intelligence dimensions for org={org_id}: "
        f"R={dims['relationship_pct']}% A={dims['authority_pct']}% "
        f"S={dims['state_pct']}% P={dims['precedent_pct']}% "
        f"tools={connected_tools}"
    )
    return dims
