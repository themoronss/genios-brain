"""
Louvain Community Detection for GeniOS Relationship Graph
Detects relationship clusters (investor networks, vendor ecosystems, etc.)
"""

import networkx as nx
from sqlalchemy import text
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# Fixed color palette for top 8 communities
COMMUNITY_COLORS = [
    "#8b5cf6",  # Purple
    "#10b981",  # Green
    "#f59e0b",  # Amber
    "#3b82f6",  # Blue
    "#ef4444",  # Red
    "#06b6d4",  # Cyan
    "#ec4899",  # Pink
    "#f97316",  # Orange
]


def build_networkx_graph(db, org_id: str) -> nx.Graph:
    """Build a networkx graph from contacts and interactions."""
    G = nx.Graph()

    # Get all contacts
    contacts = db.execute(
        text("""
            SELECT id, name, email, interaction_count, sentiment_avg
            FROM contacts
            WHERE org_id = :org_id
            AND relationship_stage IS NOT NULL
            AND relationship_stage != 'unknown'
        """),
        {"org_id": org_id}
    ).fetchall()

    for c in contacts:
        G.add_node(str(c[0]), name=c[1], email=c[2])

    # Get interaction-based edges (contacts that share email threads via CC)
    edges = db.execute(
        text("""
            SELECT i1.contact_id, i2.contact_id, COUNT(*) as weight
            FROM interactions i1
            JOIN interactions i2
                ON i1.gmail_message_id = i2.gmail_message_id
                AND i1.contact_id < i2.contact_id
            WHERE i1.org_id = :org_id AND i2.org_id = :org_id
            GROUP BY i1.contact_id, i2.contact_id
        """),
        {"org_id": org_id}
    ).fetchall()

    for edge in edges:
        source, target, weight = str(edge[0]), str(edge[1]), edge[2]
        if source in G.nodes and target in G.nodes:
            G.add_edge(source, target, weight=weight)

    # Also add edges based on account interactions (contacts who interact with same account)
    account_edges = db.execute(
        text("""
            SELECT a.contact_id, b.contact_id, COUNT(*) as shared_count
            FROM (
                SELECT DISTINCT contact_id, account_email
                FROM interactions
                WHERE org_id = :org_id AND account_email IS NOT NULL
            ) a
            JOIN (
                SELECT DISTINCT contact_id, account_email
                FROM interactions
                WHERE org_id = :org_id AND account_email IS NOT NULL
            ) b ON a.account_email = b.account_email AND a.contact_id < b.contact_id
            GROUP BY a.contact_id, b.contact_id
            HAVING COUNT(*) >= 2
        """),
        {"org_id": org_id}
    ).fetchall()

    for edge in account_edges:
        source, target, weight = str(edge[0]), str(edge[1]), edge[2]
        if source in G.nodes and target in G.nodes:
            if G.has_edge(source, target):
                G[source][target]["weight"] += weight
            else:
                G.add_edge(source, target, weight=weight)

    return G


def run_louvain_detection(db, org_id: str) -> Dict:
    """
    Run Louvain community detection and store results.
    Returns dict of {contact_id: community_id}.
    """
    try:
        import community as community_louvain
    except ImportError:
        logger.warning("python-louvain not installed, skipping community detection")
        return {}

    G = build_networkx_graph(db, org_id)

    if len(G.nodes) < 2:
        logger.info(f"Not enough nodes ({len(G.nodes)}) for community detection")
        return {}

    # Run Louvain
    try:
        partition = community_louvain.best_partition(G, random_state=42)
    except Exception as e:
        logger.error(f"Louvain failed: {e}")
        return {}

    if not partition:
        return {}

    # Count nodes per community
    community_counts = {}
    for node_id, comm_id in partition.items():
        community_counts[comm_id] = community_counts.get(comm_id, 0) + 1

    # Clear old communities
    db.execute(
        text("DELETE FROM communities WHERE org_id = :org_id"),
        {"org_id": org_id}
    )

    # Store communities
    for comm_id, count in community_counts.items():
        color = COMMUNITY_COLORS[comm_id % len(COMMUNITY_COLORS)]
        db.execute(
            text("""
                INSERT INTO communities (org_id, community_id, color, node_count, updated_at)
                VALUES (:org_id, :community_id, :color, :node_count, NOW())
            """),
            {"org_id": org_id, "community_id": comm_id, "color": color, "node_count": count}
        )

    # Update contacts with community_id
    for contact_id, comm_id in partition.items():
        db.execute(
            text("UPDATE contacts SET community_id = :comm_id WHERE id = :contact_id"),
            {"comm_id": comm_id, "contact_id": contact_id}
        )

    db.commit()
    logger.info(f"Louvain: {len(community_counts)} communities detected for org {org_id}")

    return partition


def get_communities(db, org_id: str) -> List[Dict]:
    """Get all communities for an org."""
    results = db.execute(
        text("""
            SELECT community_id, color, node_count, updated_at
            FROM communities
            WHERE org_id = :org_id
            ORDER BY node_count DESC
        """),
        {"org_id": org_id}
    ).fetchall()

    return [
        {
            "community_id": r[0],
            "color": r[1],
            "node_count": r[2],
            "updated_at": r[3].isoformat() if r[3] else None
        }
        for r in results
    ]
