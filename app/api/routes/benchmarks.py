"""Public benchmarks scorecard.

Unauthenticated, aggregated-only, signed, Redis-cached. Never exposes per-org data.

Endpoint: GET /v1/benchmarks/scorecard
  - Returns the 4 hero numbers (Acted Rate, Latency p95, Faithfulness, ECE)
  - Plus per-detector AAR breakdown (insight_type only — no org_id, no titles)
  - Cached 1h in Redis; ETag for client cache; min-N gate for "insufficient data"

Anti-leak invariants:
  - No org_id, no contact_id, no email, no title, no body fields ever returned
  - Per-detector rows aggregate ≥3 orgs OR are suppressed
  - Min sample thresholds: AAR n≥500, Latency n≥1000, ECE n≥100
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

CACHE_KEY = "benchmarks:scorecard:v1"
CACHE_TTL = 3600  # 1h
SCORECARD_VERSION = "1.0.0"
WINDOW_DAYS = 30

MIN_AAR_SAMPLES = 500
MIN_LATENCY_SAMPLES = 1000
MIN_ECE_SAMPLES = 100
MIN_DETECTOR_SAMPLES = 50
MIN_ORGS_PER_DETECTOR = 3   # k-anonymity guard


def _aggregate_aar(db: Session, since: datetime) -> dict:
    """Cross-org AAR. Aggregates only — no org_id ever exits this function."""
    row = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE outcome = 'acted')     AS acted,
                COUNT(*) FILTER (WHERE outcome = 'dismissed') AS dismissed,
                COUNT(*) FILTER (WHERE outcome = 'ignored')   AS ignored,
                COUNT(*) FILTER (WHERE outcome IS NULL)       AS pending
            FROM recommendations
            WHERE created_at >= :since
        """),
        {"since": since},
    ).fetchone()
    acted = int(row.acted or 0)
    dismissed = int(row.dismissed or 0)
    ignored = int(row.ignored or 0)
    labelled = acted + dismissed + ignored
    if labelled < MIN_AAR_SAMPLES:
        return {"value": None, "n": labelled, "reason": "insufficient_data",
                "min_n": MIN_AAR_SAMPLES, "window_days": WINDOW_DAYS}
    return {
        "value": round(acted / labelled, 4),
        "n": labelled,
        "acted": acted,
        "dismissed": dismissed,
        "ignored": ignored,
        "window_days": WINDOW_DAYS,
    }


def _per_detector_aar(db: Session, since: datetime) -> list[dict]:
    """Per-insight_type AAR. Suppresses rows from <3 orgs (k-anonymity)."""
    rows = db.execute(
        text("""
            SELECT
                COALESCE(insight_type, 'unknown') AS insight_type,
                COUNT(DISTINCT org_id)                          AS n_orgs,
                COUNT(*) FILTER (WHERE outcome = 'acted')       AS acted,
                COUNT(*) FILTER (WHERE outcome = 'dismissed')   AS dismissed,
                COUNT(*) FILTER (WHERE outcome = 'ignored')     AS ignored
            FROM recommendations
            WHERE created_at >= :since
            GROUP BY COALESCE(insight_type, 'unknown')
            HAVING COUNT(DISTINCT org_id) >= :min_orgs
        """),
        {"since": since, "min_orgs": MIN_ORGS_PER_DETECTOR},
    ).fetchall()

    out = []
    for r in rows:
        a, d, i = int(r.acted or 0), int(r.dismissed or 0), int(r.ignored or 0)
        labelled = a + d + i
        if labelled < MIN_DETECTOR_SAMPLES:
            continue
        out.append({
            "insight_type": r.insight_type,
            "acted_rate": round(a / labelled, 4),
            "n": labelled,
            "n_orgs": int(r.n_orgs),
        })
    out.sort(key=lambda x: -x["n"])
    return out


