"""Warm lane — the policy that needs no database: grouping, backoff, park, wake, fail-open.

The queue semantics themselves (SKIP LOCKED claims, leases, coalescing, single-flight across the
chain callers) are proven against real Postgres in `test_warm_lane_pg.py`.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from genios_engine.platform import warm_lane as W

T0 = datetime(2026, 9, 12, 10, 0, tzinfo=timezone.utc)


def _row(i: int, org: str, event: str, minutes: int, attempts: int = 1) -> W.QueueRow:
    return W.QueueRow(id=i, org_id=org, event_id=event, source="webhook:gmail",
                      enqueued_at=T0 + timedelta(minutes=minutes), attempts=attempts)


# ── grouping ────────────────────────────────────────────────────────────────────────────────────

def test_rows_group_one_batch_per_org_longest_waiting_org_first():
    rows = [_row(1, "org_b", "e1", 5), _row(2, "org_a", "e2", 3), _row(3, "org_b", "e3", 1),
            _row(4, "org_a", "e4", 9)]
    batches = W.group_by_org(rows)
    assert [b.org_id for b in batches] == ["org_b", "org_a"]     # org_b's oldest row is minute 1
    assert batches[0].ids == [1, 3] and batches[1].ids == [2, 4]
    assert batches[0].oldest == T0 + timedelta(minutes=1)


def test_a_batch_names_its_events_once_and_never_the_org_trigger():
    batch = W.group_by_org([_row(1, "org_a", "e1", 0), _row(2, "org_a", W.ORG_TRIGGER, 1),
                            _row(3, "org_a", "e1", 2)])[0]
    assert batch.event_ids == ["e1"]
    assert batch.ids == [1, 2, 3]


def test_no_rows_no_batches():
    assert W.group_by_org([]) == []


# ── backoff + park ─────────────────────────────────────────────────────────────────────────────

def test_backoff_doubles_from_the_base_and_is_capped():
    assert [W.backoff_seconds(n) for n in (1, 2, 3, 4)] == [10.0, 20.0, 40.0, 80.0]
    assert W.backoff_seconds(30) == W.BACKOFF_CAP_SECONDS
    assert W.backoff_seconds(0) == W.BACKOFF_BASE_SECONDS


def test_a_failed_run_parks_rows_out_of_attempts_and_backs_off_the_rest():
    rows = [_row(1, "org_a", "e1", 0, attempts=1), _row(2, "org_a", "e2", 0, attempts=2),
            _row(3, "org_a", "e3", 0, attempts=W.MAX_ATTEMPTS),
            _row(4, "org_a", "e4", 0, attempts=1)]
    park, retry = W.plan_failure(rows)
    assert park == [3]
    assert retry == {10.0: [1, 4], 20.0: [2]}


# ── enqueue never breaks a door ────────────────────────────────────────────────────────────────

def test_enqueue_without_an_engine_or_events_is_a_no_op():
    assert W.enqueue(None, "org_a", ["e1"], "upload") == 0
    assert W.enqueue(object(), "org_a", [], "upload") == 0
    assert W.enqueue(object(), "org_a", ["", None], "upload") == 0


def test_enqueue_swallows_a_database_failure():
    class _Broken:
        def begin(self):
            raise OSError("db down")
    assert W.enqueue(_Broken(), "org_a", ["e1"], "webhook:gmail") == 0


# ── the lease fails OPEN when there is no lease table to read ──────────────────────────────────

def test_run_exclusive_runs_the_chain_unguarded_when_the_lease_cannot_be_read():
    calls = []
    out = W.run_exclusive(SimpleNamespace(), "org_a", lambda: calls.append(1), caller="t")
    assert calls == [1]
    assert out.ok and out.locked is False and out.started_at is None


def test_run_exclusive_reports_a_chain_that_returned_false_as_failed():
    out = W.run_exclusive(SimpleNamespace(), "org_a", lambda: False, caller="t")
    assert out.status == "failed"


def test_run_exclusive_lets_the_chains_exception_through():
    def boom():
        raise RuntimeError("chain broke")
    with pytest.raises(RuntimeError):
        W.run_exclusive(SimpleNamespace(), "org_a", boom, caller="t")


# ── wake: an enqueue starts the worker now, not at its next poll ───────────────────────────────

@pytest.fixture
def lane(monkeypatch):
    ticks: list[float] = []
    ticked = threading.Event()

    def fake_run_once(engine, worker_id, **_kw):
        ticks.append(time.monotonic())
        ticked.set()
        return False

    monkeypatch.setattr(W, "run_once", fake_run_once)
    monkeypatch.setattr(W, "housekeep", lambda engine, **_kw: None)
    monkeypatch.setattr(W, "_resolve_engine", lambda: object())
    monkeypatch.setattr(W, "POLL_SECONDS", 30.0)              # a poll can never explain a tick
    yield SimpleNamespace(ticks=ticks, ticked=ticked)
    W.stop_warm_lane()


def test_wake_runs_the_worker_immediately_instead_of_after_the_poll(lane):
    assert W.start_warm_lane(initial_delay=0)
    assert lane.ticked.wait(2), "the worker never made its first pass"
    assert W.worker_alive()
    lane.ticked.clear()
    woke_at = time.monotonic()
    W.wake()
    assert lane.ticked.wait(2), "wake() did not start a pass"
    assert lane.ticks[-1] - woke_at < 1.0


def test_start_is_idempotent_and_stop_ends_the_threads(lane):
    assert W.start_warm_lane(initial_delay=0)
    assert W.start_warm_lane(initial_delay=0)
    assert len(W._threads) == 1
    W.stop_warm_lane()
    assert not W.worker_alive()


def test_the_lane_can_be_switched_off(monkeypatch):
    from genios_engine.platform.config import get_settings
    monkeypatch.setenv("GENIOS_WARM_LANE_ENABLED", "false")
    get_settings.cache_clear()
    try:
        assert W.start_warm_lane(initial_delay=0) is False
        assert not W.worker_alive()
    finally:
        monkeypatch.delenv("GENIOS_WARM_LANE_ENABLED")
        get_settings.cache_clear()


def test_the_settings_default_to_on_with_one_global_worker():
    from genios_engine.platform.config import Settings
    s = Settings(_env_file=None)
    assert s.warm_lane_enabled is True and s.warm_lane_workers == 1
