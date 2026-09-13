"""P0 · the light due-source tick.

Gmail's 15-minute cadence was only consulted on the 6-hour heavy tick, so polled mail could wait
six hours. The scheduler thread now runs a light pass every `due_sync_interval_minutes`: only due
connections are polled, and the reasoning chain runs only for an org that received new events.
These tests assert the three things that make that true and affordable:

* the light sweep reasons for an org with new events and SKIPS an org with none;
* the loop runs heavy first, light in between, heavy again once its interval has passed;
* the cadence grace uses the light tick, not six hours.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
from genios_engine.capture.acquire.sync_runner import (
    in_scheduled_sweep,
    scheduled_sweep,
    sweep_cadence_policy,
    sweep_tick_seconds,
)
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.connection import Connection

OWNER = "founder@genios.ai"


class _Mailbox:
    """One new message per page; counts provider calls."""

    def __init__(self, cid: str) -> None:
        self.source = "gmail"
        self.cid = cid
        self.fetches = 0

    def validate_connection(self) -> bool:
        return True

    def _batch(self, cursor):
        self.fetches += 1
        return SourceBatch(objects=[RawObject(
            source="gmail", object_type="email_message",
            source_object_id=f"{self.cid}_m{self.fetches}",
            occurred_at=datetime.now(timezone.utc), actor_email="buyer@acme.com",
            recipients=(OWNER,),
            raw={"subject": "Renewal", "body": "We can move forward with the annual contract."})],
            next_cursor=None)

    def initial_snapshot(self, cursor=None, limit=50):
        return self._batch(cursor)

    def incremental_changes(self, cursor=None, limit=50, since=None):
        return self._batch(cursor)

    def fetch_content(self, object_ref):
        return {}


class _Store:
    def __init__(self, *connections: Connection) -> None:
        self._by_id = {c.connection_id: c for c in connections}

    def list_active(self, source_type: str | None = None):
        return list(self._by_id.values())

    def get(self, connection_id: str):
        return self._by_id.get(connection_id)


@pytest.fixture
def two_orgs(monkeypatch):
    """`org_new` has never been polled (due, one new mail); `org_quiet` was polled a minute ago
    (not due on a 15-minute cadence, so nothing new). Records which orgs the chain ran for."""
    from genios_engine.api import routes

    conns = [Connection(org_id=o, connection_id=f"con_{o}", source_type="gmail",
                        composio_user_id=o) for o in ("org_new", "org_quiet")]
    boxes = {c.connection_id: _Mailbox(c.connection_id) for c in conns}
    cursors = InMemoryCursorStore(clock=lambda: datetime.now(timezone.utc) - timedelta(minutes=1))
    cursors.save("org_quiet", "con_org_quiet", "gmail", cursor=None, watermark=None)
    cursors._clock = lambda: datetime.now(timezone.utc)
    chained: list[str] = []

    monkeypatch.setattr(routes, "_connections", _Store(*conns))
    monkeypatch.setattr(routes, "_cursors", cursors)
    monkeypatch.setattr(routes, "_repo", InMemorySourceEventRepository())
    for name in ("_parked", "_trace_repo", "_payload_store", "_prepared_store", "_documents",
                 "_graph"):
        monkeypatch.setattr(routes, name, None)
    monkeypatch.setattr(routes, "make_connector_for", lambda c: boxes[c.connection_id])
    for name in ("make_relevance_classifier", "_semantic_lane_for", "_structured_lane_for",
                 "_esqe_stage_for", "_coverage_fn_for", "_sender_resolver_for", "_run_ledger"):
        monkeypatch.setattr(routes, name, lambda *a, **kw: None)
    monkeypatch.setattr(routes, "_mailbox_owner_for", lambda *a, **kw: OWNER)
    monkeypatch.setattr(routes, "_semantic_activated_orgs", lambda *a, **kw: frozenset())
    monkeypatch.setattr(routes, "_notify_sync_failure", lambda **kw: None)
    monkeypatch.setattr(routes, "_run_l2", lambda org, **kw: chained.append(org))
    return SimpleNamespace(boxes=boxes, chained=chained)


def test_the_light_sweep_reasons_only_for_the_org_that_received_new_events(two_orgs):
    from genios_engine.api import routes

    with scheduled_sweep():
        res = routes.run_sync_sweep(chain_only_on_new_data=True)

    assert two_orgs.boxes["con_org_quiet"].fetches == 0, "a connection that was not due was polled"
    assert two_orgs.chained == ["org_new"], (
        f"chain ran for {two_orgs.chained} — an org with no new events was reasoned about")
    assert res["orgs"] == 1 and res["orgs_skipped_no_new_data"] == 1


def test_the_heavy_sweep_still_reasons_for_every_org(two_orgs):
    from genios_engine.api import routes

    with scheduled_sweep():
        res = routes.run_sync_sweep()

    assert sorted(two_orgs.chained) == ["org_new", "org_quiet"]
    assert res["orgs"] == 2 and res["orgs_skipped_no_new_data"] == 0


def test_a_second_light_tick_with_nothing_due_runs_no_chain(two_orgs):
    from genios_engine.api import routes

    with scheduled_sweep():
        routes.run_sync_sweep(chain_only_on_new_data=True)
        routes.run_sync_sweep(chain_only_on_new_data=True)

    assert two_orgs.boxes["con_org_new"].fetches == 1, "polled again one moment later"
    assert two_orgs.chained == ["org_new"], "the idle second tick paid for a chain run"


def test_a_connector_that_cannot_be_built_never_stops_the_sweep(two_orgs, monkeypatch):
    """Found live: the failure handler re-called the connector factory outside its own try, so
    one source with no connector raised out of the sweep and no org was reasoned about."""
    from genios_engine.api import routes

    def factory(c):
        if c.connection_id == "con_org_quiet":
            raise ValueError("no connector for this source")
        return two_orgs.boxes[c.connection_id]

    monkeypatch.setattr(routes, "make_connector_for", factory)
    with scheduled_sweep():
        res = routes.run_sync_sweep(chain_only_on_new_data=True)

    assert (res["l1_ok"], res["l1_err"]) == (1, 1)
    assert two_orgs.chained == ["org_new"], "the healthy org lost its chain to the broken one"


def test_the_light_tick_is_marked_and_asks_for_chain_on_new_data_only(monkeypatch):
    from genios_engine.api import routes
    from genios_engine.platform import scheduler as S

    seen: list[tuple[dict, bool]] = []
    monkeypatch.setattr(routes, "run_sync_sweep",
                        lambda *a, **kw: seen.append((kw, in_scheduled_sweep())) or {"ok": 1})
    assert S._run_sweep_bounded(S._light_tick) == {"ok": 1}
    assert seen == [({"chain_only_on_new_data": True}, True)]


class _FakeStop:
    """Stands in for the thread's stop event: every wait advances a fake clock; stops after N."""

    def __init__(self, clock: list[float], waits: int) -> None:
        self.clock = clock
        self.left = waits

    def is_set(self) -> bool:
        return False

    def wait(self, seconds: float) -> bool:
        self.clock[0] += seconds
        self.left -= 1
        return self.left < 0


