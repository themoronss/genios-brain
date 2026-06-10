"""Cross-tool signal detectors — Gmail vs Calendar divergence analysis."""

from sqlalchemy import text
from typing import List, Dict


# ─── Stage level mapping for contradiction detection ─────────────────────────

_STAGE_LEVELS = {
    "ACTIVE": 5,
    "WARM": 4,
    "NEEDS_ATTENTION": 3,
    "DORMANT": 2,
    "COLD": 1,
    "AT_RISK": 0,
}


def _detect_email_calendar_divergence(db, org_id: str) -> List[Dict]:
    """
    Detect contacts where email and calendar signals diverge.

    Patterns:
      TRANSACTIONAL   — email warm + calendar rare (HIGH RISK)
      ASYNC_PREFERENCE — email cold + calendar frequent (LOW RISK)
      COMMITMENT_AT_RISK — open commitment + no calendar event (HIGH RISK)
      IMPLEMENTER     — attends meetings but never organizes (MEDIUM RISK)
    """
    # Get per-contact email vs calendar counts (60-day window)
    rows = db.execute(
        text("""
            SELECT
                c.id, c.name, c.company, c.entity_type,
                COUNT(*) FILTER (WHERE i.source = 'gmail'
                    AND i.interaction_at > NOW() - INTERVAL '60 days') as email_60d,
                COUNT(*) FILTER (WHERE i.source = 'calendar'
                    AND i.interaction_at > NOW() - INTERVAL '60 days') as meeting_60d
            FROM contacts c
            JOIN interactions i ON i.contact_id = c.id AND i.org_id = c.org_id
            WHERE c.org_id = :org_id
            AND c.is_archived = FALSE
            AND i.interaction_at > NOW() - INTERVAL '90 days'
            GROUP BY c.id, c.name, c.company, c.entity_type
            HAVING COUNT(DISTINCT i.source) >= 1
        """),
        {"org_id": org_id},
    ).fetchall()

    insights = []

    for r in rows:
        cid, name, company, entity_type, email_60d, meeting_60d = r

        # TRANSACTIONAL: lots of emails, zero meetings
        if email_60d >= 5 and meeting_60d == 0:
            insights.append({
                "insight_type": "relationship",
                "priority": "P2",
                "category": "signal_divergence",
                "title": f"{name} — transactional relationship (email-only, no meetings)",
                "detail": (
                    f"{name} from {company or 'Unknown'} has {email_60d} emails "
                    f"but 0 meetings in 60 days. Relationship may be transactional, "
                    f"not strategic. Consider scheduling a meeting."
                ),
                "contact_id": str(cid),
                "contact_name": name,
                "metadata": {
                    "pattern": "TRANSACTIONAL",
                    "risk_level": "HIGH",
                    "email_60d": email_60d,
                    "meeting_60d": meeting_60d,
                },
            })

        # ASYNC_PREFERENCE: few emails, frequent meetings
        elif email_60d <= 2 and meeting_60d >= 3:
            insights.append({
                "insight_type": "relationship",
                "priority": "P3",
                "category": "signal_divergence",
                "title": f"{name} — prefers meetings over email",
                "detail": (
                    f"{name} from {company or 'Unknown'} has {meeting_60d} meetings "
                    f"but only {email_60d} emails in 60 days. They prefer synchronous "
                    f"communication — lean into meetings."
                ),
                "contact_id": str(cid),
                "contact_name": name,
                "metadata": {
                    "pattern": "ASYNC_PREFERENCE",
                    "risk_level": "LOW",
                    "email_60d": email_60d,
                    "meeting_60d": meeting_60d,
                },
            })

    # COMMITMENT_AT_RISK: open commitment with no linked calendar event
    commitment_rows = db.execute(
        text("""
            SELECT cm.contact_id, c.name, c.company, cm.commit_text, cm.due_date
            FROM commitments cm
            JOIN contacts c ON c.id = cm.contact_id
            WHERE cm.org_id = :org_id
            AND cm.status = 'OPEN'
            AND cm.created_at > NOW() - INTERVAL '30 days'
            AND NOT EXISTS (
                SELECT 1 FROM interactions i
                WHERE i.contact_id = cm.contact_id
                AND i.source = 'calendar'
                AND i.interaction_at > cm.created_at
                AND i.interaction_at < COALESCE(cm.due_date, NOW() + INTERVAL '30 days')
            )
        """),
        {"org_id": org_id},
    ).fetchall()

    for r in commitment_rows:
        cid, name, company, commit_text, due_date = r
        insights.append({
            "insight_type": "relationship",
            "priority": "P1",
            "category": "commitment_at_risk",
            "title": f"{name} — commitment made but no meeting scheduled",
            "detail": (
                f'"{commit_text[:80]}..." was committed by {name} from '
                f"{company or 'Unknown'} but no calendar event exists to "
                f"follow through. High risk of drop-off."
            ),
            "contact_id": str(cid),
            "contact_name": name,
            "metadata": {
                "pattern": "COMMITMENT_AT_RISK",
                "risk_level": "HIGH",
                "commitment": commit_text[:120],
                "due_date": due_date.isoformat() if due_date else None,
            },
        })

    # IMPLEMENTER: attends meetings but never organizes (90-day window)
    implementer_rows = db.execute(
        text("""
            SELECT
                cea.person_id, c.name, c.company,
                COUNT(*) as total_attended,
                COUNT(*) FILTER (WHERE cea.is_organizer = TRUE) as organized
            FROM calendar_event_attendees cea
            JOIN contacts c ON c.id = cea.person_id
            JOIN calendar_events ce ON ce.id = cea.event_id
            WHERE ce.org_id = :org_id
            AND ce.start_time > NOW() - INTERVAL '90 days'
            AND cea.person_id IS NOT NULL
            AND c.is_archived = FALSE
            GROUP BY cea.person_id, c.name, c.company
            HAVING COUNT(*) >= 3
            AND COUNT(*) FILTER (WHERE cea.is_organizer = TRUE) = 0
        """),
        {"org_id": org_id},
    ).fetchall()

    for r in implementer_rows:
        cid, name, company, total_attended, _ = r
        insights.append({
            "insight_type": "relationship",
            "priority": "P2",
            "category": "authority_signal",
            "title": f"{name} — always invited, never organizes ({total_attended} meetings)",
            "detail": (
                f"{name} from {company or 'Unknown'} attended {total_attended} meetings "
                f"in 90 days but organized none. Likely an implementer, not a "
                f"decision-maker. Adjust authority weight accordingly."
            ),
            "contact_id": str(cid),
            "contact_name": name,
            "metadata": {
                "pattern": "IMPLEMENTER",
                "risk_level": "MEDIUM",
                "total_attended": total_attended,
                "organized": 0,
            },
        })

    return insights


