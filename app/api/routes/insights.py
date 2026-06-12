"""Insights & activity API — v2-native readers.

Reads from v2 tables only:
  proactive_insights  — g-i-4 fired insights (replaces v1 `insights`)
  graph_nodes / facts — counts that drive the "intelligence dimensions" tile
  decisions           — replaces v1 activity_log for the activity feed

v1 had `insights`, `graph_intelligence_dimensions`, `activity_log` —
all dropped in migration 0015.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

router = APIRouter()


@router.get("/api/org/{org_id}/insights")
def get_insights(org_id: str, priority: str = None, limit: int = 20,
                 db: Session = Depends(get_db)):
    """List fired proactive insights for an org. Priority filter is a no-op
    here — v2 insights don't carry an explicit priority column; the type is
    surfaced instead so the frontend can group them."""
    rows = db.execute(
        text("""
            SELECT id, type, primary_entity, derivation_chain_jsonb,
                   scores_jsonb, delivery_route, created_at
            FROM proactive_insights
            WHERE org_id = :org_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"org_id": org_id, "limit": min(limit, 50)},
    ).fetchall()

    # Map module priority labels (low/medium/high) to the legacy P1/P2/P3
    # ladder the dashboard expects. P1 = most urgent at the top.
    _PRIORITY_LABEL = {"high": "P1", "medium": "P2", "low": "P3"}

    def _shape(r):
        scores = r[4] if isinstance(r[4], dict) else {}
        chain = r[3]  # list[dict] for v2 / dict for legacy v1 — handled below
        return {
            "id": str(r[0]),
            "insight_type": r[1],
            # Prefer the rule-set priority (low/medium/high) when present —
            # that's what the module author calibrated. Fall back to route
            # when older rows lack it.
            "priority": (
                _PRIORITY_LABEL.get(scores.get("priority", ""))
                or ("P1" if r[5] == "push" else "P2" if r[5] == "review" else "P3")
            ),
            "category": scores.get("category")
            or (chain.get("category") if isinstance(chain, dict) else None)
            or "general",
            # The human headline lives in scores.title (new pipeline). Fall
            # back to a derived label so legacy rows still render readably.
            "title": (
                scores.get("title")
                or (chain.get("title") if isinstance(chain, dict) else None)
                or f"{r[1]}: {r[2]}"
            ),
            "detail": (
                scores.get("memory_view")
                or (chain.get("summary") if isinstance(chain, dict) else None)
                or ""
            ),
            "contact_id": None,
            # Prefer the actual client name; fall back to the entity id
            # so the row never renders blank.
            "contact_name": scores.get("client_name") or r[2],
            "metadata": {
                "scores": scores,
                "route": r[5],
                "rule_id": scores.get("rule_id"),
                "genios_view": scores.get("genios_view"),
                "invoice_id": r[2] if scores.get("rule_id") else None,
            },
            "generated_at": r[6].isoformat() if r[6] else None,
        }

    out = [_shape(r) for r in rows]
    if priority:
        out = [i for i in out if i["priority"] == priority]
    return {"insights": out, "total": len(out)}


@router.post("/api/org/{org_id}/insights/{insight_id}/dismiss")
def dismiss_insight(org_id: str, insight_id: str, db: Session = Depends(get_db)):
    """Record a 'dismissed' feedback row against the insight's signature.

    v2 doesn't have an is_dismissed column — suppression is keyed on
    (org_id, user_id, signature_hash) in insight_feedback. We look up the
    signature for this insight_id and write a dismissed row scoped to org.
    """
    row = db.execute(
        text("SELECT signature_hash FROM proactive_insights WHERE id = :id AND org_id = :org_id"),
        {"id": insight_id, "org_id": org_id},
    ).fetchone()
    if not row:
        return {"dismissed": False, "reason": "not_found"}

    db.execute(
        text("""
            INSERT INTO insight_feedback
                (id, org_id, user_id, signature_hash, action, created_at)
            VALUES (gen_random_uuid()::text, :org_id, :uid, :sig, 'dismissed', NOW())
        """),
        {"org_id": org_id, "uid": "__org__", "sig": row[0]},
    )
    db.commit()
    return {"dismissed": True}


@router.get("/api/org/{org_id}/intelligence-dimensions")
def get_intelligence_dimensions(org_id: str, db: Session = Depends(get_db)):
    """Compute the 4 dimension % from v2 graph state instead of the dropped
    `graph_intelligence_dimensions` snapshot table.

    Dimensions are simple coverage ratios over the org's graph_nodes:
      relationship — entity nodes with at least one edge
      authority    — entity nodes with role/title/seniority facts
      state        — entity nodes with a recent (≤30d) state-typed fact
      precedent    — entity nodes referenced in ≥2 decisions
    """
    counts = db.execute(
        text("""
            WITH ents AS (
                SELECT id, canonical_name FROM graph_nodes
                WHERE org_id = :oid AND type = 'entity'
            ),
            rel AS (
                SELECT COUNT(DISTINCT n.id) c
                FROM ents n JOIN graph_edges e
                  ON e.org_id = :oid AND (e.from_node = n.id OR e.to_node = n.id)
            ),
            auth AS (
                SELECT COUNT(DISTINCT n.canonical_name) c
                FROM ents n JOIN facts f
                  ON f.org_id = :oid AND f.subject = n.canonical_name
                  AND f.predicate IN ('role', 'title', 'seniority', 'works_at')
            ),
            st AS (
                SELECT COUNT(DISTINCT n.canonical_name) c
                FROM ents n JOIN facts f
                  ON f.org_id = :oid AND f.subject = n.canonical_name
                  AND f.created_at >= NOW() - INTERVAL '30 days'
            ),
            prec AS (
                SELECT COUNT(*) c FROM decisions
                WHERE org_id = :oid
                  AND created_at >= NOW() - INTERVAL '30 days'
            ),
            total AS (SELECT GREATEST(COUNT(*), 1)::float c FROM ents)
            SELECT
                ROUND((rel.c::float  / total.c) * 100)::int AS relationship_pct,
                ROUND((auth.c::float / total.c) * 100)::int AS authority_pct,
                ROUND((st.c::float   / total.c) * 100)::int AS state_pct,
                LEAST(100, prec.c)::int                      AS precedent_pct
            FROM rel, auth, st, prec, total
        """),
        {"oid": org_id},
    ).fetchone()

    tools = db.execute(
        text("SELECT DISTINCT source_type FROM connections WHERE org_id = :oid AND status = 'active'"),
        {"oid": org_id},
    ).fetchall()

    return {
        "relationship_pct": float((counts[0] if counts else 0) or 0),
        "authority_pct":   float((counts[1] if counts else 0) or 0),
        "state_pct":       float((counts[2] if counts else 0) or 0),
        "precedent_pct":   float((counts[3] if counts else 0) or 0),
        "connected_tools": [t[0] for t in tools],
        "computed_at": None,
    }


@router.get("/activity")
def get_activity_feed(org_id: str, limit: int = 20, db: Session = Depends(get_db)):
    """Recent decisions (v2 replacement for v1 activity_log)."""
    rows = db.execute(
        text("""
            SELECT route, module_id, confidence_score, created_at
            FROM decisions
            WHERE org_id = :oid
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"oid": org_id, "limit": min(limit, 50)},
    ).fetchall()

    return {
        "events": [
            {
                "event_type": f"decision.{r[0]}",
                "event_data": {"module": r[1], "confidence": float(r[2] or 0)},
                "created_at": r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ],
        "total": len(rows),
    }
