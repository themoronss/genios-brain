"""Layer 5.2 · Phase 7 — the DeliveryFact seam Layer 6 consumes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.feedback.delivery_facts import DeliveryFact, load_delivery_facts

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def _fact(**over) -> DeliveryFact:
    base = dict(delivery_id="d", execution_id="e", channel="slack", priority="high",
                lifecycle="delivered", delivered_at=NOW, viewed_at=None, ignored_at=None,
                accepted_at=None, executed_at=None, attempts=1, failed=False)
    base.update(over)
    return DeliveryFact(**base)


def test_impression_requires_a_delivered_clock():
    assert _fact(delivered_at=NOW).is_impression is True
    assert _fact(delivered_at=None).is_impression is False


def test_engagement_is_receipt_backed_not_inferred():
    assert _fact().engaged is False                       # delivered but no receipt
    assert _fact(viewed_at=NOW).engaged is True


def test_only_pre_delivery_failure_is_transport_negative():
    assert _fact(failed=True, delivered_at=None).pre_delivery_failure is True
    # a failure AFTER delivery is the execution's problem, not the transport's
    assert _fact(failed=True, delivered_at=NOW).pre_delivery_failure is False


@pytest.fixture()
def conn():
    try:
        from genios_engine.platform.config import get_settings
        from genios_engine.platform.db import get_engine
        from sqlalchemy import text
        url = get_settings().database_url
        if not url:
            pytest.skip("no database configured")
        c = get_engine(url).connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no live database: {exc}")
    from sqlalchemy import text
    tx = c.begin()
    if not c.execute(text("select to_regclass('public.delivery_outbox')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0043 not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def test_load_reads_the_outbox_by_window(conn):
    from genios_engine.deliver import spine
    from genios_engine.deliver.tracker import record_transition
    from genios_engine.contracts.delivery import (DeliveryFormat, DeliveryLifecycle,
                                                  DeliveryObject, DeliveryPriority)
    from genios_engine.contracts.execution import AudienceClass, ChannelClass
    c, org = conn
    obj = DeliveryObject(org_id=org, delivery_id="del_fact_t", execution_id="exec_fact_t",
                         execution_hash="h", audience=AudienceClass.OWNER, channel="slack",
                         channel_class=ChannelClass.CHAT, fmt=DeliveryFormat.CHAT_MESSAGE,
                         priority=DeliveryPriority.HIGH, band="high",
                         dedupe_key=spine.logical_dedupe_key(org, "exec_fact_t", "initial"),
                         route_ladder=("slack",), recipient="seat_fact")
    spine.materialize(c, obj, at=NOW - timedelta(hours=1))
    record_transition(c, org_id=org, delivery_id="del_fact_t",
                      target=DeliveryLifecycle.DELIVERED, at=NOW, now=NOW)
    facts = load_delivery_facts(c, org_id=org, since=NOW - timedelta(days=1))
    mine = [f for f in facts if f.delivery_id == "del_fact_t"]
    assert len(mine) == 1
    assert mine[0].is_impression is True and mine[0].engaged is False   # delivered, no receipt yet