def _drive_loop(monkeypatch, *, heavy_s: float, light_s: float, waits: int) -> list[str]:
    from genios_engine.platform import scheduler as S

    clock = [0.0]
    calls: list[str] = []
    monkeypatch.setattr(S, "_stop", _FakeStop(clock, waits))
    monkeypatch.setattr(S, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(S, "_run_sweep_bounded",
                        lambda fn=None: calls.append("heavy" if fn is S._tick else "light"))
    S._loop(heavy_s, 0.0, light_s)
    return calls


def test_the_loop_runs_heavy_first_light_between_and_heavy_again_when_due(monkeypatch):
    calls = _drive_loop(monkeypatch, heavy_s=3600, light_s=900, waits=6)
    assert calls == ["heavy", "light", "light", "light", "heavy", "light"]


def test_with_the_light_tick_off_the_loop_is_exactly_the_old_heavy_loop(monkeypatch):
    calls = _drive_loop(monkeypatch, heavy_s=3600, light_s=0, waits=3)
    assert calls == ["heavy", "heavy", "heavy"]


@pytest.mark.parametrize("minutes,expected", [("15", 900), ("0", 6 * 3600)])
def test_the_cadence_grace_uses_the_light_tick(monkeypatch, minutes, expected):
    from genios_engine.platform import config as C

    C.get_settings.cache_clear()
    sweep_cadence_policy.cache_clear()
    monkeypatch.setenv("GENIOS_DUE_SYNC_INTERVAL_MINUTES", minutes)
    monkeypatch.setenv("GENIOS_SYNC_INTERVAL_HOURS", "6")
    try:
        assert sweep_tick_seconds() == expected
    finally:
        monkeypatch.delenv("GENIOS_DUE_SYNC_INTERVAL_MINUTES", raising=False)
        monkeypatch.delenv("GENIOS_SYNC_INTERVAL_HOURS", raising=False)
        C.get_settings.cache_clear()
        sweep_cadence_policy.cache_clear()
