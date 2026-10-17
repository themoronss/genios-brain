"""Layer 1 · a message whose time we could not read is marked, counted, and never moves the cursor.

    pytest tests/capture/connectors/test_a_time_we_could_not_read_is_never_passed_off_as_now.py -q

THE DEFECT (GeniOS-008 L1 W8). Nine connectors fell back to `datetime.now()` when the source's own
time was missing or unreadable. The result was indistinguishable from a mail that really arrived
now: an old thread read as today's, and the sync cursor jumped to "now" on it — so the next poll
asked for changes after a moment the provider had not reached.

THE FIX (A3). The fallback is an `InferredInstant`. `RawObject` records `occurred_at_inferred`,
stores a plain `datetime`, and writes the flag into `raw` so it survives into the payload;
`run_sync` counts it and does not let it move the watermark.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit


def test_a_gmail_message_with_no_time_is_marked_and_stays_a_plain_datetime():
    from genios_engine.capture.connectors.base import InferredInstant
    from genios_engine.capture.connectors.composio import _parse_ts

    assert isinstance(_parse_ts({}), InferredInstant)
    real = _parse_ts({"internalDate": "1785000000000"})
    assert not isinstance(real, InferredInstant), "a real time must never be marked"


@pytest.mark.parametrize("module, fn, arg", [
    ("genios_engine.capture.connectors.calendar", "_parse_start", {}),
    ("genios_engine.capture.connectors.drive", "_parse_ts", None),
    ("genios_engine.capture.connectors.hubspot", "_parse_ts", None),
    ("genios_engine.capture.connectors.linear", "_parse_ts", None),
    ("genios_engine.capture.connectors.notion", "_parse_ts", None),
])
def test_every_connector_fallback_is_marked(module, fn, arg):
    import importlib

    from genios_engine.capture.connectors.base import InferredInstant

    assert isinstance(getattr(importlib.import_module(module), fn)(arg), InferredInstant)


def test_a_transcript_with_no_start_and_no_day_is_marked():
    from genios_engine.capture.connectors.base import InferredInstant
    from genios_engine.capture.transcripts.ingest import _occurred

    assert isinstance(_occurred(None, None), InferredInstant)


def test_the_raw_object_records_the_mark_and_hides_the_subclass():
    from genios_engine.capture.connectors.base import InferredInstant, RawObject

    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                    occurred_at=InferredInstant.now_utc(), raw={"subject": "s"})
    assert raw.occurred_at_inferred is True
    assert type(raw.occurred_at) is datetime, "nothing downstream may see the subclass"
    assert raw.raw == {"subject": "s", "occurred_at_inferred": True}

    plain = RawObject(source="gmail", object_type="email_message", source_object_id="m2",
                      occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc), raw={"subject": "s"})
    assert plain.occurred_at_inferred is False and "occurred_at_inferred" not in plain.raw


def test_an_inferred_time_is_counted_and_never_moves_the_cursor():
    from genios_engine.capture.acquire.sync_runner import run_sync
    from genios_engine.capture.connectors.base import InferredInstant, RawObject, SourceBatch
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    real = datetime(2026, 9, 1, tzinfo=timezone.utc)

    class _Saved:
        def __init__(self):
            self.watermark = None

        def get(self, org_id, connection_id, source):
            return None

        def save(self, org_id, connection_id, source, *, cursor, watermark):
            self.watermark = watermark

    class _Two:
        source = "fake"

        def _batch(self):
            return SourceBatch(objects=[
                RawObject(source="fake", object_type="note", source_object_id="dated",
                          occurred_at=real, actor_email="a@example.com", raw={"snippet": "a"}),
                RawObject(source="fake", object_type="note", source_object_id="undated",
                          occurred_at=InferredInstant.now_utc(), actor_email="b@example.com",
                          raw={"snippet": "b"}),
            ], next_cursor=None)

        def initial_snapshot(self, cursor=None, limit=100):
            return self._batch()

        def incremental_changes(self, cursor=None, limit=100, since=None):
            return self._batch()

        def fetch_content(self, object_ref):
            return {}

    saved = _Saved()
    summary = run_sync(_Two(), org_id="org_t", connection_id="con_t",
                       repo=InMemorySourceEventRepository(), source="fake",
                       cursor_store=saved, respect_cadence=False)
    assert summary.time_inferred == 1
    assert summary.scanned == 2, "the undated object is still captured, never dropped"
    assert saved.watermark == real, "the cursor moved to a time we made up"
