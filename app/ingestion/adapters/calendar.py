"""
Google Calendar pull adapter — per-agent.

Each calendar event (recent + upcoming 7-day window) becomes an `interaction`
record with kind='calendar_event'. Attendees become contacts.

We don't insert as 'email' since calendar events have different shape — but
the sync task can still call this via the `fetch_calendar` op once we wire
the calendar source into ingest.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import register

logger = logging.getLogger(__name__)


def _to_iso(ts) -> str:
    if not ts:
        return ""
    if isinstance(ts, str):
        return ts
    if isinstance(ts, datetime):
        return ts.isoformat()
    return str(ts)


def fetch_events(credentials: dict, since_iso: Optional[str] = None) -> list[dict]:
    """Returns canonical calendar events. Each event maps to one or more
    contacts (attendees) — caller upserts contacts and inserts interactions."""
    access = credentials.get("access_token")
    refresh = credentials.get("refresh_token")
    if not access or not refresh:
        raise ValueError("calendar adapter: access_token + refresh_token required")

    try:
        from app.ingestion.calendar_connector import build_calendar_service
    except Exception as e:
        logger.error(f"calendar_connector import failed: {e}")
        return []

    try:
        service = build_calendar_service(access, refresh)
    except Exception as e:
        logger.warning(f"calendar service build failed: {e}")
        return []

    now = datetime.now(timezone.utc)
    time_min = since_iso or (now - timedelta(days=7)).isoformat()
    time_max = (now + timedelta(days=14)).isoformat()

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            maxResults=100,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as e:
        logger.warning(f"calendar list failed: {e}")
        return []

    events = events_result.get("items", [])
    out: list[dict] = []
    for ev in events:
        if not ev.get("id"):
            continue
        organizer = (ev.get("organizer") or {}).get("email")
        attendees = [a.get("email") for a in (ev.get("attendees") or []) if a.get("email")]
        start = (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date")
        end = (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date")

        # Emit one synthetic event row per attendee+organizer pair so the caller
        # can upsert each as a contact and create an interaction.
        out.append({
            "external_id":  ev["id"],
            "summary":      ev.get("summary") or "",
            "description": (ev.get("description") or "")[:5000],
            "organizer":    organizer,
            "attendees":    attendees,
            "start":        _to_iso(start),
            "end":          _to_iso(end),
            "location":     ev.get("location"),
            "html_link":    ev.get("htmlLink"),
        })
    return out


def mark_read(credentials: dict, external_id: str) -> bool:
    """No-op for calendar — events stay forever, idempotency handled by external_id."""
    return True


def _register():
    register("calendar", {
        "fetch_calendar": fetch_events,
        "mark_read":      mark_read,
    })


_register()
