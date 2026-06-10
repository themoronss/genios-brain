"""V2 scope enforcement — SQL helpers for graph_nodes / facts / graph_edges.

Mirrors the contract of app/policy/scope_filter.py but for the v2 thin-pipe
schema. Per agent_scopes.policy_json, returns WHERE-clause fragments + bind
parameters that the caller appends to their SELECT.

Per MD spec (Agent Registry PRD §05):
  - Scope is enforced at the SQL layer, NEVER post-filter on model output.
  - empty list ([]) means "block everything" (explicit denial), not "all".
  - None means "no filter on this dimension".

Policy dimensions and their v2 mapping:
  connectors      → source_item_id prefix match  (e.g. "gmail:" / "slack:")
  segments        → graph_nodes.attributes->>'segment' membership
  fact_types      → facts.predicate ∈ predicate-set (mapped from 13-type
                    taxonomy via _TYPE_TO_PREDICATES)
  exclude_tags    → graph_nodes.attributes->'tags' overlap
  max_age_days    → facts.created_at > NOW() - interval
  min_confidence  → facts.confidence >= float
  data_visibility → 'own' filters to source_item_ids tagged with this agent
                    (extracted from sync_runner's source_id); 'all' (default)
                    is no filter.
"""

from __future__ import annotations

from typing import Any, Optional

# Re-export the canonical policy shape utilities so callers don't need two
# imports. v1 and v2 share the same agent_scopes.policy_json structure.
from app.policy.scope_filter import (
    ALLOWED_FACT_TYPES,
    KNOWN_CONNECTORS,
    is_unrestricted,
    normalize,
)

# Map the 13-type v1 fact taxonomy to v2 predicate groups so existing policies
# (saved against v1 type names) still meaningfully scope v2 facts.
_TYPE_TO_PREDICATES: dict[str, list[str]] = {
    "identity":         ["is", "has_name", "has_email"],
    "membership":       ["member_of", "works_at", "employed_by", "belongs_to"],
    "relation":         ["knows", "introduced_by", "sent_message_to", "received_from"],
    "attendance":       ["attended", "co_attended", "scheduled_for", "joined"],
    "mention":          ["mentioned", "referenced", "linked_to"],
    "thread_link":      ["reply_of", "in_thread", "responds_to"],
    "ownership":        ["owns", "owned_by", "responsible_for"],
    "role":             ["role", "title", "seniority"],
    "permission":       ["can", "may", "granted"],
    "deal_state":       ["state", "stage", "status"],
    "engagement_state": ["interested_in", "engaged_with", "responding_to"],
    "commitment":       ["committed_to", "will_do", "promised", "agreed_to",
                          "follow_up", "scheduled", "due", "should_do"],
    "meeting_state":    ["scheduled_for", "happened_at", "cancelled"],
}


def fact_clauses_v2(
    policy: Optional[dict],
    fact_alias: str = "f",
    bind_prefix: str = "sfv2",
) -> tuple[str, dict[str, Any]]:
    """Build WHERE fragments + binds for the v2 `facts` table.

    Filters: connectors (source_item_id prefix), fact_types (predicate),
    max_age_days (created_at), min_confidence (confidence).

    Fragment starts with " AND " so it can be safely appended. Empty when
    the policy is unrestricted.
    """
    if is_unrestricted(policy):
        return "", {}
    p = normalize(policy)
    a = fact_alias
    bp = bind_prefix
    parts: list[str] = []
    binds: dict[str, Any] = {}

    if p["connectors"] is not None:
        if not p["connectors"]:
            parts.append("FALSE")
        else:
            # source_item_id is shaped 'gmail:<hash>' / 'slack:<hash>' etc.
            # We OR together "starts with X:" for each allowed connector.
            prefix_clauses = []
            for i, c in enumerate(p["connectors"]):
                key = f"{bp}_c{i}"
                prefix_clauses.append(f"{a}.source_item_id LIKE :{key}")
                binds[key] = f"{c}:%"
            parts.append("(" + " OR ".join(prefix_clauses) + ")")

    if p["fact_types"] is not None:
        if not p["fact_types"]:
            parts.append("FALSE")
        else:
            preds: list[str] = []
            for t in p["fact_types"]:
                if t in _TYPE_TO_PREDICATES:
                    preds.extend(_TYPE_TO_PREDICATES[t])
                elif t in ALLOWED_FACT_TYPES:
                    # Caller named a known v1 type with no v2 mapping — block
                    # silently rather than fail open.
                    pass
                else:
                    # Free-form predicate the caller passed through directly.
                    preds.append(t)
            preds = sorted(set(preds))
            if not preds:
                parts.append("FALSE")
            else:
                parts.append(f"{a}.predicate = ANY(:{bp}_predicates)")
                binds[f"{bp}_predicates"] = preds

    if p["max_age_days"] < 3650:
        parts.append(f"{a}.created_at > NOW() - (:{bp}_max_age || ' days')::interval")
        binds[f"{bp}_max_age"] = str(p["max_age_days"])

    if p["min_confidence"] > 0.0:
        parts.append(f"{a}.confidence >= :{bp}_min_conf")
        binds[f"{bp}_min_conf"] = p["min_confidence"]

    if not parts:
        return "", {}
    return " AND " + " AND ".join(parts), binds


