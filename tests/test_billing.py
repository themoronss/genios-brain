"""Billing credits/ledger/crypto/read paths on real Postgres (skips without DB).

The gateway order-create and webhook delivery need real Razorpay/Stripe keys (prod only); this
covers everything else: plan activation, idempotency, deduction, topups, invoices, signature guard.
"""

from __future__ import annotations

import os

import pytest
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
                       "set subscription_tier='trial', credits=0, topup_credits=0"), {"o": org})
    return BR, org


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
    assert v["activated"] and v["plan"] == "startup" and v["balance"] == 100_000

    # idempotent re-verify — the same payment never double-grants
    v2 = BR.verify(org, BR.VerifyIn(razorpay_payment_id="pay_1", razorpay_order_id=order["order_id"],
                                    razorpay_signature=sig, plan="startup"), org=org)
    assert v2["balance"] == 100_000

    with BR._graph.engine.begin() as c:
        assert B.deduct(c, org, 3, reason="query", idem="q1") is True
        assert B.balance(c, org)["balance"] == 99_997
        assert B.deduct(c, org, 3, reason="query", idem="q1") is True   # idempotent
        assert B.balance(c, org)["balance"] == 99_997

    tsig = B.razorpay_signature(order["order_id"], "tp1", _SECRET)
    tv = BR.verify_topup(org, BR.TopupVerifyIn(razorpay_payment_id="tp1",
                                               razorpay_order_id=order["order_id"],
                                               razorpay_signature=tsig, pack="small"), org=org)
    assert tv["balance_after"] == 99_997 + 5_000

    assert BR.invoices(org, org=org)["invoices"][0]["status"] == "active"


def test_bad_signature_is_rejected(monkeypatch):
    BR, org = _setup(monkeypatch)
    with pytest.raises(Exception):
        BR.verify(org, BR.VerifyIn(razorpay_payment_id="x", razorpay_order_id="y",
                                   razorpay_signature="bad", plan="startup"), org=org)
