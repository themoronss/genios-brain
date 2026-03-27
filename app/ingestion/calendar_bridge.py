"""
Calendar Bridge — Phase 2

Bridges calendar data into the relationship graph by:
1. Resolving external attendee emails → contacts table
2. Creating MEETING interaction edges in interactions table
3. Linking upcoming_meetings to primary contacts

Per PDF spec signal weights:
  - Confirmed 60min meeting = 8.0x (vs email 1.0x)
  - Recurring weekly 1:1     = 12.0x
  - Cancelled meeting         = -3.0x
"""

import logging
from uuid import uuid4
from sqlalchemy import text

from app.ingestion.graph_builder import upsert_contact

logger = logging.getLogger(__name__)


# ─── 1. Resolve attendees to contacts ─────────────────────────────────────────

def resolve_attendees_to_contacts(db, org_id: str, org_domain: str | None):
    """
    For every calendar_event_attendee with person_id IS NULL,
    match or create a contact in the contacts table.

    Skips internal attendees (same org domain) and automated/resource emails.
    """
    unresolved = db.execute(
        text("""
            SELECT cea.id, cea.event_id, cea.email, cea.display_name
            FROM calendar_event_attendees cea
            WHERE cea.org_id = :oid AND cea.person_id IS NULL
            AND cea.email IS NOT NULL AND cea.email != ''
        """),
        {"oid": org_id},
    ).fetchall()

    if not unresolved:
        return 0

    resolved_count = 0
    for row in unresolved:
        email = (row.email or "").lower().strip()
        if not email or "@" not in email:
            continue

        # Skip internal attendees
        if org_domain and email.endswith(f"@{org_domain}"):
            continue

        # Skip resource/room/group emails
        if _is_resource_email(email):
            continue

        # Upsert into contacts (handles dedup, company extraction)
        display_name = row.display_name or email.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, display_name)

        if contact_id:
            # Link attendee → contact
            db.execute(
                text("UPDATE calendar_event_attendees SET person_id = :cid WHERE id = :aid"),
                {"cid": contact_id, "aid": row.id},
            )
            resolved_count += 1

    logger.info(f"Calendar bridge: resolved {resolved_count}/{len(unresolved)} attendees for org={org_id}")
    return resolved_count


def _is_resource_email(email: str) -> bool:
    """Skip conference rooms, groups, and automated calendar addresses."""
    local = email.split("@")[0].lower()
    skip_patterns = [
        "noreply", "no-reply", "calendar-notification", "resource_",
        "room_", "conference", "meeting-room", "boardroom",
    ]
    return any(p in local for p in skip_patterns)


# ─── 2. Create MEETING interactions ───────────────────────────────────────────