def _detect_stage_contradiction(db, org_id: str) -> List[Dict]:
    """
    Detect contacts where gmail-only stage contradicts calendar-only stage.

    Computes what stage each tool would assign independently, then flags
    contacts where they disagree by 2+ levels.
    """
    rows = db.execute(
        text("""
            WITH gmail_signal AS (
                SELECT
                    contact_id,
                    MAX(interaction_at) as last_email,
                    AVG(sentiment) as avg_sentiment,
                    COUNT(*) as email_count
                FROM interactions
                WHERE org_id = :org_id AND source = 'gmail'
                AND interaction_at > NOW() - INTERVAL '90 days'
                GROUP BY contact_id
            ),
            calendar_signal AS (
                SELECT
                    contact_id,
                    MAX(interaction_at) as last_meeting,
                    AVG(sentiment) as avg_sentiment,
                    COUNT(*) as meeting_count,
                    COUNT(*) FILTER (WHERE rsvp_status = 'declined' OR sentiment < 0) as negative_count
                FROM interactions
                WHERE org_id = :org_id AND source = 'calendar'
                AND interaction_at > NOW() - INTERVAL '90 days'
                GROUP BY contact_id
            )
            SELECT
                c.id, c.name, c.company, c.relationship_stage,
                g.last_email, g.avg_sentiment as gmail_sentiment, g.email_count,
                cal.last_meeting, cal.avg_sentiment as cal_sentiment,
                cal.meeting_count, cal.negative_count
            FROM contacts c
            JOIN gmail_signal g ON g.contact_id = c.id
            JOIN calendar_signal cal ON cal.contact_id = c.id
            WHERE c.org_id = :org_id
            AND c.is_archived = FALSE
        """),
        {"org_id": org_id},
    ).fetchall()

    insights = []

    for r in rows:
        (cid, name, company, current_stage,
         last_email, gmail_sentiment, email_count,
         last_meeting, cal_sentiment, meeting_count, negative_count) = r

        # Compute gmail-only stage
        gmail_stage = _infer_stage_from_signal(
            last_email, float(gmail_sentiment or 0)
        )
        # Compute calendar-only stage
        cal_stage = _infer_stage_from_signal(
            last_meeting, float(cal_sentiment or 0)
        )

        gmail_level = _STAGE_LEVELS.get(gmail_stage, 1)
        cal_level = _STAGE_LEVELS.get(cal_stage, 1)

        # Flag if they differ by 2+ levels
        if abs(gmail_level - cal_level) >= 2:
            insights.append({
                "insight_type": "relationship",
                "priority": "P1",
                "category": "stage_contradiction",
                "title": (
                    f"{name} — conflicting signals "
                    f"(email: {gmail_stage}, calendar: {cal_stage})"
                ),
                "detail": (
                    f"{name} from {company or 'Unknown'}: "
                    f"Email suggests {gmail_stage} ({email_count} emails, "
                    f"sentiment {float(gmail_sentiment or 0):.2f}) but "
                    f"Calendar suggests {cal_stage} ({meeting_count} meetings, "
                    f"sentiment {float(cal_sentiment or 0):.2f}). "
                    f"Investigate which signal is accurate."
                ),
                "contact_id": str(cid),
                "contact_name": name,
                "metadata": {
                    "gmail_stage": gmail_stage,
                    "calendar_stage": cal_stage,
                    "current_stage": current_stage,
                    "gmail_sentiment": float(gmail_sentiment or 0),
                    "cal_sentiment": float(cal_sentiment or 0),
                    "email_count": email_count,
                    "meeting_count": meeting_count,
                },
            })

    return insights


def _infer_stage_from_signal(last_interaction_at, sentiment: float) -> str:
    """Infer what stage a single source would assign, using base rules only."""
    from datetime import datetime, timezone

    if last_interaction_at is None:
        return "COLD"

    now = datetime.now(timezone.utc)
    if last_interaction_at.tzinfo is None:
        last_interaction_at = last_interaction_at.replace(tzinfo=timezone.utc)

    days_since = (now - last_interaction_at).days

    if sentiment < -0.3:
        return "AT_RISK"
    if days_since < 14 and sentiment > 0:
        return "ACTIVE"
    if days_since < 30:
        return "WARM"
    if days_since <= 60:
        return "NEEDS_ATTENTION"
    return "COLD"


CROSS_TOOL_DETECTORS = [
    _detect_email_calendar_divergence,
    _detect_stage_contradiction,
]
