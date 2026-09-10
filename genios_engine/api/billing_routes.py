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
from genios_engine.platform.logging import get_logger
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()
_log = get_logger("genios.billing")

# There is NO Stripe webhook. There was one, and it verified a signature and acked —
# but `_create_order` has only ever built Razorpay orders, so no Stripe session could
# exist for it to fulfil. It is removed rather than left as a route that looks like a
# payment path and is not; USD is refused at `_currency` until Stripe is actually built.


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


#: The currencies checkout can actually complete. USD is NOT one of them: `_create_order` only
#: ever builds a Razorpay order, so a USD request used to fall through to `processor="dev"` — an
#: order that can never be verified — and the frontend then opened Razorpay with
#: `key_id: undefined`. Every non-INR upgrade failed silently. Until a Stripe Checkout Session
#: and its webhook fulfilment exist, USD is refused at the door where the customer can see it.
SUPPORTED_CURRENCIES = ("INR",)


def _currency(body_currency: str | None) -> str:
    c = (body_currency or "INR").upper()
    if c not in SUPPORTED_CURRENCIES:
        raise HTTPException(400, {
            "code": "CURRENCY_UNSUPPORTED",
            "message": "Card payments are currently available in INR only. "
                       "Write to us and we will invoice you directly."})
    return c


