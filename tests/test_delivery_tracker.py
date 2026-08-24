"""Layer 5.2 · Phase 4 — the Tracker, against real PostgreSQL (rolled-back transaction)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.delivery import DeliveryFormat, DeliveryObject, DeliveryLifecycle, DeliveryPriority
from genios_engine.contracts.execution import AudienceClass, ChannelClass
from genios_engine.deliver import spine
from genios_engine.deliver.tracker import (
    ChronologyError,
    IllegalTransition,
    record_transition,
    validate_chronology,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


def test_chronology_pure_rules():
    validate_chronology(receipt_at=NOW, created_at=NOW - timedelta(hours=1), now=NOW)  # ok
    with pytest.raises(ChronologyError):
        validate_chronology(receipt_at=NOW - timedelta(hours=2), created_at=NOW - timedelta(hours=1), now=NOW)
    with pytest.raises(ChronologyError):
        validate_chronology(receipt_at=NOW + timedelta(minutes=10), created_at=NOW - timedelta(hours=1), now=NOW)


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
    if not c.execute(text("select to_regclass('public.delivery_events')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0043 control plane not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    # materialise one delivery to move around
    obj = DeliveryObject(org_id=org, delivery_id="del_trk_t", execution_id="exec_trk_t",
                         execution_hash="h", audience=AudienceClass.OWNER, channel="slack",
                         channel_class=ChannelClass.CHAT, fmt=DeliveryFormat.CHAT_MESSAGE,
                         priority=DeliveryPriority.HIGH, band="high",
                         dedupe_key=spine.logical_dedupe_key(org, "exec_trk_t", "initial"),
                         route_ladder=("slack", "in_app"), recipient="seat_trk")
    spine.materialize(c, obj, at=NOW - timedelta(hours=1))
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def _lifecycle(c, org):
    from sqlalchemy import text
    return c.execute(text("select lifecycle from delivery_outbox where org_id=:o and delivery_id='del_trk_t'"),
                     {"o": org}).scalar()


def test_legal_engagement_path_advances_and_stamps_clocks(conn):
    from sqlalchemy import text
    c, org = conn
    assert record_transition(c, org_id=org, delivery_id="del_trk_t",
                             target=DeliveryLifecycle.DELIVERED, at=NOW, now=NOW) is True
    assert record_transition(c, org_id=org, delivery_id="del_trk_t",
                             target=DeliveryLifecycle.VIEWED, at=NOW, now=NOW) is True
    assert _lifecycle(c, org) == "viewed"
    stamps = c.execute(text("select delivered_at, viewed_at from delivery_outbox "
                            "where org_id=:o and delivery_id='del_trk_t'"), {"o": org}).mappings().first()
    assert stamps["delivered_at"] is not None and stamps["viewed_at"] is not None


def test_illegal_transition_is_refused(conn):
    c, org = conn
    # queued -> viewed skips delivered; the state machine forbids it
    with pytest.raises(IllegalTransition):
        record_transition(c, org_id=org, delivery_id="del_trk_t",
                          target=DeliveryLifecycle.VIEWED, at=NOW, now=NOW)


def test_idempotent_receipt_is_a_no_op(conn):
    c, org = conn
    record_transition(c, org_id=org, delivery_id="del_trk_t",
                      target=DeliveryLifecycle.DELIVERED, at=NOW, now=NOW)
    first = record_transition(c, org_id=org, delivery_id="del_trk_t",
                              target=DeliveryLifecycle.VIEWED, at=NOW, now=NOW,
                              idempotency_key="tap_1")
    replay = record_transition(c, org_id=org, delivery_id="del_trk_t",
                               target=DeliveryLifecycle.IGNORED, at=NOW, now=NOW,
                               idempotency_key="tap_1")
    assert first is True and replay is False, "a replayed client receipt does nothing"
    assert _lifecycle(c, org) == "viewed"


def test_receipt_before_creation_is_rejected(conn):
    c, org = conn
    with pytest.raises(ChronologyError):
        record_transition(c, org_id=org, delivery_id="del_trk_t",
                          target=DeliveryLifecycle.DELIVERED,
                          at=NOW - timedelta(days=1), now=NOW)   # before the row existed
