from __future__ import annotations

from genios_engine.capture.connectors.base import RawObject

# Real-time webhook dispatch. A Composio trigger (Gmail message, calendar event, Notion page edit,
# Drive change, CRM update…) must be parsed by the connector for THAT source. The live-webhook route
# used to force EVERY trigger through the Gmail parser, so a calendar/Notion/Drive push was parsed as
# a malformed "email" — garbage fields, usually dropped. This routes by the connection's source_type.
#
# gmail/calendar parse the pushed payload directly (no creds needed). notion/drive only get a
# reference in the trigger and must fetch the page/file body, so they need the tenant's real
# connector — supplied by `connector_factory` (kept injectable so this stays unit-testable).


def webhook_to_raw(source_type: str, data: dict, *, connector_factory=None) -> RawObject | None:
    """Map one Composio trigger payload → RawObject using the right connector, or None if the
    source/payload isn't recognised (the caller reports it, never fabricates an event)."""
    st = (source_type or "").lower()
    if not isinstance(data, dict):
        return None

    if st == "gmail":
        from genios_engine.capture.connectors.composio import ComposioGmailConnector
        msg = data.get("message") or data.get("email") or data
        return ComposioGmailConnector(api_key="", user_id="")._to_raw(msg) if isinstance(msg, dict) else None

    if st in ("gcal", "calendar", "google_calendar"):
        from genios_engine.capture.connectors.calendar import ComposioCalendarConnector
        ev = data.get("event") or data.get("calendar_event") or data
        return ComposioCalendarConnector(api_key="", user_id="")._to_raw(ev) if isinstance(ev, dict) else None

    if st in ("notion", "gdrive", "drive", "google_drive") and connector_factory is not None:
        connector = connector_factory()                 # tenant creds — parse must fetch page/file body
        obj = data.get("page") or data.get("file") or data
        to_raw = getattr(connector, "_to_raw", None)
        return to_raw(obj) if callable(to_raw) and isinstance(obj, dict) else None

    return None