def _processor(currency: str) -> str:
    return "razorpay"


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
    state = B.expiry_state(row.plan_status if row else None,
                           row.plan_expires_at if row else None,
                           row.grace_until if row else None, now=now)
    return {
        "plan": plan,
        "plan_status": (row.plan_status if row else "trial") or "trial",
        "state": state,                                   # active | grace | expired
        "in_grace": state == "grace",
        # CREDITS, as the customer reads them — the store is points, the API is not.
        "credits": {"balance": B.to_credits(bal["balance"]),
                    "plan": B.to_credits(bal["plan"]),
                    "topup": B.to_credits(bal["topup"]),
                    "period_limit": B.plan_of(plan).credits,
                    "daily_limit": B.to_credits(B.daily_credit_ceiling(plan))},
        "action_prices": {a: B.to_credits(pts) for a, pts in B.COSTS.items()},
        "free_units": list(B.FREE_UNITS),                   # what each billable action costs
        "currencies": list(SUPPORTED_CURRENCIES),
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


@router.get("/api/org/{org_id}/billing/ledger")
def ledger(org_id: str, limit: int = 100, org: str = Depends(_org)) -> dict:
    """Every credit movement, plus a per-bucket rollup for the current period.

    `credit_ledger.bucket` has always been written (`query` / `analyze` / `draft` / `topup`) and
    until now only `admin_routes` read it, so the customer could see a balance falling and had
    no way to answer "where did my credits go".
    """
    limit = max(1, min(int(limit or 100), 500))
    with _store().engine.connect() as conn:
        period_start = conn.execute(text(
            "select coalesce(credit_period_start, plan_started_at) from orgs where id=:o"),
            {"o": org}).scalar()
        rows = conn.execute(text(
            "select occurred_at, kind, bucket, amount, balance_after, reason, metadata "
            "from credit_ledger where org_id=:o order by occurred_at desc limit :n"),
            {"o": org, "n": limit}).mappings().all()
        rollup = {r.bucket or "other": int(r.n) for r in conn.execute(text(
            "select bucket, coalesce(sum(-amount),0) n from credit_ledger "
            "where org_id=:o and kind='deduct' and occurred_at >= coalesce(:s, '-infinity'::timestamptz) "
            "group by bucket"), {"o": org, "s": period_start})}
    return {
        "period_start": period_start.isoformat() if period_start else None,
        "spent_by_bucket": {k: B.to_credits(v) for k, v in rollup.items()},
        "spent_total": B.to_credits(sum(rollup.values())),
        "action_prices": {a: B.to_credits(pts) for a, pts in B.COSTS.items()},
        "entries": [{
            "at": r["occurred_at"].isoformat() if r["occurred_at"] else None,
            "kind": r["kind"], "bucket": r["bucket"],
            "amount": B.to_credits(int(r["amount"] or 0)),
            "balance_after": B.to_credits(int(r["balance_after"] or 0)),
            "units": (r["metadata"] or {}).get("units") if r["metadata"] else None,
            "reason": r["reason"],
        } for r in rows],
    }


def _create_order(org: str, *, kind: str, plan_or_pack: str, currency: str,
                  amount: int) -> dict:
    """Create a pending subscriptions row + a gateway order. Falls back to a dev order (inert:
    it cannot be verified without the gateway secret) when no keys are configured."""
    processor = _processor(currency)
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    order_id = None
    if key_id and os.environ.get("RAZORPAY_KEY_SECRET"):
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


def _fulfil(conn, *, order_id: str, payment_id: str) -> dict | None:
    """Mark a paid order active and grant what it bought. The ONLY place a payment turns into
    credits — the browser's `verify` return and the gateway's webhook both come through here.

    The org, the plan and the pack are read from the ORDER ROW, never from the caller: a webhook
    is authenticated by an HMAC over the body and nothing else, so a body that could name its own
    org or plan would let anyone who learned the secret grant themselves an enterprise plan.

    Idempotent twice over, which is what makes the two paths safe to race: the status update only
    fires on a `pending` row, and `activate_plan` / `grant_topup` both guard on `payment_id`.
    Returns None when no such order exists (a webhook for an order we never created).
    """
    row = conn.execute(text(
        "select id, org_id, plan, invoice_type from subscriptions where order_id=:oid"),
        {"oid": order_id}).first()
    if row is None:
        return None
    conn.execute(text(
        "update subscriptions set status='active', payment_id=coalesce(payment_id, :pid) "
        "where id=:id and status <> 'active'"), {"pid": payment_id, "id": row.id})
    if row.invoice_type == "topup":
        pack = B.TOPUP_PACKS.get(row.plan)
        if pack is None:                                  # a pack we retired after selling it
            return None
        # The pack is advertised in CREDITS and the pool is kept in POINTS. Granting the raw
        # number here would hand a 25,000-credit pack 25,000 points — 250 credits, a 100x
        # short-change on something the customer paid for.
        balance = B.grant_topup(conn, row.org_id, pack["credits"] * B.POINTS_PER_CREDIT,
                                idem=f"topup:{payment_id}", reason=f"pack:{row.plan}")
        return {"org": row.org_id, "kind": "topup", "pack": row.plan,
                "credits": pack["credits"], "label": pack["label"], "balance": balance}
    newly = B.activate_plan(conn, row.org_id, row.plan, payment_id=payment_id)
    return {"org": row.org_id, "kind": "subscription", "plan": row.plan,
            "newly_activated": newly, "balance": B.balance(conn, row.org_id)["balance"]}


def _announce(result: dict) -> None:
    """SSE nudge + the server-side revenue event. Best-effort: the money is already committed."""
    try:
        _publish(result["org"])
        from genios_engine.platform import analytics
        if result["kind"] == "topup":
            pack = B.TOPUP_PACKS.get(result["pack"], {})
            analytics.capture_with_person(_store().engine, result["org"], "topup_purchased", {
                "pack": result["pack"], "credits": result["credits"],
                "amount_inr": pack.get("inr", 0) / 100.0, "processor": "razorpay"})
        elif result.get("newly_activated"):                # never re-count a replayed payment
            analytics.capture_with_person(_store().engine, result["org"], "payment_completed", {
                "plan": result["plan"],
                "amount_inr": B.PLAN_PRICES.get(result["plan"], {}).get("inr", 0) / 100.0,
                "processor": "razorpay"})
    except Exception:                                     # noqa: BLE001
        pass


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
        result = _fulfil(conn, order_id=body.razorpay_order_id,
                         payment_id=body.razorpay_payment_id)
    if result is None or result["kind"] != "subscription":
        raise HTTPException(404, {"error": "order_not_found"})
    if result["org"] != org:                              # a signed payment for someone else
        raise HTTPException(403, "org mismatch")
    _announce(result)                                     # revenue is recorded server-side only
    plan = result["plan"]
    return {"activated": True, "plan": plan, "unlocked": [],
            "period_days": B.PLAN_PRICES.get(plan, {}).get("period_days", 30),
            "balance": B.to_credits(result["balance"])}


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
    if body.pack not in B.TOPUP_PACKS:
        raise HTTPException(400, f"unknown pack {body.pack}")
    with _store().engine.begin() as conn:
        result = _fulfil(conn, order_id=body.razorpay_order_id,
                         payment_id=body.razorpay_payment_id)
    if result is None or result["kind"] != "topup":
        raise HTTPException(404, {"error": "order_not_found"})
    if result["org"] != org:
        raise HTTPException(403, "org mismatch")
    _announce(result)
    return {"granted": True, "pack": result["pack"], "credits": result["credits"],
            "label": result["label"], "balance_after": B.to_credits(result["balance"])}


# ── the webhook, which is the ONLY path that survives a closed browser ───────────────────────
#
# This used to verify the signature and `return {"ack": True}` — nothing else. So the entire
# fulfilment of a payment hung on the customer's tab staying open long enough to POST /verify:
# close it between capture and return, or lose the network, and they were charged and got
# nothing, with no async path that could ever notice. Razorpay retries a webhook it does not get
# a 2xx for, so this is also the recovery path for our own downtime.


def _payment_from(event: dict) -> tuple[str, str] | None:
    """(order_id, payment_id) out of a Razorpay event, or None if it carries neither.

    `payment.captured` and `payment.failed` both put the entity at payload.payment.entity;
    `order.paid` carries the order too. Read defensively — an unexpected shape must be a
    no-op ack, not a 500 that makes Razorpay retry the same unusable body for hours.
    """
    payload = event.get("payload") or {}
    payment = ((payload.get("payment") or {}).get("entity") or {})
    order = ((payload.get("order") or {}).get("entity") or {})
    order_id = payment.get("order_id") or order.get("id")
    payment_id = payment.get("id")
    if not order_id or not payment_id:
        return None
    return str(order_id), str(payment_id)


@router.post("/v1/billing/webhook")
async def razorpay_webhook(request: Request) -> dict:
    raw = await request.body()
    secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET") or os.environ.get("RAZORPAY_KEY_SECRET", "")
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not B.verify_webhook(raw, sig, secret):
        raise HTTPException(400, {"error": "signature_invalid"})
    try:
        event = json.loads(raw or b"{}")
    except ValueError:
        return {"ack": True, "fulfilled": False, "reason": "unparseable"}
    kind = str(event.get("event") or "")
    ids = _payment_from(event)
    if ids is None:
        return {"ack": True, "fulfilled": False, "reason": "no_payment_in_payload"}
    order_id, payment_id = ids

    if kind == "payment.failed":
        # Recorded, never fulfilled. A pending row left pending for ever is indistinguishable
        # from an order the customer simply abandoned, and support cannot tell them apart.
        with _store().engine.begin() as conn:
            conn.execute(text("update subscriptions set status='failed', payment_id=:pid "
                              "where order_id=:oid and status='pending'"),
                         {"pid": payment_id, "oid": order_id})
        return {"ack": True, "fulfilled": False, "reason": "payment_failed"}

    if kind not in ("payment.captured", "order.paid"):
        return {"ack": True, "fulfilled": False, "reason": f"ignored:{kind}"}

    with _store().engine.begin() as conn:
        result = _fulfil(conn, order_id=order_id, payment_id=payment_id)
    if result is None:
        # 200, deliberately. A 4xx makes Razorpay retry an order we will never recognise.
        _log.warning("billing webhook for unknown order %s", order_id)
        return {"ack": True, "fulfilled": False, "reason": "unknown_order"}
    _announce(result)
    return {"ack": True, "fulfilled": True, "kind": result["kind"], "org": result["org"]}


# ---- live balance SSE stream ----------------------------------------------------------------
_publish_flags: dict[str, bool] = {}


def _publish(org_id: str) -> None:
    _publish_flags[org_id] = True                         # nudge; the stream re-reads authoritative DB


def _read_balance(org_id: str) -> dict:
    with _store().engine.connect() as conn:
        bal = B.balance(conn, org_id)
    return {"balance": B.to_credits(bal["balance"]), "plan": B.to_credits(bal["plan"]),
            "topup": B.to_credits(bal["topup"])}


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
