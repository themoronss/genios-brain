"""Layer 5.2 · Phase 5 — Rate Limiter + Analytics, against real PostgreSQL (rolled back)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.deliver.rate_limiter import hour_recipient_key, release_slot, reserve_slot

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
HOUR = NOW.replace(minute=0, second=0, microsecond=0)


def test_shared_hour_key_is_a_stream_for_chat_families():
    assert hour_recipient_key("slack", "seat_1") == hour_recipient_key("teams", "seat_2")
    assert hour_recipient_key("in_app", "seat_1") == "seat_1"     # non-chat is per-seat


@pytest.fixture()
def conn(live_db_url):
    try:
        from genios_engine.platform.db import get_engine
        from sqlalchemy import text
        # The scratch database when one is set — never the configured (production) one.
        # See tests/conftest.py::live_test_database_url for why that ordering matters.
        url = live_db_url
        if not url:
            pytest.skip("no database configured")
        c = get_engine(url).connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no live database: {exc}")
    from sqlalchemy import text
    tx = c.begin()
    if not c.execute(text("select to_regclass('public.delivery_rate_windows')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0043 not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def test_bounded_window_reserves_up_to_budget_then_refuses(conn):
    c, org = conn
    kw = dict(org_id=org, recipient="seat_rl", window_kind="hour", window_start=HOUR, at=NOW)
    assert reserve_slot(c, budget=2, **kw) is True     # 1/2
    assert reserve_slot(c, budget=2, **kw) is True     # 2/2
    assert reserve_slot(c, budget=2, **kw) is False    # full — the last slot is spent once
    # a definite non-delivery releases one slot, which can then be reserved again
    release_slot(c, org_id=org, recipient="seat_rl", window_kind="hour", window_start=HOUR, at=NOW)
    assert reserve_slot(c, budget=2, **kw) is True


def test_unbounded_budget_always_reserves(conn):
    c, org = conn
    kw = dict(org_id=org, recipient="seat_unb", window_kind="day", window_start=HOUR, at=NOW)
    for _ in range(5):
        assert reserve_slot(c, budget=None, **kw) is True


def test_analytics_denominator_is_real_impressions(conn):
    from genios_engine.deliver import spine
    from genios_engine.deliver.analytics import delivery_analytics
    from genios_engine.deliver.tracker import record_transition
    from genios_engine.contracts.delivery import (DeliveryFormat, DeliveryLifecycle,
                                                  DeliveryObject, DeliveryPriority)
    from genios_engine.contracts.execution import AudienceClass, ChannelClass
    c, org = conn
    obj = DeliveryObject(org_id=org, delivery_id="del_an_t", execution_id="exec_an_t",
                         execution_hash="h", audience=AudienceClass.OWNER, channel="slack",
                         channel_class=ChannelClass.CHAT, fmt=DeliveryFormat.CHAT_MESSAGE,
                         priority=DeliveryPriority.HIGH, band="high",
                         dedupe_key=spine.logical_dedupe_key(org, "exec_an_t", "initial"),
                         route_ladder=("slack",), recipient="seat_an")
    spine.materialize(c, obj, at=NOW - timedelta(hours=1))
    record_transition(c, org_id=org, delivery_id="del_an_t",
                      target=DeliveryLifecycle.DELIVERED, at=NOW, now=NOW)
    record_transition(c, org_id=org, delivery_id="del_an_t",
                      target=DeliveryLifecycle.VIEWED, at=NOW, now=NOW)
    a = delivery_analytics(c, org_id=org, since=NOW - timedelta(days=1))
    assert a["impressions"] >= 1 and a["engagement"]["viewed"] >= 1
    assert 0.0 <= a["rates"]["view"] <= 1.0
