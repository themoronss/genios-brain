from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import uuid

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

CALENDAR_REDIRECT_URI = None  # Loaded lazily from config

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def _get_redirect_uri():
    global CALENDAR_REDIRECT_URI
    if CALENDAR_REDIRECT_URI is None:
        from app.config import GOOGLE_CALENDAR_REDIRECT_URI
        CALENDAR_REDIRECT_URI = GOOGLE_CALENDAR_REDIRECT_URI
    return CALENDAR_REDIRECT_URI


def create_calendar_oauth_flow():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = _get_redirect_uri()
    return flow


def build_calendar_service(access_token, refresh_token=None):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("calendar", "v3", credentials=creds)


def get_calendar_user_email(service):
    """Get authenticated user's email via OAuth2 userinfo."""
    oauth2_service = build("oauth2", "v2", credentials=service._http.credentials)
    info = oauth2_service.userinfo().get().execute()
    return info.get("email")


def list_calendars(service):
    """
    List all calendars for the authenticated user.
    Returns list of calendar dicts with id, summary, primary flag.
    """
    result = service.calendarList().list().execute()
    return result.get("items", [])


def fetch_events(service, calendar_id="primary", sync_token=None, page_token=None, max_results=250):
    """
    Fetch calendar events using incremental sync via syncToken.
    On first call, sync_token is None — fetches full event list.
    On subsequent calls, pass the syncToken from the previous response.
    For pagination, pass page_token from previous response.

    Returns:
        (events: list, next_sync_token: str, next_page_token: str or None)
    """
    kwargs = {
        "calendarId": calendar_id,
        "maxResults": max_results,
    }
    if sync_token:
        # Incremental sync — syncToken is incompatible with timeMin/orderBy/singleEvents
        kwargs["syncToken"] = sync_token
        if page_token:
            kwargs["pageToken"] = page_token
    else:
        # Full sync: fetch future + 90 days back
        kwargs["singleEvents"] = True
        kwargs["orderBy"] = "startTime"
        from datetime import datetime, timedelta, timezone
        time_min = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        kwargs["timeMin"] = time_min
        if page_token:
            kwargs["pageToken"] = page_token

    try:
        result = service.events().list(**kwargs).execute()
    except Exception as e:
        if "410" in str(e):
            # syncToken expired — caller must do a full re-sync
            raise SyncTokenExpiredError("Calendar sync token expired, full re-sync required")
        raise

    events = result.get("items", [])
    next_sync_token = result.get("nextSyncToken")
    next_page_token = result.get("nextPageToken")
    return events, next_sync_token, next_page_token


def setup_watch_channel(service, calendar_id, webhook_url, channel_token: str = None):
    """
    Set up push notifications for a calendar via watch channel.
    CRITICAL: Expiry is set to 6.5 days (NOT 7) to ensure renewal before Google's
    7-day hard limit. The renewal cron must run before this timestamp.

    channel_token (optional) — opaque secret Google echoes back in every push as
    X-Goog-Channel-Token; receiver verifies it to reject spoofed calls.

    Returns:
        dict with id (channelId), resourceId, expiration (ms timestamp),
        and 'token' echoed back for caller to persist.
    """
    from datetime import datetime, timedelta, timezone

    expiry_ms = int(
        (datetime.now(timezone.utc) + timedelta(days=6, hours=12)).timestamp() * 1000
    )

    channel_id = str(uuid.uuid4())
    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": webhook_url,
        "expiration": expiry_ms,
    }
    if channel_token:
        body["token"] = channel_token

    result = service.events().watch(calendarId=calendar_id, body=body).execute()
    if channel_token:
        result["token"] = channel_token
    return result


def stop_watch_channel(service, channel_id, resource_id):
    """Stop an active push notification channel."""
    body = {"id": channel_id, "resourceId": resource_id}
    service.channels().stop(body=body).execute()


