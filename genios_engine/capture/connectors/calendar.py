from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .base import RawObject, SourceBatch
from .composio_base import ComposioExec

# Google Calendar via Composio. Events are STRUCTURED — they carry the gcal.calendar_event
# mapping, so the gate short-circuits them (no LLM extraction needed). Field paths are
# defensive and finalized against the real response on first live run (as with Gmail).

# First-connect backfill window: how far BACK to pull on a fresh sync (all FUTURE events are
# always pulled — no timeMax). Kept to the last 2 months to match the Gmail backfill window, so
# email + calendar cover the same recent period without dragging in stale calendar noise.
_BACKFILL_DAYS = 60


def _parse_start(ev: dict) -> datetime:
    start = ev.get("start") or {}
    val = start.get("dateTime") or start.get("date") or ev.get("updated")
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


class ComposioCalendarConnector:
    source = "gcal"

    def __init__(self, *, api_key: str, user_id: str, calendar_id: str = "primary") -> None:
        self._x = ComposioExec(api_key=api_key, user_id=user_id)
        self._cal = calendar_id

    def _fetch(self, *, max_results: int, since: datetime | None, page_token: str | None):
        # window: from the watermark, or the last _BACKFILL_DAYS (2 months) on a first run
        # (+ all future). Matches the Gmail 60-day backfill so both sources cover the same period.
        tmin = since or (datetime.now(timezone.utc) - timedelta(days=_BACKFILL_DAYS))
        args: dict[str, Any] = {"calendarId": self._cal, "maxResults": max_results,
                                "singleEvents": True, "orderBy": "startTime",
                                "timeMin": tmin.astimezone(timezone.utc).isoformat()}
        if page_token:
            args["pageToken"] = page_token
        return self._x.execute("GOOGLECALENDAR_EVENTS_LIST", args)

    def _to_batch(self, data: dict) -> SourceBatch:
        items = data.get("items") or data.get("events") or []
        objs = [self._to_raw(e) for e in items if isinstance(e, dict)]
        return SourceBatch(objects=[o for o in objs if o], next_cursor=data.get("nextPageToken"))

    def _to_raw(self, ev: dict) -> RawObject | None:
        eid = ev.get("id")
        if not eid:
            return None
        organizer = (ev.get("organizer") or {}).get("email")
        attendees = [a.get("email") for a in (ev.get("attendees") or []) if a.get("email")]
        return RawObject(
            source="gcal", object_type="calendar_event", source_object_id=str(eid),
            occurred_at=_parse_start(ev), actor_email=organizer, actor_type="internal_user",
            # `updated` changes whenever the event is edited (rescheduled, status change) →
            # a reschedule re-lands and updates meeting.start_at instead of being deduped away.
            content_version=str(ev.get("updated")) if ev.get("updated") else None,
            raw={  # structured fields the gcal.calendar_event mapping reads
                "summary": ev.get("summary"),
                "start": (ev.get("start") or {}).get("dateTime") or (ev.get("start") or {}).get("date"),
                "end": (ev.get("end") or {}).get("dateTime") or (ev.get("end") or {}).get("date"),
                "status": ev.get("status"),
                "attendees": attendees,
                "hangoutLink": ev.get("hangoutLink"),
                # agenda/notes + where — real relevant info that was being dropped (only summary was kept)
                "description": ev.get("description"),
                "location": ev.get("location"),
            },
        )

    def validate_connection(self) -> bool:
        self._fetch(max_results=1, since=None, page_token=None)
        return True

    def initial_snapshot(self, cursor: str | None = None, limit: int = 50) -> SourceBatch:
        return self._to_batch(self._fetch(max_results=limit, since=None, page_token=cursor))

    def incremental_changes(self, cursor: str | None = None, limit: int = 50,
                            since: datetime | None = None) -> SourceBatch:
        return self._to_batch(self._fetch(max_results=limit, since=since, page_token=cursor))

    def fetch_content(self, object_ref: str) -> dict[str, Any]:
        return self._x.execute("GOOGLECALENDAR_EVENTS_GET",
                               {"calendarId": self._cal, "eventId": object_ref})
