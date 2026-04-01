"""
Google Calendar Sync Task

Phase 1 MVP:
  - Full calendar list → quality gate → incremental event sync via syncToken
  - Upsert calendar_events + calendar_event_attendees
  - Upsert upcoming_meetings for future events
  - syncToken renewal; watch channel renewal at 6.5 days
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import text

from app.config import SYNC_MAX_CALENDAR_EVENTS
from app.database import SessionLocal
from app.ingestion.calendar_connector import (
    build_calendar_service,
    list_calendars,
    fetch_events,
    classify_event,
    setup_watch_channel,
    SyncTokenExpiredError,
)
from app.ingestion.calendar_bridge import (
    resolve_attendees_to_contacts,
    create_meeting_interactions,
    link_upcoming_meeting_contacts,
    infer_no_shows,
    detect_rescheduled_events,
    cross_match_gmail_calendar,
    check_meeting_followups,
)
from app.ingestion.calendar_extractor import extract_agenda_from_events
from app.ingestion.bridge_utils import get_org_domain
from app.graph.relationship_calculator import recalculate_all_relationships

logger = logging.getLogger(__name__)

# Watch channel must be renewed before Google's 7-day hard limit
WATCH_RENEWAL_THRESHOLD_HOURS = 6.5 * 24  # 6.5 days in hours


def _get_calendar_tokens(db, org_id):
    """Fetch Calendar OAuth tokens from oauth_tokens (keyed as gcal:<email>)."""
    row = db.execute(
        text("""
            SELECT access_token, refresh_token, token_expiry
            FROM oauth_tokens
            WHERE org_id = :oid AND account_email LIKE 'gcal:%'
            LIMIT 1
        """),
        {"oid": org_id},
    ).fetchone()
    return row


def run_calendar_sync(org_id: str, max_results=None):
    """
    Main Calendar sync entry point. Called after OAuth connect and by scheduler.

    Signal taxonomy quality gates applied BEFORE any DB writes:
      - DROP visibility == "private"
      - DROP all-day events with zero attendees (OOO, holidays, focus blocks)
      - DROP event_type == "focusTime" or "outOfOffice"
      - DROP all attendees share same org domain (internal-only)
      - DROP description empty AND attendee_count == 1 (blocked time)
      - DROP master RRULE events (process instances only)
      - DROP if user RSVP status is "declined"
    """
    db = SessionLocal()
    try:
        token_row = _get_calendar_tokens(db, org_id)
        if not token_row:
            logger.warning(f"Calendar sync: no tokens found for org {org_id}")
            return

        service = build_calendar_service(token_row.access_token, token_row.refresh_token)

        # Get org domain for internal/external detection
        org_domain = get_org_domain(db, org_id)

        # Check if user has explicitly selected calendars
        selected_rows = db.execute(
            text("""
                SELECT calendar_id FROM calendar_sync_state
                WHERE org_id = :oid AND sync_enabled = TRUE
                AND calendar_id != 'primary'
            """),
            {"oid": org_id},
        ).fetchall()

        if selected_rows:
            # User has selected specific calendars — sync only those
            calendar_ids = [r.calendar_id for r in selected_rows]
            logger.info(f"Calendar sync org={org_id}: syncing {len(calendar_ids)} user-selected calendars")
        else:
            # No explicit selection — default to primary calendar only
            calendar_ids = ["primary"]
            logger.info(f"Calendar sync org={org_id}: no calendars selected, defaulting to primary")

        _max_results = max_results if max_results is not None else SYNC_MAX_CALENDAR_EVENTS
        for calendar_id in calendar_ids:
            _sync_calendar(db, service, org_id, calendar_id, org_domain, max_results=_max_results)

        # ── Phase 2: Bridge calendar data into relationship graph ──
        logger.info(f"Calendar bridge: resolving attendees for org={org_id}")
        resolve_attendees_to_contacts(db, org_id, org_domain)
        db.commit()

        logger.info(f"Calendar bridge: creating meeting interactions for org={org_id}")
        interactions_created = create_meeting_interactions(db, org_id, org_domain)
        db.commit()

        logger.info(f"Calendar bridge: linking upcoming meetings for org={org_id}")
        link_upcoming_meeting_contacts(db, org_id)
        db.commit()

        # Phase 1C: Infer no-shows for past meetings
        logger.info(f"Calendar bridge: inferring no-shows for org={org_id}")
        no_shows = infer_no_shows(db, org_id)
        db.commit()

        # Phase 1D: Detect rescheduled events
        logger.info(f"Calendar bridge: detecting rescheduled events for org={org_id}")
        rescheduled = detect_rescheduled_events(db, org_id)
        db.commit()

        # Phase 2B: Cross-match emails ±7 days of meetings
        logger.info(f"Calendar bridge: cross-matching Gmail for org={org_id}")
        cross_match_gmail_calendar(db, org_id)
        db.commit()

        # Phase 3A: Check for missing follow-ups (72h post-meeting)
        logger.info(f"Calendar bridge: checking meeting follow-ups for org={org_id}")
        check_meeting_followups(db, org_id)
        db.commit()

        # Phase 4: LLM agenda extraction for events with descriptions >50 chars
        try:
            logger.info(f"Calendar bridge: extracting agendas for org={org_id}")
            extracted = extract_agenda_from_events(db, org_id)
            if extracted > 0:
                logger.info(f"Calendar bridge: extracted agendas from {extracted} events")
        except Exception as e:
            logger.warning(f"Calendar bridge: agenda extraction failed (non-critical): {e}")

        # Recalculate relationship graph with new calendar signals
        # Also recalculate any contacts stuck with NULL or 'unknown' stage (from previous syncs)
        stageless_count = db.execute(
            text("""
                SELECT COUNT(*) FROM contacts
                WHERE org_id = :oid
                AND (relationship_stage IS NULL OR relationship_stage = 'unknown' OR relationship_stage = 'COLD')
                AND EXISTS (SELECT 1 FROM interactions WHERE contact_id = contacts.id)
            """),
            {"oid": org_id},
        ).scalar() or 0

        if interactions_created > 0 or stageless_count > 0:
            logger.info(f"Calendar bridge: recalculating relationships for org={org_id} (new={interactions_created}, stageless={stageless_count})")
            try:
                updated = recalculate_all_relationships(db, org_id)
                logger.info(f"Calendar bridge: updated {updated} contacts")
            except Exception as e:
                logger.error(f"Calendar bridge: relationship recalc failed: {e}")

        # Phase 3B: Pre-compute context bundles for upcoming meetings (48h window)
        try:
            upcoming = db.execute(
                text("""
                    SELECT um.id, um.primary_contact_id
                    FROM upcoming_meetings um
                    WHERE um.org_id = :oid
                    AND um.status = 'scheduled'
                    AND um.prep_context_generated = FALSE
                    AND um.start_time BETWEEN NOW() AND NOW() + INTERVAL '48 hours'
                    AND um.primary_contact_id IS NOT NULL
                """),
                {"oid": org_id},
            ).fetchall()

            for row in upcoming:
                try:
                    from app.context.bundle_builder import build_context_bundle
                    bundle = build_context_bundle(db, org_id, "", None)
                    if bundle and not bundle.get("error"):
                        db.execute(
                            text("UPDATE upcoming_meetings SET prep_context_generated = TRUE, prep_context_at = NOW() WHERE id = :mid"),
                            {"mid": row.id},
                        )
                except Exception:
                    pass  # Non-critical — skip silently
            db.commit()
            if upcoming:
                logger.info(f"Calendar bridge: pre-computed context for {len(upcoming)} upcoming meetings")
        except Exception as e:
            logger.warning(f"Calendar bridge: meeting prep context failed (non-critical): {e}")

    except Exception as e:
        logger.error(f"Calendar sync failed for org {org_id}: {e}")
        raise
    finally:
        db.close()


def _sync_calendar(db, service, org_id, calendar_id, org_domain, max_results=None):
    """Sync a single calendar using incremental syncToken."""
    if max_results is None:
        max_results = SYNC_MAX_CALENDAR_EVENTS
    # Get current sync token from DB
    state_row = db.execute(
        text("""
            SELECT sync_token, watch_channel_id, watch_expiry
            FROM calendar_sync_state
            WHERE org_id = :oid AND calendar_id = :cal_id
        """),
        {"oid": org_id, "cal_id": calendar_id},
    ).fetchone()

    sync_token = state_row.sync_token if state_row else None

    events_added = 0
    events_filtered = 0
    next_sync_token = None

    try:
        while True:
            events, next_sync_token, next_page_token = fetch_events(
                service, calendar_id=calendar_id, sync_token=sync_token, max_results=max_results
            )

            for event in events:
                classification = classify_event(event, org_domain)
                if classification is None:
                    events_filtered += 1
                    continue  # Quality gate: drop this event

                _upsert_calendar_event(db, org_id, calendar_id, event, classification, org_domain)
                events_added += 1

            if not next_page_token:
                break
            # Continue paginating with same sync_token, different page_token

        db.commit()
        logger.info(
            f"Calendar sync: org={org_id} cal={calendar_id} "
            f"added={events_added} filtered={events_filtered}"
        )

    except SyncTokenExpiredError:
        # Full re-sync required — clear sync token
        logger.warning(f"Calendar sync token expired for org={org_id} cal={calendar_id}, doing full re-sync")
        db.execute(
            text("UPDATE calendar_sync_state SET sync_token = NULL WHERE org_id = :oid AND calendar_id = :cal_id"),
            {"oid": org_id, "cal_id": calendar_id},
        )
        db.commit()
        _sync_calendar(db, service, org_id, calendar_id, org_domain)
        return

    # Update sync token + persist run stats, then check watch channel
    _update_sync_state(db, org_id, calendar_id, next_sync_token, events_added, events_filtered)
    _check_watch_channel_renewal(db, service, org_id, calendar_id, state_row)


def _upsert_calendar_event(db, org_id, calendar_id, event, classification, org_domain=None):
    """Upsert a single calendar event and its attendees."""
    google_event_id = event.get("id")
    start = event.get("start", {})
    end = event.get("end", {})

    start_time = start.get("dateTime") or start.get("date")
    end_time = end.get("dateTime") or end.get("date")

    duration_minutes = None
    if start.get("dateTime") and end.get("dateTime"):
        try:
            from dateutil import parser as dtparser
            s = dtparser.parse(start["dateTime"])
            e = dtparser.parse(end["dateTime"])
            duration_minutes = int((e - s).total_seconds() / 60)
        except Exception:
            pass

    db.execute(
        text("""
            INSERT INTO calendar_events (
                org_id, google_event_id, recurring_event_id, calendar_id,
                title, start_time, end_time, duration_minutes,
                organizer_email, location_type, meeting_type,
                is_cancelled, is_recurring, recurrence_rule,
                raw_event, synced_at
            )
            VALUES (
                :org_id, :google_event_id, :recurring_event_id, :calendar_id,
                :title, :start_time, :end_time, :duration_minutes,
                :organizer_email, :location_type, :meeting_type,
                :is_cancelled, :is_recurring, :recurrence_rule,
                CAST(:raw_event AS jsonb), NOW()
            )
            ON CONFLICT (org_id, google_event_id) DO UPDATE SET
                title = EXCLUDED.title,
                start_time = EXCLUDED.start_time,
                end_time = EXCLUDED.end_time,
                duration_minutes = EXCLUDED.duration_minutes,
                organizer_email = EXCLUDED.organizer_email,
                location_type = EXCLUDED.location_type,
                meeting_type = EXCLUDED.meeting_type,
                is_cancelled = EXCLUDED.is_cancelled,
                is_recurring = EXCLUDED.is_recurring,
                recurrence_rule = EXCLUDED.recurrence_rule,
                raw_event = EXCLUDED.raw_event,
                synced_at = NOW()
        """),
        {
            "org_id": org_id,
            "google_event_id": google_event_id,
            "recurring_event_id": event.get("recurringEventId"),
            "calendar_id": calendar_id,
            "title": event.get("summary", ""),
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration_minutes,
            "organizer_email": event.get("organizer", {}).get("email"),
            "location_type": _infer_location_type(event),
            "meeting_type": classification.get("meeting_type", "unknown"),
            "is_cancelled": event.get("status") == "cancelled",
            "is_recurring": classification.get("is_recurring", False),
            "recurrence_rule": str(event.get("recurrence", [])) if event.get("recurrence") else None,
            "raw_event": __import__("json").dumps(event),
        },
    )

    # Get the event's UUID for attendee FK
    event_row = db.execute(
        text("SELECT id FROM calendar_events WHERE org_id = :oid AND google_event_id = :geid"),
        {"oid": org_id, "geid": google_event_id},
    ).fetchone()

    if not event_row:
        return

    event_uuid = event_row.id

    # Upsert attendees
    for attendee in event.get("attendees", []):
        db.execute(
            text("""
                INSERT INTO calendar_event_attendees (
                    org_id, event_id, email, display_name, rsvp_status,
                    is_organizer, is_optional, is_external
                )
                VALUES (
                    :org_id, :event_id, :email, :display_name, :rsvp_status,
                    :is_organizer, :is_optional, :is_external
                )
                ON CONFLICT (event_id, email) DO UPDATE SET
                    rsvp_status = EXCLUDED.rsvp_status,
                    is_organizer = EXCLUDED.is_organizer,
                    is_optional = EXCLUDED.is_optional
            """),
            {
                "org_id": org_id,
                "event_id": event_uuid,
                "email": attendee.get("email", ""),
                "display_name": attendee.get("displayName"),
                "rsvp_status": attendee.get("responseStatus"),
                "is_organizer": attendee.get("organizer", False),
                "is_optional": attendee.get("optional", False),
                "is_external": (
                    not attendee.get("email", "").lower().endswith(f"@{org_domain}")
                    if org_domain else True
                ),
            },
        )

    # Upsert upcoming meeting record for future events
    if start_time and start_time > datetime.now(timezone.utc).isoformat():
        db.execute(
            text("""
                INSERT INTO upcoming_meetings (org_id, event_id, start_time, status)
                VALUES (:org_id, :event_id, :start_time, 'scheduled')
                ON CONFLICT DO NOTHING
            """),
            {"org_id": org_id, "event_id": event_uuid, "start_time": start_time},
        )


def _infer_location_type(event):
    location = (event.get("location") or "").lower()
    description = (event.get("description") or "").lower()
    combined = location + " " + description

    video_keywords = ["meet.google.com", "zoom.us", "teams.microsoft", "webex", "whereby", "around.co", "loom.com"]
    if any(kw in combined for kw in video_keywords):
        return "video"
    if location and any(w in location for w in ["office", "room", "floor", "building", "street", "ave"]):
        return "in_person"
    return "unknown"


def _update_sync_state(db, org_id, calendar_id, sync_token, events_added=0, events_filtered=0):
    db.execute(
        text("""
            INSERT INTO calendar_sync_state (
                org_id, calendar_id, sync_token, last_full_sync_at,
                last_sync_events_added, last_sync_events_filtered, total_events_synced
            )
            VALUES (:oid, :cal_id, :token, NOW(), :added, :filtered, :added)
            ON CONFLICT (org_id, calendar_id) DO UPDATE SET
                sync_token = EXCLUDED.sync_token,
                last_full_sync_at = NOW(),
                updated_at = NOW(),
                last_sync_events_added = EXCLUDED.last_sync_events_added,
                last_sync_events_filtered = EXCLUDED.last_sync_events_filtered,
                total_events_synced = COALESCE(calendar_sync_state.total_events_synced, 0) + EXCLUDED.last_sync_events_added
        """),
        {"oid": org_id, "cal_id": calendar_id, "token": sync_token, "added": events_added, "filtered": events_filtered},
    )
    db.commit()


def _check_watch_channel_renewal(db, service, org_id, calendar_id, state_row):
    """Renew watch channel if expiry is within 6.5 days."""
    if not state_row or not state_row.watch_expiry:
        return

    hours_until_expiry = (
        state_row.watch_expiry.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
    ).total_seconds() / 3600

    if hours_until_expiry < WATCH_RENEWAL_THRESHOLD_HOURS:
        import os
        webhook_url = os.getenv("GOOGLE_CALENDAR_WEBHOOK_URL")
        if not webhook_url:
            logger.warning("GOOGLE_CALENDAR_WEBHOOK_URL not set — skipping watch renewal")
            return

        try:
            result = setup_watch_channel(service, calendar_id, webhook_url)
            db.execute(
                text("""
                    UPDATE calendar_sync_state
                    SET watch_channel_id = :channel_id,
                        watch_expiry = to_timestamp(:expiry_ms / 1000.0),
                        updated_at = NOW()
                    WHERE org_id = :oid AND calendar_id = :cal_id
                """),
                {
                    "channel_id": result.get("id"),
                    "expiry_ms": result.get("expiration", 0),
                    "oid": org_id,
                    "cal_id": calendar_id,
                },
            )
            db.commit()
            logger.info(f"Watch channel renewed for org={org_id} cal={calendar_id}")
        except Exception as e:
            logger.error(f"Watch channel renewal failed: {e}")


