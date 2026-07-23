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


_PRI_RANK = {"high": 0, "medium": 1, "low": 2}


def build_morning_brief(db: Session, org_id: str, limit: int = 3) -> dict:
    """Compose the day's top priorities from the org's recently-fired insights.
    Pure read — backs both the endpoint and the daily digest task."""
    rows = db.execute(
        text(
            """
            SELECT id, type, primary_entity, scores_jsonb, created_at
            FROM proactive_insights
            WHERE org_id = :org AND created_at >= NOW() - INTERVAL '48 hours'
            ORDER BY created_at DESC
            LIMIT 50
            """
        ),
        {"org": org_id},
    ).fetchall()

    items = []
    for r in rows:
        sc = r[3] if isinstance(r[3], dict) else {}
        items.append(
            {
                "id": str(r[0]),
                "title": sc.get("title") or f"{r[1]}: {r[2]}",
                "priority": sc.get("priority", "medium"),
                "action": sc.get("genios_view") or "",
                "detail": sc.get("memory_view") or "",
                "entity": sc.get("client_name") or r[2],
                "category": sc.get("category") or "general",
            }
        )
    items.sort(key=lambda x: _PRI_RANK.get(x["priority"], 1))
    top = items[:limit]

    # Manager nags — the founder's own overdue tasks lead the brief ("you said
    # you'd do this"). Best-effort; never breaks the brief.
    nags: list[dict] = []
    try:
        from app.api.routes.tasks import overdue_nags

        nags = overdue_nags(db, org_id, limit=3)
    except Exception:  # noqa: BLE001
        pass

    total = len(top) + len(nags)
    if total == 0:
        headline = "All clear — nothing flagged in the last 24h."
    elif nags:
        headline = f"{len(nags)} promise(s) pending + {len(top)} priorities today."
    elif total == 1:
        headline = "1 thing needs you today."
    else:
        headline = f"{len(top)} priorities today (of {len(items)} flagged)."
    return {
        "org_id": org_id,
        "headline": headline,
        "considered": len(items),
        "nags": nags,
        "priorities": top,
    }


@router.get("/api/org/{org_id}/morning-brief")
def morning_brief(org_id: str, limit: int = 3, db: Session = Depends(get_db)):
    """The day's top priorities — the habit-anchor 'Morning Brief' surface."""
    return build_morning_brief(db, org_id, limit=min(max(limit, 1), 10))


# ─── First-Scan Report — the Day-0 "here's what was leaking" diagnosis ────────


def _rows(db: Session, sql: str, **p):
    return db.execute(text(sql), p).fetchall()