def _aggregate_latency(db: Session, since: datetime) -> dict:
    """p50/p95/p99 across all paths + per-path breakdown."""
    overall = db.execute(
        text("""
            SELECT
                COUNT(*) AS n,
                percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
                percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99
            FROM context_calls
            WHERE called_at >= :since AND latency_ms IS NOT NULL
        """),
        {"since": since},
    ).fetchone()
    n = int(overall.n or 0)
    if n < MIN_LATENCY_SAMPLES:
        return {"value": None, "n": n, "reason": "insufficient_data",
                "min_n": MIN_LATENCY_SAMPLES, "window_days": WINDOW_DAYS}

    path_rows = db.execute(
        text("""
            SELECT
                COALESCE(cache_source, 'unknown') AS path,
                COUNT(*) AS n,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95
            FROM context_calls
            WHERE called_at >= :since AND latency_ms IS NOT NULL
            GROUP BY COALESCE(cache_source, 'unknown')
            ORDER BY n DESC
        """),
        {"since": since},
    ).fetchall()
    by_path = [
        {"path": r.path, "n": int(r.n or 0), "p95_ms": int(r.p95 or 0)}
        for r in path_rows
    ]

    return {
        "value_p95_ms": int(overall.p95 or 0),
        "p50_ms": int(overall.p50 or 0),
        "p99_ms": int(overall.p99 or 0),
        "n": n,
        "window_days": WINDOW_DAYS,
        "sla_p95_ms": 400,
        "by_path": by_path,
    }


def _aggregate_calibration(db: Session) -> dict:
    """Cross-org weighted ECE from calibration_models. Each org weighted by sample_count."""
    rows = db.execute(
        text("""
            SELECT ece, sample_count
            FROM calibration_models
            WHERE ece IS NOT NULL AND sample_count >= 20
        """),
    ).fetchall()
    if not rows:
        return {"value": None, "n": 0, "reason": "insufficient_data",
                "min_n": MIN_ECE_SAMPLES, "n_orgs": 0}

    total_n = sum(int(r.sample_count) for r in rows)
    if total_n < MIN_ECE_SAMPLES:
        return {"value": None, "n": total_n, "reason": "insufficient_data",
                "min_n": MIN_ECE_SAMPLES, "n_orgs": len(rows)}

    weighted_ece = sum(float(r.ece) * int(r.sample_count) for r in rows) / total_n
    return {
        "value": round(weighted_ece, 4),
        "n": total_n,
        "n_orgs": len(rows),
        "target": 0.10,
    }


def _faithfulness_proxy(db: Session, since: datetime) -> dict:
    """Faithfulness proxy until labeled gold set exists.

    Defined here as: % of context calls returning a non-null relationship_stage
    AND non-null confidence (i.e. the bundle had real graph state, not a degraded
    fallback). True faithfulness benchmark requires the labeled fixture set in
    benchmarks/fixtures/faithfulness_v1.jsonl — replaces this proxy when ready.
    """
    row = db.execute(
        text("""
            SELECT
                COUNT(*) AS n,
                COUNT(*) FILTER (
                    WHERE relationship_stage IS NOT NULL
                      AND confidence IS NOT NULL
                      AND confidence > 0
                ) AS grounded
            FROM context_calls
            WHERE called_at >= :since
        """),
        {"since": since},
    ).fetchone()
    n = int(row.n or 0)
    if n < MIN_LATENCY_SAMPLES:
        return {"value": None, "n": n, "reason": "insufficient_data",
                "min_n": MIN_LATENCY_SAMPLES, "method": "groundedness_proxy_v1"}
    return {
        "value": round(int(row.grounded) / n, 4),
        "n": n,
        "method": "groundedness_proxy_v1",
        "note": "Proxy metric. Replaced by labeled fixture set when faithfulness_v1.jsonl ships.",
        "window_days": WINDOW_DAYS,
    }


def _build_id() -> str:
    return os.getenv("BUILD_SHA", "dev")


