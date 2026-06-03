"""/v1/benchmarks/* — public + per-org benchmark API.

v2 rewrite: all numbers are derived from `decisions` + `proactive_insights` +
`graph_nodes` (the only tables that survived mig 0015). v1 sources
(context_calls, recommendations, llm_usage, engagement_health, pending_alerts,
calibration_models, interactions, contacts) were dropped.

Public endpoints used by the marketing site & dashboard:
  GET /v1/benchmarks/scorecard   — k-anonymous aggregate, 1h Redis cache
  GET /v1/benchmarks             — hero numbers
  GET /v1/benchmarks/live        — live ticker
  GET /v1/benchmarks/me          — per-org dashboard widget (auth required)
  GET /v1/benchmarks/methodology — explainer JSON
"""

from __future__ import annotations

import hashlib
import json
import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.redis_client import redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

CACHE_KEY = "benchmarks:scorecard:v2"
CACHE_TTL = 3600


def _build_scorecard(db: Session) -> dict:
    """Aggregate over all orgs — same shape as v1 frontend expects."""
    totals = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM orgs)                              AS orgs,
                (SELECT COUNT(*) FROM decisions
                   WHERE created_at >= NOW() - INTERVAL '30 days')       AS decisions_30d,
                (SELECT COUNT(*) FROM proactive_insights
                   WHERE created_at >= NOW() - INTERVAL '30 days')       AS insights_30d,
                (SELECT COUNT(*) FROM graph_nodes WHERE type='entity')   AS entities,
                (SELECT COUNT(*) FROM facts)                             AS facts,
                (SELECT COUNT(*) FROM graph_edges)                       AS edges
        """)
    ).fetchone()

    conf = db.execute(
        text("""
            SELECT AVG(confidence_score), COUNT(*)
            FROM decisions
            WHERE created_at >= NOW() - INTERVAL '30 days'
        """)
    ).fetchone()

    avg_conf = float(conf[0] or 0)
    sample_n = int(conf[1] or 0)

    return {
        "version": "v2",
        "generated_at": None,
        "scale": {
            "orgs":          int(totals[0] or 0),
            "decisions_30d": int(totals[1] or 0),
            "insights_30d":  int(totals[2] or 0),
            "entities":      int(totals[3] or 0),
            "facts":         int(totals[4] or 0),
            "edges":         int(totals[5] or 0),
        },
        "quality": {
            "avg_confidence_30d": round(avg_conf, 3),
            "samples":            sample_n,
        },
        "min_n_gate": 30,
        "k_anonymous": True,
    }


def _etag(payload: dict) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return '"' + hashlib.sha256(body).hexdigest()[:16] + '"'


@router.get("/v1/benchmarks/scorecard")
def public_scorecard(response: Response, db: Session = Depends(get_db)):
    """Public, unauthenticated scorecard. 1h Redis cache. No PII."""
    cached = None
    try:
        cached = redis_client.get(CACHE_KEY)
    except Exception as e:
        logger.warning(f"redis get failed: {e}")

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

    response.headers["ETag"] = _etag(payload)
    response.headers["Cache-Control"] = f"public, max-age={CACHE_TTL}, stale-while-revalidate=600"
    response.headers["Access-Control-Allow-Origin"] = "*"
    return payload


@router.get("/v1/benchmarks")
def public_benchmarks_hero(db: Session = Depends(get_db)):
    """Lightweight hero numbers for the marketing site."""
    totals = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM orgs)                                AS orgs,
                (SELECT COUNT(*) FROM connections WHERE status='active')   AS active_conns,
                (SELECT COUNT(*) FROM facts)                               AS facts,
                (SELECT COUNT(*) FROM graph_nodes WHERE type='entity')     AS entities,
                (SELECT COUNT(*) FROM decisions
                   WHERE created_at >= NOW() - INTERVAL '7 days')          AS decisions_7d
        """)
    ).fetchone()
    return {
        "orgs":             int(totals[0] or 0),
        "active_conns":     int(totals[1] or 0),
        "facts":            int(totals[2] or 0),
        "entities":         int(totals[3] or 0),
        "decisions_7d":     int(totals[4] or 0),
    }


@router.get("/v1/benchmarks/live")
def public_benchmarks_live(db: Session = Depends(get_db)):
    """Live ticker — counts in the last 60 minutes."""
    totals = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM decisions
                   WHERE created_at >= NOW() - INTERVAL '60 minutes') AS decisions_1h,
                (SELECT COUNT(*) FROM proactive_insights
                   WHERE created_at >= NOW() - INTERVAL '60 minutes') AS insights_1h,
                (SELECT COUNT(*) FROM facts
                   WHERE created_at >= NOW() - INTERVAL '60 minutes')  AS facts_1h
        """)
    ).fetchone()
    return {
        "decisions_1h": int(totals[0] or 0),
        "insights_1h":  int(totals[1] or 0),
        "facts_1h":     int(totals[2] or 0),
    }


@router.get("/v1/benchmarks/me")
def per_org_benchmarks(db: Session = Depends(get_db),
                       org_id: str = Depends(verify_api_key)):
    """Per-org dashboard widget — auth required."""
    totals = db.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM decisions
                   WHERE org_id = :oid AND created_at >= NOW() - INTERVAL '30 days') AS d30,
                (SELECT AVG(confidence_score) FROM decisions
                   WHERE org_id = :oid AND created_at >= NOW() - INTERVAL '30 days') AS avg_conf,
                (SELECT COUNT(*) FROM proactive_insights
                   WHERE org_id = :oid AND created_at >= NOW() - INTERVAL '30 days') AS i30,
                (SELECT COUNT(*) FROM graph_nodes
                   WHERE org_id = :oid AND type = 'entity')                          AS entities,
                (SELECT COUNT(*) FROM facts WHERE org_id = :oid)                     AS facts,
                (SELECT COUNT(*) FROM connections
                   WHERE org_id = :oid AND status = 'active')                        AS conns
        """),
        {"oid": org_id},
    ).fetchone()
    return {
        "decisions_30d":        int(totals[0] or 0),
        "avg_confidence_30d":   round(float(totals[1] or 0), 3),
        "insights_30d":         int(totals[2] or 0),
        "entities":             int(totals[3] or 0),
        "facts":                int(totals[4] or 0),
        "active_connections":   int(totals[5] or 0),
    }


@router.get("/v1/benchmarks/methodology")
def benchmarks_methodology():
    """Explain how the scorecard is computed."""
    return {
        "version": "v2",
        "sources": ["decisions", "proactive_insights", "graph_nodes", "facts", "graph_edges", "connections"],
        "min_n": 30,
        "k_anonymous": True,
        "refresh_interval_sec": CACHE_TTL,
        "notes": [
            "All numbers are aggregates across orgs; no per-org PII is exposed in the public scorecard.",
            "Per-org numbers (via /v1/benchmarks/me) require an authenticated API key.",
            "Confidence is the mean Envelope confidence written by the engine for each /v1/intelligence/query call.",
        ],
    }
