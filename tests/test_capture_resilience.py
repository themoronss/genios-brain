from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.acquire.sync_runner import _fetch_page
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import (_EMITTED_PAYLOAD_TTL_DAYS,
                                            _PARKED_PAYLOAD_TTL_DAYS, capture_event)

# #7 — a PARKED event waits in the human-review queue for weeks; before this its body expired at the
# default 30 days, so /recover after a month re-emitted an EMPTY event. Parked payloads now get a long
# TTL, emitted ones keep the short one.
# #8 — a transient connector fetch failure (429/network) used to throw out of run_sync, freezing the
# watermark so every following sync died on the same page. _fetch_page retries with backoff.


class _RecordingPayloadStore:
    def __init__(self) -> None:
        self.ttls: dict[str, int] = {}

    def put(self, *, payload_id, org_id, event_id, content, content_type="application/json", ttl_days=30):
        self.ttls[payload_id] = ttl_days


def _capture(raw: RawObject):
    res = capture_event(raw, org_id="o", connection_id="c",
                        repo=InMemorySourceEventRepository(), payload_store=(store := _RecordingPayloadStore()))
    return res, store


def _email(body: str) -> RawObject:
    return RawObject(source="gmail", object_type="email", source_object_id="m1",
                     occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                     actor_type="external_contact", actor_email="priya@chat360.io",
                     raw={"body": body, "subject": "proposal", "headers": {}})


def _unmapped_db_row() -> RawObject:
    return RawObject(source="postgres", object_type="public.orders", source_object_id="7",
                     occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                     actor_type="system", content_version="v1", raw={"id": 7, "status": "paid"})


def test_parked_payload_gets_long_ttl_so_recover_works():
    res, store = _capture(_unmapped_db_row())
    assert res.outcome == "parked"
    assert store.ttls[res.event.payload_ref] == _PARKED_PAYLOAD_TTL_DAYS


def test_emitted_payload_keeps_short_ttl():
    res, store = _capture(_email("Hi, can we meet Friday about the proposal? Details attached."))
    assert res.outcome == "emitted"
    assert store.ttls[res.event.payload_ref] == _EMITTED_PAYLOAD_TTL_DAYS


class _FlakyConnector:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    def incremental_changes(self, cursor, limit, since=None) -> SourceBatch:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise ConnectionError("429 rate limited")
        return SourceBatch(objects=[], next_cursor=None)

    def initial_snapshot(self, cursor, limit) -> SourceBatch:
        return self.incremental_changes(cursor, limit)


def test_fetch_retries_transient_failure_then_succeeds():
    slept: list = []
    conn = _FlakyConnector(fail_times=2)
    batch = _fetch_page(conn, mode="incremental", cursor=None, limit=10, since=None,
                        retries=2, backoff=0.01, sleep=slept.append)
    assert batch.next_cursor is None and conn.calls == 3     # 2 fails + 1 success
    assert len(slept) == 2                                    # backed off before each retry


def test_fetch_raises_after_exhausting_retries():
    conn = _FlakyConnector(fail_times=99)
    raised = False
    try:
        _fetch_page(conn, mode="incremental", cursor=None, limit=10, since=None,
                    retries=2, backoff=0.0, sleep=lambda *_: None)
    except ConnectionError:
        raised = True
    assert raised and conn.calls == 3                         # initial + 2 retries, then propagate