def _sign(payload: dict) -> str:
    secret = os.getenv("BENCHMARK_SIGNING_SECRET", "").encode()
    if not secret:
        return ""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def _build_scorecard(db: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=WINDOW_DAYS)

    aar = _aggregate_aar(db, since)
    latency = _aggregate_latency(db, since)
    ece = _aggregate_calibration(db)
    faithfulness = _faithfulness_proxy(db, since)
    per_detector = _per_detector_aar(db, since)

    payload = {
        "version": SCORECARD_VERSION,
        "build_sha": _build_id(),
        "generated_at": now.isoformat(),
        "window_days": WINDOW_DAYS,
        "tier1": {
            "acted_rate": aar,
            "context_latency": latency,
            "faithfulness": faithfulness,
            "calibration_ece": ece,
        },
        "per_detector": per_detector,
        "methodology_url": "/v1/benchmarks/methodology",
        "anti_gaming": {
            "min_orgs_per_detector": MIN_ORGS_PER_DETECTOR,
            "min_aar_samples": MIN_AAR_SAMPLES,
            "min_latency_samples": MIN_LATENCY_SAMPLES,
            "min_ece_samples": MIN_ECE_SAMPLES,
            "pii_filter": "no_org_id_no_contact_id_no_titles",
        },
    }
    payload["signature"] = _sign(payload)
    return payload


def _etag(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return '"' + hashlib.sha256(body).hexdigest()[:16] + '"'


@router.get("/v1/benchmarks/scorecard")
def public_scorecard(response: Response, db: Session = Depends(get_db)):
    """Public, unauthenticated scorecard. 1h Redis cache. No PII."""
    try:
        cached = redis_client.get(CACHE_KEY)
    except Exception as e:
        logger.warning(f"redis get failed: {e}")
        cached = None

    if cached:
        payload = json.loads(cached)
        response.headers["X-Cache"] = "HIT"
    else:
        payload = _build_scorecard(db)
        try:
            redis_client.setex(CACHE_KEY, CACHE_TTL, json.dumps(payload))
        except Exception as e:
            logger.warning(f"redis set failed: {e}")
        response.headers["X-Cache"] = "MISS"

    etag = _etag(payload)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = f"public, max-age={CACHE_TTL}, stale-while-revalidate=600"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return payload


# ── Phase 8: Hero/dashboard endpoints (lightweight, no min-N gating) ──────────
# These supplement the rigorous scorecard above. They power:
#   • /v1/benchmarks       — hero numbers shown on the website
#   • /v1/benchmarks/live  — ticker for homepage live counters
#   • /v1/benchmarks/me    — per-org dashboard widget (auth required)
# The scorecard above is the SOURCE OF TRUTH for marketing claims (signed,
# k-anonymous, min-N gated). These are best-effort liveness signals.

@router.get("/v1/benchmarks")
def public_benchmarks_hero(db: Session = Depends(get_db)):
    """Lightweight aggregate numbers for the website hero. Phase 8."""

    latency = {"p50_ms": None, "p95_ms": None, "p99_ms": None, "samples": 0}
    try:
        row = db.execute(text("""
            SELECT
                percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
                percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms) AS p99,
                COUNT(*) AS n
            FROM context_calls
            WHERE called_at >= NOW() - INTERVAL '7 days'
              AND latency_ms IS NOT NULL
        """)).fetchone()
        if row:
            latency = {
                "p50_ms": int(row.p50) if row.p50 is not None else None,
                "p95_ms": int(row.p95) if row.p95 is not None else None,
                "p99_ms": int(row.p99) if row.p99 is not None else None,
                "samples": int(row.n or 0),
            }
    except Exception as e:
        logger.debug(f"benchmark hero latency failed: {e}")

    cost = {"avg_per_query_usd": 0.0, "total_30d_usd": 0.0, "queries_30d": 0}
    try:
        row = db.execute(text("""
            SELECT COALESCE(AVG(cost_usd),0) AS avg_cost,
                   COALESCE(SUM(cost_usd),0) AS total_cost,
                   COUNT(*) AS n
            FROM llm_usage
            WHERE called_at >= NOW() - INTERVAL '30 days'
        """)).fetchone()
        if row:
            cost = {
                "avg_per_query_usd": round(float(row.avg_cost or 0), 6),
                "total_30d_usd": round(float(row.total_cost or 0), 2),
                "queries_30d": int(row.n or 0),
            }
    except Exception:
        pass

    scale = {"orgs": 0, "contacts": 0, "interactions": 0,
             "decisions_today": 0, "recommendations_24h": 0}
    try:
        scale["orgs"] = db.execute(text("SELECT COUNT(*) FROM orgs")).scalar() or 0
        scale["contacts"] = db.execute(text(
            "SELECT COUNT(*) FROM contacts WHERE is_archived IS FALSE OR is_archived IS NULL"
        )).scalar() or 0
        scale["interactions"] = db.execute(text("SELECT COUNT(*) FROM interactions")).scalar() or 0
        scale["decisions_today"] = db.execute(text("""
            SELECT COUNT(*) FROM recommendations
            WHERE created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
        """)).scalar() or 0
        scale["recommendations_24h"] = db.execute(text("""
            SELECT COUNT(*) FROM recommendations
            WHERE created_at >= NOW() - INTERVAL '24 hours'
        """)).scalar() or 0
    except Exception:
        pass

    retention = {"high_risk_orgs": 0, "offers_pushed_7d": 0}
    try:
        retention["high_risk_orgs"] = db.execute(text("""
            SELECT COUNT(DISTINCT org_id) FROM engagement_health
            WHERE snapshot_date >= CURRENT_DATE - 7 AND churn_score >= 0.6
        """)).scalar() or 0
        retention["offers_pushed_7d"] = db.execute(text("""
            SELECT COUNT(*) FROM pending_alerts
            WHERE insight_type = 'retention_offer'
              AND created_at >= NOW() - INTERVAL '7 days'
        """)).scalar() or 0
    except Exception:
        pass  # tables may not exist on older deploys

    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "latency": latency,
        "cost": cost,
        "scale": scale,
        "retention": retention,
        "stack": {
            "detectors": "50+",
            "connectors": "9 (Gmail, Calendar, Slack, Jira, Notion, Drive, Docs, Sheets, HubSpot)",
            "live_fetch_p95_ms_target": 2500,
            "cached_p95_ms_target": 400,
        },
    }


