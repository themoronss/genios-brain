"""Founder-only financial metrics — the DB-TRUTH layer.

PostHog is good for product/behavioural metrics, but money (MRR, ARR, revenue,
churn) must be EXACT. These endpoints read the system of record — the `orgs`,
`subscriptions` and `llm_costs` tables — so the numbers are penny-accurate and
independent of analytics-event delivery. PostHog *mirrors* these; this is the
source of truth.

Auth: a single shared admin token (env ADMIN_METRICS_TOKEN) via the
`X-Admin-Token` header. NOT exposed to normal API keys — global financials must
never be readable per-tenant. If the token env is unset, the endpoints 503 so
financials are never accidentally public.

Accuracy guardrails baked in:
  • every query excludes `orgs.is_internal = true` (founder/test accounts)
  • multi-gateway revenue normalized to INR (Razorpay ₹ + Stripe $) via one rate
  • metrics that need period-over-period history (exact NRR) are returned null
    with a note rather than faked.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.analytics import _PLAN_MRR_INR, to_inr_paise, INR_PER_USD

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate on a shared admin token. 503 if unset (never silently public)."""
    expected = os.getenv("ADMIN_METRICS_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503,
                            detail="ADMIN_METRICS_TOKEN not configured")
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


def _llm_cost_inr(db: Session, days: int) -> float | None:
    """Sum LLM spend (USD) over the window, external orgs only, → INR.
    Defensive: any schema surprise returns None so gross-margin degrades to
    'unknown' instead of 500-ing the whole report."""
    try:
        usd = db.execute(
            text(f"""
                SELECT COALESCE(SUM(lc.cost_usd), 0)
                FROM llm_costs lc
                JOIN orgs o ON o.id::text = lc.org_id
                WHERE lc.created_at > now() - (:days || ' days')::interval
                  AND COALESCE(o.is_internal, false) = false
            """),
            {"days": days},
        ).scalar() or 0
        return round(float(usd) * INR_PER_USD, 2)
    except Exception as e:
        logger.warning("admin_metrics: LLM cost query failed — %s", e)
        return None


@router.get("/v1/admin/metrics")
def admin_metrics(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin),
):
    """DB-truth financial snapshot. `days` controls the rolling window for the
    flow metrics (new/revenue/churn); MRR/ARR are point-in-time."""

    # ── MRR / ARR / paying accounts — from CURRENT org state (point-in-time) ──
    # Paying = active plan, not expired, not internal, on a paid tier.
    rows = db.execute(
        text("""
            SELECT COALESCE(subscription_tier, 'trial') AS tier, COUNT(*) AS n
            FROM orgs
            WHERE plan_status = 'active'
              AND plan_expires_at > now()
              AND COALESCE(is_internal, false) = false
              AND COALESCE(subscription_tier, 'trial') NOT IN ('trial', '')
            GROUP BY 1
        """)
    ).fetchall()
    mrr_by_plan = {}
    mrr_inr = 0
    paying = 0
    for r in rows:
        price = _PLAN_MRR_INR.get((r.tier or "").lower(), 0)
        mrr_by_plan[r.tier] = {"accounts": int(r.n), "mrr_inr": price * int(r.n)}
        mrr_inr += price * int(r.n)
        paying += int(r.n)
    arpu = round(mrr_inr / paying, 2) if paying else 0

    # ── Revenue actually COLLECTED — from paid subscription rows (cash truth) ──
    # Normalize each row to INR (Razorpay charges ₹, Stripe charges $).
    paid_rows = db.execute(
        text("""
            SELECT s.invoice_type, s.amount_paise, s.currency, s.processor,
                   (s.created_at > now() - (:days || ' days')::interval) AS in_window
            FROM subscriptions s
            JOIN orgs o ON o.id = s.org_id
            WHERE s.status = 'active'
              AND COALESCE(o.is_internal, false) = false
        """),
        {"days": days},
    ).fetchall()

    rev_all = rev_window = rev_sub_window = rev_topup_window = 0
    cur_split = {}
    for r in paid_rows:
        inr_paise = to_inr_paise(r.amount_paise or 0, r.currency or "INR")
        inr = inr_paise / 100
        rev_all += inr
        cur_split[r.currency or "INR"] = round(cur_split.get(r.currency or "INR", 0) + inr, 2)
        if r.in_window:
            rev_window += inr
            if (r.invoice_type or "subscription") == "topup":
                rev_topup_window += inr
            else:
                rev_sub_window += inr

    # ── New paying logos in window ────────────────────────────────────────────
    new_paying = db.execute(
        text("""
            SELECT COUNT(DISTINCT s.org_id)
            FROM subscriptions s
            JOIN orgs o ON o.id = s.org_id
            WHERE s.status = 'active'
              AND COALESCE(s.invoice_type, 'subscription') = 'subscription'
              AND s.created_at > now() - (:days || ' days')::interval
              AND COALESCE(o.is_internal, false) = false
        """),
        {"days": days},
    ).scalar() or 0

    # ── Logo churn (APPROXIMATE) — paid orgs whose plan expired in-window and ──
    # were not renewed. Exact churn/NRR need a monthly mrr_snapshots table.
    churned = db.execute(
        text("""
            SELECT COUNT(*)
            FROM orgs
            WHERE COALESCE(is_internal, false) = false
              AND COALESCE(subscription_tier, 'trial') NOT IN ('trial', '')
              AND plan_status <> 'active'
              AND plan_expires_at >= now() - (:days || ' days')::interval
              AND plan_expires_at < now()
        """),
        {"days": days},
    ).scalar() or 0
    churn_base = paying + int(churned)
    logo_churn_pct = round(100 * int(churned) / churn_base, 2) if churn_base else 0

    # ── Gross margin (window) = collected revenue − LLM cost ───────────────────
    llm_cost = _llm_cost_inr(db, days)
    gross_margin = round(rev_window - llm_cost, 2) if llm_cost is not None else None
    gross_margin_pct = (
        round(100 * gross_margin / rev_window, 2)
        if (gross_margin is not None and rev_window) else None
    )

    return {
        "window_days": days,
        "fx_inr_per_usd": INR_PER_USD,
        # point-in-time
        "mrr_inr": mrr_inr,
        "arr_inr": mrr_inr * 12,
        "paying_accounts": paying,
        "arpu_inr": arpu,
        "mrr_by_plan": mrr_by_plan,
        # window flows
        "revenue_collected_window_inr": round(rev_window, 2),
        "revenue_subscription_window_inr": round(rev_sub_window, 2),
        "revenue_topup_window_inr": round(rev_topup_window, 2),
        "revenue_collected_all_time_inr": round(rev_all, 2),
        "currency_split_inr": cur_split,
        "new_paying_accounts_window": int(new_paying),
        # cost / margin
        "llm_cost_window_inr": llm_cost,
        "gross_margin_window_inr": gross_margin,
        "gross_margin_pct": gross_margin_pct,
        # churn (approx)
        "churned_logos_window": int(churned),
        "logo_churn_pct_approx": logo_churn_pct,
        "nrr_pct": None,
        "_notes": {
            "source": "DB system-of-record (orgs/subscriptions/llm_costs) — penny-accurate, internal orgs excluded",
            "churn": "APPROX: derived from plan expiry, not period snapshots",
            "nrr": "null until a monthly mrr_snapshots table exists (exact NRR needs start-of-period MRR)",
        },
    }


