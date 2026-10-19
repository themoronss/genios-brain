"""L1 rebuild C2 — a duplicate writes no `event_trace` row.

The first landing traces the mail's decision. A re-listing of the same mail (the date watermark's
boundary day every tick, a recovery re-scan, a catch-up) used to write one more row per mail per
look — the table grew with how often we looked, not with what arrived. The duplicate is still
returned as `duplicate`, with its trace on the result, so every count that reads outcomes is
unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.pipeline import capture_event


class _Traces:
    def __init__(self):
        self.saved = []

    def save(self, trace):
        self.saved.append(trace)


def _mail() -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id="m_dup",
                     actor_type="human", actor_email="priya@acme.test",
                     occurred_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
                     raw={"subject": "renewal", "body": "Can we talk about the renewal?"})


def test_the_second_landing_is_a_duplicate_without_a_trace_row():
    repo, traces = InMemorySourceEventRepository(), _Traces()

    first = capture_event(_mail(), org_id="o", connection_id="c", repo=repo, trace_repo=traces)
    assert first.outcome != "duplicate"
    assert len(traces.saved) == 1, "the first landing is traced"

    again = capture_event(_mail(), org_id="o", connection_id="c", repo=repo, trace_repo=traces)
    assert again.outcome == "duplicate"
    assert len(traces.saved) == 1, "a re-listing must not add a trace row"
    assert any(r.reason_code == "duplicate" for r in again.trace.records), (
        "the result still carries why it stopped")
