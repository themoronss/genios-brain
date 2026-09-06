"""L1.2.5-U1 · `ingest_pushed_objects` — the webhook lane's ingest, unit by unit.

    pytest tests/capture/connectors/test_push_ingest.py -q

`tests/capture/test_webhook_parity.py` proves the two DOORS land the same rows. This file proves
the unit behind the push door behaves the way the sweep's aggregation loop behaves for the cases
a live push actually hits — every object of a payload, a poison object, a park, and the absence
of a store. Hermetic: an in-memory repo, a stub pipeline where the question is about the CALL,
and no clock of its own.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.connectors import push_ingest as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.connectors.push_ingest import (PushIngestWiring,
                                                          ingest_pushed_objects)
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.parked.store import InMemoryParkedStore
from genios_engine.contracts.source_event import SyncMode

WAVE = "W9"
GATE = "G9"

ORG, CONNECTION = "org_push", "con_push"
AT = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)


def _obj(oid: str, object_type: str = "email_message", parent: str | None = None) -> RawObject:
    return RawObject(source="gmail", object_type=object_type, source_object_id=oid,
                     occurred_at=AT, actor_email="priya@acme.com", parent_object_id=parent,
                     raw={"subject": "Revised contract", "body": "Send the contract by Friday."})


MESSAGE = _obj("msg_1")
ATTACHMENT = _obj("msg_1::att_1", object_type="email_attachment", parent="msg_1")


def _wiring(**kw) -> PushIngestWiring:
    kw.setdefault("repo", InMemorySourceEventRepository())
    return PushIngestWiring(**kw)


# ── every object of the payload, not just the first ──────────────────────────────────────────

@pytest.mark.parametrize("objects, expected, why", [
    ((), (), "an empty payload lands nothing and raises nothing"),
    ((MESSAGE,), ("msg_1",), "a message with no attachment is one row"),
    ((MESSAGE, ATTACHMENT), ("msg_1", "msg_1::att_1"),
     "THE defect — the route landed objects[0] and dropped the document"),
])
def test_every_object_of_one_payload_is_captured(objects, expected, why):
    out = ingest_pushed_objects(objects, org_id=ORG, connection_id=CONNECTION, wiring=_wiring())
    assert tuple(r.event.source_object_id for r in out.results) == expected, why
    assert out.quarantined == ()


def test_the_primary_object_is_the_first_one_and_none_when_nothing_landed():
    out = ingest_pushed_objects((MESSAGE, ATTACHMENT), org_id=ORG, connection_id=CONNECTION,
                                wiring=_wiring())
    assert out.primary is not None and out.primary.event.object_type == "email_message"
    assert ingest_pushed_objects((), org_id=ORG, connection_id=CONNECTION,
                                 wiring=_wiring()).primary is None


# ── the keywords the pipeline is handed ──────────────────────────────────────────────────────

def test_the_wiring_reaches_the_pipeline_verbatim(monkeypatch):
    """Each field is forwarded under the name `capture_event` knows it by. A field silently not
    forwarded is exactly the failure this unit exists to end, and it is invisible in a row."""
    seen: dict = {}
    monkeypatch.setattr(P, "capture_event", lambda raw, **kw: seen.update(kw) or _Result())

    def _known(raw):
        return raw.actor_email == "priya@acme.com"

    wiring = _wiring(trace_repo="TR", payload_store="PS", prepared_store="PREP",
                     document_job_store="DOC", relevance="REL", sender_resolver=_known,
                     mailbox_owner="founder@acme.com", coverage_fn="COV", semantic="SEM",
                     structured="STRUCT", esqe="ESQE", sync_mode=SyncMode.backfill)
    ingest_pushed_objects((MESSAGE,), org_id=ORG, connection_id=CONNECTION, wiring=wiring)
    assert seen == {"org_id": ORG, "connection_id": CONNECTION, "repo": wiring.repo,
                    "sender_known": True, "relevance": "REL", "trace_repo": "TR",
                    "payload_store": "PS", "prepared_store": "PREP", "document_job_store": "DOC",
                    "mailbox_owner": "founder@acme.com", "coverage_fn": "COV",
                    "semantic": "SEM", "structured": "STRUCT", "esqe": "ESQE",
                    "sync_mode": SyncMode.backfill}


@pytest.mark.parametrize("resolver, expected, why", [
    (None, False, "no resolver → the gate's W-01 whitelist simply does not fire"),
    (lambda raw: True, True, "a known sender is passed through as the flag, per object"),
    (lambda raw: False, False, "an unknown sender is not silently promoted"),
])
def test_sender_known_is_resolved_per_object(monkeypatch, resolver, expected, why):
    seen: list[bool] = []
    monkeypatch.setattr(P, "capture_event",
                        lambda raw, **kw: seen.append(kw["sender_known"]) or _Result())
    ingest_pushed_objects((MESSAGE,), org_id=ORG, connection_id=CONNECTION,
                          wiring=_wiring(sender_resolver=resolver))
    assert seen == [expected], why


# ── poison and parks: store-don't-delete, on the push door too ───────────────────────────────

class _Result:
    """The smallest thing `ingest_pushed_objects` reads off a CaptureResult."""

    outcome = "emitted"
    extraction_parked = None

    class event:                      # noqa: D106 — a stand-in, not a contract
        source_object_id = "msg_1"
        object_type = "email_message"
        event_id = "evt_1"


def test_a_poison_object_is_quarantined_and_the_rest_of_the_payload_still_lands(monkeypatch):
    """One unparseable object must not take the whole push down, and must not vanish either —
    the sweep quarantines it to `parked_events`; so does this."""
    calls = {"n": 0}

    def _boom(raw, **kw):
        calls["n"] += 1
        if raw.source_object_id == "msg_1":
            raise RuntimeError("poison")
        return _Result()

    monkeypatch.setattr(P, "capture_event", _boom)
    parked = InMemoryParkedStore()
    out = ingest_pushed_objects((MESSAGE, ATTACHMENT), org_id=ORG, connection_id=CONNECTION,
                                wiring=_wiring(parked_store=parked))
    assert out.quarantined == ("msg_1",)
    assert len(out.results) == 1, "the attachment still landed"
    assert calls["n"] == 4, "3 attempts (retries=2) on the poison + 1 on the good object"
    rows = parked.list(ORG, "poison_quarantine")
    assert [r.event_id for r in rows] == ["gmail:msg_1"]
    assert rows[0].trace[0]["error"] == "RuntimeError"


def test_a_poisoned_payload_with_no_parked_store_still_reports_rather_than_raising(monkeypatch):
    monkeypatch.setattr(P, "capture_event",
                        lambda raw, **kw: (_ for _ in ()).throw(RuntimeError("poison")))
    out = ingest_pushed_objects((MESSAGE,), org_id=ORG, connection_id=CONNECTION,
                                wiring=_wiring())
    assert out.results == () and out.quarantined == ("msg_1",) and out.primary is None


def test_a_gate_park_is_filed_so_the_push_door_leaves_a_recoverable_record():
    """"Any park outcome is recorded nowhere" was the third limb of the defect. A real capture,
    not a stub: the object carries no body, so the gate parks it as empty."""
    parked = InMemoryParkedStore()
    empty = RawObject(source="gmail", object_type="email_message", source_object_id="msg_empty",
                      occurred_at=AT, actor_email="stranger@example.com", raw={})
    out = ingest_pushed_objects((empty,), org_id=ORG, connection_id=CONNECTION,
                                wiring=_wiring(parked_store=parked))
    assert out.results[0].outcome in ("parked", "dropped")
    if out.results[0].outcome == "parked":
        assert parked.list(ORG), "a parked event with no parked row is a lost event"


def test_an_s2_extraction_park_is_filed_even_though_the_event_itself_emitted(monkeypatch):
    """The two parks are different: this one says the event reached the model and came back
    unusable. Dropping it because the event was fine loses the only record of that."""
    from genios_engine.contracts.parked import ParkedEvent

    park = ParkedEvent(event_id="evt_1", org_id=ORG, source="gmail",
                       reason_code="extraction_schema_refusal", stage="semantic")

    class _WithExtractionPark(_Result):
        extraction_parked = park

    monkeypatch.setattr(P, "capture_event", lambda raw, **kw: _WithExtractionPark())
    parked = InMemoryParkedStore()
    ingest_pushed_objects((MESSAGE,), org_id=ORG, connection_id=CONNECTION,
                          wiring=_wiring(parked_store=parked))
    assert [p.reason_code for p in parked.list(ORG)] == ["extraction_schema_refusal"]


def test_the_default_sync_mode_is_incremental_because_a_push_is_a_live_delivery():
    assert PushIngestWiring(repo=InMemorySourceEventRepository()).sync_mode is SyncMode.incremental
