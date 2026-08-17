"""Credits + plan primitives for billing. Deterministic, atomic, idempotent.

Single credit pool: balance = orgs.credits (plan, reset each period) + orgs.topup_credits (rolls
over). Deduct drains topup first, then plan, in one atomic UPDATE. Every mutation appends an
immutable credit_ledger row; a double charge is blocked by a unique idempotency_key. Plan
activation is idempotent on payment_id (paid-but-no-credits and double-grant both guarded).
Prices are in minor units (paise / cents). No gateway calls here — pure DB + crypto.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

# plan tier → {inr, usd (minor units), credits, period_days}
PLAN_PRICES = {
    "early":   {"inr": 450000,  "usd": 5900,  "credits": 10_000,  "period_days": 30},
    "startup": {"inr": 2500000, "usd": 29900, "credits": 100_000, "period_days": 30},
}
PLAN_CREDITS = {"trial": 10_000, "early": 10_000, "startup": 100_000, "enterprise": 1_000_000}
TOPUP_PACKS = {
    "small":  {"credits": 5_000,   "inr": 250000,  "usd": 3500,  "label": "Small"},
    "medium": {"credits": 25_000,  "inr": 1000000, "usd": 12900, "label": "Medium"},
    "large":  {"credits": 100_000, "inr": 3500000, "usd": 44900, "label": "Large"},
}
GRACE_DAYS = 7
TRIAL_DAYS = 15                # a fresh signup gets 10,000 credits for 15 days
_ALIAS = {"hustler": "early"}


def normalize_plan(plan: str) -> str:
    p = (plan or "").lower()
    return _ALIAS.get(p, p)


def balance(conn, org_id: str) -> dict:
    row = conn.execute(text(
        "select coalesce(credits,0) plan_credits, coalesce(topup_credits,0) topup_pool, "
        "subscription_tier, plan_status from orgs where id=:o"), {"o": org_id}).first()
    if row is None:
        return {"balance": 0, "plan": 0, "topup": 0}
    plan_c, topup_c = int(row.plan_credits), int(row.topup_pool)
    return {"balance": plan_c + topup_c, "plan": plan_c, "topup": topup_c,
            "tier": row.subscription_tier, "plan_status": row.plan_status}


def _ledger(conn, org_id: str, *, kind: str, amount: int, balance_after: int,
            reason: str, idem: str | None, bucket: str = "credits") -> bool:
    """Append a ledger row. Returns False if the idempotency key already recorded a row."""
    result = conn.execute(text(
        "insert into credit_ledger (org_id,kind,amount,balance_after,reason,bucket,idempotency_key) "
        "values (:o,:k,:a,:b,:r,:bk,:idem) "
        "on conflict (org_id, idempotency_key) where idempotency_key is not null "
        "do nothing returning id"),
        {"o": org_id, "k": kind, "a": amount, "b": balance_after, "r": reason,
         "bk": bucket, "idem": idem}).first()
    return result is not None


def grant_topup(conn, org_id: str, credits: int, *, idem: str, reason: str = "topup") -> int:
    """Add topup credits (roll-over pool). Idempotent on idem; returns the new total balance."""
    if not _ledger(conn, org_id, kind="topup", amount=credits, balance_after=0,
                   reason=reason, idem=idem):
        return balance(conn, org_id)["balance"]           # already granted
    conn.execute(text("update orgs set topup_credits = coalesce(topup_credits,0) + :c where id=:o"),
                 {"c": credits, "o": org_id})
    new = balance(conn, org_id)["balance"]
    conn.execute(text("update credit_ledger set balance_after=:b where org_id=:o "
                      "and idempotency_key=:idem"), {"b": new, "o": org_id, "idem": idem})
    return new


def activate_plan(conn, org_id: str, plan: str, *, payment_id: str) -> bool:
    """Set the org's tier/status/period + reset plan credits. Idempotent on payment_id.

    Returns True if newly activated, False if this payment was already applied.
    """
    plan = normalize_plan(plan)
    credits = PLAN_CREDITS.get(plan, 0)
    period_days = PLAN_PRICES.get(plan, {}).get("period_days", 30)
    if not _ledger(conn, org_id, kind="reset", amount=credits, balance_after=credits,
                   reason=f"plan:{plan}", idem=f"activate:{payment_id}"):
        return False
    now = datetime.now(timezone.utc)
    conn.execute(text(
        "update orgs set subscription_tier=:t, plan_status='active', credits=:c, "
        "plan_started_at=:now, plan_expires_at=:exp, credit_period_start=:now, "
        "credit_period_end=:exp, grace_until=null where id=:o"),
        {"t": plan, "c": credits, "now": now, "exp": now + timedelta(days=period_days),
         "o": org_id})
    return True


def deduct(conn, org_id: str, cost: int, *, reason: str, idem: str, bucket: str = "context") -> bool:
    """Atomically drain topup first then plan credits. Idempotent. False if insufficient."""
    if cost <= 0:
        return True
    existing = conn.execute(text("select 1 from credit_ledger where org_id=:o and idempotency_key=:i"),
                            {"o": org_id, "i": idem}).first()
    if existing:
        return True                                       # already deducted
    updated = conn.execute(text(
        "update orgs set topup_credits = greatest(0, coalesce(topup_credits,0) - :c), "
        "credits = credits - greatest(0, :c - coalesce(topup_credits,0)) "
        "where id=:o and (coalesce(credits,0)+coalesce(topup_credits,0)) >= :c "
        "returning coalesce(credits,0)+coalesce(topup_credits,0) as bal"),
        {"c": cost, "o": org_id}).first()
    if updated is None:
        return False                                      # insufficient balance
    _ledger(conn, org_id, kind="deduct", amount=-cost, balance_after=int(updated.bal),
            reason=reason, idem=idem, bucket=bucket)
    return True


def razorpay_signature(order_id: str, payment_id: str, secret: str) -> str:
    return hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(),
                    hashlib.sha256).hexdigest()


def verify_razorpay(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    if not (order_id and payment_id and signature and secret):
        return False
    return hmac.compare_digest(razorpay_signature(order_id, payment_id, secret), signature)


def verify_webhook(raw_body: bytes, signature: str, secret: str) -> bool:
    if not (signature and secret):
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
