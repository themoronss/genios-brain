from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.parked.store import InMemoryParkedStore
from genios_engine.contracts.events import AgentEvent, HumanEvent


def test_human_event_known_vs_unknown_type():
    assert HumanEvent(type="human.fact_edit", org_id="o", actor_id="u").is_known_type()
    assert not HumanEvent(type="human.random", org_id="o", actor_id="u").is_known_type()


def test_agent_event_idempotency_key():
    ev = AgentEvent(org_id="o", agent_id="agt_1", client_event_id="c1",
                    action_taken="email_sent")
    assert ev.idempotency_key == "agt_1:c1"


class _UnknownStructuredConn:
    source = "weirdapp"

    def _objs(self):
        return [RawObject("weirdapp", "thing", "t1",
                          datetime(2026, 7, 28, tzinfo=timezone.utc),
                          actor_type="system", raw={"x": 1})]

    def incremental_changes(self, cursor=None, limit=100, since=None):
        return SourceBatch(objects=self._objs())

    def initial_snapshot(self, cursor=None, limit=100):
        return SourceBatch(objects=self._objs())


def test_parked_event_lands_in_store():
    repo = InMemorySourceEventRepository()
    parked = InMemoryParkedStore()

    def structured_resolver(_raw):    # mark as structured so unknown mapping parks it
        return False

    # run_sync doesn't know structured; call capture directly via a small structured sync:
    from genios_engine.capture.pipeline import capture_event
    for o in _UnknownStructuredConn().incremental_changes().objects:
        res = capture_event(o, org_id="o", connection_id="c", repo=repo, is_structured=True)
        if res.outcome == "parked":
            from genios_engine.capture.parked.store import parked_from_trace
            parked.add(parked_from_trace("o", res.event.event_id, res.event.source,
                                         res.trace.records[-1].reason_code, res.trace))

    items = parked.list("o")
    assert len(items) == 1
    assert items[0].reason_code == "mapping_missing"
