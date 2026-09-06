"""L1.2.6's BATCH half, and `validate_connection`, reached from the real cross-org sweep.

    pytest tests/capture/acquire/test_sweep_wiring.py -q

Three units shipped with no call site anywhere in `genios_engine/`:

* `schedules_for` / `schedule_for` / `select_due` — the batch half of the scheduler. `run_sync`
  asked the per-connection question and always had; nothing ever asked it for the LIST, so the
  sweep ran `list_active()` in store order. `select_due`'s own docstring names the cost:
  *"a sweep with a wall-clock budget that runs its list in store order starves whatever sorts
  last"* — and this sweep has exactly such a budget, the per-org daily LLM cap.
* `SourceConnector.validate_connection` — implemented by EVERY connector, called by nothing.
  So a revoked Google grant and a provider hiccup produced the same `l1_err`, the same alert and
  the same next tick that failed identically, for ever.

Everything here enters through `routes.run_sync_sweep`, the function the background scheduler
drives; nothing constructs a scheduler or a connector and asks it directly.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.cursor_store import InMemoryCursorStore
from genios_engine.capture.acquire.sync_runner import scheduled_sweep
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.connection import Connection

OWNER = "founder@genios.ai"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)


class _Recorder:
    """A connector that records the order it was polled in, and can refuse its credential."""

    order: list[str] = []

    def __init__(self, connection_id: str, *, valid: bool = True, explodes: bool = False) -> None:
        self.source = "gmail"
        self.connection_id = connection_id
        self._valid = valid
        self._explodes = explodes

    def validate_connection(self) -> bool:
        return self._valid

    def _batch(self, cursor):
        _Recorder.order.append(self.connection_id)
        if self._explodes:
            raise RuntimeError("provider said no")
        return SourceBatch(objects=[RawObject(
            source="gmail", object_type="email_message",
            source_object_id=f"{self.connection_id}_m1", occurred_at=NOW,
            actor_email="buyer@acme.com", recipients=(OWNER,),
            raw={"subject": "Renewal", "body": "We can move forward with the contract."})],
            next_cursor=None)

    def initial_snapshot(self, cursor, limit):
        return self._batch(cursor)

    def incremental_changes(self, cursor, limit, since=None):
        return self._batch(cursor)

    def fetch_content(self, object_ref):
        return {}


class _Store:
    """The narrowest `ConnectionStore` the sweep needs, plus a record of status writes."""

    def __init__(self, *connections: Connection) -> None:
        self._by_id = {c.connection_id: c for c in connections}
        self.status_writes: list[tuple[str, str]] = []

    def list_active(self, source_type: str | None = None):
        return [c for c in self._by_id.values() if c.status == "connected"]

    def get(self, connection_id: str):
        return self._by_id.get(connection_id)

    def add(self, c: Connection) -> None:
        self._by_id[c.connection_id] = c

    def set_status(self, connection_id: str, status: str) -> None:
        self.status_writes.append((connection_id, status))
        if connection_id in self._by_id:
            self._by_id[connection_id].status = status


@pytest.fixture
def sweep(monkeypatch):
    """`routes.run_sync_sweep` with every optional store off and the connector injectable."""
    from genios_engine.api import routes

    _Recorder.order = []
    connectors: dict[str, _Recorder] = {}

    def _install(*connections: Connection, factory=None) -> _Store:
        store = _Store(*connections)
        monkeypatch.setattr(routes, "_connections", store)
        monkeypatch.setattr(routes, "_cursors", InMemoryCursorStore())
        monkeypatch.setattr(routes, "_repo", InMemorySourceEventRepository())
        for name in ("_parked", "_trace_repo", "_payload_store", "_prepared_store",
                     "_documents", "_graph"):
            monkeypatch.setattr(routes, name, None)
        made = factory or (lambda c: _Recorder(c.connection_id))
        monkeypatch.setattr(routes, "make_connector_for",
                            lambda c: connectors.setdefault(c.connection_id, made(c)))
        monkeypatch.setattr(routes, "make_relevance_classifier", lambda *a, **kw: None)
        monkeypatch.setattr(routes, "_semantic_lane_for", lambda *a, **kw: None)
        monkeypatch.setattr(routes, "_structured_lane_for", lambda *a, **kw: None)
        monkeypatch.setattr(routes, "_esqe_stage_for", lambda *a, **kw: None)
        monkeypatch.setattr(routes, "_coverage_fn_for", lambda *a, **kw: None)
        monkeypatch.setattr(routes, "_sender_resolver_for", lambda *a, **kw: None)
        monkeypatch.setattr(routes, "_mailbox_owner_for", lambda *a, **kw: OWNER)
        monkeypatch.setattr(routes, "_semantic_activated_orgs", lambda *a, **kw: frozenset())
        monkeypatch.setattr(routes, "_run_l2", lambda *a, **kw: None)
        monkeypatch.setattr(routes, "_notify_sync_failure", lambda **kw: None)
        monkeypatch.setattr(routes, "_run_ledger", lambda *a, **kw: None)
        return store

    return _install


def _conn(cid: str, org: str = "org_sweep") -> Connection:
    return Connection(org_id=org, connection_id=cid, source_type="gmail", composio_user_id=org)


def test_the_sweep_polls_the_longest_waiting_connection_first(sweep):
    """`select_due`'s fairness, on the real loop. Three connections in store order c, a, b;
    their cursors make `a` the one that has waited longest, then `b`, then `c`. The sweep must
    run them oldest-due first, because the tick's budget is spent in the order it iterates."""
    from genios_engine.api import routes

    store = sweep(_conn("c"), _conn("a"), _conn("b"))
    cursors = routes._cursors
    # Oldest last success first: a (2h ago), b (1h), c (30m). All three are past a 15-minute
    # gmail cadence, so all three are due — this is about ORDER, never about which ones run.
    # `InMemoryCursorStore` takes its clock as a parameter precisely so a save can be placed in
    # the past without sleeping — its own docstring says so.
    for cid, ago in (("a", 120), ("b", 60), ("c", 30)):
        cursors._clock = (lambda m=ago: datetime.now(timezone.utc) - timedelta(minutes=m))
        cursors.save("org_sweep", cid, "gmail", cursor=None, watermark=None)
    cursors._clock = lambda: datetime.now(timezone.utc)

    with scheduled_sweep():
        result = routes.run_sync_sweep()

    assert result["l1_ok"] == 3
    assert result["l1_due"] == 3, "the scheduler did not report its own batch decision"
    assert _Recorder.order == ["a", "b", "c"], (
        f"the sweep polled in {_Recorder.order} — store order, not oldest-due first. A tick "
        "that runs out of budget now starves whichever connection sorts last in the table")


