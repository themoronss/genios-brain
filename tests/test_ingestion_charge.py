"""Reading the mailbox is never charged in credits.

User-facing credits are charged on ONE surface, `POST /v1/intelligence/query`. Ingestion is
metered by the plan's `sync_messages` allowance and bounded in dollars by `ingest_usd_day`; a sync
pass that bills credits would make a customer pay for how much mail other people send them.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_a_sync_pass_never_touches_the_credit_ledger(monkeypatch):
    from genios_engine.api import routes
    from genios_engine.context import runner as l2_runner
    from genios_engine.platform import billing, intelligence_onboarding
    from genios_engine.reason import runner as l3_runner

    deducted, reasoned = [], []
    monkeypatch.setattr(billing, "deduct",
                        lambda *args, **kwargs: deducted.append((args, kwargs)) or True)
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=object()))
    monkeypatch.setattr(routes, "_card_store", None)
    monkeypatch.setattr(intelligence_onboarding, "provision_intelligence", lambda *_a, **_k: None)
    monkeypatch.setattr(l2_runner, "process_pending", lambda **_kw: {
        "processed": 1_240, "outcomes": {"committed": 900, "committed_facts": 340}})
    monkeypatch.setattr(l3_runner, "run_all", lambda **kw: reasoned.append(kw) or {})

    routes._run_l2("org_1")

    assert reasoned, "the pass did not reach reasoning, so this test proved nothing"
    assert deducted == [], "a sync pass charged credits"


def test_the_ingestion_charge_path_is_gone():
    from genios_engine.api import routes
    from genios_engine.platform import billing

    assert not hasattr(routes, "_charge_ingestion")
    assert not hasattr(billing, "charge_units")


def test_ingestion_units_are_free_and_absent_from_the_price_table():
    from genios_engine.platform import billing as B

    for unit in ("message_read", "document_page"):
        assert unit not in B.COSTS
        assert unit in B.FREE_UNITS
        assert B.cost_of(unit) == 0
        assert B.cost_of(unit, units=5_000) == 0
