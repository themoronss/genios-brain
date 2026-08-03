from __future__ import annotations

from genios_engine.capture.connectors.fake import FakeGmailConnector
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import land_raw_object


def _raw():
    return FakeGmailConnector().incremental_changes().objects[0]


def test_lands_new_event_with_trace():
    # landing = normalize + dedup check only (writing is deferred to after the gate)
    repo = InMemorySourceEventRepository()
    res = land_raw_object(_raw(), org_id="org_demo", connection_id="con_demo", repo=repo)

    assert res.landed is True                       # "new", not "written"
    assert res.event.dedup_key == "gmail:email_message:msg_18c4a9e2f7"
    assert res.event.actor.email == "priya@acme.com"
    assert repo.count() == 0                         # landing does not persist
    # trace shows exactly one landing/pass decision
    assert [r.action.value for r in res.trace.records] == ["pass"]


def test_duplicate_is_dropped_and_traced():
    repo = InMemorySourceEventRepository()
    r1 = land_raw_object(_raw(), org_id="org_demo", connection_id="con_demo", repo=repo)
    repo.add(r1.event, outcome="emitted")            # simulate the post-gate ledger write
    res2 = land_raw_object(_raw(), org_id="org_demo", connection_id="con_demo", repo=repo)

    assert res2.landed is False
    assert repo.count() == 1          # not double-counted
    last = res2.trace.records[-1]
    assert last.action.value == "drop"
    assert last.reason_code == "duplicate"


def test_dedup_key_is_stable_across_resync():
    # same source object, two separate pulls → identical dedup_key (idempotency backbone)
    raw1, raw2 = _raw(), _raw()
    repo = InMemorySourceEventRepository()
    r1 = land_raw_object(raw1, org_id="o", connection_id="c", repo=repo)
    r2 = land_raw_object(raw2, org_id="o", connection_id="c", repo=repo)
    assert r1.event.dedup_key == r2.event.dedup_key
    assert r1.event.event_id != r2.event.event_id   # event_id is per-ingest, unique
