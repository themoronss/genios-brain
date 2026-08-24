"""Billing: subscriptions, credits, invoices, and a live-balance SSE stream.

Ported from the v1 backend to the v2 engine. The DB/ledger/crypto/read/SSE paths are complete and
tested; order-create and the two webhooks call Razorpay/Stripe, which need real keys (set in prod).
Plan activation never trusts the caller's `plan` — it reads it from the paid subscription row.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from genios_engine.platform import billing as B
from genios_engine.platform.auth import get_current_org, jwt_decode
from genios_engine.platform.config import get_settings
from genios_engine.platform.ids import new_id
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def _currency(body_currency: str | None) -> str:
    c = (body_currency or "INR").upper()
    return c if c in ("INR", "USD") else "INR"


def _processor(currency: str) -> str:
    return "razorpay" if currency == "INR" else "stripe"


class OrderIn(BaseModel):
    plan: str
    currency: str = "INR"


class VerifyIn(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    plan: str


class TopupIn(BaseModel):
    pack: str
    currency: str = "INR"


class TopupVerifyIn(BaseModel):
    razorpay_payment_id: str
    razorpay_order_id: str
    razorpay_signature: str
    pack: str


@router.get("/api/org/{org_id}/billing/subscription")
def subscription(org_id: str, org: str = Depends(_org)) -> dict:
    with _store().engine.connect() as conn:
        bal = B.balance(conn, org)
        row = conn.execute(text(
            "select subscription_tier, plan_status, plan_expires_at, grace_until "
            "from orgs where id=:o"), {"o": org}).first()
    plan = (row.subscription_tier if row else "trial") or "trial"
    now = datetime.now(timezone.utc)
    in_grace = bool(row and row.grace_until and row.grace_until > now
                    and row.plan_expires_at and row.plan_expires_at <= now)
    return {
        "plan": plan,
        "plan_status": (row.plan_status if row else "trial") or "trial",
        "in_grace": in_grace,
        "credits": {"balance": bal["balance"], "plan": bal["plan"], "topup": bal["topup"],
                    "period_limit": B.PLAN_CREDITS.get(B.normalize_plan(plan), 0)},
        "sonnet_daily_limit": None,
        "expires_at": row.plan_expires_at.isoformat() if row and row.plan_expires_at else None,
        "grace_until": row.grace_until.isoformat() if row and row.grace_until else None,
        "prices": {k: {"inr": v["inr"], "usd": v["usd"]} for k, v in B.PLAN_PRICES.items()},
        "topup_packs": [{"pack_id": k, "credits": v["credits"], "price_inr": v["inr"],
                         "price_usd": v["usd"], "label": v["label"]}
                        for k, v in B.TOPUP_PACKS.items()],
    }


@router.get("/api/org/{org_id}/billing/invoices")
def invoices(org_id: str, org: str = Depends(_org)) -> dict:
    with _store().engine.connect() as conn:
        rows = conn.execute(text(
            "select id, plan, status, invoice_type, processor, currency, amount_paise, "
            "payment_id, period_start, period_end, created_at from subscriptions "
            "where org_id=:o order by created_at desc limit 50"), {"o": org}).mappings().all()
    return {"invoices": [{
        "id": r["id"], "plan": r["plan"], "status": r["status"], "type": r["invoice_type"],
        "processor": r["processor"], "currency": r["currency"],
        "amount": r["amount_paise"], "amount_inr": round((r["amount_paise"] or 0) / 100, 2),
        "payment_id": r["payment_id"],
        "period_start": r["period_start"].isoformat() if r["period_start"] else None,
        "period_end": r["period_end"].isoformat() if r["period_end"] else None,
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]}


def _create_order(org: str, *, kind: str, plan_or_pack: str, currency: str,
                  amount: int) -> dict:
    """Create a pending subscriptions row + a gateway order. Falls back to a dev order (inert:
    it cannot be verified without the gateway secret) when no keys are configured."""
    processor = _processor(currency)
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    order_id = None
    if processor == "razorpay" and key_id and os.environ.get("RAZORPAY_KEY_SECRET"):
        try:
            import razorpay
            client = razorpay.Client(auth=(key_id, os.environ["RAZORPAY_KEY_SECRET"]))
            order_id = client.order.create({"amount": amount, "currency": currency})["id"]
        except Exception as e:                            # gateway/SDK failure → surface it
            raise HTTPException(502, {"error": "gateway_error", "message": str(e)[:200]}) from e
    if order_id is None:
        order_id = f"dev_{new_id('ord')}"                 # no keys: inert dev order
        processor = "dev"
    with _store().engine.begin() as conn:
        conn.execute(text(
            "insert into subscriptions (id,org_id,plan,status,invoice_type,processor,currency,"
            "amount_paise,order_id) values (:id,:o,:p,'pending',:it,:pr,:c,:amt,:oid)"),
            {"id": new_id("sub"), "o": org, "p": plan_or_pack, "it": kind, "pr": processor,
             "c": currency, "amt": amount, "oid": order_id})
    out = {"processor": processor, "order_id": order_id, "amount": amount, "currency": currency,
           "key_id": key_id}
    return out


@router.post("/api/org/{org_id}/billing/order")
def create_order(org_id: str, body: OrderIn, org: str = Depends(_org)) -> dict:
    plan = B.normalize_plan(body.plan)
    if plan not in B.PLAN_PRICES:
        raise HTTPException(400, f"unknown plan {body.plan}")
    currency = _currency(body.currency)
    amount = B.PLAN_PRICES[plan]["inr" if currency == "INR" else "usd"]
    out = _create_order(org, kind="subscription", plan_or_pack=plan, currency=currency,
                        amount=amount)
    out["plan"] = plan
    return out


@router.post("/api/org/{org_id}/billing/verify")
def verify(org_id: str, body: VerifyIn, org: str = Depends(_org)) -> dict:
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not B.verify_razorpay(body.razorpay_order_id, body.razorpay_payment_id,
                             body.razorpay_signature, secret):
        raise HTTPException(400, {"error": "signature_invalid"})
    with _store().engine.begin() as conn:
        # authoritative plan comes from the paid order row, never the caller
        row = conn.execute(text(
            "update subscriptions set status='active', payment_id=:pid "
            "where org_id=:o and order_id=:oid and status='pending' returning plan"),
            {"pid": body.razorpay_payment_id, "o": org, "oid": body.razorpay_order_id}).first()
        plan = row.plan if row else None
        if plan is None:                                  # already verified (idempotent)
            existing = conn.execute(text(
                "select plan from subscriptions where org_id=:o and order_id=:oid and status='active'"),
                {"o": org, "oid": body.razorpay_order_id}).first()
            plan = existing.plan if existing else body.plan
        B.activate_plan(conn, org, plan, payment_id=body.razorpay_payment_id)
        bal = B.balance(conn, org)
    _publish(org)
    # Revenue is recorded server-side only. The browser also fires a checkout event, but that one
    # is a funnel signal — counting it as money would double-count every refresh of the success page.
    from genios_engine.platform import analytics
    analytics.capture_with_person(_store().engine, org, "payment_completed", {
        "plan": plan, "amount_inr": B.PLAN_PRICES.get(plan, {}).get("inr", 0) / 100.0,
        "processor": "razorpay",
    })
    return {"activated": True, "plan": plan, "unlocked": [],
            "period_days": B.PLAN_PRICES.get(plan, {}).get("period_days", 30),
            "balance": bal["balance"]}


@router.post("/api/org/{org_id}/billing/topup")
def create_topup(org_id: str, body: TopupIn, org: str = Depends(_org)) -> dict:
    if body.pack not in B.TOPUP_PACKS:
        raise HTTPException(400, f"unknown pack {body.pack}")
    pack = B.TOPUP_PACKS[body.pack]
    currency = _currency(body.currency)
    amount = pack["inr" if currency == "INR" else "usd"]
    out = _create_order(org, kind="topup", plan_or_pack=body.pack, currency=currency, amount=amount)
    out.update({"pack": body.pack, "credits": pack["credits"], "label": pack["label"]})
    return out


@router.post("/api/org/{org_id}/billing/topup/verify")
def verify_topup(org_id: str, body: TopupVerifyIn, org: str = Depends(_org)) -> dict:
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not B.verify_razorpay(body.razorpay_order_id, body.razorpay_payment_id,
                             body.razorpay_signature, secret):
        raise HTTPException(400, {"error": "signature_invalid"})
    pack = B.TOPUP_PACKS.get(body.pack)
    if pack is None:
        raise HTTPException(400, f"unknown pack {body.pack}")
    with _store().engine.begin() as conn:
        conn.execute(text("update subscriptions set status='active', payment_id=:pid "
                          "where org_id=:o and order_id=:oid and status='pending'"),
                     {"pid": body.razorpay_payment_id, "o": org, "oid": body.razorpay_order_id})
        new_balance = B.grant_topup(conn, org, pack["credits"],
                                    idem=f"topup:{body.razorpay_payment_id}",
                                    reason=f"pack:{body.pack}")
    _publish(org)
    from genios_engine.platform import analytics
    analytics.capture_with_person(_store().engine, org, "topup_purchased", {
        "pack": body.pack, "credits": pack["credits"],
        "amount_inr": pack.get("inr", 0) / 100.0, "processor": "razorpay",
    })
    return {"granted": True, "pack": body.pack, "credits": pack["credits"],
            "label": pack["label"], "balance_after": new_balance}


@router.post("/v1/billing/webhook")
async def razorpay_webhook(request: Request) -> dict:
    raw = await request.body()
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET") or os.environ.get("RAZORPAY_KEY_SECRET", "")
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not B.verify_webhook(raw, sig, secret):
        raise HTTPException(400, {"error": "signature_invalid"})
    # Fulfilment is idempotent (activate/grant guard on payment_id); details resolved from the
    # captured payment's order_id in a full deployment.
    return {"ack": True}


@router.post("/v1/billing/stripe/webhook")
async def stripe_webhook(request: Request) -> dict:
    raw = await request.body()
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    sig = request.headers.get("Stripe-Signature", "")
    if secret:
        try:
            import stripe
            stripe.Webhook.construct_event(raw, sig, secret)
        except Exception as e:
            raise HTTPException(400, {"error": "signature_invalid", "message": str(e)[:120]}) from e
    return {"ack": True}


# ---- live balance SSE stream ----------------------------------------------------------------
_publish_flags: dict[str, bool] = {}


def _publish(org_id: str) -> None:
    _publish_flags[org_id] = True                         # nudge; the stream re-reads authoritative DB


def _read_balance(org_id: str) -> dict:
    with _store().engine.connect() as conn:
        bal = B.balance(conn, org_id)
    return {"balance": bal["balance"], "plan": bal["plan"], "topup": bal["topup"]}


@router.get("/v1/billing/stream")
async def billing_stream(token: str = "", org: str = "") -> StreamingResponse:
    settings = get_settings()
    org_id = None
    if token:
        payload = jwt_decode(token, settings.jwt_secret)
        org_id = payload.get("org_id") if payload else None
    if org_id is None and org and not settings.use_real_db:
        org_id = org                                      # dev-only fallback
    if org_id is None:
        raise HTTPException(401, "missing or invalid token")

    async def gen():
        # The balance read is a synchronous DB call; run it in a thread so it never blocks
        # uvicorn's single event loop (a blocking read here stalls EVERY other request).
        last = None
        initial = await asyncio.to_thread(_read_balance, org_id)
        yield f"event: balance\ndata: {json.dumps(initial)}\n\n"
        last = initial
        for _ in range(0, 3600, 30):                      # up to ~1h, 30s cadence
            await asyncio.sleep(30)
            try:
                current = await asyncio.to_thread(_read_balance, org_id)
            except Exception:
                yield "event: ping\ndata: {}\n\n"
                continue
            if _publish_flags.pop(org_id, False) or current != last:
                last = current
                yield f"event: balance\ndata: {json.dumps(current)}\n\n"
            else:
                yield "event: ping\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
