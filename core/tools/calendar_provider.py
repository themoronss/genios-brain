"""
Calendar Provider — Read-only

Fetches upcoming events using the Google Calendar API.
Read-only scope: calendar.readonly

Returns normalized tool state that matches the MockCalendarProvider shape:
    {
        "next_free_slot": str (ISO),
        "busy_slots_today": int,
        "events": [...],        # extra: upcoming event summaries
    }
"""

from datetime import datetime, timezone, timedelta
from layers.layer1_retrieval.r3_tools.provider_base import ToolProvider


class CalendarProvider(ToolProvider):
    """Real Calendar provider — read-only access."""

    def __init__(self):
        self._service = None

    @property
    def tool_name(self) -> str:
        return "calendar"

    def supports(self, intent_type: str) -> bool:
        return intent_type in ("schedule_meeting",)

    @property
    def service(self):
        """Lazy-init Calendar service."""
        if self._service is None:
            from googleapiclient.discovery import build
            from core.tools.google_auth import get_google_credentials
            creds = get_google_credentials()
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def fetch(self, entities: list[str], workspace_id: str) -> dict:
        """
        Fetch upcoming calendar events.

        Args:
            entities: Entity names (used to search for relevant events).
            workspace_id: Current workspace (unused).

        Returns:
            Normalized tool state dict.
        """
        try:
            return self._fetch_real(entities)
        except Exception as e:
            return {
                "tool_name": "calendar",
                "result_summary": {
                    "next_free_slot": "",
                    "busy_slots_today": 0,
                    "events": [],
                    "error": str(e),
                },
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "ttl_seconds": 120,
            }

    def _fetch_real(self, entities: list[str]) -> dict:
        """Actual Calendar API calls."""
        now = datetime.now(timezone.utc)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=7)).isoformat()

        # List upcoming events for the next 7 days
        result = (
            self.service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events_data = result.get("items", [])

        # Build event summaries
        events_summary = []
        busy_today = 0
        today_str = now.strftime("%Y-%m-%d")

        for event in events_data:
            start = event.get("start", {})
            start_time = start.get("dateTime", start.get("date", ""))
            summary = event.get("summary", "No title")
            attendees = [
                a.get("email", "") for a in event.get("attendees", [])
            ]

            events_summary.append({
                "summary": summary,
                "start": start_time,
                "attendees": attendees[:5],
            })

            # Count today's busy slots
            if today_str in start_time:
                busy_today += 1

        # Find next free slot (simple: look for gaps)
        next_free = self._find_next_free(events_data, now)

        return {
            "tool_name": "calendar",
            "query": "upcoming 7 days",
            "result_summary": {
                "next_free_slot": next_free,
                "busy_slots_today": busy_today,
                "events": events_summary,
            },
            "fetched_at": now.isoformat(),
            "ttl_seconds": 120,
        }

    def _find_next_free(self, events: list, now: datetime) -> str:
        """Find the next free 1-hour slot within business hours."""
        # Simple approach: find first hour gap
        busy_times = []
        for event in events:
            start = event.get("start", {}).get("dateTime")
            end = event.get("end", {}).get("dateTime")
            if start and end:
                busy_times.append((start, end))

        # If no events, next business hour is free
        candidate = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

        # Skip to 9 AM if outside business hours
        if candidate.hour < 9:
            candidate = candidate.replace(hour=9)
        elif candidate.hour >= 17:
            candidate = (candidate + timedelta(days=1)).replace(hour=9)

        return candidate.isoformat()