@router.get("/v1/benchmarks/live")
def public_benchmarks_live(db: Session = Depends(get_db)):
    """Tiny ticker payload for homepage live counters. Phase 8."""
    try:
        decisions_today = db.execute(text("""
            SELECT COUNT(*) FROM recommendations
            WHERE created_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
        """)).scalar() or 0
        contacts_total = db.execute(text("""
            SELECT COUNT(*) FROM contacts
            WHERE is_archived IS FALSE OR is_archived IS NULL
        """)).scalar() or 0
        active_orgs_24h = db.execute(text("""
            SELECT COUNT(DISTINCT org_id) FROM context_calls
            WHERE called_at >= NOW() - INTERVAL '24 hours'
        """)).scalar() or 0
        live_fetches_today = db.execute(text("""
            SELECT COUNT(*) FROM interactions
            WHERE source IN ('gmail_live', 'calendar_live')
              AND interaction_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
        """)).scalar() or 0
    except Exception:
        decisions_today = contacts_total = active_orgs_24h = live_fetches_today = 0

    return {
        "decisions_today": int(decisions_today),
        "contacts_total": int(contacts_total),
        "active_orgs_24h": int(active_orgs_24h),
        "live_fetches_today": int(live_fetches_today),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


from app.api.deps import verify_api_key as _verify_api_key  # noqa: E402


@router.get("/v1/benchmarks/me")
def per_org_benchmarks(
    db: Session = Depends(get_db),
    org_id: str = Depends(_verify_api_key),
    days: int = 30,
):
    """Per-org benchmarks (auth required). Used by dashboard widget."""
    days = max(1, min(int(days), 90))
    out: dict = {"org_id": org_id, "window_days": days}

    try:
        row = db.execute(text("""
            SELECT
                percentile_cont(0.50) WITHIN GROUP (ORDER BY latency_ms) AS p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95,
                COALESCE(SUM(cost_usd), 0) AS total_cost,
                COUNT(*) AS calls
            FROM llm_usage
            WHERE org_id = :oid
              AND called_at >= NOW() - (:d || ' days')::interval
        """), {"oid": org_id, "d": str(days)}).fetchone()
        if row:
            out["latency"] = {
                "p50_ms": int(row.p50) if row.p50 is not None else None,
                "p95_ms": int(row.p95) if row.p95 is not None else None,
            }
            out["cost"] = {
                "total_usd": round(float(row.total_cost or 0), 4),
                "calls": int(row.calls or 0),
            }
    except Exception as e:
        logger.debug(f"per-org latency/cost failed: {e}")

    try:
        rec = db.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE outcome = 'acted')   AS acted,
                COUNT(*) FILTER (WHERE outcome IS NOT NULL) AS labeled
            FROM recommendations
            WHERE org_id = :oid
              AND created_at >= NOW() - (:d || ' days')::interval
        """), {"oid": org_id, "d": str(days)}).fetchone()
        if rec:
            out["recommendations"] = {
                "total": int(rec.total or 0),
                "acted": int(rec.acted or 0),
                "labeled": int(rec.labeled or 0),
                "acted_rate": (
                    round(float(rec.acted) / float(rec.labeled), 3)
                    if (rec.labeled or 0) > 0 else None
                ),
            }
    except Exception as e:
        logger.debug(f"per-org recs failed: {e}")

    # Phase 7: live fetch budget status
    try:
        from app.retrieval import cost_guard
        out["live_fetch_budget"] = cost_guard.status(org_id)
    except Exception:
        pass

    return out


@router.get("/v1/benchmarks/methodology")
def public_methodology():
    """Static methodology pointer. Real doc: docs/BENCHMARKS.md."""
    return {
        "version": SCORECARD_VERSION,
        "doc": "https://github.com/genios-ai/genios-brain/blob/main/docs/BENCHMARKS.md",
        "metrics": {
            "acted_rate": {
                "definition": "acted / (acted + dismissed + ignored)",
                "source": "recommendations table, outcome column",
                "window_days": WINDOW_DAYS,
                "min_n": MIN_AAR_SAMPLES,
            },
            "context_latency": {
                "definition": "p50/p95/p99 of /v1/context end-to-end latency",
                "source": "context_calls.latency_ms",
                "sla_p95_ms": 400,
                "min_n": MIN_LATENCY_SAMPLES,
            },
            "faithfulness": {
                "definition": "Proxy: % bundles with grounded relationship_stage + non-zero confidence. Replaced by labeled fixture set.",
                "method": "groundedness_proxy_v1",
                "min_n": MIN_LATENCY_SAMPLES,
            },
            "calibration_ece": {
                "definition": "Sample-weighted Expected Calibration Error across orgs",
                "source": "calibration_models.ece",
                "target": 0.10,
                "min_n": MIN_ECE_SAMPLES,
            },
        },
        "honesty": {
            "we_do_not_run": [
                {"benchmark": "SWE-bench", "reason": "GeniOS is not a code agent"},
                {"benchmark": "GAIA", "reason": "GeniOS is not a web-automation agent"},
                {"benchmark": "LoCoMo", "reason": "GeniOS is not a chatbot; conversational memory is not our product surface"},
            ],
            "what_we_measure_instead": "Proactive context-intelligence: did we flag the right thing, fast, faithfully, with calibrated confidence",
        },
    }
