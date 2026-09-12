"""Billing credits/ledger/crypto/read paths on real Postgres (skips without DB).

The gateway order-create and webhook delivery need real Razorpay/Stripe keys (prod only); this
covers everything else: plan activation, idempotency, deduction, topups, invoices, signature guard.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("GENIOS_TEST_DATABASE_URL"),
    reason="GENIOS_TEST_DATABASE_URL not set")

_SECRET = "test_secret_123"


def _setup(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", _SECRET)
    from genios_engine.api import billing_routes as BR
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.migrate import apply_migrations
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    apply_migrations(database_url=url)
    BR._graph = GraphStore(url)
    org = "bill_org"
    with BR._graph.engine.begin() as c:
        c.execute(text("insert into orgs (id,name,subscription_tier,plan_status) "
                       "values (:o,'S','trial','trial') on conflict (id) do update "
                       "set subscription_tier='trial', credits=0, topup_credits=0, "
                       "plan_expires_at=null, grace_until=null"), {"o": org})
        _wipe(c, org)
    return BR, org


def _wipe(conn, org: str) -> None:
    """Zeroing the columns is not enough to reset a tenant: `grant_topup` and `activate_plan` are
    idempotent on the LEDGER, so a surviving row from an earlier run makes the next grant a
    no-op and the test reads as a broken grant rather than a dirty database."""
    conn.execute(text("delete from credit_ledger where org_id=:o"), {"o": org})
    conn.execute(text("delete from subscriptions where org_id=:o"), {"o": org})


def test_billing_activate_deduct_topup(monkeypatch):
    from genios_engine.platform import billing as B
    BR, org = _setup(monkeypatch)

    sub = BR.subscription(org, org=org)
    assert sub["plan"] == "trial" and len(sub["topup_packs"]) == 3

    order = BR.create_order(org, BR.OrderIn(plan="startup", currency="INR"), org=org)
    assert order["amount"] == 2500000                     # ₹25,000 in paise

    sig = B.razorpay_signature(order["order_id"], "pay_1", _SECRET)
    v = BR.verify(org, BR.VerifyIn(razorpay_payment_id="pay_1", razorpay_order_id=order["order_id"],
                                   razorpay_signature=sig, plan="startup"), org=org)
    assert v["activated"] and v["plan"] == "startup" and v["balance"] == 100_000  # credits

    # idempotent re-verify — the same payment never double-grants
    v2 = BR.verify(org, BR.VerifyIn(razorpay_payment_id="pay_1", razorpay_order_id=order["order_id"],
                                    razorpay_signature=sig, plan="startup"), org=org)
    assert v2["balance"] == 100_000

    with BR._graph.engine.begin() as c:
        # POINTS below the API line: 3 credits is 300 points.
        assert B.deduct(c, org, 300, reason="query", idem="q1") is True
        assert B.balance(c, org)["balance_credits"] == 99_997
        assert B.deduct(c, org, 300, reason="query", idem="q1") is True   # idempotent
        assert B.balance(c, org)["balance_credits"] == 99_997

    # A top-up is redeemed against its OWN order. This used to pass the SUBSCRIPTION order id
    # and still be granted 5,000 credits, because fulfilment took the pack from the caller
    # instead of from the paid row — anyone who could sign one order could claim any pack.
    topup = BR.create_topup(org, BR.TopupIn(pack="small", currency="INR"), org=org)
    tsig = B.razorpay_signature(topup["order_id"], "tp1", _SECRET)
    tv = BR.verify_topup(org, BR.TopupVerifyIn(razorpay_payment_id="tp1",
                                               razorpay_order_id=topup["order_id"],
                                               razorpay_signature=tsig, pack="small"), org=org)
    assert tv["balance_after"] == 99_997 + 5_000

    with pytest.raises(HTTPException):                    # the subscription order is not a pack
        BR.verify_topup(org, BR.TopupVerifyIn(
            razorpay_payment_id="tp2", razorpay_order_id=order["order_id"],
            razorpay_signature=B.razorpay_signature(order["order_id"], "tp2", _SECRET),
            pack="large"), org=org)

    assert BR.invoices(org, org=org)["invoices"][0]["status"] == "active"


def test_bad_signature_is_rejected(monkeypatch):
    BR, org = _setup(monkeypatch)
    with pytest.raises(Exception):
        BR.verify(org, BR.VerifyIn(razorpay_payment_id="x", razorpay_order_id="y",
                                   razorpay_signature="bad", plan="startup"), org=org)


# ── plan lifecycle on real Postgres ──────────────────────────────────────────────────────────
#
# The trial that never ended. `run_billing_tick` is the only thing in the product that writes
# `plan_status='expired'` or sets `grace_until`, and `refusal_for` is the gate that turns those
# columns into a 402 the customer can act on.

def _org_with(BR, org, *, tier, status, expires_days, grace_days=None, credits=100):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    with BR._graph.engine.begin() as c:
        c.execute(text(
            "insert into orgs (id,name,subscription_tier,plan_status,credits,topup_credits,"
            "plan_expires_at,grace_until) values (:o,'S',:t,:s,:cr,0,:exp,:gr) "
            "on conflict (id) do update set subscription_tier=:t, plan_status=:s, credits=:cr, "
            "topup_credits=0, plan_expires_at=:exp, grace_until=:gr"),
            {"o": org, "t": tier, "s": status, "cr": credits,
             "exp": None if expires_days is None else now + timedelta(days=expires_days),
             "gr": None if grace_days is None else now + timedelta(days=grace_days)})
        _wipe(c, org)
    return now


def test_the_tick_expires_a_lapsed_trial_and_opens_its_grace_window(monkeypatch):
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_lapsed"
    _org_with(BR, org, tier="trial", status="trial", expires_days=-1)

    assert B.run_billing_tick(BR._graph.engine)["expired"] >= 1

    with BR._graph.engine.connect() as c:
        row = c.execute(text("select plan_status, grace_until from orgs where id=:o"),
                        {"o": org}).first()
    assert row.plan_status == "expired"
    assert row.grace_until is not None, "grace was never opened — the banner has nothing to read"


def test_the_tick_leaves_a_live_trial_alone(monkeypatch):
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_live"
    _org_with(BR, org, tier="trial", status="trial", expires_days=5)

    B.run_billing_tick(BR._graph.engine)

    with BR._graph.engine.connect() as c:
        row = c.execute(text("select plan_status, grace_until from orgs where id=:o"),
                        {"o": org}).first()
    assert row.plan_status == "trial"
    assert row.grace_until is None


def test_the_tick_is_idempotent_and_never_re_opens_grace(monkeypatch):
    """It runs on every scheduler heartbeat. A second pass must not push the grace window
    forward, or an expired account would be granted grace for ever."""
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_idem"
    _org_with(BR, org, tier="trial", status="trial", expires_days=-1)

    B.run_billing_tick(BR._graph.engine)
    with BR._graph.engine.connect() as c:
        first = c.execute(text("select grace_until from orgs where id=:o"), {"o": org}).scalar()
    B.run_billing_tick(BR._graph.engine)
    with BR._graph.engine.connect() as c:
        second = c.execute(text("select grace_until from orgs where id=:o"), {"o": org}).scalar()
    assert first == second


def test_a_trial_inside_grace_can_still_spend_what_it_has(monkeypatch):
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_grace"
    # One credit (100 points): enough for the cheapest billable unit, a query. Grace must not
    # refuse a balance that can still pay for something.
    _org_with(BR, org, tier="trial", status="expired", expires_days=-1, grace_days=5, credits=100)
    with BR._graph.engine.connect() as c:
        assert B.refusal_for(c, org) is None


def test_past_grace_the_refusal_names_the_plan_not_the_wallet(monkeypatch):
    """A customer with credits left but an ended trial must be sent to Upgrade, not to Top-up."""
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_over"
    _org_with(BR, org, tier="trial", status="expired", expires_days=-30, grace_days=-1, credits=500)
    with BR._graph.engine.connect() as c:
        refusal = B.refusal_for(c, org)
    assert refusal["code"] == "PLAN_EXPIRED"
    assert "trial" in refusal["message"].lower()


def test_an_empty_wallet_on_a_live_plan_names_the_wallet(monkeypatch):
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_empty"
    _org_with(BR, org, tier="startup", status="active", expires_days=20, credits=0)
    with BR._graph.engine.connect() as c:
        refusal = B.refusal_for(c, org)
    assert refusal["code"] == "OUT_OF_CREDITS"


def test_a_healthy_paid_org_is_refused_nothing(monkeypatch):
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_ok"
    _org_with(BR, org, tier="startup", status="active", expires_days=20, credits=5000)
    with BR._graph.engine.connect() as c:
        assert B.refusal_for(c, org) is None


def test_the_ledger_route_tells_the_customer_where_the_credits_went(monkeypatch):
    """`credit_ledger.bucket` was written from the start and read only by the admin console."""
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_ledger"
    _org_with(BR, org, tier="startup", status="active", expires_days=20,
              credits=1000 * 100)                           # 1,000 credits, in points
    with BR._graph.engine.begin() as c:
        c.execute(text("delete from credit_ledger where org_id=:o"), {"o": org})
        c.execute(text("update orgs set credit_period_start=now() - interval '1 day' where id=:o"),
                  {"o": org})
        B.deduct(c, org, B.cost_of("intelligence_query"), reason="q", idem="L1", bucket="query")
        # Rows filed before only the query endpoint was billed. They stay on the ledger and
        # must still render in the customer's rollup.
        B.deduct(c, org, 200, reason="intelligence_analyze", idem="L2", bucket="analyze")
        B.deduct(c, org, 150, reason="intelligence_draft", idem="L3", bucket="draft")
        B.deduct(c, org, 24_800, reason="message_read", idem="L4", bucket="ingest", units=1_240)

    out = BR.ledger(org, org=org)
    assert out["spent_by_bucket"] == {"query": 1.0, "analyze": 2.0, "draft": 1.5, "ingest": 248.0}
    assert out["spent_total"] == 252.5
    assert len(out["entries"]) == 4
    # the published price list names the one billable action and nothing else
    assert out["action_prices"] == {"intelligence_query": 1.0}
    ingest = [e for e in out["entries"] if e["bucket"] == "ingest"][0]
    assert (ingest["units"], ingest["amount"]) == (1_240, -248.0)


def test_subscription_reports_the_live_plan_allowance_and_the_grace_flag(monkeypatch):
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    org = "bill_sub"
    _org_with(BR, org, tier="startup", status="expired", expires_days=-1, grace_days=3, credits=7)

    out = BR.subscription(org, org=org)
    assert out["state"] == "grace" and out["in_grace"] is True
    assert out["credits"]["period_limit"] == B.PLANS["startup"].credits
    assert out["credits"]["daily_limit"] == B.to_credits(B.daily_credit_ceiling("startup"))
    assert out["currencies"] == ["INR"]


def test_usd_checkout_is_refused_at_the_door(monkeypatch):
    """It used to produce a `processor="dev"` order that could never be verified, and the browser
    then opened Razorpay with `key_id: undefined`."""
    from fastapi import HTTPException
    BR, org = _setup(monkeypatch)
    with pytest.raises(HTTPException) as e:
        BR.create_order(org, BR.OrderIn(plan="startup", currency="USD"), org=org)
    assert e.value.status_code == 400
    assert e.value.detail["code"] == "CURRENCY_UNSUPPORTED"


def test_usage_is_read_from_the_ledger_not_from_decisions(monkeypatch):
    """It used to count rows in `decisions` since the 1st of the calendar month against a
    hardcoded limit, so it disagreed with the balance in both directions."""
    from genios_engine.api import account_routes as AR
    from genios_engine.platform import billing as B
    BR, _ = _setup(monkeypatch)
    AR._graph = BR._graph
    org = "bill_usage"
    _org_with(BR, org, tier="individual", status="active", expires_days=10,
              credits=900 * 100)                            # 900 credits, in points
    with BR._graph.engine.begin() as c:
        c.execute(text("delete from credit_ledger where org_id=:o"), {"o": org})
        c.execute(text("update orgs set credit_period_start=now() - interval '2 days' where id=:o"),
                  {"o": org})
        B.deduct(c, org, 200, reason="q", idem="U1", bucket="query")
        B.deduct(c, org, 400, reason="a", idem="U2", bucket="analyze")

    out = AR.usage(org, org=org)
    assert out["period_used"] == 6.0
    assert out["by_bucket"] == {"query": 2.0, "analyze": 4.0}
    assert out["period_limit"] == B.PLANS["individual"].credits, "it used to fall to 100"
    assert out["today_limit"] == B.to_credits(B.daily_credit_ceiling("individual"))
    assert out["balance"] == 900 - 6
    assert out["expires_at"] is not None and out["days_remaining"] is not None


# ── webhook fulfilment ───────────────────────────────────────────────────────────────────────
#
# The webhook used to verify its signature and `return {"ack": True}`. Nothing else. So a payment
# only became credits if the customer's browser stayed open long enough to POST /verify — close
# the tab between capture and return and they were charged and got nothing, with no async path
# that could ever notice.

import hashlib
import hmac
import json


def _signed(body: dict) -> tuple[bytes, str]:
    raw = json.dumps(body).encode()
    return raw, hmac.new(_SECRET.encode(), raw, hashlib.sha256).hexdigest()


class _FakeRequest:
    def __init__(self, raw: bytes, sig: str):
        self._raw, self.headers = raw, {"X-Razorpay-Signature": sig}

    async def body(self):
        return self._raw


def _captured(order_id: str, payment_id: str, event: str = "payment.captured") -> dict:
    return {"event": event,
            "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id,
                                               "status": "captured"}}}}


def _pending_order(BR, org, *, plan, kind, order_id):
    from genios_engine.platform.ids import new_id
    with BR._graph.engine.begin() as c:
        c.execute(text("delete from subscriptions where order_id=:oid"), {"oid": order_id})
        c.execute(text(
            "insert into subscriptions (id,org_id,plan,status,invoice_type,processor,currency,"
            "amount_paise,order_id) values (:id,:o,:p,'pending',:it,'razorpay','INR',1,:oid)"),
            {"id": new_id("sub"), "o": org, "p": plan, "it": kind, "oid": order_id})


def _run(coro):
    import asyncio
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_a_closed_browser_still_gets_the_plan(monkeypatch):
    from genios_engine.platform import billing as B
    BR, org = _setup(monkeypatch)
    _org_with(BR, org, tier="trial", status="trial", expires_days=3, credits=0)
    _pending_order(BR, org, plan="startup", kind="subscription", order_id="order_wh_1")

    raw, sig = _signed(_captured("order_wh_1", "pay_wh_1"))
    out = _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))

    assert out["fulfilled"] is True and out["org"] == org
    with BR._graph.engine.connect() as c:
        row = c.execute(text("select subscription_tier, plan_status from orgs where id=:o"),
                        {"o": org}).first()
        assert row.subscription_tier == "startup" and row.plan_status == "active"
        assert B.balance(c, org)["balance_credits"] == B.PLANS["startup"].credits


def test_a_topup_webhook_grants_the_pack(monkeypatch):
    from genios_engine.platform import billing as B
    BR, org = _setup(monkeypatch)
    _org_with(BR, org, tier="startup", status="active", expires_days=20, credits=0)
    _pending_order(BR, org, plan="medium", kind="topup", order_id="order_wh_2")

    raw, sig = _signed(_captured("order_wh_2", "pay_wh_2"))
    out = _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))

    assert out["fulfilled"] is True
    with BR._graph.engine.connect() as c:
        assert B.balance(c, org)["topup_credits_display"] == B.TOPUP_PACKS["medium"]["credits"]


def test_the_webhook_and_the_browser_cannot_both_grant(monkeypatch):
    """Both fire on a normal successful payment. The ledger's payment_id guard is what stops the
    customer being given the plan twice."""
    from genios_engine.platform import billing as B
    BR, org = _setup(monkeypatch)
    _org_with(BR, org, tier="trial", status="trial", expires_days=3, credits=0)
    _pending_order(BR, org, plan="startup", kind="subscription", order_id="order_wh_3")

    raw, sig = _signed(_captured("order_wh_3", "pay_wh_3"))
    _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))
    with BR._graph.engine.begin() as c:
        B.deduct(c, org, 500 * B.POINTS_PER_CREDIT, reason="q", idem="wh_spend",
                 bucket="query")
    _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))          # a retry from Razorpay

    with BR._graph.engine.connect() as c:
        assert B.balance(c, org)["balance_credits"] == B.PLANS["startup"].credits - 500


def test_the_browser_return_now_goes_through_the_same_path(monkeypatch):
    from genios_engine.platform import billing as B
    BR, org = _setup(monkeypatch)
    _org_with(BR, org, tier="trial", status="trial", expires_days=3, credits=0)
    _pending_order(BR, org, plan="individual", kind="subscription", order_id="order_wh_4")

    out = BR.verify(org, BR.VerifyIn(
        razorpay_payment_id="pay_wh_4", razorpay_order_id="order_wh_4",
        razorpay_signature=B.razorpay_signature("order_wh_4", "pay_wh_4", _SECRET),
        plan="startup"), org=org)                              # caller LIES about the plan

    assert out["plan"] == "individual", "the plan comes from the paid order, never the caller"
    with BR._graph.engine.connect() as c:
        assert B.balance(c, org)["balance_credits"] == B.PLANS["individual"].credits


def test_a_failed_payment_is_recorded_and_never_fulfilled(monkeypatch):
    from genios_engine.platform import billing as B
    BR, org = _setup(monkeypatch)
    _org_with(BR, org, tier="trial", status="trial", expires_days=3, credits=0)
    _pending_order(BR, org, plan="startup", kind="subscription", order_id="order_wh_5")

    raw, sig = _signed(_captured("order_wh_5", "pay_wh_5", event="payment.failed"))
    out = _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))

    assert out["fulfilled"] is False
    with BR._graph.engine.connect() as c:
        assert c.execute(text("select status from subscriptions where order_id='order_wh_5'"),
                         ).scalar() == "failed"
        assert B.balance(c, org)["balance"] == 0


def test_an_unsigned_webhook_is_refused(monkeypatch):
    from fastapi import HTTPException
    BR, _ = _setup(monkeypatch)
    raw, _sig = _signed(_captured("order_x", "pay_x"))
    with pytest.raises(HTTPException) as e:
        _run(BR.razorpay_webhook(_FakeRequest(raw, "deadbeef")))
    assert e.value.status_code == 400


def test_an_unknown_order_is_acked_not_retried_for_ever(monkeypatch):
    """A 4xx makes Razorpay retry a body we will never be able to fulfil."""
    BR, _ = _setup(monkeypatch)
    raw, sig = _signed(_captured("order_never_created", "pay_z"))
    out = _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))
    assert out == {"ack": True, "fulfilled": False, "reason": "unknown_order"}


def test_an_unrecognised_event_shape_is_a_no_op_not_a_500(monkeypatch):
    BR, _ = _setup(monkeypatch)
    raw, sig = _signed({"event": "payment.captured", "payload": {}})
    assert _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))["fulfilled"] is False
    raw, sig = _signed({"event": "subscription.charged", "payload": {
        "payment": {"entity": {"id": "p", "order_id": "o"}}}})
    assert _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))["fulfilled"] is False


def test_a_signed_webhook_cannot_grant_across_tenants(monkeypatch):
    """The org is read from the order row. A body that could name its own org would turn a leaked
    webhook secret into a free enterprise plan for anyone."""
    from genios_engine.platform import billing as B
    BR, org = _setup(monkeypatch)
    other = "bill_other_tenant"
    _org_with(BR, org, tier="trial", status="trial", expires_days=3, credits=0)
    _org_with(BR, other, tier="trial", status="trial", expires_days=3, credits=0)
    _pending_order(BR, other, plan="startup", kind="subscription", order_id="order_wh_6")

    raw, sig = _signed(_captured("order_wh_6", "pay_wh_6"))
    out = _run(BR.razorpay_webhook(_FakeRequest(raw, sig)))

    assert out["org"] == other
    with BR._graph.engine.connect() as c:
        assert B.balance(c, org)["balance"] == 0


def test_there_is_no_stripe_webhook_route(monkeypatch):
    """It verified a signature and acked, for sessions `_create_order` has never been able to
    create. A route that looks like a payment path and is not is worse than no route."""
    BR, _ = _setup(monkeypatch)
    assert not hasattr(BR, "stripe_webhook")
    assert not any("stripe" in getattr(r, "path", "") for r in BR.router.routes)
