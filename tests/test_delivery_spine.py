"""Layer 5.2 · Phase 3 — the outbox spine, proven against real PostgreSQL.

The spine's SQL (partial-index ON CONFLICT, FOR UPDATE SKIP LOCKED, fencing) is exactly the kind a
fake cannot model, so this exercises it against a live database — inside ONE transaction that is
rolled back, leaving the DB byte-identical. Skips cleanly when no database is configured, so the
rest of the suite never depends on it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.delivery import DeliveryFormat, DeliveryObject, DeliveryPriority
from genios_engine.contracts.execution import AudienceClass, ChannelClass
from genios_engine.deliver import spine

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def conn():
    """A live connection in a rolled-back transaction, or skip if no DB / schema is reachable."""
    try:
        from genios_engine.platform.config import get_settings
        from genios_engine.platform.db import get_engine
        from sqlalchemy import text
        url = get_settings().database_url
        if not url:
            pytest.skip("no database configured")
        engine = get_engine(url)
        c = engine.connect()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no live database: {exc}")
    tx = c.begin()
    # require the 0043 control-plane schema + at least one org for FK satisfaction
    from sqlalchemy import text
    if not c.execute(text("select to_regclass('public.delivery_events')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0043 control plane not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org to satisfy cascade FKs")
    try:
        yield c, org
    finally:
        tx.rollback()
        c.close()


def _obj(org: str, dedupe: str) -> DeliveryObject:
    return DeliveryObject(
        org_id=org, delivery_id="del_spine_t", execution_id="exec_spine_t", execution_hash="h",
        audience=AudienceClass.OWNER, channel="slack", channel_class=ChannelClass.CHAT,
        fmt=DeliveryFormat.CHAT_MESSAGE, priority=DeliveryPriority.CRITICAL, band="critical",
        dedupe_key=dedupe, route_ladder=("slack", "in_app"), recipient="seat_spine_t")


def test_materialize_is_atomic_and_deduped(conn):
    from sqlalchemy import text
    c, org = conn
    dk = spine.logical_dedupe_key(org, "exec_spine_t", "initial")
    assert spine.materialize(c, _obj(org, dk), at=NOW) is True
    assert spine.materialize(c, _obj(org, dk), at=NOW) is False, "one logical delivery per key"
    rows = c.execute(text("select count(*) from delivery_outbox where org_id=:o and dedupe_key=:d"),
                     {"o": org, "d": dk}).scalar()
    events = c.execute(text("select count(*) from delivery_events "
                            "where org_id=:o and delivery_id='del_spine_t' and kind='queued'"),
                       {"o": org}).scalar()
    assert rows == 1 and events == 1, "the row and its queued event are written together"


def test_claim_is_fenced_against_a_second_worker(conn):
    c, org = conn
    dk = spine.logical_dedupe_key(org, "exec_spine_t", "initial")
    spine.materialize(c, _obj(org, dk), at=NOW)
    at = NOW + timedelta(minutes=1)
    claimed = spine.claim_due(c, org_id=org, worker_id="worker_A", at=at)
    assert any(r["delivery_id"] == "del_spine_t" for r in claimed)
    assert all(r["fence_token"] for r in claimed), "a claim carries a fencing token"
    # the lease is live, so a second worker at the same instant cannot re-claim it
    again = spine.claim_due(c, org_id=org, worker_id="worker_B", at=at)
    assert not any(r["delivery_id"] == "del_spine_t" for r in again)


def test_materialization_failure_is_visible(conn):
    from sqlalchemy import text
    c, org = conn
    fid = spine.record_materialization_failure(
        c, org_id=org, execution_id="exec_bad", reason_code="unparseable_object", at=NOW)
    n = c.execute(text("select count(*) from delivery_materialization_failures where id=:i"),
                  {"i": fid}).scalar()
    assert n == 1, "a corrupt source object is recorded for operations, never silently dropped"