def node_clauses_v2(
    policy: Optional[dict],
    node_alias: str = "n",
    bind_prefix: str = "snv2",
) -> tuple[str, dict[str, Any]]:
    """Build WHERE fragments + binds for the v2 `graph_nodes` table.

    Filters: connectors (any source_item_ids entry prefix matches),
    segments (attributes->>'segment'), exclude_tags (attributes->'tags'
    overlap), max_age_days (last_seen).
    """
    if is_unrestricted(policy):
        return "", {}
    p = normalize(policy)
    a = node_alias
    bp = bind_prefix
    parts: list[str] = []
    binds: dict[str, Any] = {}

    if p["connectors"] is not None:
        if not p["connectors"]:
            parts.append("FALSE")
        else:
            like_clauses = []
            for i, c in enumerate(p["connectors"]):
                key = f"{bp}_c{i}"
                like_clauses.append(
                    f"EXISTS (SELECT 1 FROM jsonb_array_elements_text("
                    f"  CASE jsonb_typeof({a}.source_item_ids::jsonb)"
                    f"       WHEN 'array' THEN {a}.source_item_ids::jsonb"
                    f"       ELSE '[]'::jsonb END"
                    f") AS i WHERE i LIKE :{key})"
                )
                binds[key] = f"{c}:%"
            parts.append("(" + " OR ".join(like_clauses) + ")")

    if p["segments"] is not None:
        if not p["segments"]:
            parts.append("FALSE")
        else:
            parts.append(
                f"({a}.attributes->>'segment') = ANY(:{bp}_segments)"
            )
            binds[f"{bp}_segments"] = p["segments"]

    if p["exclude_tags"]:
        # attributes->'tags' is expected to be a JSON array. Exclude when any
        # tag in the row overlaps the excluded set.
        parts.append(
            f"NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text("
            f"  CASE jsonb_typeof(COALESCE({a}.attributes->'tags', '[]'::jsonb))"
            f"       WHEN 'array' THEN {a}.attributes->'tags'"
            f"       ELSE '[]'::jsonb END"
            f") AS t WHERE t = ANY(:{bp}_excl_tags))"
        )
        binds[f"{bp}_excl_tags"] = p["exclude_tags"]

    if p["max_age_days"] < 3650:
        parts.append(f"{a}.last_seen > NOW() - (:{bp}_max_age || ' days')::interval")
        binds[f"{bp}_max_age"] = str(p["max_age_days"])

    if not parts:
        return "", {}
    return " AND " + " AND ".join(parts), binds


def edge_clauses_v2(
    policy: Optional[dict],
    edge_alias: str = "e",
    bind_prefix: str = "sev2",
) -> tuple[str, dict[str, Any]]:
    """Build WHERE fragments + binds for the v2 `graph_edges` table.

    The only meaningful policy-level filter for edges is age (asserted_at) and
    confidence (weight). Connector/segment/fact-type don't map naturally to
    edges — they're enforced one hop away via node_clauses_v2 on the endpoints.
    """
    if is_unrestricted(policy):
        return "", {}
    p = normalize(policy)
    a = edge_alias
    bp = bind_prefix
    parts: list[str] = []
    binds: dict[str, Any] = {}

    if p["max_age_days"] < 3650:
        parts.append(f"{a}.asserted_at > NOW() - (:{bp}_max_age || ' days')::interval")
        binds[f"{bp}_max_age"] = str(p["max_age_days"])

    if p["min_confidence"] > 0.0:
        parts.append(f"{a}.weight >= :{bp}_min_conf")
        binds[f"{bp}_min_conf"] = p["min_confidence"]

    if not parts:
        return "", {}
    return " AND " + " AND ".join(parts), binds


def is_node_in_scope_v2(
    db,
    org_id: str,
    node_name: str,
    policy: Optional[dict],
) -> bool:
    """Pre-check: may the calling agent see ANY node matching this name?

    Used by /context to return 404 not_in_scope without materialising a bundle.
    """
    if is_unrestricted(policy):
        return True
    from sqlalchemy import text

    frag, binds = node_clauses_v2(policy, node_alias="n", bind_prefix="snip")
    sql = (
        "SELECT n.id FROM graph_nodes n WHERE n.org_id = :org_id "
        "AND LOWER(n.canonical_name) = LOWER(:name)"
        + frag
        + " LIMIT 1"
    )
    binds = {**binds, "org_id": org_id, "name": node_name.strip()}
    row = db.execute(text(sql), binds).fetchone()
    return row is not None


def filter_facts_v2(
    facts: list[dict],
    policy: Optional[dict],
) -> list[dict]:
    """In-memory filter for facts already loaded (e.g. inside engine fusion).

    Mirrors fact_clauses_v2 semantics so callers that can't push down SQL
    (because the facts came from a graph traversal step) still respect scope.
    """
    if is_unrestricted(policy) or not facts:
        return facts
    p = normalize(policy)
    out = []
    for f in facts:
        sid = (f.get("source_item_id") or "")
        if p["connectors"] is not None:
            if not p["connectors"]:
                continue
            if not any(sid.startswith(f"{c}:") for c in p["connectors"]):
                continue
        if p["fact_types"] is not None:
            allowed_preds: set[str] = set()
            for t in p["fact_types"] or []:
                allowed_preds.update(_TYPE_TO_PREDICATES.get(t, [t]))
            if not allowed_preds or f.get("predicate") not in allowed_preds:
                continue
        if p["min_confidence"] > 0.0 and float(f.get("confidence") or 0) < p["min_confidence"]:
            continue
        out.append(f)
    return out
