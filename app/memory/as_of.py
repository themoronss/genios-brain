"""
Bitemporal "as-of" reconstruction (Phase 2).

Given an entity + timestamp, reconstruct the state we had on that date.

This is a read-only projection from event_log. It does NOT rewind contacts/
interactions rows (those will be filtered by valid_from/valid_to once the
projector back-fills them). For now we return:

  - interactions with valid_from <= as_of   (if bitemporal columns populated)
  - otherwise: raw events from event_log for that entity window

Callers should treat the response as a best-effort historical snapshot.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _parse_iso(ts: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def build_as_of_bundle(
    db: Session,
    org_id: str,
    entity: str,
    as_of: str,
) -> dict:
    """
    Lightweight historical context. Falls back gracefully when events for the
    exact entity cannot be joined (returns 'insufficient_history').
    """
    ts = _parse_iso(as_of)
    if not ts:
        return {"error": "INVALID_AS_OF"}

    entity_norm = entity.lower().strip()

    # 1) Try to find contact identity as it was valid at `ts`.
    contact = db.execute(
        text("""
            SELECT id, name, email, company, relationship_stage, sentiment_trend,
                   interaction_count, valid_from, valid_to
            FROM contacts
            WHERE org_id = :org
              AND LOWER(TRIM(name)) = :entity
              AND (valid_from IS NULL OR valid_from <= :ts)
              AND (valid_to   IS NULL OR valid_to   > :ts)
            LIMIT 1
        """),
        {"org": org_id, "entity": entity_norm, "ts": ts},
    ).fetchone()

    # 2) Interactions observed up to `ts`.
    # Note: interactions row has no sender email column; we match by contact_id
    # (already resolved from the bitemporal contacts lookup) or account_email.
    interactions = db.execute(
        text("""
            SELECT id, direction, subject, interaction_at AS sent_at,
                   sentiment, topics
            FROM interactions
            WHERE org_id = :org
              AND (contact_id = :cid OR LOWER(account_email) LIKE :email_like)
              AND interaction_at <= :ts
              AND (valid_to IS NULL OR valid_to > :ts)
            ORDER BY interaction_at DESC
            LIMIT 20
        """),
        {
            "org": org_id,
            "cid": str(contact.id) if contact else "00000000-0000-0000-0000-000000000000",
            "email_like": f"%{entity_norm}%",
            "ts": ts,
        },
    ).fetchall()

    # 3) Raw events for the same window — useful when contacts row didn't exist yet.
    events = db.execute(
        text("""
            SELECT source, verb, actor, observed_at, payload
            FROM event_log
            WHERE org_id = :org
              AND observed_at <= :ts
              AND (actor ILIKE :entity_like OR payload::text ILIKE :entity_like)
            ORDER BY observed_at DESC
            LIMIT 20
        """),
        {"org": org_id, "ts": ts, "entity_like": f"%{entity_norm}%"},
    ).fetchall()

    if not contact and not interactions and not events:
        return {
            "error": "NO_HISTORY_AT_AS_OF",
            "as_of": ts.isoformat(),
            "entity": entity,
        }

    return {
        "as_of": ts.isoformat(),
        "entity": entity,
        "entity_snapshot": (
            {
                "name": contact.name,
                "email": contact.email,
                "company": contact.company,
                "relationship_stage": contact.relationship_stage,
                "sentiment_trend": contact.sentiment_trend,
                "interaction_count": contact.interaction_count,
                "valid_from": contact.valid_from.isoformat() if contact.valid_from else None,
            }
            if contact
            else None
        ),
        "interactions": [
            {
                "id": str(r.id),
                "direction": r.direction,
                "subject": r.subject,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "sentiment": r.sentiment,
                "topics": r.topics,
            }
            for r in interactions
        ],
        "events": [
            {
                "source": e.source,
                "verb": e.verb,
                "actor": e.actor,
                "observed_at": e.observed_at.isoformat() if e.observed_at else None,
                "payload": e.payload,
            }
            for e in events
        ],
        "note": (
            "Historical snapshot reconstructed from event_log + bitemporal tables. "
            "Populated from the moment Phase 2 migrations were applied; rows before "
            "that date may only show source events, not derived scores."
        ),
    }
