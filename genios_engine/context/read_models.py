from __future__ import annotations

import json

from sqlalchemy import text

from genios_engine.context.graph_store import GraphStore

# B9 — read models. Compact projection per entity for L3/dashboard/cards. Rebuilt from the
# graph (facts + observations + edges) for the affected node; stored in context_read_models.

#: ⛔ L3-12 · WHICH NODE TYPES GET A SPECIALISED PROJECTION. This was an inline dict literal inside
#: `build_entity_360`, so "which entities have a tailored view" was a question you could only
#: answer by reading a function body — and `context_read_models.model_type` is free text whose
#: migration comment ends `-- company_360 | person_360 | deal_360 | ...`.
#:
#: The default is deliberate and is not a gap: an entity with no tailored projection still gets
#: `entity_360`, which carries its facts, observations and edges. What was missing is that ADDING A
#: NODE TYPE ASKED NOBODY whether it needed a view — it just silently became generic.
READ_MODELS: dict[str, str] = {
    "person": "person_360",
    "company": "company_360",
    "deal": "deal_360",
    "meeting": "meeting_360",
}

#: Every other node type. A real answer, not a fallback for an error.
DEFAULT_READ_MODEL = "entity_360"


def build_entity_360(store: GraphStore, *, org_id: str, node_id: str) -> dict | None:
    with store.engine.connect() as c:
        node = c.execute(text(
            "select node_type, display_name, canonical_key, identity_strength "
            "from graph_nodes where org_id=:o and node_id=:n and valid_to is null limit 1"),
            {"o": org_id, "n": node_id}).first()
        if node is None:
            return None
        # The stored 360 is ONE row per entity, served to every seat — so it carries no private
        # fact (§3.4). A seat's own private facts are merged per request (`private_facts_for`).
        private_clause = (" and visibility_scope is distinct from 'private'"
                          if c.dialect.name == "postgresql" else "")
        facts = c.execute(text(
            "select field, value, confidence, authority_rank, occurred_at from graph_facts "
            "where org_id=:o and subject_node_id=:n and valid_to is null and status='active'"
            + private_clause),
            {"o": org_id, "n": node_id}).fetchall()
        obs = c.execute(text(
            "select kind, occurred_at, confidence from graph_observations "
            "where org_id=:o and subject_node_id=:n and status='active' order by occurred_at desc"),
            {"o": org_id, "n": node_id}).fetchall()
        gv = c.execute(text("select graph_version from graph_versions where org_id=:o"),
                       {"o": org_id}).scalar()

    model_type = READ_MODELS.get(node.node_type, DEFAULT_READ_MODEL)
    payload = {
        "node_id": node_id, "node_type": node.node_type, "display_name": node.display_name,
        "canonical_key": node.canonical_key, "identity_strength": node.identity_strength,
        "facts": {f.field: {"value": (f.value if not isinstance(f.value, str) else f.value),
                            "confidence": float(f.confidence), "authority": f.authority_rank}
                  for f in facts},
        "observations": [{"kind": o.kind,
                          "at": o.occurred_at.isoformat() if o.occurred_at else None}
                         for o in obs],
    }
    with store.engine.begin() as c:
        c.execute(text(
            "insert into context_read_models (org_id, model_type, entity_id, payload, graph_version) "
            "values (:o, :mt, :e, cast(:p as jsonb), :v) "
            "on conflict (org_id, model_type, entity_id) do update set "
            "payload=excluded.payload, graph_version=excluded.graph_version, built_at=now()"),
            {"o": org_id, "mt": model_type, "e": node_id,
             "p": json.dumps(payload, default=str), "v": gv})
    return {"model_type": model_type, **payload}


def private_facts_for(store, *, org_id: str, node_id: str, viewer_email: str | None) -> dict:
    """The entity's PRIVATE facts this viewer is a principal of, shaped like the 360's `facts`.
    Empty for no viewer (an API key) and off PostgreSQL."""
    viewer = str(viewer_email or "").strip().lower()
    if not viewer:
        return {}
    with store.engine.connect() as c:
        if c.dialect.name != "postgresql":
            return {}
        rows = c.execute(text(
            "select field, value, confidence, authority_rank from graph_facts "
            "where org_id=:o and subject_node_id=:n and valid_to is null and status='active' "
            "and visibility_scope='private' and :v = any(visibility_principals)"),
            {"o": org_id, "n": node_id, "v": viewer}).fetchall()
    return {f.field: {"value": f.value, "confidence": float(f.confidence),
                      "authority": f.authority_rank} for f in rows}
