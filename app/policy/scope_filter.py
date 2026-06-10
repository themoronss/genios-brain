"""
Scope filter — the brain's "who's allowed to read what" gate.

This is a pure helper. Given a base SQL query (SELECT against contacts /
contact_facts) and an agent's scope policy, it returns SQL fragments to
append to WHERE plus the bind params.

It is the single chokepoint per the Agent Registry PRD: scope is enforced
at the SQL layer — never as a prompt instruction, never as a post-filter
on a model response. If the policy says NSRCEL is invisible, the database
never returns the row.

The brain is still the brain (judgment, learning, recommendations). This
module only constrains what the brain reveals to a given downstream agent.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

# 13-type fact taxonomy (mig 070_fact_taxonomy.sql) — kept here for
# validation only. Source of truth is the DB CHECK constraint.
ALLOWED_FACT_TYPES = frozenset([
    "identity", "membership", "relation", "attendance", "mention",
    "thread_link", "ownership", "role", "permission", "deal_state",
    "engagement_state", "commitment", "meeting_state",
])

# Connectors recognised across the system. None = all allowed.
KNOWN_CONNECTORS = frozenset([
    "gmail", "calendar", "slack", "hubspot", "jira", "notion",
    "drive", "docs", "sheets", "manual", "inferred",
])


def empty_policy() -> dict:
    """Permissive default — used for legacy / brain keys / null policies."""
    return {
        "version": 1,
        "connectors": None,
        "segments": None,
        "fact_types": None,
        "exclude_tags": [],
        "max_age_days": 3650,
        "min_confidence": 0.0,
        # 'all' = master / brain key (sees every agent's ingested data)
        # 'own' = scoped agent (only sees interactions tagged with own agent_uuid
        #         or untagged/workspace-level rows like Gmail OAuth syncs)
        "data_visibility": "all",
    }


def normalize(policy: Optional[dict]) -> dict:
    """Coerce a policy_json into the canonical 7-field shape with safe defaults.

    Important: empty list ≠ None.
      - None means "all allowed" (no filter on this dimension).
      - []   means "block everything" — explicit denial (PRD §05 callout).
    """
    if not policy:
        return empty_policy()
    out = empty_policy()
    out.update({k: v for k, v in policy.items() if k in out})
    # Coerce list-typed fields, preserving the [] vs None distinction.
    for k in ("connectors", "segments", "fact_types", "exclude_tags"):
        v = out.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            v = [v]
        out[k] = list(v)
    # Bound numerics
    try:
        out["max_age_days"] = max(1, min(3650, int(out["max_age_days"])))
    except Exception:
        out["max_age_days"] = 3650
    try:
        out["min_confidence"] = max(0.0, min(1.0, float(out["min_confidence"])))
    except Exception:
        out["min_confidence"] = 0.0
    # data_visibility: only 'own' or 'all' allowed; default to 'all' (permissive)
    dv = str(out.get("data_visibility") or "all").lower()
    out["data_visibility"] = dv if dv in ("own", "all") else "all"
    return out


def is_unrestricted(policy: Optional[dict]) -> bool:
    """A no-op policy — equivalent to a brain/master key. Skip filtering entirely."""
    if not policy:
        return True
    p = normalize(policy)
    return (
        p["connectors"] is None
        and p["segments"] is None
        and p["fact_types"] is None
        and not p["exclude_tags"]
        and p["max_age_days"] >= 3650
        and p["min_confidence"] <= 0.0
        and p.get("data_visibility", "all") == "all"
    )


def policy_hash(policy: Optional[dict]) -> str:
    """Stable hash of a normalized policy — for context_calls.scope_hash."""
    p = normalize(policy)
    canonical = json.dumps(p, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def contact_clauses(
    policy: Optional[dict],
    contact_alias: str = "c",
    bind_prefix: str = "sf",
) -> tuple[str, dict[str, Any]]:
    """
    Build WHERE fragments + binds for the contacts table.

    Returns (sql_fragment, binds). The fragment starts with " AND " so it
    can be safely concatenated onto an existing WHERE clause. Empty string
    if no constraints apply.
    """
    if is_unrestricted(policy):
        return "", {}
    p = normalize(policy)
    a = contact_alias
    bp = bind_prefix
    parts: list[str] = []
    binds: dict[str, Any] = {}

    if p["segments"] is not None:
        # contacts.segment_id → graph_segments.cluster_type matches PRD's
        # "segment" concept. We accept either the cluster_type name OR a
        # raw segment uuid; assume cluster_type names for now (PRD shape).
        # Empty list means "block everything" per PRD §05 callout.
        if not p["segments"]:
            parts.append("FALSE")
        else:
            parts.append(
                f"EXISTS (SELECT 1 FROM graph_segments gs WHERE gs.id = {a}.segment_id "
                f"AND gs.cluster_type = ANY(:{bp}_segments))"
            )
            binds[f"{bp}_segments"] = p["segments"]

    if p["exclude_tags"]:
        parts.append(f"NOT ({a}.tags && :{bp}_excl_tags)")
        binds[f"{bp}_excl_tags"] = p["exclude_tags"]

    if not parts:
        return "", {}
    return " AND " + " AND ".join(parts), binds


def interaction_clauses(
    policy: Optional[dict],
    agent_uuid: Optional[str],
    interaction_alias: str = "i",
    bind_prefix: str = "siv",
) -> tuple[str, dict[str, Any]]:
    """
    Read-time interaction isolation between agents.

      - master (data_visibility='all')   → no filter (sees everything)
      - scoped (own) without agent_uuid  → no filter (defensive fail-open)
      - scoped (own) with agent_uuid     → an interaction is visible when ANY of:
          1. genuine workspace data — account_id IS NULL AND agent_uuid IS NULL
             (legacy rows / Gmail-OAuth-at-workspace);
          2. the agent itself ingested it — interactions.agent_uuid = me;
          3. the interaction's source-account is granted to the agent.

    Returns (sql_fragment, binds); fragment starts with ' AND ' so it can be
    concatenated onto an existing WHERE clause. Empty string when no filter
    applies.
    """
    if not agent_uuid:
        return "", {}
    p = normalize(policy)
    if p.get("data_visibility") != "own":
        return "", {}
    a = interaction_alias
    bp = bind_prefix
    binds = {f"{bp}_agent": agent_uuid}
    # Rule 1 deliberately requires agent_uuid IS NULL too. Without that,
    # bootstrap-ingested rows (account_id NULL but agent_uuid set) would leak
    # to every agent — that was the isolation bug this clause now closes.
    return (
        f" AND ("
        f"({a}.account_id IS NULL AND {a}.agent_uuid IS NULL)"
        f" OR {a}.agent_uuid = :{bp}_agent"
        f" OR EXISTS ("
        f"  SELECT 1 FROM agent_account_grants g "
        f"  WHERE g.agent_uuid = :{bp}_agent AND g.account_id = {a}.account_id"
        f"))"
    ), binds


def fact_clauses(
    policy: Optional[dict],
    fact_alias: str = "f",
    bind_prefix: str = "sf",
) -> tuple[str, dict[str, Any]]:
    """
    Build WHERE fragments + binds for contact_facts table.

    Filters: connectors (source), fact_types, max_age_days, min_confidence.
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
            parts.append(f"{a}.source = ANY(:{bp}_connectors)")
            binds[f"{bp}_connectors"] = p["connectors"]

    if p["fact_types"] is not None:
        if not p["fact_types"]:
            parts.append("FALSE")
        else:
            # Quietly drop unknown types so a typo in policy doesn't kill all data.
            valid = [t for t in p["fact_types"] if t in ALLOWED_FACT_TYPES]
            if not valid:
                parts.append("FALSE")
            else:
                parts.append(f"{a}.fact_type = ANY(:{bp}_fact_types)")
                binds[f"{bp}_fact_types"] = valid

    if p["max_age_days"] < 3650:
        parts.append(f"{a}.created_at > NOW() - (:{bp}_max_age || ' days')::interval")
        binds[f"{bp}_max_age"] = str(p["max_age_days"])

    if p["min_confidence"] > 0.0:
        parts.append(f"{a}.composite_score >= :{bp}_min_conf")
        binds[f"{bp}_min_conf"] = p["min_confidence"]

    if not parts:
        return "", {}
    return " AND " + " AND ".join(parts), binds


