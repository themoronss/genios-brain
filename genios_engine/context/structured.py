from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from genios_engine.context.correlation import correlate_event
from genios_engine.context.graph_store import GraphStore

# B1 — Structured lane. Structured events (calendar / CRM / client-DB) already carry typed
# fields (L1 mapped them via the registry). We write them straight to the graph — NO LLM,
# confidence 1.0, authority R3 (configured system-of-record). This is the cost hero.

# A meeting with more than this many people is a webinar / mass event, not a set of 1:1
# relationships (mirrors the email path's _BULK_RECIPIENTS). Above it we do NOT turn each attendee
# into a person node + a situation — that floods the graph with meaningless "X attended Y"
# situations (against the MD: "a meeting is not a situation" / "when unsure, leave apart"). The
# attendee list is NOT lost — it stays as the meeting node's `attendees` fact — it just doesn't
# explode into nodes/edges/correlations. Small meetings keep per-person relationships.
_BULK_ATTENDEES = 10


@dataclass
class StructuredResult:
    event_id: str
    outcome: str                 # committed_structured
    node_id: str
    facts: int = 0
    edges: int = 0
    graph_version: int | None = None
    correlations: int = 0


def commit_structured(store: GraphStore, *, org_id: str, event_id: str, source: str,
                      source_object_id: str, structured_fields: dict, node_type: str,
                      occurred_at: datetime | None,
                      display_name: str | None = None,
                      relations: list[dict] | None = None,
                      internal_emails: frozenset[str] | None = None,
                      domain_hints: list | None = None) -> StructuredResult:
    with store.engine.begin() as conn:
        version = store.bump_version(conn, org_id)
        node = store.find_or_create_node(
            conn, org_id=org_id, node_type=node_type,
            canonical_key=f"{source}:{source_object_id}",
            display_name=display_name or source_object_id,   # readable title, not the raw id
            event_id=event_id)
        store.map_identity(conn, org_id=org_id, source=source,
                           source_object_id=source_object_id, node_id=node)
        fact_n = 0
        for field, value in (structured_fields or {}).items():
            if value in (None, ""):
                continue
            wrote = store.write_fact(
                conn, org_id=org_id, subject_node_id=node, field=field, value=value,
                value_type="string", confidence=1.0, occurred_at=occurred_at,
                event_id=event_id,
                evidence={"source_field": field, "source_object": source_object_id},
                source=source, authority_rank=3)      # R3 system-of-record
            if wrote:
                fact_n += 1
        # relationships → graph edges (person→attended→meeting, deal→about→company, …). The related
        # node is find-or-created by its own canonical_key (email for people) so it MERGES with the
        # same entity seen elsewhere, turning the graph from a scatter of nodes into a real network.
        # Bulk-event guard: a webinar's 100 attendees are not 100 relationships. We skip exploding
        # them into per-person nodes/edges/situations — but the data is NOT lost: the whole attendee
        # list is written as ONE `attendees` fact on the meeting node (store-don't-delete). The gcal
        # mapping never carried attendees as a field (only as relations), so without this the skip
        # would silently drop them. Non-person relations (e.g. a deal→company) are unaffected.
        attendee_keys = [r.get("canonical_key") for r in (relations or [])
                         if r.get("node_type") == "person" and r.get("canonical_key")]
        bulk_attendees = len(attendee_keys) > _BULK_ATTENDEES
        if bulk_attendees and store.write_fact(
                conn, org_id=org_id, subject_node_id=node, field="attendees", value=attendee_keys,
                value_type="string", confidence=1.0, occurred_at=occurred_at, event_id=event_id,
                evidence={"derived": "bulk attendee list", "count": len(attendee_keys)},
                source=source, authority_rank=3):
            fact_n += 1
        edge_n = 0
        related_nodes: dict[str, str] = {}
        for rel in (relations or []):
            if bulk_attendees and rel.get("node_type") == "person":
                continue                                  # data retained as the meeting's attendees fact
            other = store.find_or_create_node(
                conn, org_id=org_id, node_type=rel["node_type"],
                canonical_key=rel["canonical_key"], display_name=rel.get("display_name"),
                event_id=event_id)
            related_nodes[rel["canonical_key"]] = other
            frm, to = (other, node) if rel.get("direction", "in") == "in" else (node, other)
            wrote = store.write_edge(
                conn, org_id=org_id, edge_type=rel["edge_type"], from_node_id=frm, to_node_id=to,
                confidence=1.0, occurred_at=occurred_at, event_id=event_id,
                evidence={"relation": rel["edge_type"], "source_object": source_object_id},
                source=source, authority_rank=3)
            if wrote:
                edge_n += 1
        # CORRELATION — structured events must reach the same situations as email, or the
        # headline case fails: Slack + email say one thing, the CRM deal and the calendar
        # invite say the rest, and only two of the four ever meet. This lane was silent
        # until now, so every deal and every meeting sat outside every situation.
        #
        # The event's OWN node anchors when it is a business object (a deal); otherwise
        # the counterparties do (a meeting is not a situation — it is evidence within
        # one). Our own seats are removed: a calendar invite lists us as attendees, and
        # anchoring on ourselves files every meeting into one company-wide group.
        internal = internal_emails or frozenset()
        touched = {node: node_type}
        for rel in (relations or []):
            key = (rel.get("canonical_key") or "").strip().lower()
            if rel["node_type"] == "person" and key in internal:
                continue
            related = related_nodes.get(rel["canonical_key"])
            if related:
                touched[related] = rel["node_type"]
        correlations = correlate_event(
            conn, org_id=org_id, event_id=event_id, occurred_at=occurred_at,
            thread_id=None, node_types=touched, domain_hints=domain_hints)

        store.write_change(conn, org_id=org_id, graph_version=version, cause_event_id=event_id,
                           payload={"structured": True, "facts": fact_n, "edges": edge_n,
                                    "correlations": len(correlations)})
    return StructuredResult(event_id, "committed_structured", node, fact_n, edge_n, version,
                            correlations=len(correlations))
