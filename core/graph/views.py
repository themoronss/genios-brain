"""Dashboard-shaped views built FROM the v2 graph (per g-i-1 plan).

Replaces v1's content-table reads (`contacts`, `contact_facts`, `interactions`)
with queries against v2 `graph_nodes`, `facts`, `graph_edges`. Everything
org-isolated.

These functions are designed to be drop-in replacements for what the v1
dashboard read endpoints used to return — same SHAPE the frontend expects.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.graph.store import EdgeRow, FactRow, NodeRow
from core.memory.store import Connection

# ─────────────────────────────────────────────────────────────────────────────
# Contacts view (formerly: SELECT FROM contacts)
# ─────────────────────────────────────────────────────────────────────────────


def list_contacts(
    session: Session,
    *,
    org_id: str,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Return entity-type nodes shaped like v1's contacts list.

    Each "contact" = a NodeRow with type='entity'. Source mailbox / channel
    captured via the linked FactRows (we surface a short summary).
    """
    base = (
        select(NodeRow)
        .where(NodeRow.org_id == org_id)
        .where(NodeRow.type == "entity")
    )
    total = session.execute(
        select(func.count()).select_from(base.subquery())
    ).scalar_one()

    rows = (
        session.execute(
            base.order_by(NodeRow.last_seen.desc()).offset(offset).limit(limit)
        )
        .scalars()
        .all()
    )

    contacts: list[dict[str, Any]] = []
    for n in rows:
        # Pull last 3 facts grounded to this node's source_items for a brief
        last_facts = (
            session.execute(
                select(FactRow)
                .where(FactRow.org_id == org_id)
                .where(FactRow.source_item_id.in_(n.source_item_ids or []))
                .order_by(FactRow.created_at.desc())
                .limit(3)
            )
            .scalars()
            .all()
        )
        aliases = n.aliases or []
        first_alias = aliases[0] if aliases else None
        contacts.append(
            {
                "id": n.id,
                "name": n.canonical_name,
                "email": first_alias if first_alias and "@" in first_alias else "",
                "company": _attr(n, "company", ""),
                "interactionCount": len(n.source_item_ids or []),
                "lastInteraction": n.last_seen.isoformat() if n.last_seen else None,
                "sentiment": 0.0,  # v2 doesn't auto-compute sentiment — engine work
                "relationshipStage": _derive_stage(n),
                "recent_facts": [
                    {
                        "subject": f.subject,
                        "predicate": f.predicate,
                        "object": f.object,
                    }
                    for f in last_facts
                ],
            }
        )

    return {"contacts": contacts, "total": total, "limit": limit, "offset": offset}


# ─────────────────────────────────────────────────────────────────────────────
# Graph view (formerly: SELECT FROM contacts JOIN interactions)
# ─────────────────────────────────────────────────────────────────────────────


def graph_d3(session: Session, *, org_id: str, entity_type: str | None = None) -> dict[str, Any]:
    """Build a D3-friendly {nodes, links} payload from v2 graph_nodes + graph_edges.

    Replaces v1's heavy contacts+interactions query.
    """
    nq = select(NodeRow).where(NodeRow.org_id == org_id)
    if entity_type and entity_type != "all":
        nq = nq.where(NodeRow.type == entity_type)
    nodes = session.execute(nq.limit(500)).scalars().all()

    eq = select(EdgeRow).where(EdgeRow.org_id == org_id)
    edges = session.execute(eq.limit(2000)).scalars().all()

    type_counts = Counter(n.type for n in nodes)

    return {
        "nodes": [
            {
                "id": n.id,
                "name": n.canonical_name,
                "type": n.type,
                "size": min(40, 8 + len(n.source_item_ids or [])),
                "company": _attr(n, "company", ""),
                "first_seen": n.first_seen.isoformat() if n.first_seen else None,
                "last_seen": n.last_seen.isoformat() if n.last_seen else None,
            }
            for n in nodes
        ],
        "links": [
            {
                "source": e.from_node,
                "target": e.to_node,
                "type": e.type,
                "weight": float(e.weight or 0),
                "provenance": e.asserted_by_type,
                "status": e.status,
            }
            for e in edges
        ],
        "entityTypeCounts": dict(type_counts),
        "communities": [],
        "connectedTools": _connected_sources(session, org_id=org_id),
    }


def _connected_sources(session: Session, *, org_id: str) -> list[str]:
    """Return distinct source_types from active connections — for dashboard chips."""
    rows = (
        session.execute(
            select(Connection.source_type)
            .where(Connection.org_id == org_id)
            .where(Connection.status == "active")
            .distinct()
        )
        .scalars()
        .all()
    )
    return sorted(set(rows))


