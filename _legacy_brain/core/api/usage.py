"""LLM cost / usage read API.

GET /v1/usage/llm/summary       org's today + 7d + 30d totals
GET /v1/usage/llm/breakdown     per-purpose × per-model rollup for a window
GET /v1/usage/llm/recent        last N raw calls (for debugging spikes)

All org-scoped. Numbers are pulled fresh from llm_costs every call — no
materialized view yet; the index (org_id, ts DESC) keeps a 30-day window
cheap up to a few hundred thousand rows per org.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org

router = APIRouter(prefix="/v1/usage/llm", tags=["usage"])


@router.get("/summary")
def llm_summary(
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict:
    """Roll-up: today, last 7 days, last 30 days. Calls + tokens + USD."""
    rows = session.execute(
        text(
            """
            SELECT
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '1 day'  THEN 1 ELSE 0 END), 0)  AS calls_24h,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '7 days' THEN 1 ELSE 0 END), 0)  AS calls_7d,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '30 days' THEN 1 ELSE 0 END), 0) AS calls_30d,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '1 day'   THEN input_tokens + output_tokens ELSE 0 END), 0) AS tokens_24h,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '7 days'  THEN input_tokens + output_tokens ELSE 0 END), 0) AS tokens_7d,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '30 days' THEN input_tokens + output_tokens ELSE 0 END), 0) AS tokens_30d,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '1 day'   THEN cost_usd ELSE 0 END), 0) AS usd_24h,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '7 days'  THEN cost_usd ELSE 0 END), 0) AS usd_7d,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '30 days' THEN cost_usd ELSE 0 END), 0) AS usd_30d,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '1 day'   THEN credits_billed ELSE 0 END), 0) AS credits_24h,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '7 days'  THEN credits_billed ELSE 0 END), 0) AS credits_7d,
              COALESCE(SUM(CASE WHEN ts >= NOW() - INTERVAL '30 days' THEN credits_billed ELSE 0 END), 0) AS credits_30d
            FROM llm_costs
            WHERE org_id = :org
            """
        ),
        {"org": org_id},
    ).fetchone()
    return {
        "window_24h": {
            "calls": int(rows.calls_24h), "tokens": int(rows.tokens_24h),
            "cost_usd": float(rows.usd_24h), "credits_billed": int(rows.credits_24h),
        },
        "window_7d": {
            "calls": int(rows.calls_7d),  "tokens": int(rows.tokens_7d),
            "cost_usd": float(rows.usd_7d),  "credits_billed": int(rows.credits_7d),
        },
        "window_30d": {
            "calls": int(rows.calls_30d), "tokens": int(rows.tokens_30d),
            "cost_usd": float(rows.usd_30d), "credits_billed": int(rows.credits_30d),
        },
    }


@router.get("/breakdown")
def llm_breakdown(
    days: int = Query(default=7, ge=1, le=90),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict:
    """(purpose, model) → (calls, tokens, cost). For dashboard chart.

    The grouping answers "where is my budget going?" — extraction vs
    intelligence vs custom mapping, and Haiku vs Sonnet within each.
    """
    rows = session.execute(
        text(
            """
            SELECT purpose, model,
                   COUNT(*)                      AS calls,
                   SUM(input_tokens)             AS input_tokens,
                   SUM(output_tokens)            AS output_tokens,
                   SUM(cost_usd)                 AS cost_usd,
                   SUM(credits_billed)           AS credits_billed
            FROM llm_costs
            WHERE org_id = :org
              AND ts >= NOW() - (:days || ' days')::INTERVAL
            GROUP BY purpose, model
            ORDER BY cost_usd DESC
            """
        ),
        {"org": org_id, "days": days},
    ).fetchall()
    return {
        "window_days": days,
        "rows": [
            {
                "purpose":        r.purpose,
                "model":          r.model,
                "calls":          int(r.calls or 0),
                "input_tokens":   int(r.input_tokens or 0),
                "output_tokens":  int(r.output_tokens or 0),
                "cost_usd":       float(r.cost_usd or 0),
                "credits_billed": int(r.credits_billed or 0),
            }
            for r in rows
        ],
    }


@router.get("/recent")
def llm_recent(
    limit: int = Query(default=50, ge=1, le=500),
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict:
    """Recent raw calls — useful when summary shows a cost spike and you
    want to know which decision or extraction caused it."""
    rows = session.execute(
        text(
            """
            SELECT id, model, purpose,
                   input_tokens, output_tokens, cost_usd,
                   credits_billed, success, error,
                   source_item_id, decision_id, ts
            FROM llm_costs
            WHERE org_id = :org
            ORDER BY ts DESC
            LIMIT :lim
            """
        ),
        {"org": org_id, "lim": limit},
    ).fetchall()
    return {
        "calls": [
            {
                "id":             int(r.id),
                "model":          r.model,
                "purpose":        r.purpose,
                "input_tokens":   int(r.input_tokens or 0),
                "output_tokens":  int(r.output_tokens or 0),
                "cost_usd":       float(r.cost_usd or 0),
                "credits_billed": int(r.credits_billed or 0),
                "success":        bool(r.success),
                "error":          r.error,
                "source_item_id": r.source_item_id,
                "decision_id":    r.decision_id,
                "ts":             r.ts.isoformat() if r.ts else None,
            }
            for r in rows
        ],
    }
