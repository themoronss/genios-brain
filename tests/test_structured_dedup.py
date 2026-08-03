from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
from genios_engine.capture.connectors.database import ClientDatabaseConnector
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.contracts.source_event import compute_dedup_key

# D2 · structured-lane freeze fix. A MUTABLE structured object (CRM deal, calendar event, DB row)
# must re-land when it CHANGES (so deal.stage/meeting.start_at update), while an immutable email
# must NOT re-land on re-sync. The discriminator is a per-object content_version in dedup_key.

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)


def test_email_dedup_is_stable_across_resync():
    # no content_version → same object always same key (an email never edits)
    k1 = compute_dedup_key("gmail", "message", "msg_1")
    k2 = compute_dedup_key("gmail", "message", "msg_1")
    assert k1 == k2 == "gmail:message:msg_1"


def test_structured_change_gets_a_new_dedup_key():
    proposal = compute_dedup_key("hubspot", "deal", "deal_9", "2026-07-20T10:00:00Z")
    won = compute_dedup_key("hubspot", "deal", "deal_9", "2026-07-28T14:00:00Z")   # stage moved
    unchanged = compute_dedup_key("hubspot", "deal", "deal_9", "2026-07-20T10:00:00Z")
    assert proposal != won                 # a real change re-lands → graph updates
    assert proposal == unchanged           # an unchanged re-sync still dedups (no spurious work)


def test_calendar_connector_sets_content_version_from_updated():
    conn = ComposioCalendarConnector.__new__(ComposioCalendarConnector)   # no network
    ev = {"id": "ev1", "updated": "2026-07-30T09:00:00Z",
          "start": {"dateTime": "2026-08-01T15:00:00Z"}, "status": "confirmed",
          "organizer": {"email": "a@acme.io"}}
    raw = conn._to_raw(ev)
    assert raw.content_version == "2026-07-30T09:00:00Z"
    # a reschedule (updated changes) → different dedup_key → meeting.start_at can update
    ev2 = {**ev, "updated": "2026-07-31T18:00:00Z", "start": {"dateTime": "2026-08-02T15:00:00Z"}}
    assert to_source_event(raw, org_id="o", connection_id="c").dedup_key != \
        to_source_event(conn._to_raw(ev2), org_id="o", connection_id="c").dedup_key


def test_database_connector_uses_watermark_as_content_version():
    conn = ClientDatabaseConnector(database_url="postgresql://x/y", table="deals",
                                   identity_field="id", watermark_col="updated_at",
                                   source="postgres")
    row1 = {"id": 5, "updated_at": datetime(2026, 7, 20, tzinfo=timezone.utc), "stage": "proposal"}
    row2 = {"id": 5, "updated_at": datetime(2026, 7, 28, tzinfo=timezone.utc), "stage": "won"}
    r1, r2 = conn._to_raw(row1), conn._to_raw(row2)
    assert r1.content_version != r2.content_version
    assert to_source_event(r1, org_id="o", connection_id="c").dedup_key != \
        to_source_event(r2, org_id="o", connection_id="c").dedup_key   # the deal-stage-freeze fix