def test_a_provider_that_refuses_the_credential_is_disconnected_not_retried_for_ever(sweep):
    """`validate_connection`, asked at last. A revoked grant fails every future tick
    identically; without the probe it is indistinguishable from a blip, and the tenant gets the
    same unactionable alert every six hours."""
    from genios_engine.api import routes

    store = sweep(_conn("revoked"),
                  factory=lambda c: _Recorder(c.connection_id, valid=False, explodes=True))

    with scheduled_sweep():
        result = routes.run_sync_sweep()

    assert result["l1_err"] == 1
    assert result["l1_credentials_revoked"] == 1, (
        "the provider refused the credential and the sweep reported an ordinary error — "
        "nothing tells the tenant to reconnect")
    assert ("revoked", "disconnected") in store.status_writes


def test_a_transient_failure_leaves_a_working_connection_alone(sweep):
    """The other direction, and the one that matters more: a connection whose credential still
    works must NOT be disconnected because one poll failed. Marking it would take a tenant's
    ingestion down over a provider hiccup."""
    from genios_engine.api import routes

    store = sweep(_conn("blip"),
                  factory=lambda c: _Recorder(c.connection_id, valid=True, explodes=True))

    with scheduled_sweep():
        result = routes.run_sync_sweep()

    assert result["l1_err"] == 1
    assert result["l1_credentials_revoked"] == 0
    assert store.status_writes == [], "a transient failure disconnected a working connection"


def test_a_probe_that_cannot_answer_never_disconnects_anything(sweep):
    """`None` is not evidence of revocation. A connector whose health check RAISES must leave
    the connection connected — degrading a tenant because a probe timed out is a worse outcome
    than ignoring the probe."""
    from genios_engine.api import routes

    class _Unanswerable(_Recorder):
        def validate_connection(self):
            raise RuntimeError("the health endpoint is down too")

    store = sweep(_conn("unknown"),
                  factory=lambda c: _Unanswerable(c.connection_id, explodes=True))

    with scheduled_sweep():
        result = routes.run_sync_sweep()

    assert result["l1_err"] == 1
    assert result["l1_credentials_revoked"] == 0
    assert store.status_writes == []
