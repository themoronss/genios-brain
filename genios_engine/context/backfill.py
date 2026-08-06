"""L2 · Backfill — applying entity resolution and correlation to data already in the graph.

WHY THIS HAS TO EXIST
Aliases are claimed inside `find_or_create_node`, and correlation runs inside the L2
drain. Both only fire when an event arrives. So on a tenant that already has months of
history, everything built in Steps 1–3 would appear to do nothing:

  * no aliases      → "Acme" in an email never reaches the acme.io node, and no duplicate
                      is ever proposed for entities that already exist
  * no correlations → historical events belong to no situation
  * no situations   → because they are derived from correlations

The features would look broken while being perfectly implemented, which is worse than
missing: nobody would know where to look.

ORDER MATTERS AND IS NOT NEGOTIABLE
Aliases first, then correlations, then situations. Correlating before entities are
resolved groups the same company under several nodes and produces situations that must
later be folded. Situations before correlations produces nothing at all.

TIME ORDER MATTERS TOO
Events are replayed oldest-first. Correlation generations depend on the gap between an
event and a group's existing span, so processing newest-first would open a fresh
generation for every old event and shatter one history into dozens of situations.

This is safe to re-run. Aliases are insert-or-ignore, membership is idempotent, and
situations are rebuilt from scratch every time.
"""
from __future__ import annotations

from sqlalchemy import text

from genios_engine.context.correlation import correlate_event
from genios_engine.context.identity import register_node_identity
from genios_engine.context.situations import refresh_situations

# Events per transaction. Small enough that a failure costs little and a long backfill
# does not hold one transaction open across a tenant's entire history.
_BATCH = 200


def backfill_aliases(store, org_id: str) -> dict:
    """Claim lookup keys for every entity already in the graph.

    Nodes are processed oldest-first so the ORIGINAL entity keeps a contested key and the
    later duplicate is the one raised as a proposal. Reversing that would make the newest
    row the canonical one purely by accident of iteration order.
    """
    with store.engine.connect() as conn:
        nodes = conn.execute(text(
            "select node_id, node_type, canonical_key, display_name, created_by_event_id "
            "from graph_nodes where org_id = :o and valid_to is null "
            "  and canonical_key is not null "
            "order by valid_from asc"), {"o": org_id}).all()

    registered = 0
    proposals = 0
    for start in range(0, len(nodes), _BATCH):
        with store.engine.begin() as conn:
            for node in nodes[start:start + _BATCH]:
                raised = register_node_identity(
                    conn, org_id=org_id, node_id=node.node_id,
                    node_type=node.node_type, canonical_key=node.canonical_key,
                    display_name=node.display_name,
                    event_id=node.created_by_event_id)
                registered += 1
                proposals += len(raised)
    return {"nodes_registered": registered, "merge_proposals_raised": proposals}


def backfill_correlations(store, org_id: str, *, limit: int | None = None) -> dict:
    """Group historical events into situations.

    The node set for an old event is recovered from the evidence it left behind: every
    fact, observation and node it created. That is the same material the live path uses
    — it just reads it back out of the graph instead of holding it in memory.

    Our own seats are excluded here exactly as in the live path. Without it, every
    outbound email in the tenant's history would anchor on our own company and the
    backfill would build one situation containing the entire business.
    """
    with store.engine.connect() as conn:
        internal = frozenset(r.e for r in conn.execute(text(
            "select lower(email) as e from org_seats "
            "where org_id = :o and active and email is not null"), {"o": org_id}) if r.e)

        events = conn.execute(text(
            "select se.event_id, se.occurred_at, se.parent_object_id, se.domain_hints "
            "from source_events se "
            "where se.org_id = :o and se.outcome = 'emitted' "
            "  and se.event_id not in ("
            "    select event_id from context_correlation_members where org_id = :o) "
            "order by se.occurred_at asc nulls last" +
            (" limit :lim" if limit else "")),
            {"o": org_id, **({"lim": limit} if limit else {})}).all()
        if not events:
            return {"events_seen": 0, "events_correlated": 0}

        # Nodes an event touched, recovered from what it created. One query for the whole
        # tenant beats one per event by orders of magnitude on a real history.
        touched: dict[str, dict[str, str]] = {}
        for row in conn.execute(text(
                "select ev, node_id, node_type, canonical_key from ("
                "  select f.created_by_event_id as ev, n.node_id, n.node_type, n.canonical_key "
                "  from graph_facts f join graph_nodes n on n.org_id = f.org_id "
                "    and n.node_id = f.subject_node_id and n.valid_to is null "
                "  where f.org_id = :o and f.created_by_event_id is not null "
                "  union "
                "  select o2.created_by_event_id as ev, n.node_id, n.node_type, n.canonical_key "
                "  from graph_observations o2 join graph_nodes n on n.org_id = o2.org_id "
                "    and n.node_id = o2.subject_node_id and n.valid_to is null "
                "  where o2.org_id = :o and o2.created_by_event_id is not null "
                "  union "
                "  select n.created_by_event_id as ev, n.node_id, n.node_type, n.canonical_key "
                "  from graph_nodes n "
                "  where n.org_id = :o and n.valid_to is null "
                "    and n.created_by_event_id is not null"
                ") reached"), {"o": org_id}):
            if (row.canonical_key or "").lower() in internal:
                continue                       # our own people never anchor a situation
            touched.setdefault(row.ev, {})[row.node_id] = row.node_type

    correlated = 0
    for start in range(0, len(events), _BATCH):
        with store.engine.begin() as conn:
            for event in events[start:start + _BATCH]:
                nodes = touched.get(event.event_id)
                if not nodes:
                    continue                   # anchored nothing — correctly uncorrelated
                if correlate_event(conn, org_id=org_id, event_id=event.event_id,
                                   occurred_at=event.occurred_at,
                                   thread_id=event.parent_object_id,
                                   node_types=nodes,
                                   domain_hints=event.domain_hints):
                    correlated += 1
    return {"events_seen": len(events), "events_correlated": correlated}


def backfill_layer2(store, org_id: str, *, limit: int | None = None) -> dict:
    """The whole of Layer 2 applied to existing history, in the only order that works."""
    aliases = backfill_aliases(store, org_id)
    correlations = backfill_correlations(store, org_id, limit=limit)
    situations = refresh_situations(store, org_id)
    return {**aliases, **correlations, "situations_written": situations}
