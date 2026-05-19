"""
Billing routes — Razorpay payment integration.
Endpoints:
  POST /api/org/{org_id}/billing/order    — create Razorpay order for plan upgrade
  POST /api/org/{org_id}/billing/verify   — verify payment signature, activate plan
  POST /api/org/{org_id}/billing/topup    — create Razorpay order for credit top-up
  POST /v1/billing/webhook                — Razorpay async webhook (signature-verified)
  GET  /api/org/{org_id}/billing/subscription — current plan + credit balances + overage
  GET  /api/org/{org_id}/billing/invoices — payment history

Plan prices (INR, in paise):
  Early       ₹4,500  → 450,000   paise   (covers ~$54 of LLM cost; positive margin)
  Startup    ₹14,000  → 1,400,000 paise   (covers ~$168; positive margin)
  Enterprise  custom — contract-priced; no fixed amount here

Top-up packs (INR, in paise) — survive period resets, never expire:
  context_5k    ₹1,000 → 5,000 context credits
  sync_25k      ₹2,000 → 25,000 sync credits
  context_50k   ₹8,000 → 50,000 context credits  (bulk discount)
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
from app.plan_enforcer import get_org_plan, PLAN_CONFIG, reset_period_credits

logger = logging.getLogger(__name__)
router = APIRouter()

RAZORPAY_KEY_ID     = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

PLAN_PRICES_PAISE = {
    # Single-pool credit model (post-099). Prices reflect cost-based
    # margins documented in UNIT_ECONOMICS.md §7.
    "early":   450_000,     # ₹4,500   — 10K credits, ~36% margin realistic
    "startup": 2_500_000,   # ₹25,000  — 100K credits, ~34% margin realistic
    # "enterprise" intentionally absent — contract-priced, handled offline
    # via admin grant (see app.credits.grant).
    # Legacy alias so existing checkout buttons keep working during rollout.
    "hustler": 450_000,
}

# Top-up packs (single pool — bucket arg is just analytics tag).
# Prices re-tuned post-099 for ~40-50% margin (see UNIT_ECONOMICS.md §10).
TOPUP_PACKS = {
    # pack_id   → (bucket_tag, credits, price_paise, label)
    "small":      ("credits",   5_000,   250_000, "5,000 credits"),
    "medium":     ("credits",  25_000, 1_000_000, "25,000 credits"),
    "large":      ("credits", 100_000, 3_500_000, "100,000 credits (-30% bulk)"),
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
    plan: str  # "early" or "startup" (legacy "hustler" accepted)


@router.post("/api/org/{org_id}/billing/order")
def create_order(org_id: str, body: CreateOrderRequest, db: Session = Depends(get_db)):
    if body.plan not in PLAN_PRICES_PAISE:
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'early' or 'startup'.")

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
    """Update org plan, mark subscription active, and grant period credits
    — all in a SINGLE atomic transaction.

    Production-safety contract: either ALL of the following land, or NONE:
        1. orgs.subscription_tier / plan_status / expiry timestamps update
        2. subscriptions row marked 'active' with payment_id
        3. context/sync/proactive credit balances set to plan grants
        4. credit_ledger rows written for each grant (audit trail)

    Without this atomicity, a DB blip between step 2 and step 3 would
    leave a customer in the "paid but no credits" state — exactly the
    failure mode money-loss scenarios are made of.

    Idempotency: the credit grant is keyed on payment_id, so a Razorpay
    webhook+verify race that double-activates only credits the customer
    once.
    """
    from datetime import datetime, timezone, timedelta
    # Resolve legacy "hustler" → "early" before reading config
    from app.plan_enforcer import _normalize_tier
    plan = _normalize_tier(plan)

    period_days = PLAN_CONFIG[plan]["period_days"]
    plan_config = PLAN_CONFIG[plan]
    now = datetime.now(timezone.utc)
    period_end = now + timedelta(days=period_days)

    try:
        # ── Atomic plan activation: org row + credits in ONE update ─────
        # Single transaction means either ALL of plan_status / expiry /
        # credit pool / ledger row land, or NONE. Prevents the dreaded
        # "paid but no credits" state. See UNIT_ECONOMICS.md §11.
        new_credits = plan_config["credits"]
        db.execute(
            text("""
                UPDATE orgs
                SET subscription_tier      = :plan,
                    plan_status            = 'active',
                    plan_started_at        = :now,
                    plan_expires_at        = :end,
                    period_reset_at        = :end,
                    period_context_count   = 0,
                    grace_until            = NULL,
                    credits                = :credits,
                    credit_period_start    = :now,
                    credit_period_end      = :end,
                    sonnet_daily_count     = 0,
                    sonnet_daily_reset_at  = NULL
                WHERE id = :org_id
            """),
            {
                "plan": plan, "now": now, "end": period_end, "org_id": org_id,
                "credits": new_credits,
            },
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
        # Ledger row — idempotent on payment_id so verify+webhook race
        # doesn't double-credit.
        db.execute(
            text("""
                INSERT INTO credit_ledger
                    (org_id, bucket, kind, amount, balance_after,
                     reason, related_kind, related_id, idempotency_key)
                VALUES (:org, 'credits', 'reset', :amt, :amt,
                        :reason, 'subscription', :pid, :key)
                ON CONFLICT (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL
                DO NOTHING
            """),
            {
                "org": org_id, "amt": new_credits,
                "reason": f"plan_activate:{plan}",
                "pid": payment_id,
                "key": f"plan_activate:{payment_id}",
            },
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Plan activation failed atomically for org={org_id}: {e}")
        # Re-raise so the route returns 500 to the caller (verify or
        # webhook). Razorpay webhook will retry; verify will surface the
        # failure to the user who can retry. Customer is NEVER left in a
        # "paid but no credits" state because we rolled back.
        raise

    from app.plan_enforcer import _plan_cache_invalidate
    _plan_cache_invalidate(org_id)
    logger.info(f"Plan activated atomically: org={org_id} plan={plan} payment={payment_id}")
    try:
        from app.core.analytics import capture
        capture(org_id, "plan_upgraded", {"plan": plan, "payment_id": payment_id})
    except Exception:
        pass


def _unlocked_features(plan: str) -> list[str]:
    from app.plan_enforcer import _normalize_tier
    plan = _normalize_tier(plan)
    if plan == "early":
        return ["10,000 credits/month", "6h auto-sync", "Temporal queries",
                "Manual context", "5 agents", "Gmail + Calendar + Docs"]
    if plan == "startup":
        return ["100,000 credits/month", "Real-time sync", "Semantic queries",
                "25 agents", "Slack + HubSpot + Jira + Notion",
                "Top-up packs", "Higher Sonnet daily cap"]
    if plan == "enterprise":
        return ["Custom credits", "White-label", "Custom integrations",
                "Unlimited Sonnet", "Dedicated support", "Unlimited agents"]
    return []


# ── Top-up flow ──────────────────────────────────────────────────────────────

class TopupOrderRequest(BaseModel):
    pack: str  # one of TOPUP_PACKS keys


@router.post("/api/org/{org_id}/billing/topup")
def create_topup_order(org_id: str, body: TopupOrderRequest, db: Session = Depends(get_db)):
    """Create a Razorpay order for a credit top-up pack.

    Top-up credits land in `topup_context_credits` / `topup_sync_credits`
    columns and DO NOT expire at period reset — only plan-included credits
    do. Drained first on deduct (see app.credits.ledger).
    """
    pack = TOPUP_PACKS.get(body.pack)
    if not pack:
        raise HTTPException(
            status_code=400,
            detail={"error": "UNKNOWN_PACK", "available": list(TOPUP_PACKS.keys())},
        )
    bucket_tag, credits, amount_paise, label = pack

    client = _razorpay_client()
    try:
        order = client.order.create({
            "amount":   amount_paise,
            "currency": "INR",
            "receipt":  f"gn_tu_{org_id[:8]}_{secrets.token_hex(4)}",
            "notes":    {"org_id": org_id, "pack": body.pack,
                         "credits": str(credits), "type": "topup"},
        })
    except Exception as e:
        logger.error(f"Razorpay top-up order creation failed: {e}")
        raise HTTPException(status_code=502, detail="Payment gateway error")

    db.execute(
        text("""
            INSERT INTO subscriptions (org_id, plan, status, order_id, amount_paise, invoice_type)
            VALUES (:org_id, :plan, 'pending', :order_id, :amount, 'topup')
        """),
        {"org_id": org_id, "plan": body.pack, "order_id": order["id"],
         "amount": amount_paise},
    )
    db.commit()

    return {
        "order_id": order["id"],
        "amount":   amount_paise,
        "currency": "INR",
        "key_id":   RAZORPAY_KEY_ID,
        "pack":     body.pack,
        "credits":  credits,
        "label":    label,
    }


class VerifyTopupRequest(BaseModel):
    razorpay_payment_id:  str
    razorpay_order_id:    str
    razorpay_signature:   str
    pack:                 str


@router.post("/api/org/{org_id}/billing/topup/verify")
def verify_topup(org_id: str, body: VerifyTopupRequest, db: Session = Depends(get_db)):
    """Verify top-up payment + grant credits ATOMICALLY.

    Production-safety: subscription row is marked 'active' only AFTER the
    credit grant succeeds. If grant fails (DB outage, idempotency violation),
    both updates roll back so the customer is never left in "paid but no
    credits" state. The Razorpay webhook is the fallback path that will
    retry the grant on the same payment_id.
    """
    if not _verify_signature(body.razorpay_order_id, body.razorpay_payment_id,
                              body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Payment signature verification failed")
    pack = TOPUP_PACKS.get(body.pack)
    if not pack:
        raise HTTPException(status_code=400, detail="Unknown pack")
    bucket_tag, credits, _amt, label = pack

    from app.credits import topup
    try:
        # Step 1: grant credits to single pool (UPDATE org + INSERT ledger).
        res = topup(
            db, org_id=org_id, bucket=bucket_tag, amount=credits,
            reason=f"topup:{body.pack}",
            related_id=body.razorpay_payment_id,
            idempotency_key=f"topup:{body.razorpay_payment_id}",
        )
        # Step 2: only NOW mark subscription paid. Atomic — if topup
        # raised above this never runs and the txn rolls back as a unit.
        db.execute(
            text("""
                UPDATE subscriptions SET status = 'active', payment_id = :pid
                WHERE order_id = :oid AND org_id = :org_id
            """),
            {"pid": body.razorpay_payment_id, "oid": body.razorpay_order_id, "org_id": org_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Top-up atomic grant failed for org={org_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Credit grant failed; payment will be reconciled by webhook. "
                   "Refresh balance in a minute.",
        )

    from app.plan_enforcer import _plan_cache_invalidate
    _plan_cache_invalidate(org_id)
    return {"granted": True, "pack": body.pack, "credits": credits,
            "label": label, "balance_after": res.balance_after}


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
        text("""
            SELECT org_id, plan, invoice_type FROM subscriptions
            WHERE order_id = :oid AND status = 'pending'
        """),
        {"oid": order_id},
    ).fetchone()

    if not row:
        return {"ack": True}

    if (row.invoice_type or "subscription") == "topup":
        # row.plan stores the pack_id for top-up rows.
        pack = TOPUP_PACKS.get(row.plan)
        if not pack:
            logger.error(f"Unknown top-up pack in webhook: {row.plan}")
            return {"ack": True}
        bucket_tag, credits, _amt, _label = pack
        from app.credits import topup
        try:
            topup(
                db, org_id=str(row.org_id), bucket=bucket_tag, amount=credits,
                reason=f"topup_webhook:{row.plan}",
                related_id=payment_id,
                idempotency_key=f"topup:{payment_id}",
            )
            db.execute(
                text("""
                    UPDATE subscriptions SET status = 'active', payment_id = :pid
                    WHERE order_id = :oid
                """),
                {"pid": payment_id, "oid": order_id},
            )
            db.commit()
            from app.plan_enforcer import _plan_cache_invalidate
            _plan_cache_invalidate(str(row.org_id))
        except Exception as e:
            db.rollback()
            logger.error(f"Top-up webhook credit grant failed: {e}")
    else:
        _activate_plan(db, str(row.org_id), row.plan, payment_id, order_id)

    return {"ack": True}


# ── Subscription status ──────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/billing/subscription")
def get_subscription(org_id: str, db: Session = Depends(get_db)):
    """Single-pool billing snapshot for dashboard meter + upgrade UX."""
    plan_info = get_org_plan(db, org_id)
    config    = plan_info["config"]
    tier      = plan_info["tier"]
    from app.plan_enforcer import is_in_grace
    in_grace  = is_in_grace(plan_info)

    plan_credits  = plan_info.get("credits", 0)
    topup_credits = plan_info.get("topup_credits", 0)
    total         = plan_credits + topup_credits

    expires_at = plan_info.get("expires_at")
    grace_until = plan_info.get("grace_until")
    return {
        "plan":            tier,
        "plan_status":     plan_info.get("plan_status", "active"),
        "in_grace":        in_grace,
        # Single visible meter — frontend renders one progress bar.
        "credits": {
            "balance":      total,
            "plan":         plan_credits,
            "topup":        topup_credits,
            "period_limit": config["credits"],
        },
        "sonnet_daily_limit": config.get("sonnet_daily_limit", 0),
        "expires_at":      expires_at.isoformat() if expires_at else None,
        "grace_until":     grace_until.isoformat() if grace_until else None,
        "prices": {
            "early":    PLAN_PRICES_PAISE["early"]   // 100,
            "startup":  PLAN_PRICES_PAISE["startup"] // 100,
        },
        "topup_packs": [
            {"pack_id": pid, "credits": c, "price_inr": amt // 100, "label": lbl}
            for pid, (_b, c, amt, lbl) in TOPUP_PACKS.items()
        ],
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
