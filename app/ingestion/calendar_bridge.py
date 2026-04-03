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
        # ── Determine edge weight per PDF spec + RSVP awareness ──
        rsvp = (row.rsvp_status or "").lower()

        if row.is_cancelled:
            # Cancellation = cooling signal
            edge_weight = -3.0
            sentiment = -0.2
            summary_prefix = "Cancelled"
        elif rsvp == "declined":
            # Attendee explicitly declined — negative signal
            edge_weight = -2.0
            sentiment = -0.15
            summary_prefix = "Declined"
        elif row.is_recurring and row.meeting_type == "one_on_one":
            edge_weight = 12.0  # Recurring weekly 1:1 = strongest signal
            sentiment = 0.3
            summary_prefix = "Recurring 1:1"
        elif rsvp == "tentative":
            # Tentative = half-weight, neutral sentiment
            edge_weight = 4.0
            sentiment = 0.05
            summary_prefix = "Tentative"
        elif rsvp == "needsAction":
            # No RSVP response yet — weak signal
            edge_weight = 3.0
            sentiment = 0.0
            summary_prefix = "Awaiting RSVP"
        else:
            # Accepted / confirmed meeting = 8x a single email
            edge_weight = 8.0
            sentiment = 0.3
            summary_prefix = "Meeting"

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

        # Direction: cancelled/declined = one-directional (they pulled out)
        direction = "bidirectional"
        if row.is_cancelled or rsvp == "declined":
            direction = "inbound"  # Cooling signal initiated by them

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
                    :direction, :subject, :summary,
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
                    sentiment = EXCLUDED.sentiment,
                    direction = EXCLUDED.direction,
                    account_email = EXCLUDED.account_email
            """),
            {
                "id": interaction_id,
                "org_id": org_id,
                "contact_id": str(row.contact_id),
                "gmail_message_id": synthetic_msg_id,
                "calendar_event_id": str(row.event_id),
                "account_email": account_email,
                "direction": direction,
                "subject": row.title or "Meeting",
                "summary": f"{summary_prefix}: {row.title or 'Untitled'}",
                "interaction_at": row.start_time,
                "sentiment": sentiment,
                "weight_score": 0.9 if edge_weight > 0 else 0.3,
                "signal_score": 0.8 if edge_weight > 0 else 0.4,
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


# ─── 4. No-show inference ────────────────────────────────────────────────────

def infer_no_shows(db, org_id: str):
    """
    For past events where the attendee has no email interaction within 24h
    after the meeting end time, mark as probable no-show.

    Updates attended_inferred and attended_confidence on calendar_event_attendees.
    Also transitions upcoming_meetings.status from 'scheduled' to 'completed' or 'no_show'.
    """
    # Step 1: Transition past meetings from 'scheduled' → 'completed'
    db.execute(
        text("""
            UPDATE upcoming_meetings
            SET status = 'completed'
            WHERE org_id = :oid
            AND status = 'scheduled'
            AND start_time < NOW() - INTERVAL '1 hour'
        """),
        {"oid": org_id},
    )

    # Step 2: Find past events (ended 24h+ ago) with resolved attendees
    #         where attended_inferred is still NULL
    candidates = db.execute(
        text("""
            SELECT cea.id AS attendee_id,
                   cea.person_id AS contact_id,
                   ce.end_time,
                   ce.id AS event_id,
                   ce.is_cancelled
            FROM calendar_event_attendees cea
            JOIN calendar_events ce ON ce.id = cea.event_id
            WHERE ce.org_id = :oid
              AND cea.person_id IS NOT NULL
              AND cea.attended_inferred IS NULL
              AND ce.end_time IS NOT NULL
              AND ce.end_time < NOW() - INTERVAL '48 hours'
              AND ce.is_cancelled = FALSE
        """),
        {"oid": org_id},
    ).fetchall()

    if not candidates:
        return 0

    no_show_count = 0
    for row in candidates:
        # Triple-signal attended inference per PDF spec:
        #   (a) Past start time — already filtered in candidate query
        #   (b) No cancellation — already filtered (is_cancelled = FALSE)
        #   (c) Follow-up email within 72h of meeting end

        # Check for email within 48h (strong signal)
        email_within_48h = db.execute(
            text("""
                SELECT 1 FROM interactions
                WHERE contact_id = :cid
                  AND source = 'gmail'
                  AND interaction_at BETWEEN :end_time AND :end_time + INTERVAL '48 hours'
                LIMIT 1
            """),
            {"cid": str(row.contact_id), "end_time": row.end_time},
        ).fetchone()

        # Check for email within 72h (weaker signal — late follow-up)
        email_within_72h = None
        if not email_within_48h:
            email_within_72h = db.execute(
                text("""
                    SELECT 1 FROM interactions
                    WHERE contact_id = :cid
                      AND source = 'gmail'
                      AND interaction_at BETWEEN :end_time + INTERVAL '48 hours'
                                             AND :end_time + INTERVAL '72 hours'
                    LIMIT 1
                """),
                {"cid": str(row.contact_id), "end_time": row.end_time},
            ).fetchone()

        # Score: all 3 signals (past + no cancel + email <48h) = 0.85
        #        past + no cancel + late email (48-72h)         = 0.70
        #        past + no cancel + no email at all             = 0.55 (inferred no-show)
        if email_within_48h:
            attended = True
            confidence = 0.85
        elif email_within_72h:
            attended = True
            confidence = 0.70
        else:
            attended = False
            confidence = 0.55

        db.execute(
            text("""
                UPDATE calendar_event_attendees
                SET attended_inferred = :attended, attended_confidence = :conf
                WHERE id = :aid
            """),
            {"attended": attended, "conf": confidence, "aid": row.attendee_id},
        )

        if not attended:
            no_show_count += 1
            # Update upcoming_meetings status to 'no_show' if exists
            db.execute(
                text("""
                    UPDATE upcoming_meetings
                    SET status = 'no_show'
                    WHERE event_id = :eid AND org_id = :oid
                """),
                {"eid": row.event_id, "oid": org_id},
            )

    logger.info(f"Calendar bridge: inferred {no_show_count} no-shows out of {len(candidates)} past meetings for org={org_id}")
    return no_show_count


# ─── 5. Rescheduling detection ───────────────────────────────────────────────

def detect_rescheduled_events(db, org_id: str):
    """
    Find cancelled events that were rescheduled (a new event was created
    with overlapping attendees within 14 days of the cancelled event).

    Updates rescheduled_count on the new event.
    """
    # Find cancelled events with resolved attendees
    cancelled = db.execute(
        text("""
            SELECT ce.id AS event_id, ce.title, ce.start_time,
                   array_agg(cea.person_id) AS attendee_ids
            FROM calendar_events ce
            JOIN calendar_event_attendees cea ON cea.event_id = ce.id
            WHERE ce.org_id = :oid
              AND ce.is_cancelled = TRUE
              AND cea.person_id IS NOT NULL
              AND ce.start_time > NOW() - INTERVAL '60 days'
            GROUP BY ce.id
        """),
        {"oid": org_id},
    ).fetchall()

    if not cancelled:
        return 0

    rescheduled_count = 0
    for row in cancelled:
        if not row.start_time or not row.attendee_ids:
            continue

        # Look for a non-cancelled event within 14 days with at least one
        # overlapping attendee (likely a reschedule)
        match = db.execute(
            text("""
                SELECT ce.id
                FROM calendar_events ce
                JOIN calendar_event_attendees cea ON cea.event_id = ce.id
                WHERE ce.org_id = :oid
                  AND ce.is_cancelled = FALSE
                  AND ce.id != :cancelled_id
                  AND ce.start_time BETWEEN :start - INTERVAL '14 days'
                                        AND :start + INTERVAL '14 days'
                  AND cea.person_id = ANY(:attendees)
                LIMIT 1
            """),
            {
                "oid": org_id,
                "cancelled_id": row.event_id,
                "start": row.start_time,
                "attendees": row.attendee_ids,
            },
        ).fetchone()

        if match:
            db.execute(
                text("""
                    UPDATE calendar_events
                    SET rescheduled_count = COALESCE(rescheduled_count, 0) + 1
                    WHERE id = :eid
                """),
                {"eid": match.id},
            )
            rescheduled_count += 1

    logger.info(f"Calendar bridge: detected {rescheduled_count} rescheduled events for org={org_id}")
    return rescheduled_count


# ─── 6. Gmail cross-matcher — link emails ±7 days of meeting ─────────────

def cross_match_gmail_calendar(db, org_id: str):
    """
    Find email interactions within ±7 days of a calendar meeting with the same contact.
    Links them by setting linked_calendar_event_id on the email interaction.
    Builds the full arc: email thread → meeting → follow-up email.
    """
    linked_count = db.execute(
        text("""
            UPDATE interactions email_i
            SET calendar_event_id = cal_i.calendar_event_id
            FROM interactions cal_i
            WHERE email_i.org_id = :oid
              AND cal_i.org_id = :oid
              AND email_i.contact_id = cal_i.contact_id
              AND email_i.source = 'gmail'
              AND cal_i.source = 'calendar'
              AND cal_i.calendar_event_id IS NOT NULL
              AND email_i.calendar_event_id IS NULL
              AND email_i.interaction_at BETWEEN cal_i.interaction_at - INTERVAL '7 days'
                                             AND cal_i.interaction_at + INTERVAL '7 days'
        """),
        {"oid": org_id},
    ).rowcount

    logger.info(f"Calendar bridge: cross-matched {linked_count} emails to calendar events for org={org_id}")
    return linked_count


# ─── 7. Follow-up scheduler — 72h post-meeting open loop ─────────────────

def check_meeting_followups(db, org_id: str):
    """
    For completed meetings older than 72h, check if a follow-up email was sent.
    If not → create a P2 insight alerting the user.
    """
    from uuid import uuid4

    # Find meetings that ended 72h+ ago with no follow-up email
    no_followup = db.execute(
        text("""
            SELECT um.id, um.event_id, um.primary_contact_id,
                   ce.title, ce.end_time, c.name
            FROM upcoming_meetings um
            JOIN calendar_events ce ON ce.id = um.event_id
            LEFT JOIN contacts c ON c.id = um.primary_contact_id
            WHERE um.org_id = :oid
              AND um.status = 'completed'
              AND um.follow_up_sent = FALSE
              AND ce.end_time < NOW() - INTERVAL '72 hours'
              AND um.primary_contact_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM interactions i
                  WHERE i.contact_id = um.primary_contact_id
                    AND i.source = 'gmail'
                    AND i.direction = 'outbound'
                    AND i.interaction_at > ce.end_time
                    AND i.interaction_at < ce.end_time + INTERVAL '72 hours'
              )
        """),
        {"oid": org_id},
    ).fetchall()

    insight_count = 0
    for row in no_followup:
        meeting_id, event_id, contact_id, title, end_time, contact_name = row

        # Create insight
        db.execute(
            text("""
                INSERT INTO insights (id, org_id, insight_type, priority, category,
                    title, detail, contact_id, contact_name, metadata, generated_at, expires_at)
                VALUES (:id, :org_id, 'relationship', 'P2', 'no_followup',
                    :title, :detail, :contact_id, :contact_name, :metadata,
                    NOW(), NOW() + INTERVAL '7 days')
                ON CONFLICT DO NOTHING
            """),
            {
                "id": str(uuid4()),
                "org_id": org_id,
                "title": f"No follow-up after meeting with {contact_name or 'contact'}",
                "detail": f"Meeting \"{title or 'Untitled'}\" ended {end_time.strftime('%b %d') if end_time else 'recently'} but no outbound email was sent within 72h. Follow up to close the loop.",
                "contact_id": str(contact_id) if contact_id else None,
                "contact_name": contact_name,
                "metadata": "{}",
            },
        )

        # Mark follow-up as checked (even if not sent — don't re-alert)
        db.execute(
            text("UPDATE upcoming_meetings SET follow_up_due_at = :due WHERE id = :mid"),
            {"due": end_time, "mid": meeting_id},
        )
        insight_count += 1

    logger.info(f"Calendar bridge: found {insight_count} meetings without follow-up for org={org_id}")
    return insight_count


# ─── 8. Co-attendance edges — attendee-to-attendee clustering ──────────────

def create_co_attendance_edges(db, org_id: str):
    """
    For each calendar event with 2+ resolved external attendees,
    create co_attendance rows between every pair.

    Enables community/cluster detection: people who always appear
    in the same meetings form a hidden team or decision group.

    Uses contact_a_id < contact_b_id ordering for consistent dedup.
    """
    # Find events with 2+ resolved external attendees
    events = db.execute(
        text("""
            SELECT ce.id, ce.title, ce.start_time,
                   ARRAY_AGG(cea.person_id ORDER BY cea.person_id) as attendee_ids
            FROM calendar_events ce
            JOIN calendar_event_attendees cea ON cea.event_id = ce.id
            WHERE ce.org_id = :oid
            AND cea.person_id IS NOT NULL
            AND cea.is_external = TRUE
            GROUP BY ce.id, ce.title, ce.start_time
            HAVING COUNT(DISTINCT cea.person_id) >= 2
        """),
        {"oid": org_id},
    ).fetchall()

    edge_count = 0
    for event in events:
        event_id, title, start_time, attendee_ids = event
        # Deduplicate attendee list
        unique_ids = sorted(set(str(a) for a in attendee_ids))

        # Create edges for every pair (N*(N-1)/2)
        for i in range(len(unique_ids)):
            for j in range(i + 1, len(unique_ids)):
                db.execute(
                    text("""
                        INSERT INTO co_attendance
                            (org_id, contact_a_id, contact_b_id,
                             calendar_event_id, event_title, event_at)
                        VALUES (:oid, :a, :b, :eid, :title, :at)
                        ON CONFLICT (contact_a_id, contact_b_id, calendar_event_id)
                        DO NOTHING
                    """),
                    {
                        "oid": org_id,
                        "a": unique_ids[i],
                        "b": unique_ids[j],
                        "eid": event_id,
                        "title": title,
                        "at": start_time,
                    },
                )
                edge_count += 1

    logger.info(f"Calendar bridge: created {edge_count} co-attendance edges for org={org_id}")
    return edge_count