# ─────────────────────────────────────────────────────────────────────────────
# Facts view (direct from v2 facts table)
# ─────────────────────────────────────────────────────────────────────────────


def list_facts(
    session: Session,
    *,
    org_id: str,
    subject: str | None = None,
    predicate: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """List facts (S-P-O) — optionally filtered."""
    q = select(FactRow).where(FactRow.org_id == org_id)
    if subject:
        q = q.where(FactRow.subject.ilike(f"%{subject}%"))
    if predicate:
        q = q.where(FactRow.predicate == predicate)
    total = session.execute(
        select(func.count()).select_from(q.subquery())
    ).scalar_one()
    rows = (
        session.execute(q.order_by(FactRow.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    return {
        "facts": [
            {
                "id": f.id,
                "subject": f.subject,
                "predicate": f.predicate,
                "object": f.object,
                "source_item_id": f.source_item_id,
                "asserted_by_type": f.asserted_by_type,
                "asserted_by_id": f.asserted_by_id,
                "confidence": float(f.confidence or 0),
                "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Network health (derived: counts + density + last_sync)
# ─────────────────────────────────────────────────────────────────────────────


def network_health(session: Session, *, org_id: str) -> dict[str, Any]:
    """High-level health snapshot for the dashboard header."""
    n_nodes = session.execute(
        select(func.count(NodeRow.id)).where(NodeRow.org_id == org_id)
    ).scalar_one()
    n_edges = session.execute(
        select(func.count(EdgeRow.id)).where(EdgeRow.org_id == org_id)
    ).scalar_one()
    n_facts = session.execute(
        select(func.count(FactRow.id)).where(FactRow.org_id == org_id)
    ).scalar_one()
    n_conns = session.execute(
        select(func.count(Connection.id))
        .where(Connection.org_id == org_id)
        .where(Connection.status == "active")
    ).scalar_one()

    week_ago = datetime.now(UTC) - timedelta(days=7)
    recent_nodes = session.execute(
        select(func.count(NodeRow.id))
        .where(NodeRow.org_id == org_id)
        .where(NodeRow.last_seen >= week_ago)
    ).scalar_one()

    # Stage breakdown (derive from last_seen)
    active = recent_nodes
    cold = max(0, n_nodes - active)

    return {
        "summary": {
            "connections": n_conns,
            "nodes": n_nodes,
            "edges": n_edges,
            "facts": n_facts,
        },
        "segments": {
            "active": active,
            "cold": cold,
        },
        "computed_at": datetime.now(UTC).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard top-line metrics (composite)
# ─────────────────────────────────────────────────────────────────────────────


def dashboard_metrics(session: Session, *, org_id: str) -> dict[str, Any]:
    """v1-shape metrics so the existing dashboard renders without a frontend rewrite.

    `brainHealth` is composite: node count + edge density + sync recency.
    """
    h = network_health(session, org_id=org_id)
    facts = h["summary"]["facts"]
    nodes = h["summary"]["nodes"]
    conns = h["summary"]["connections"]

    # Naïve composite (0..100). Engine refinement is g-i-8 / brain activity work.
    brain_health = min(100, int(20 * conns + min(80, facts // 5 + nodes // 10)))

    return {
        "contacts_count": nodes,
        "interactions_count": facts,
        "active_relationships_count": h["segments"]["active"],
        "context_calls_count": 0,
        "aer": 0.0,
        "graph_quality_score": float(brain_health) / 100.0,
        "time_saved_hours": 0.0,
        "context_calls_today": 0,
        "internal_calls_today": 0,
        "brainHealth": brain_health,
        "aerRate": 0.0,
        "timeSavedHours": 0.0,
        "contextCallsToday": 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _attr(node: NodeRow, key: str, default: Any = "") -> Any:
    """Read attribute from node.attributes JSONB."""
    attrs = node.attributes or {}
    return attrs.get(key, default)


def _derive_stage(node: NodeRow) -> str:
    """Rough relationship-stage derivation from last_seen.

    v2 engine would compute this properly via rules; this is a placeholder
    so the dashboard renders without nulls.
    """
    if not node.last_seen:
        return "unknown"
    age = datetime.now(UTC) - node.last_seen.replace(tzinfo=UTC)
    if age < timedelta(days=14):
        return "active"
    if age < timedelta(days=30):
        return "warm"
    if age < timedelta(days=60):
        return "needs_attention"
    return "cold"