def is_entity_in_scope(
    db,
    org_id: str,
    entity_email_or_name: str,
    policy: Optional[dict],
    agent_uuid: Optional[str] = None,
) -> bool:
    """
    Pre-check: may the calling agent see any contact matching this entity?
    Used by /v1/context to return 404 not_in_scope without materialising the
    full bundle.

    Two gates:
      1. contact-level   — segment / exclude-tag scope (contact_clauses);
      2. interaction-level — the contact must have AT LEAST ONE interaction
         visible to the agent (interaction_clauses). This is what stops one
         agent from reading another agent's ingested contacts.
    """
    if is_unrestricted(policy):
        return True
    from sqlalchemy import text  # local import to keep this module SDK-importable

    frag, binds = contact_clauses(policy, contact_alias="c", bind_prefix="sfp")
    sql = (
        "SELECT c.id FROM contacts c WHERE c.org_id = :org_id "
        "AND (LOWER(TRIM(c.name)) = LOWER(TRIM(:ent)) OR LOWER(c.email) = LOWER(:ent))"
        + frag
        + " LIMIT 1"
    )
    binds = {**binds, "org_id": org_id, "ent": entity_email_or_name.strip()}
    row = db.execute(text(sql), binds).fetchone()
    if row is None:
        return False

    # Interaction-level gate. interaction_clauses returns '' for master agents
    # (data_visibility='all') and when agent_uuid is absent — in both cases the
    # contact-level check above is authoritative.
    ifrag, ibinds = interaction_clauses(policy, agent_uuid, interaction_alias="i")
    if not ifrag:
        return True
    irow = db.execute(
        text("SELECT 1 FROM interactions i WHERE i.contact_id = :cid" + ifrag + " LIMIT 1"),
        {**ibinds, "cid": row[0]},
    ).fetchone()
    return irow is not None


def filter_facts(
    facts: list[dict],
    policy: Optional[dict],
) -> list[dict]:
    """
    Post-filter helper for callers that already have a list of fact dicts in
    memory (e.g. precomputed bundles). Mirrors fact_clauses semantics.
    """
    if is_unrestricted(policy) or not facts:
        return facts
    p = normalize(policy)
    out = []
    for f in facts:
        if p["connectors"] is not None and f.get("source") not in (p["connectors"] or []):
            continue
        if p["fact_types"] is not None and f.get("fact_type") not in (p["fact_types"] or []):
            continue
        if p["min_confidence"] > 0.0 and float(f.get("composite_score") or 0) < p["min_confidence"]:
            continue
        out.append(f)
    return out