def _posthog_revenue(days: int) -> dict | None:
    """Best-effort: query PostHog's HogQL API for the same revenue, to compare
    against the DB. Needs POSTHOG_READ_KEY (personal API key) + POSTHOG_PROJECT_ID.
    Returns None if not configured — then compare manually."""
    key = os.getenv("POSTHOG_READ_KEY", "")
    pid = os.getenv("POSTHOG_PROJECT_ID", "")
    if not key or not pid:
        return None
    host = os.getenv("POSTHOG_HOST", "https://eu.posthog.com")
    hogql = (
        "SELECT count() AS events, sum(toFloat(properties.amount_inr)) AS revenue_inr "
        "FROM events WHERE event IN ('payment_completed','topup_purchased') "
        f"AND timestamp > now() - INTERVAL {int(days)} DAY "
        "AND coalesce(properties.$set.is_internal, false) = false"
    )
    try:
        body = json.dumps({"query": {"kind": "HogQLQuery", "query": hogql}}).encode()
        req = urllib.request.Request(
            f"{host}/api/projects/{pid}/query/",
            data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        row = (data.get("results") or [[0, 0]])[0]
        return {"events": row[0], "revenue_inr": round(float(row[1] or 0), 2)}
    except Exception as e:
        logger.warning("reconciliation: PostHog query failed — %s", e)
        return None


@router.get("/v1/admin/reconciliation")
def admin_reconciliation(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: None = Depends(_require_admin),
):
    """3-way accuracy check. DB is the truth; PostHog should match it; the
    gateway settled amount is printed for you to eyeball. Any mismatch = a bug."""
    # DB truth: revenue + event-eligible count (one payment_completed per active
    # paid subscription in window).
    db_rows = db.execute(
        text("""
            SELECT s.amount_paise, s.currency, s.invoice_type
            FROM subscriptions s
            JOIN orgs o ON o.id = s.org_id
            WHERE s.status = 'active'
              AND s.created_at > now() - (:days || ' days')::interval
              AND COALESCE(o.is_internal, false) = false
        """),
        {"days": days},
    ).fetchall()
    db_revenue = round(sum(to_inr_paise(r.amount_paise or 0, r.currency or "INR")
                           for r in db_rows) / 100, 2)
    db_events_expected = len(db_rows)

    ph = _posthog_revenue(days)
    out = {
        "window_days": days,
        "db_truth": {
            "revenue_inr": db_revenue,
            "events_expected": db_events_expected,
            "note": "one payment_completed/topup_purchased should exist per row",
        },
        "posthog": ph or "set POSTHOG_READ_KEY + POSTHOG_PROJECT_ID to auto-compare, else check PostHog manually",
        "gateway": "compare db_truth.revenue_inr against Razorpay + Stripe settled totals for the window",
    }
    if ph:
        out["diff_revenue_inr"] = round(db_revenue - ph["revenue_inr"], 2)
        out["diff_events"] = db_events_expected - ph["events"]
        out["match"] = abs(out["diff_revenue_inr"]) < 1 and out["diff_events"] == 0
    return out