def classify_event(event, org_domain=None):
    """
    First-pass quality gate. Returns None if the event should be dropped,
    or a classification dict if it should be processed.

    Args:
        event: Raw Google Calendar event dict
        org_domain: The org's email domain for internal/external detection (e.g. "acme.com")
    """
    # DROP: private events — hard filter, no exceptions
    if event.get("visibility") == "private":
        return None

    # DROP: auto-generated event types
    if event.get("eventType") in ("focusTime", "outOfOffice", "workingLocation"):
        return None

    # DROP: master RRULE events (process instances only)
    # Master = has recurrence[] but no recurringEventId
    if event.get("recurrence") and not event.get("recurringEventId"):
        return None

    # KEEP cancelled events — they produce a -3.0 cooling signal in the bridge.
    # Mark them so downstream can apply the right edge weight.
    is_cancelled = event.get("status") == "cancelled"

    attendees = event.get("attendees", [])

    # DROP: all-day events with no attendees (OOO, holidays, focus blocks)
    if "date" in event.get("start", {}) and len(attendees) == 0:
        return None

    # DROP: description empty AND single attendee (blocked time, personal reminders)
    if not event.get("description") and len(attendees) <= 1:
        return None

    # DROP: user RSVP declined
    for att in attendees:
        if att.get("self") and att.get("responseStatus") == "declined":
            return None

    # DROP: all attendees share same org domain (internal-only sync)
    if org_domain and len(attendees) > 0:
        external = [
            a for a in attendees
            if not a.get("email", "").endswith(f"@{org_domain}")
            and not a.get("email", "").endswith(f".{org_domain}")
        ]
        if len(external) == 0:
            return None

    # Classify meeting type
    attendee_count = len(attendees)
    is_recurring = bool(event.get("recurringEventId"))

    if attendee_count == 2:
        meeting_type = "one_on_one"
    elif attendee_count > 2:
        meeting_type = "group"
    else:
        meeting_type = "unknown"

    return {
        "meeting_type": meeting_type,
        "is_recurring": is_recurring,
        "attendee_count": attendee_count,
        "is_cancelled": is_cancelled,
        "is_external": any(
            not a.get("email", "").endswith(f"@{org_domain or ''}")
            for a in attendees
        ),
    }


class SyncTokenExpiredError(Exception):
    pass


# ── Phase 1: Live Tool Dispatcher ──────────────────────────────────────────
# Real-time Calendar search invoked when graph data is missing/insufficient.

def live_search(
    org_id: str,
    query: str = "",
    days_back: int = 30,
    days_forward: int = 60,
    limit: int = 10,
) -> list:
    """
    Live Calendar search — invoked from /v1/context when graph misses.

    Loads the gcal: prefixed token from oauth_tokens, runs Calendar's
    `q=` search across the primary calendar in the chosen window. Returns
    lightweight event summaries. NEVER raises — returns [] on failure.

    Args:
        org_id: org UUID (string)
        query: free-text search across event title/description/attendees
        days_back: how far back to look
        days_forward: how far forward to look (defaults to upcoming 60d)
        limit: max events (hard cap 25)

    Returns:
        list of dicts: {id, summary, start, end, attendees, location, source}
    """
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text as sa_text
    from app.database import SessionLocal

    if not org_id:
        return []
    limit = min(max(1, int(limit)), 25)

    db = SessionLocal()
    try:
        token_row = db.execute(
            sa_text(
                """
                SELECT access_token, refresh_token, account_email
                FROM oauth_tokens
                WHERE org_id = :oid
                  AND account_email LIKE 'gcal:%'
                  AND access_token IS NOT NULL
                LIMIT 1
                """
            ),
            {"oid": org_id},
        ).fetchone()
    finally:
        db.close()

    if not token_row:
        return []

    try:
        service = build_calendar_service(
            token_row.access_token, token_row.refresh_token
        )
        time_min = (
            datetime.now(timezone.utc) - timedelta(days=days_back)
        ).isoformat()
        time_max = (
            datetime.now(timezone.utc) + timedelta(days=days_forward)
        ).isoformat()

        kwargs = {
            "calendarId": "primary",
            "maxResults": limit,
            "singleEvents": True,
            "orderBy": "startTime",
            "timeMin": time_min,
            "timeMax": time_max,
        }
        if query:
            kwargs["q"] = query

        resp = service.events().list(**kwargs).execute()
        events = resp.get("items", []) or []
    except Exception:
        return []

    results = []
    for ev in events[:limit]:
        try:
            results.append({
                "id": ev.get("id"),
                "summary": ev.get("summary", ""),
                "description": (ev.get("description") or "")[:500],
                "start": (ev.get("start") or {}).get(
                    "dateTime", (ev.get("start") or {}).get("date")
                ),
                "end": (ev.get("end") or {}).get(
                    "dateTime", (ev.get("end") or {}).get("date")
                ),
                "location": ev.get("location", ""),
                "attendees": [
                    {
                        "email": a.get("email"),
                        "response": a.get("responseStatus"),
                    }
                    for a in (ev.get("attendees") or [])[:10]
                ],
                "status": ev.get("status"),
                "source": "calendar_live",
            })
        except Exception:
            continue
    return results
