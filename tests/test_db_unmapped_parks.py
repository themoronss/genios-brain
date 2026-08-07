from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.payload_store import InMemoryRawPayloadStore
from genios_engine.capture.pipeline import capture_event

# A client's own DB row is STRUCTURED but carries no prose `body`. Before this fix, any table
# without a registry mapping (i.e. every table except the one example) fell to the unstructured
# lane, read an empty string, and was N-10 DROPPED as "empty" — the whole table vanished while
# the sync reported success. Now an enterprise_system source with no mapping PARKS (mapping_missing,
# recoverable) instead of dropping. Mapped tables are unaffected.


def _db_row(object_type: str, row: dict) -> RawObject:
    return RawObject(source="postgres", object_type=object_type,
                     source_object_id=str(row.get("id")),
                     occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                     actor_type="system", content_version="v1", raw=row)


def _capture(raw: RawObject):
    repo = InMemorySourceEventRepository()
    payloads = InMemoryRawPayloadStore()
    res = capture_event(raw, org_id="o", connection_id="c", repo=repo, payload_store=payloads)
    return res, payloads


def test_unmapped_db_table_parks_instead_of_silent_drop():
    res, _ = _capture(_db_row("public.orders", {"id": 7, "total": 999, "status": "paid"}))
    assert res.outcome == "parked"                                  # NOT "dropped"
    assert res.trace.records[-1].reason_code == "mapping_missing"


def test_parked_db_row_retains_content_for_recovery():
    res, payloads = _capture(_db_row("public.orders", {"id": 8, "status": "churned"}))
    assert res.outcome == "parked"
    # store-don't-delete: the payload is kept so /recover can re-emit once a mapping exists
    stored = payloads.payloads.get(res.event.payload_ref)
    assert stored is not None and "churned" in stored["content"]


def test_mapped_db_table_still_emits_structured():
    # public.customer_accounts HAS a registry mapping → structured short-circuit → emitted
    res, _ = _capture(_db_row("public.customer_accounts",
                              {"id": 3, "account_id": 3, "plan": "pro", "status": "active"}))
    assert res.outcome == "emitted"
