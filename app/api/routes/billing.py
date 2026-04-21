"""
Billing routes — Razorpay payment integration.
Endpoints:
  POST /api/org/{org_id}/billing/order    — create Razorpay order for plan upgrade
  POST /api/org/{org_id}/billing/verify   — verify payment signature, activate plan
  POST /v1/billing/webhook                — Razorpay async webhook (signature-verified)
  GET  /api/org/{org_id}/billing/subscription — current plan + overage status
  GET  /api/org/{org_id}/billing/invoices — payment history

Plan prices (INR, in paise):
  Hustler  ₹2,500  → 250,000 paise
  Startup  ₹10,000 → 1,000,000 paise
"""

import hashlib
import hmac
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.plan_enforcer import get_org_plan, PLAN_CONFIG

logger = logging.getLogger(__name__)
router = APIRouter()

RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

PLAN_PRICES_PAISE = {
    "hustler": 250_000,   # ₹2,500
    "startup": 1_000_000, # ₹10,000
}


def _razorpay_client():
    """Lazy import so startup doesn't fail if razorpay not installed."""
    try:
        import razorpay
        return razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))
    except ImportError:
        raise HTTPException(status_code=503, detail="Razorpay SDK not installed")


def _verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature."""
    body = f"{order_id}|{payment_id}"
    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Create order ─────────────────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    plan: str  # "hustler" or "startup"


@router.post("/api/org/{org_id}/billing/order")
def create_order(org_id: str, body: CreateOrderRequest, db: Session = Depends(get_db)):
    if body.plan not in PLAN_PRICES_PAISE:
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'hustler' or 'startup'.")

    amount = PLAN_PRICES_PAISE[body.plan]
    client = _razorpay_client()

    try:
        order = client.order.create({
            "amount":   amount,
            "currency": "INR",
            "receipt":  f"gn_{org_id[:8]}_{secrets.token_hex(4)}",
            "notes":    {"org_id": org_id, "plan": body.plan},
        })
    except Exception as e:
        logger.error(f"Razorpay order creation failed: {e}")
        raise HTTPException(status_code=502, detail="Payment gateway error")

    # Record pending subscription
    db.execute(
        text("""
            INSERT INTO subscriptions (org_id, plan, status, order_id, amount_paise, invoice_type)
            VALUES (:org_id, :plan, 'pending', :order_id, :amount, 'subscription')
        """),
        {"org_id": org_id, "plan": body.plan, "order_id": order["id"], "amount": amount},
    )
    db.commit()

    return {
        "order_id":  order["id"],
        "amount":    amount,
        "currency":  "INR",
        "key_id":    RAZORPAY_KEY_ID,
        "plan":      body.plan,
    }


# ── Verify & activate ────────────────────────────────────────────────────────

class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id:  str
    razorpay_order_id:    str
    razorpay_signature:   str
    plan:                 str


@router.post("/api/org/{org_id}/billing/verify")
def verify_payment(org_id: str, body: VerifyPaymentRequest, db: Session = Depends(get_db)):
    if not _verify_signature(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment signature verification failed")

    _activate_plan(db, org_id, body.plan, body.razorpay_payment_id, body.razorpay_order_id)
    plan_config = PLAN_CONFIG[body.plan]

    return {
        "activated": True,
        "plan":      body.plan,
        "unlocked":  _unlocked_features(body.plan),
        "period_days": plan_config["period_days"],
    }


def _activate_plan(db: Session, org_id: str, plan: str, payment_id: str, order_id: str):
    """Update org plan and mark subscription active."""
    from datetime import datetime, timezone, timedelta
    period_days = PLAN_CONFIG[plan]["period_days"]
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=period_days)

    db.execute(
        text("""
            UPDATE orgs
            SET subscription_tier  = :plan,
                plan_status        = 'active',
                plan_started_at    = :now,
                plan_expires_at    = :end,
                period_reset_at    = :end,
                period_context_count = 0
            WHERE id = :org_id
        """),
        {"plan": plan, "now": now, "end": period_end, "org_id": org_id},
    )
    db.execute(
        text("""
            UPDATE subscriptions
            SET status       = 'active',
                payment_id   = :payment_id,
                period_start = :now,
                period_end   = :end
            WHERE order_id = :order_id AND org_id = :org_id
        """),
        {"payment_id": payment_id, "now": now, "end": period_end,
         "order_id": order_id, "org_id": org_id},
    )
    db.commit()
    from app.plan_enforcer import _plan_cache_invalidate
    _plan_cache_invalidate(org_id)
    logger.info(f"Plan activated: org={org_id} plan={plan}")
    from app.core.analytics import capture
    capture(org_id, "plan_upgraded", {"plan": plan, "payment_id": payment_id})


def _unlocked_features(plan: str) -> list[str]:
    if plan == "hustler":
        return ["6h auto-sync", "Temporal queries", "Edge detail", "Manual context", "3 clusters"]
    if plan == "startup":
        return ["Real-time sync", "Semantic queries", "Full context depth", "5 seats",
                "Calendar & Slack", "10 clusters", "Graph reports"]
    return []


# ── Razorpay webhook ─────────────────────────────────────────────────────────

@router.post("/v1/billing/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Async webhook from Razorpay — verify signature then activate plan."""
    body_bytes = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")

    expected = hmac.new(
        RAZORPAY_KEY_SECRET.encode(), body_bytes, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json
    event = json.loads(body_bytes)
    if event.get("event") != "payment.captured":
        return {"ack": True}

    payment   = event["payload"]["payment"]["entity"]
    order_id  = payment.get("order_id")
    payment_id = payment.get("id")

    row = db.execute(
        text("SELECT org_id, plan FROM subscriptions WHERE order_id = :oid AND status = 'pending'"),
        {"oid": order_id},
    ).fetchone()

    if row:
        _activate_plan(db, str(row.org_id), row.plan, payment_id, order_id)

    return {"ack": True}


# ── Subscription status ──────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/billing/subscription")
def get_subscription(org_id: str, db: Session = Depends(get_db)):
    plan_info = get_org_plan(db, org_id)
    config    = plan_info["config"]
    tier      = plan_info["tier"]

    # Count overage (contexts beyond period limit)
    period_reset_at = plan_info.get("period_reset_at")
    period_used = 0
    if period_reset_at:
        period_used = db.execute(
            text("""
                SELECT COUNT(*) FROM context_calls
                WHERE org_id = :oid AND called_at >= :reset
                  AND (source = 'api' OR source IS NULL)
            """),
            {"oid": org_id, "reset": period_reset_at},
        ).scalar() or 0

    overage_units = max(0, period_used - config["period_contexts"])
    overage_rate  = config.get("overage_cost_per_1k", 0)
    overage_cost  = int((overage_units / 1000) * overage_rate) if overage_units > 0 else 0

    expires_at = plan_info.get("expires_at")
    return {
        "plan":            tier,
        "plan_status":     plan_info.get("plan_status", "active"),
        "period_used":     period_used,
        "period_limit":    config["period_contexts"],
        "overage_units":   overage_units,
        "overage_cost_inr": overage_cost,
        "overage_allowed": config.get("overage_allowed", False),
        "expires_at":      expires_at.isoformat() if expires_at else None,
        "prices": {
            "hustler": 2500,
            "startup": 10000,
        },
    }


# ── Invoice history ──────────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/billing/invoices")
def list_invoices(org_id: str, db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            SELECT id, plan, status, amount_paise, invoice_type,
                   payment_id, period_start, period_end, created_at
            FROM subscriptions
            WHERE org_id = :org_id
            ORDER BY created_at DESC
            LIMIT 50
        """),
        {"org_id": org_id},
    ).fetchall()

    invoices = []
    for r in rows:
        invoices.append({
            "id":           str(r.id),
            "plan":         r.plan,
            "status":       r.status,
            "amount_inr":   (r.amount_paise or 0) // 100,
            "type":         r.invoice_type,
            "payment_id":   r.payment_id,
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end":   r.period_end.isoformat() if r.period_end else None,
            "created_at":   r.created_at.isoformat() if r.created_at else None,
        })

    return {"invoices": invoices}
