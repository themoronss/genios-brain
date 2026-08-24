"""Layer 6 · Phase 2 — the Selector (load_batch), against real PostgreSQL (rolled back)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.feedback.store import COHORT_DAYS, LearningBatch, load_batch

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

_OUTCOME_COLS = ("outcome_id, org_id, execution_id, decision_hash, capability_id, "
                 "capability_version, play_id, play_version, terminal_state, reason_code, label, "
                 "created_at, closed_at, seconds_to_close, actions_total, actions_completed, "
                 "progress_bp, priority_bp, confidence_bp, band, routing_rule")


def _seed_outcome(c, org, *, outcome_id, execution_id, at, label="succeeded"):
    from sqlalchemy import text
    c.execute(text(
        f"insert into execution_outcomes ({_OUTCOME_COLS}) values "
        "(:i, :o, :x, 'dh', 'cap', '1.0.0', 'play', '1.0.0', 'completed', 'done', :lbl, "
        " :t, :t, 0, 1, 1, 10000, 5000, 7000, 'high', 'rule1_owner')"),
        {"i": outcome_id, "o": org, "x": execution_id, "lbl": label, "t": at})


def test_empty_batch_is_legitimate():
    b = LearningBatch(org_id="o", since=NOW)
    assert b.is_empty and b.counts() == {"outcomes": 0, "feedback": 0, "delivery": 0,
                                         "enterprise": 0, "inbox": 0}


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
    if not c.execute(text("select to_regclass('public.execution_outcomes')")).scalar():
        tx.rollback(); c.close(); pytest.skip("schema not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def test_selector_reads_outcomes_and_delivery_within_window(conn):
    from sqlalchemy import text
    from genios_engine.deliver import spine
    from genios_engine.contracts.delivery import (DeliveryFormat, DeliveryObject, DeliveryPriority)
    from genios_engine.contracts.execution import AudienceClass, ChannelClass
    c, org = conn

    # seed one Layer 5 outcome inside the window
    _seed_outcome(c, org, outcome_id="out_sel_t", execution_id="exec_sel_t", at=NOW - timedelta(days=1))

    # seed one delivery
    obj = DeliveryObject(org_id=org, delivery_id="del_sel_t", execution_id="exec_sel_t",
                         execution_hash="h", audience=AudienceClass.OWNER, channel="slack",
                         channel_class=ChannelClass.CHAT, fmt=DeliveryFormat.CHAT_MESSAGE,
                         priority=DeliveryPriority.HIGH, band="high",
                         dedupe_key=spine.logical_dedupe_key(org, "exec_sel_t", "initial"),
                         route_ladder=("slack",), recipient="seat_sel")
    spine.materialize(c, obj, at=NOW - timedelta(days=1))

    batch = load_batch(c, org_id=org, now=NOW)
    assert any(o["execution_id"] == "exec_sel_t" for o in batch.outcomes)
    assert any(d.delivery_id == "del_sel_t" for d in batch.delivery)
    assert batch.since == NOW - timedelta(days=COHORT_DAYS)
    # inbox seam does not exist yet -> empty, and that is legitimate (an empty seam emits nothing)
    assert batch.inbox == ()


def test_older_than_the_window_is_excluded(conn):
    c, org = conn
    _seed_outcome(c, org, outcome_id="out_old_t", execution_id="exec_old_t", at=NOW - timedelta(days=60))
    batch = load_batch(c, org_id=org, now=NOW)
    assert not any(o["execution_id"] == "exec_old_t" for o in batch.outcomes)