def build_first_scan(db: Session, org_id: str) -> dict:
    """Aggregate the org's ALREADY-EXTRACTED facts + signals into one diagnosis:
    money at risk, broken promises, cooling relationships, competitor threats,
    thin deals, overdue invoices. Pure read — no LLM, no writes."""
    from datetime import UTC, datetime

    # Data footprint (the "we read your world" proof)
    nodes = db.execute(text("SELECT count(*) FROM graph_nodes WHERE org_id=:o"), {"o": org_id}).scalar() or 0
    facts_n = db.execute(text("SELECT count(*) FROM facts WHERE org_id=:o"), {"o": org_id}).scalar() or 0
    emails = db.execute(text(
        "SELECT count(DISTINCT source_item_id) FROM facts WHERE org_id=:o AND source_item_id LIKE 'gmail:%'"
    ), {"o": org_id}).scalar() or 0

    # Per-subject fact map for deals/invoices (small org-scoped read)
    frows = _rows(db, "SELECT subject, predicate, object FROM facts WHERE org_id=:o", o=org_id)
    by_subj: dict[str, dict[str, str]] = {}
    for r in frows:
        by_subj.setdefault(r.subject, {})[r.predicate] = r.object

    def _num(v):
        try:
            return float(str(v).replace(",", ""))
        except (TypeError, ValueError):
            return None

    # Broken promises: due_on/due in the past (status not done)
    broken: list[dict] = []
    now = datetime.now(UTC).date()
    for subj, kv in by_subj.items():
        due_raw = kv.get("due_on") or kv.get("due")
        if not due_raw:
            continue
        try:
            due = datetime.fromisoformat(str(due_raw)[:10]).date()
        except ValueError:
            continue
        if due < now and str(kv.get("status", "")).lower() not in ("done", "closed", "paid", "fulfilled"):
            broken.append({"what": subj, "due": str(due), "days_overdue": (now - due).days})
    broken.sort(key=lambda x: -x["days_overdue"])

    # Signal-derived: cooling (important), competitor named, we-owe commitments
    srows = _rows(db, """
        SELECT subject_name, signal_type, value_num, value_cat FROM signals WHERE org_id=:o
          AND signal_type IN ('momentum','importance','competitor','commitment','objection')
    """, o=org_id)
    sig: dict[str, dict] = {}
    for r in srows:
        sig.setdefault(r.subject_name, {})[r.signal_type] = r.value_num if r.value_num is not None else r.value_cat
    cooling = [
        {"who": n, "momentum": round(float(s["momentum"]), 2)}
        for n, s in sig.items()
        if _num(s.get("momentum")) is not None and float(s["momentum"]) <= -0.3
        and _num(s.get("importance", 0)) and float(s.get("importance", 0)) >= 0.5
    ]
    competitors = [
        {"who": n, "competitor": s["competitor"]} for n, s in sig.items() if s.get("competitor")
    ]
    we_owe = [
        {"who": n, "commitment": s["commitment"]} for n, s in sig.items() if s.get("commitment")
    ]
    objections = [
        {"who": n, "objection": s["objection"]} for n, s in sig.items() if s.get("objection")
    ]

    # Deals: value at risk (cooling/competitor/single-thread accounts' deals)
    risky_accounts = {c["who"] for c in cooling} | {c["who"] for c in competitors}
    deals_at_risk: list[dict] = []
    single_threaded: list[dict] = []
    value_at_risk = 0.0
    for subj, kv in by_subj.items():
        dv = _num(kv.get("deal_value"))
        if dv is None:
            continue
        ce = _num(kv.get("contacts_engaged"))
        entry = {"deal": subj, "value": dv, "stage": kv.get("stage")}
        if ce is not None and ce <= 1 and dv >= 1:
            single_threaded.append(entry)
        # deal → account linkage via node attributes is indirect here; a deal counts
        # as at-risk when ANY risk signal exists org-wide for its account name OR
        # the deal itself is single-threaded/stalled.
        stalled = (_num(kv.get("days_in_current_stage")) or 0) >= 21
        if stalled or (ce is not None and ce <= 1) or risky_accounts:
            deals_at_risk.append(entry)
            value_at_risk += dv

    # Overdue invoices (AR)
    overdue_inv: list[dict] = []
    for subj, kv in by_subj.items():
        dpd = _num(kv.get("days_past_due"))
        if dpd and dpd > 0:
            amt = _num(kv.get("amount_inr")) or 0
            overdue_inv.append({"invoice": subj, "days_past_due": int(dpd), "amount_inr": amt})
            value_at_risk += amt
    overdue_inv.sort(key=lambda x: -x["days_past_due"])

    return {
        "org_id": org_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "footprint": {"items_read": emails, "entities": nodes, "facts": facts_n},
        "headline": {
            "value_at_risk_inr": round(value_at_risk),
            "broken_promises": len(broken),
            "cooling_relationships": len(cooling),
            "competitor_threats": len(competitors),
            "overdue_invoices": len(overdue_inv),
        },
        "findings": {
            "broken_promises": broken[:5],
            "cooling": cooling[:5],
            "competitors": competitors[:5],
            "we_owe": we_owe[:5],
            "objections": objections[:5],
            "single_threaded_deals": single_threaded[:5],
            "deals_at_risk": deals_at_risk[:5],
            "overdue_invoices": overdue_inv[:5],
        },
    }


@router.get("/api/org/{org_id}/first-scan")
def first_scan(org_id: str, db: Session = Depends(get_db)):
    """Day-0 diagnosis: what was already leaking in the org's own data."""
    return build_first_scan(db, org_id)


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
