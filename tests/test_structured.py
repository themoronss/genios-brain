from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event
from genios_engine.capture.structured.apply import apply_mapping
from genios_engine.capture.structured.registry import get_mapping, has_mapping


def test_mapping_maps_source_fields_to_targets():
    m = get_mapping("hubspot", "deal")
    assert m is not None
    fields = apply_mapping(m, {"dealstage": "proposal", "amount": 800000, "junk": "x"})
    assert fields == {"deal.stage": "proposal", "deal.amount": 800000}   # junk ignored


def test_client_db_uses_same_lane():
    assert has_mapping("postgres", "public.customer_accounts")


def test_pipeline_derives_structured_fields_from_registry():
    raw = RawObject(source="hubspot", object_type="deal", source_object_id="deal_9912",
                    occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
                    actor_type="system",
                    raw={"dealstage": "proposal", "amount": 800000})
    repo = InMemorySourceEventRepository()
    res = capture_event(raw, org_id="o", connection_id="c", repo=repo, is_structured=True)
    assert res.outcome == "emitted"
    assert res.gated.route == "structured"
    assert res.gated.structured_fields == {"deal.stage": "proposal", "deal.amount": 800000}


def test_unknown_structured_parks():
    raw = RawObject(source="weirdapp", object_type="thing", source_object_id="t1",
                    occurred_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
                    actor_type="system", raw={"x": 1})
    repo = InMemorySourceEventRepository()
    res = capture_event(raw, org_id="o", connection_id="c", repo=repo, is_structured=True)
    assert res.outcome == "parked"
    assert res.trace.records[-1].reason_code == "mapping_missing"
