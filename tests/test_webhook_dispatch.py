from __future__ import annotations

import base64
from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.connectors.dispatch import webhook_to_raw

# The live webhook used to force EVERY Composio trigger through the Gmail parser, so a calendar /
# Notion / Drive push was parsed as a malformed "email". Dispatch now routes by source_type.


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


def test_calendar_trigger_is_parsed_as_calendar_not_gmail():
    ev = {"id": "ev1", "updated": "2026-07-30T09:00:00Z", "summary": "Board sync",
          "start": {"dateTime": "2026-08-01T15:00:00Z"}, "status": "confirmed",
          "organizer": {"email": "a@acme.io"}}
    raw = webhook_to_raw("gcal", {"event": ev})
    assert raw is not None
    assert raw.source == "gcal" and raw.object_type == "calendar_event"


def test_gmail_trigger_still_parses_as_email():
    msg = {"id": "m1", "from": "x@acme.io", "subject": "hello",
           "payload": {"parts": [{"mimeType": "text/plain", "filename": "",
                                  "body": {"data": _b64("Hi there, quick question.")}}]}}
    raw = webhook_to_raw("gmail", {"message": msg})
    assert raw is not None and raw.source == "gmail" and raw.object_type == "email_message"


def test_notion_trigger_uses_the_connector_factory_for_creds():
    seen = {}

    class _FakeNotion:
        def _to_raw(self, page):
            seen["id"] = page.get("id")
            return RawObject(source="notion", object_type="page", source_object_id=page["id"],
                             occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc), raw={"body": "x"})

    raw = webhook_to_raw("notion", {"page": {"id": "p1"}}, connector_factory=lambda: _FakeNotion())
    assert raw is not None and raw.source == "notion" and seen["id"] == "p1"


def test_unknown_source_returns_none_not_a_fake_event():
    assert webhook_to_raw("slack", {"message": {"text": "hi"}}) is None
    assert webhook_to_raw("gmail", "not-a-dict") is None
