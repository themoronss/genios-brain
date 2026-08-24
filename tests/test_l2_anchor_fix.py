from __future__ import annotations

from genios_engine.context.correlation import ANCHOR_PRIORITY, choose_anchors

# Bug: subscription / product_account node types were absent from ANCHOR_PRIORITY, so choose_anchors
# returned [] for every Stripe / client-DB structured event → it reached NO situation, and admin /
# account situations reported their fields missing forever. They now anchor (like a deal).


def test_subscription_now_anchors_a_situation():
    anchors = choose_anchors({"n_sub": "subscription"}, "admin")
    assert [a.node_type for a in anchors] == ["subscription"]     # was [] → no situation


def test_product_account_now_anchors_a_situation():
    anchors = choose_anchors({"n_acc": "product_account"}, "admin")
    assert [a.node_type for a in anchors] == ["product_account"]


def test_both_are_in_anchor_priority():
    assert "subscription" in ANCHOR_PRIORITY and "product_account" in ANCHOR_PRIORITY


def test_deal_still_outranks_company_and_subscription():
    anchors = choose_anchors({"d": "deal", "s": "subscription", "c": "company"}, "sales")
    assert [a.node_type for a in anchors] == ["deal"]             # only the strongest tier anchors


def test_unanchorable_types_still_return_nothing():
    # a meeting is evidence within a situation, not an anchor for one — unchanged
    assert choose_anchors({"m": "meeting"}, "sales") == []
