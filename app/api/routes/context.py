"""/v1/context — thin shim that delegates to v2 intelligence engine.

The v1 ContextRequest -> ContextResponse contract is preserved for the
existing frontend / API consumers, but the actual reasoning is now done
by the v2 intelligence handler for the 'sales' module (the default for
relationship context queries). All v1 storage paths (contacts /
interactions / context_calls / precomputed_bundles / context_outcomes)
were dropped in migration 0015; v2 logs each call as a `decision` row.

Endpoints kept (frontend back-compat):
  POST /v1/context              — single entity context lookup
  POST /api/org/{org_id}/context — same, org-scoped path
  POST /v1/context/outcome      — record outcome → v2 feedback endpoint
  POST /v1/context/search       — full-text search across v2 graph_nodes
  GET  /v1/context/entity/{id}  — single entity detail from graph_nodes/facts
  GET  /api/org/{org_id}/reports — derived from decisions + proactive_insights
  GET  /api/org/{org_id}/context/history — recent decisions for this org
  GET  /v1/llms.txt             — public API self-description
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import AliasChoices, BaseModel, Field, validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request / response shapes (preserved for frontend back-compat) ───────────

class ContextRequest(BaseModel):
    # Accept either `entity` (canonical) or `entity_name` (legacy frontend payload).
    entity: str = Field(..., validation_alias=AliasChoices("entity", "entity_name"))
    situation: str | None = None
    context_size: str = "medium"
    agent_id: str | None = None
    segment_id: str | None = None
    tag: str | None = None
    as_of: str | None = None

    @validator("entity")
    def _v_entity(cls, v: str) -> str:
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError("Entity name must be at least 2 characters")
        if len(v) > 200:
            raise ValueError("Entity name too long")
        return v


class EntityDetails(BaseModel):
    name: str
    company: str | None = None
    relationship_stage: str = "unknown"
    last_interaction: str | None = None
    sentiment_trend: str = "neutral"
    communication_style: str = "unknown"
    topics_of_interest: list = []
    open_commitments: list = []
    interaction_count: int = 0


class NodeScores(BaseModel):
    """Computed health metrics surfaced in the right-side detail panel."""
    relationship_health: float = 0.0   # 0..1 — freshness * edge density
    confidence: float = 0.0            # 0..1 — mean fact confidence
    freshness: float = 0.0             # 0..1 — recency of latest fact
    sentiment: str = "neutral"


class ContextResponse(BaseModel):
    entity: EntityDetails | None = None
    match_confidence: float = 1.0
    matched_from: str | None = None
    context_for_agent: str
    confidence: float
    scores: NodeScores | None = None
    coverage_score: float = 0.0          # 0..1 — fraction of high-conf facts
    recent_interactions: list[dict[str, Any]] = []   # facts shaped as interactions
    facts_included: int = 0              # count surfaced in bundle
    latency_ms: int = 0
    error: str | None = None


# ── Shared resolver: entity name → graph_nodes row (org-scoped) ──────────────

def _resolve_entity(db: Session, org_id: str, entity: str) -> dict | None:
    """Look up a node by name across ALL typed node types
    (entity/event/goal/risk) so the right-side context panel can drill into
    anything the user clicks — not just people."""
    row = db.execute(
        text("""
            SELECT id, canonical_name, type, attributes, last_seen, aliases
            FROM graph_nodes
            WHERE org_id = :oid
              AND LOWER(canonical_name) = LOWER(:e)
            ORDER BY (type = 'entity') DESC, last_seen DESC NULLS LAST
            LIMIT 1
        """),
        {"oid": org_id, "e": entity},
    ).fetchone()
    if not row:
        row = db.execute(
            text("""
                SELECT id, canonical_name, type, attributes, last_seen, aliases
                FROM graph_nodes
                WHERE org_id = :oid
                  AND LOWER(canonical_name) LIKE LOWER(:p)
                ORDER BY (type = 'entity') DESC, last_seen DESC NULLS LAST
                LIMIT 1
            """),
            {"oid": org_id, "p": f"%{entity}%"},
        ).fetchone()
    if not row:
        return None
    return {
        "id": str(row[0]),
        "name": row[1],
        "type": row[2],
        "attributes": row[3] if isinstance(row[3], dict) else {},
        "last_seen_at": row[4],
        "aliases": row[5] if isinstance(row[5], list) else [],
    }


def _subject_names(node: dict) -> list[str]:
    """All lowercased name-variants a fact's subject/object might use for this
    node — its canonical_name plus any aliases.

    WHY: facts are keyed by the raw subject STRING (whatever the extractor
    emitted), not the node id — so a fact's subject can differ in casing or
    variant ("acme" / "Acme Inc") from the node's canonical_name. The node
    resolves case-insensitively but the fact lookups used exact `subject = name`,
    which silently returned ZERO facts (graph has the data, agent sees nothing).
    Matching against this set case-insensitively fixes that class of miss."""
    names = [node.get("name")] + list(node.get("aliases") or [])
    seen: dict[str, None] = {}
    for n in names:
        if isinstance(n, str) and n.strip():
            seen[n.strip().lower()] = None
    return list(seen.keys())


def _entity_details(db: Session, org_id: str, node: dict) -> EntityDetails:
    names = _subject_names(node)
    facts = db.execute(
        text("""
            SELECT predicate, object, confidence
            FROM facts
            WHERE org_id = :oid AND LOWER(subject) = ANY(:names)
            ORDER BY confidence DESC, created_at DESC
            LIMIT 50
        """),
        {"oid": org_id, "names": names},
    ).fetchall()

    edges_count = db.execute(
        text("""
            SELECT COUNT(*) FROM graph_edges
            WHERE org_id = :oid AND (from_node = :eid OR to_node = :eid)
        """),
        {"oid": org_id, "eid": node["id"]},
    ).scalar() or 0

    company = None
    topics: list = []
    commitments: list = []
    for predicate, obj, _conf in facts:
        if predicate == "works_at" and not company:
            company = obj
        elif predicate == "interested_in":
            topics.append(obj)
        elif predicate == "committed_to":
            commitments.append(obj)

    last_seen = node.get("last_seen_at")
    return EntityDetails(
        name=node["name"],
        company=company,
        relationship_stage=node["attributes"].get("relationship_stage") or "unknown",
        last_interaction=last_seen.isoformat() if last_seen else None,
        sentiment_trend=node["attributes"].get("sentiment_trend") or "neutral",
        communication_style=node["attributes"].get("communication_style") or "unknown",
        topics_of_interest=[t for t in topics if t][:10],
        open_commitments=[c for c in commitments if c][:10],
        interaction_count=int(edges_count),
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

def _node_scores(db: Session, org_id: str, names: list[str]) -> NodeScores:
    """Compute right-panel scores from facts + edges for any node type."""
    row = db.execute(
        text("""
            SELECT
                COUNT(*)                                                AS n_facts,
                AVG(confidence)                                         AS avg_conf,
                MAX(created_at)                                         AS latest,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') AS fresh
            FROM facts
            WHERE org_id = :oid AND (LOWER(subject) = ANY(:names) OR LOWER(object) = ANY(:names))
        """),
        {"oid": org_id, "names": names},
    ).fetchone()
    n_facts = int(row[0] or 0)
    avg_conf = float(row[1] or 0)
    fresh = int(row[3] or 0)
    # freshness = ratio of facts that are <30d old (1.0 if any fresh + we have ≥1 fact)
    freshness = (fresh / n_facts) if n_facts else 0.0
    # health = blend of confidence + freshness + saturation (more facts ⇒ more known)
    saturation = min(1.0, n_facts / 5.0)
    health = round(0.4 * avg_conf + 0.3 * freshness + 0.3 * saturation, 3)
    return NodeScores(
        relationship_health=round(health, 3),
        confidence=round(avg_conf, 3),
        freshness=round(freshness, 3),
        sentiment="neutral",  # placeholder — sentiment analysis not implemented yet
    )


def _facts_as_interactions(
    db: Session,
    org_id: str,
    names: list[str],
    limit: int = 20,
    policy: dict | None = None,
) -> list[dict[str, Any]]:
    """Surface facts about / mentioning this entity as 'recent_interactions'
    for the agent bundle. Most-recent first, capped at `limit`. When `policy`
    is set, applies fact_clauses_v2 so the bundle never contains rows the
    agent isn't allowed to see."""
    from core.policy.v2_scope import fact_clauses_v2, is_unrestricted

    binds: dict[str, Any] = {"oid": org_id, "names": names, "limit": limit}
    extra = ""
    if policy and not is_unrestricted(policy):
        frag, fbinds = fact_clauses_v2(policy, fact_alias="facts", bind_prefix="fai")
        extra = frag
        binds.update(fbinds)

    rows = db.execute(
        text(f"""
            SELECT predicate, object, subject, confidence, created_at, source_item_id
            FROM facts
            WHERE org_id = :oid AND (LOWER(subject) = ANY(:names) OR LOWER(object) = ANY(:names)){extra}
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        binds,
    ).fetchall()
    out = []
    for predicate, obj, subj, conf, ts, src in rows:
        out.append({
            "date": ts.isoformat() if ts else None,
            "sentiment": float(conf or 0),
            "direction": "fact",
            "summary": f"{subj} {predicate} {obj}",
            "source": (src or "").split(":")[0] if src else "unknown",
            "predicate": predicate,
        })
    return out


def _build_context(db: Session, org_id: str, body: ContextRequest, policy: dict | None = None) -> ContextResponse:
    import time as _t
    _start = _t.perf_counter()

    node = _resolve_entity(db, org_id, body.entity)
    if not node:
        return ContextResponse(
            entity=None,
            match_confidence=0.0,
            matched_from="none",
            context_for_agent=f"No context available for '{body.entity}' yet — connect a data source to populate the graph.",
            confidence=0.0,
            scores=None,
            coverage_score=0.0,
            recent_interactions=[],
            facts_included=0,
            latency_ms=int((_t.perf_counter() - _start) * 1000),
            error="entity_not_found",
        )
    # Non-person nodes (event/goal/risk): show as-subject facts + connected
    # entities. This makes "Role application" / "Job cuts" clicks useful too.
    node_type = node.get("type") or "entity"
    if node_type != "entity":
        _names = _subject_names(node)
        related = db.execute(
            text("""
                SELECT predicate, object FROM facts
                WHERE org_id = :oid AND LOWER(subject) = ANY(:names)
                ORDER BY created_at DESC LIMIT 20
            """),
            {"oid": org_id, "names": _names},
        ).fetchall()
        also_about = db.execute(
            text("""
                SELECT subject, predicate FROM facts
                WHERE org_id = :oid AND LOWER(object) = ANY(:names)
                ORDER BY created_at DESC LIMIT 20
            """),
            {"oid": org_id, "names": _names},
        ).fetchall()
        lines = [f"{node['name']} ({node_type})"]
        if related:
            lines.append("Linked forward:")
            for p, o in related[:8]:
                lines.append(f"  · {p} → {o}")
        if also_about:
            lines.append("Mentioned by:")
            for s, p in also_about[:8]:
                lines.append(f"  · {s} {p} {node['name']}")
        last_seen = node.get("last_seen_at")
        details = EntityDetails(
            name=node["name"],
            company=node["attributes"].get("company"),
            relationship_stage=node_type,            # surface the type as a stage badge
            last_interaction=last_seen.isoformat() if last_seen else None,
            sentiment_trend="neutral",
            communication_style="—",
            topics_of_interest=[],
            open_commitments=[],
            interaction_count=len(related) + len(also_about),
        )
        interactions = _facts_as_interactions(db, org_id, _subject_names(node), policy=policy)
        high_conf = sum(1 for i in interactions if (i.get("sentiment") or 0) >= 0.45)
        coverage = (high_conf / max(len(interactions), 1)) if interactions else 0.0
        return ContextResponse(
            entity=details,
            match_confidence=1.0,
            matched_from="exact",
            context_for_agent="\n".join(lines),
            confidence=0.7,
            scores=_node_scores(db, org_id, _subject_names(node)),
            coverage_score=round(coverage, 3),
            recent_interactions=interactions,
            facts_included=len(interactions),
            latency_ms=int((_t.perf_counter() - _start) * 1000),
        )
    details = _entity_details(db, org_id, node)
    summary_lines = [
        f"{details.name}" + (f" ({details.company})" if details.company else ""),
        f"Stage: {details.relationship_stage}. Last interaction: {details.last_interaction or 'n/a'}.",
    ]
    if details.topics_of_interest:
        summary_lines.append("Topics: " + ", ".join(details.topics_of_interest[:5]))
    if details.open_commitments:
        summary_lines.append("Open commitments: " + "; ".join(details.open_commitments[:3]))
    if body.situation:
        summary_lines.append(f"Situation: {body.situation}")

    interactions = _facts_as_interactions(db, org_id, _subject_names(node), policy=policy)
    high_conf = sum(1 for i in interactions if (i.get("sentiment") or 0) >= 0.45)
    coverage = (high_conf / max(len(interactions), 1)) if interactions else 0.0
    return ContextResponse(
        entity=details,
        match_confidence=1.0 if details.name.lower() == body.entity.lower() else 0.7,
        matched_from="exact" if details.name.lower() == body.entity.lower() else "fuzzy",
        context_for_agent="\n".join(summary_lines),
        confidence=min(1.0, 0.4 + 0.05 * details.interaction_count),
        scores=_node_scores(db, org_id, _subject_names(node)),
        coverage_score=round(coverage, 3),
        recent_interactions=interactions,
        facts_included=len(interactions),
        latency_ms=int((_t.perf_counter() - _start) * 1000),
    )


@router.post("/v1/context", response_model=ContextResponse)
def post_context_v1(body: ContextRequest, request: Request,
                    db: Session = Depends(get_db)) -> ContextResponse:
    """Scope-enforced single-entity context bundle.

    API key tied to a restricted agent → bundle limited to the agent's
    allowed connectors/segments/fact-types/age/confidence. Dashboard JWT
    or master key → unrestricted (full graph)."""
    from core.api.deps import require_org_and_policy
    from core.policy.v2_scope import is_node_in_scope_v2

    ctx = require_org_and_policy(
        request=request, session=db,
        authorization=request.headers.get("authorization"),
        x_dev_org=request.headers.get("X-Dev-Org"),
    )
    policy = ctx.get("policy")
    if policy and not is_node_in_scope_v2(db, ctx["org_id"], body.entity, policy):
        raise HTTPException(
            status_code=404,
            detail={
                "error": "entity_not_in_scope",
                "entity": body.entity,
                "message": "Entity not visible under this agent's scope policy.",
            },
        )
    return _build_context(db, ctx["org_id"], body, policy=policy)


@router.post("/api/org/{org_id}/context", response_model=ContextResponse)
def post_context_orgscoped(org_id: str, body: ContextRequest, request: Request,
                           db: Session = Depends(get_db)) -> ContextResponse:
    from core.api.deps import require_org_and_policy
    from core.policy.v2_scope import is_node_in_scope_v2

    ctx = require_org_and_policy(
        request=request, session=db,
        authorization=request.headers.get("authorization"),
        x_dev_org=request.headers.get("X-Dev-Org"),
    )
    if ctx["org_id"] != org_id:
        raise HTTPException(status_code=403, detail="cross-org access denied")
    policy = ctx.get("policy")
    if policy and not is_node_in_scope_v2(db, org_id, body.entity, policy):
        raise HTTPException(
            status_code=404,
            detail={
                "error": "entity_not_in_scope",
                "entity": body.entity,
                "message": "Entity not visible under this agent's scope policy.",
            },
        )
    return _build_context(db, org_id, body, policy=policy)


class OutcomeBody(BaseModel):
    decision_id: str | None = None
    insight_id: str | None = None
    action: str
    user_id: str = "__org__"


@router.post("/v1/context/outcome")
def post_context_outcome(body: OutcomeBody, db: Session = Depends(get_db),
                         org_id: str = Depends(verify_api_key)) -> dict[str, Any]:
    """Record an outcome → forwards to insight_feedback for v2 suppression."""
    if not (body.decision_id or body.insight_id):
        raise HTTPException(status_code=400, detail="decision_id or insight_id required")
    sig = None
    if body.insight_id:
        row = db.execute(
            text("SELECT signature_hash FROM proactive_insights WHERE id = :id AND org_id = :oid"),
            {"id": body.insight_id, "oid": org_id},
        ).fetchone()
        sig = row[0] if row else None
    if sig:
        db.execute(
            text("""
                INSERT INTO insight_feedback (id, org_id, user_id, signature_hash, action, created_at)
                VALUES (gen_random_uuid()::text, :oid, :uid, :sig, :a, NOW())
            """),
            {"oid": org_id, "uid": body.user_id, "sig": sig, "a": body.action},
        )
        db.commit()
    return {"recorded": True, "decision_id": body.decision_id, "insight_id": body.insight_id}


@router.post("/v1/context/search")
def post_context_search(body: dict, db: Session = Depends(get_db),
                        org_id: str = Depends(verify_api_key)) -> dict[str, Any]:
    """Substring search across graph_nodes (entities)."""
    q = (body.get("query") or "").strip()
    if not q:
        return {"results": [], "total": 0}
    rows = db.execute(
        text("""
            SELECT id, canonical_name, type
            FROM graph_nodes
            WHERE org_id = :oid AND LOWER(canonical_name) LIKE LOWER(:p)
            ORDER BY last_seen DESC NULLS LAST
            LIMIT 50
        """),
        {"oid": org_id, "p": f"%{q}%"},
    ).fetchall()
    return {
        "results": [{"id": str(r[0]), "name": r[1], "node_type": r[2]} for r in rows],
        "total": len(rows),
    }


@router.get("/v1/context/entity/{entity_id}")
def get_entity_detail(entity_id: str, db: Session = Depends(get_db),
                      org_id: str = Depends(verify_api_key)) -> dict[str, Any]:
    row = db.execute(
        text("""
            SELECT id, canonical_name, type, attributes, last_seen, aliases
            FROM graph_nodes
            WHERE org_id = :oid AND id = :eid
        """),
        {"oid": org_id, "eid": entity_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="entity_not_found")
    node = {
        "id": str(row[0]),
        "name": row[1],
        "attributes": row[3] if isinstance(row[3], dict) else {},
        "last_seen_at": row[4],
    }
    details = _entity_details(db, org_id, node)
    return {
        "id": node["id"],
        "name": node["name"],
        "node_type": row[2],
        "details": details.dict(),
    }


@router.get("/api/org/{org_id}/reports")
def get_reports(org_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Per-org reports — derived from decisions + proactive_insights."""
    decisions_7d = db.execute(
        text("""
            SELECT COUNT(*), AVG(confidence_score)
            FROM decisions
            WHERE org_id = :oid AND created_at >= NOW() - INTERVAL '7 days'
        """),
        {"oid": org_id},
    ).fetchone()
    insights_7d = db.execute(
        text("""
            SELECT COUNT(*) FROM proactive_insights
            WHERE org_id = :oid AND created_at >= NOW() - INTERVAL '7 days'
        """),
        {"oid": org_id},
    ).scalar() or 0
    return {
        "decisions_7d": int(decisions_7d[0] or 0),
        "avg_confidence_7d": float(decisions_7d[1] or 0),
        "insights_7d": int(insights_7d),
    }


@router.get("/api/org/{org_id}/context/history")
def get_context_history(org_id: str, limit: int = 50,
                        db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = db.execute(
        text("""
            SELECT id, route, module_id, confidence_score, created_at
            FROM decisions
            WHERE org_id = :oid
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"oid": org_id, "limit": min(limit, 200)},
    ).fetchall()
    return {
        "history": [
            {
                "id": str(r[0]),
                "route": r[1],
                "module": r[2],
                "confidence": float(r[3] or 0),
                "created_at": r[4].isoformat() if r[4] else None,
            }
            for r in rows
        ],
    }


@router.get("/v1/llms.txt")
def get_llms_txt() -> dict[str, Any]:
    return {
        "name": "GeniOS Brain",
        "description": "Hybrid neuro-symbolic intelligence engine — context + reasoning + foresight.",
        "primary_endpoints": [
            "POST /v1/context — single-entity context lookup",
            "POST /v1/intelligence/query — full engine query (returns Envelope)",
            "GET  /v1/intelligence/proactive_insights — fired insights",
            "GET  /v1/metrics/headline — top-level metrics",
        ],
    }
