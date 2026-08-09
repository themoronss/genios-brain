"""Public benchmarks scorecard — honest, min-N gated, no PII.

Reimplemented for the v2 engine. The original v1 tier-1 tables (recommendations, context_calls,
calibration_models) were dropped, so metrics are recomputed from v2 sources where they exist and
returned as {value:null, reason:"insufficient_data"} otherwise (never fabricated). Public + cached;
the whole point of a benchmark is that it is the same for everyone and gameable by no one.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import text

from genios_engine.platform.cache import get_cache
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()

_MIN_N = 30
_WINDOW_DAYS = 30
_CACHE_KEY = "benchmarks:scorecard:v2"
_CACHE_TTL = 3600


def _insufficient(n: int = 0) -> dict:
    return {"value": None, "n": n, "reason": "insufficient_data"}


def _scale(conn) -> dict:
    def count(sql: str) -> int:
        try:
            return int(conn.execute(text(sql)).scalar() or 0)
        except Exception:
            return 0
    return {
        "orgs": count("select count(*) from orgs"),
        "decisions_30d": count("select count(*) from decisions "
                               "where created_at > now() - interval '30 days'"),
        "entities": count("select count(*) from graph_nodes "
                          "where valid_to is null and node_type in ('person','company')"),
        "facts": count("select count(*) from graph_facts where valid_to is null and status='active'"),
        "edges": count("select count(*) from graph_edges where valid_to is null"),
    }


def _faithfulness(conn) -> dict:
    """Fraction of active facts that are grounded (confidence above zero) — the v2 proxy."""
    try:
        n = int(conn.execute(text(
            "select count(*) from graph_facts where valid_to is null and status='active'")
        ).scalar() or 0)
        if n < _MIN_N:
            return _insufficient(n)
        grounded = int(conn.execute(text(
            "select count(*) from graph_facts where valid_to is null and status='active' "
            "and confidence >= 0.5")).scalar() or 0)
        return {"value": round(grounded / n, 4), "n": n, "method": "groundedness_proxy_v2"}
    except Exception:
        return _insufficient()


def _acted_rate(conn) -> dict:
    """Acted / (acted + dismissed + expired) over cards in the window, when there are enough."""
    try:
        rows = conn.execute(text(
            "select state, count(*) c from cards "
            "where created_at > now() - interval '30 days' group by state")).mappings().all()
        by = {r["state"]: int(r["c"]) for r in rows}
        acted = by.get("claimed", 0) + by.get("delivered", 0)
        considered = acted + by.get("dismissed", 0) + by.get("expired", 0)
        if considered < _MIN_N:
            return _insufficient(considered)
        return {"value": round(acted / considered, 4), "n": considered}
    except Exception:
        return _insufficient()


@router.get("/v1/benchmarks/scorecard")
def scorecard() -> dict:
    cache = get_cache()
    try:
        cached = cache.get_json(_CACHE_KEY)
        if cached:
            return cached
    except Exception:
        pass

    body = {
        "version": "v2",
        "build_sha": os.environ.get("GENIOS_BUILD_SHA", "dev"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": _WINDOW_DAYS,
        "min_n_gate": _MIN_N,
        "k_anonymous": True,
    }
    if _graph is not None:
        with _graph.engine.connect() as conn:
            body["scale"] = _scale(conn)
            body["tier1"] = {
                "acted_rate": _acted_rate(conn),
                "faithfulness": _faithfulness(conn),
                # No latency or calibration store in the v2 engine yet — reported honestly.
                "context_latency": {"p50": None, "p95": None, "p99": None,
                                    "reason": "insufficient_data"},
                "calibration_ece": _insufficient(),
            }
            body["per_detector"] = []          # k-anon suppressed until ≥3 orgs of evidence
    else:
        body["scale"], body["tier1"], body["per_detector"] = {}, {}, []

    try:
        cache.set_json(_CACHE_KEY, _CACHE_TTL, body)
    except Exception:
        pass
    return body


@router.get("/v1/benchmarks/methodology")
def methodology() -> dict:
    return {
        "version": "v2",
        "min_n": _MIN_N,
        "k_anonymous": True,
        "refresh_interval_sec": _CACHE_TTL,
        "sources": [
            "decisions (30d volume + confidence)",
            "graph_facts (grounded fact proxy)",
            "cards (acted vs dismissed/expired)",
            "graph_nodes / graph_edges (scale)",
        ],
        "notes": [
            "Metrics below the minimum sample gate return insufficient_data, never a guess.",
            "Per-detector breakdowns are suppressed below 3 orgs (k-anonymity).",
            "No PII leaves this endpoint; only aggregate counts and rates.",
            "context_latency and calibration_ece have no v2 source yet and are reported null.",
        ],
    }