def create_meeting_interactions(db, org_id: str, org_domain: str | None):
    """
    For each calendar event with resolved external attendees,
    write a MEETING interaction edge into the interactions table.

    Signal weights per PDF spec:
      - Recurring 1:1 = 12.0x
      - Confirmed meeting = 8.0x
      - Default sentiment = 0.3 (meeting happened = slight positive)
    """
    # Get the user's primary email — needed so graph edges connect to the user node
    user_email_row = db.execute(
        text("SELECT email FROM orgs WHERE id = :oid"),
        {"oid": org_id},
    ).fetchone()
    account_email = user_email_row.email if user_email_row else None

    # Find events with resolved external attendees that don't yet have interactions
    events_with_contacts = db.execute(
        text("""
            SELECT DISTINCT
                ce.id AS event_id,
                ce.google_event_id,
                ce.title,
                ce.start_time,
                ce.duration_minutes,
                ce.is_cancelled,
                ce.is_recurring,
                ce.location_type,
                ce.meeting_type,
                ce.organizer_email,
                cea.person_id AS contact_id,
                cea.rsvp_status,
                cea.email AS attendee_email
            FROM calendar_events ce
            JOIN calendar_event_attendees cea ON cea.event_id = ce.id
            WHERE ce.org_id = :oid
              AND cea.person_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM interactions i
                  WHERE i.calendar_event_id = ce.id
                    AND i.contact_id = cea.person_id
              )
        """),
        {"oid": org_id},
    ).fetchall()

    if not events_with_contacts:
        return 0

    created_count = 0
    for row in events_with_contacts:
        # Determine edge weight per PDF spec
        if row.is_recurring and row.meeting_type == "one_on_one":
            edge_weight = 12.0  # Recurring weekly 1:1 = strongest signal
        elif row.is_cancelled:
            edge_weight = -3.0  # Cancellation = cooling signal
        else:
            edge_weight = 8.0   # Confirmed meeting = 8x a single email

        # Count external attendees for this event
        attendee_count = db.execute(
            text("""
                SELECT COUNT(*) FROM calendar_event_attendees
                WHERE event_id = :eid AND person_id IS NOT NULL
            """),
            {"eid": row.event_id},
        ).scalar() or 1

        interaction_id = str(uuid4())
        # Use synthetic gmail_message_id to satisfy unique constraint
        synthetic_msg_id = f"cal:{row.google_event_id}:{row.contact_id}"

        db.execute(
            text("""
                INSERT INTO interactions (
                    id, org_id, contact_id,
                    gmail_message_id, calendar_event_id,
                    account_email,
                    direction, subject, summary,
                    interaction_at, sentiment, intent,
                    source, weight_score, signal_score,
                    duration_minutes, attendee_count,
                    rsvp_status, location_type,
                    is_recurring, edge_weight_multiplier
                )
                VALUES (
                    :id, :org_id, :contact_id,
                    :gmail_message_id, :calendar_event_id,
                    :account_email,
                    'bidirectional', :subject, :summary,
                    :interaction_at, :sentiment, 'meeting',
                    'calendar', :weight_score, :signal_score,
                    :duration_minutes, :attendee_count,
                    :rsvp_status, :location_type,
                    :is_recurring, :edge_weight_multiplier
                )
                ON CONFLICT (calendar_event_id, contact_id)
                    WHERE calendar_event_id IS NOT NULL
                DO UPDATE SET
                    subject = EXCLUDED.subject,
                    duration_minutes = EXCLUDED.duration_minutes,
                    edge_weight_multiplier = EXCLUDED.edge_weight_multiplier,
                    rsvp_status = EXCLUDED.rsvp_status,
                    account_email = EXCLUDED.account_email
            """),
            {
                "id": interaction_id,
                "org_id": org_id,
                "contact_id": str(row.contact_id),
                "gmail_message_id": synthetic_msg_id,
                "calendar_event_id": str(row.event_id),
                "account_email": account_email,
                "subject": row.title or "Meeting",
                "summary": (
                    f"Recurring 1:1: {row.title}"
                    if row.is_recurring and row.meeting_type == "one_on_one"
                    else f"Meeting: {row.title or 'Untitled'}"
                ),
                "interaction_at": row.start_time,
                "sentiment": 0.3,  # Meeting happened = slight positive
                "weight_score": 0.9,
                "signal_score": 0.8,
                "duration_minutes": row.duration_minutes,
                "attendee_count": attendee_count,
                "rsvp_status": row.rsvp_status,
                "location_type": row.location_type,
                "is_recurring": row.is_recurring or False,
                "edge_weight_multiplier": edge_weight,
            },
        )
        created_count += 1

    logger.info(f"Calendar bridge: created {created_count} meeting interactions for org={org_id}")
    return created_count


# ─── 3. Link upcoming meetings to primary contacts ────────────────────────────

def link_upcoming_meeting_contacts(db, org_id: str):
    """
    Set primary_contact_id on upcoming_meetings to the highest-scored
    external attendee for that event.
    """
    unlinked = db.execute(
        text("""
            SELECT um.id, um.event_id
            FROM upcoming_meetings um
            WHERE um.org_id = :oid AND um.primary_contact_id IS NULL
        """),
        {"oid": org_id},
    ).fetchall()

    if not unlinked:
        return 0

    linked_count = 0
    for row in unlinked:
        best_contact = db.execute(
            text("""
                SELECT cea.person_id
                FROM calendar_event_attendees cea
                LEFT JOIN contacts c ON c.id = cea.person_id
                WHERE cea.event_id = :eid AND cea.person_id IS NOT NULL
                ORDER BY c.composite_score DESC NULLS LAST
                LIMIT 1
            """),
            {"eid": row.event_id},
        ).fetchone()

        if best_contact:
            db.execute(
                text("UPDATE upcoming_meetings SET primary_contact_id = :cid WHERE id = :uid"),
                {"cid": best_contact.person_id, "uid": row.id},
            )
            linked_count += 1

    logger.info(f"Calendar bridge: linked {linked_count}/{len(unlinked)} upcoming meetings for org={org_id}")
    return linked_count
