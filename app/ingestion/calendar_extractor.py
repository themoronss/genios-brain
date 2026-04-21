"""
Calendar Agenda Extractor — LLM-based extraction of topics and commitments
from calendar event descriptions.

Only runs on events with description > 50 chars. All LLM traffic goes through
the unified LLMClient (Groq primary, Gemini fallback, cost logged).
"""

import json
import logging
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.llm import llm_client

logger = logging.getLogger(__name__)


def _parse_result(result_text: str) -> dict:
    """Strip markdown code fences and parse JSON."""
    result_text = result_text.strip()
    if result_text.startswith("```"):
        result_text = result_text.split("```")[1]
        if result_text.startswith("json"):
            result_text = result_text[4:]
    return json.loads(result_text.strip())


def extract_agenda_from_events(db: Session, org_id: str) -> int:
    """
    Find calendar events with meaningful descriptions (>50 chars) that haven't
    been extracted yet. Run LLM to extract meeting_type, topics, and commitments.

    Returns count of events processed.
    """
    events = db.execute(
        text("""
            SELECT id, title, organizer_email, meeting_type,
                   raw_event::text
            FROM calendar_events
            WHERE org_id = :oid
              AND topics_extracted = '[]'::jsonb
              AND raw_event IS NOT NULL
              AND LENGTH(COALESCE(
                  raw_event::json->>'description', ''
              )) > 50
            LIMIT 20
        """),
        {"oid": org_id},
    ).fetchall()

    if not events:
        return 0

    processed = 0

    for row in events:
        event_id = row.id
        title = row.title or ""
        raw = json.loads(row.raw_event) if row.raw_event else {}
        description = raw.get("description", "")

        if not description or len(description.strip()) < 50:
            continue

        prompt = f"""Extract meeting intelligence from this calendar event.

Title: {title}
Description: {description[:2000]}

Return ONLY valid JSON:
{{
  "meeting_type": "one of: intro | demo | review | board | standup | planning | other",
  "topics": ["topic1", "topic2"],
  "commitments": [
    {{"text": "what was committed", "owner": "them or us", "due_signal": "date or null"}}
  ]
}}

If no commitments are found, return empty array. Max 5 topics, max 5 commitments.
"""

        try:
            result_text = llm_client.call(
                org_id=org_id, purpose="calendar_extract",
                messages=[
                    {"role": "system", "content": "You are a precise meeting intelligence extraction assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1, max_tokens=500,
            )
            result = _parse_result(result_text)

            topics = result.get("topics", [])[:5]
            commitments = result.get("commitments", [])[:5]
            _VALID_MEETING_TYPES = {"internal", "sales", "investor", "one_on_one", "group", "unknown"}
            _LLM_TYPE_MAP = {
                "intro": "sales", "demo": "sales", "review": "internal",
                "board": "investor", "standup": "internal", "planning": "internal",
                "other": "unknown",
            }
            raw_type = result.get("meeting_type", "")
            if raw_type in _VALID_MEETING_TYPES:
                meeting_type = raw_type
            else:
                meeting_type = _LLM_TYPE_MAP.get(raw_type, row.meeting_type or "unknown")

            db.execute(
                text("""
                    UPDATE calendar_events
                    SET topics_extracted = :topics,
                        commitments_extracted = :commitments,
                        meeting_type = :meeting_type
                    WHERE id = :eid
                """),
                {
                    "eid": event_id,
                    "topics": json.dumps(topics),
                    "commitments": json.dumps(commitments),
                    "meeting_type": meeting_type,
                },
            )

            for c in commitments:
                _store_calendar_commitment(db, org_id, event_id, c)

            processed += 1

        except Exception as e:
            logger.warning(f"Calendar extractor: failed for event {event_id}: {e}")
            continue

    db.commit()
    logger.info(f"Calendar extractor: processed {processed}/{len(events)} events for org={org_id}")
    return processed


def _store_calendar_commitment(db, org_id: str, event_id, commitment: dict):
    """Store an extracted calendar commitment in the commitments table."""
    text_val = str(commitment.get("text", ""))[:200]
    if not text_val:
        return

    owner = commitment.get("owner", "them")
    due_signal = commitment.get("due_signal")

    contact_row = db.execute(
        text("""
            SELECT person_id FROM calendar_event_attendees
            WHERE event_id = :eid AND person_id IS NOT NULL
            LIMIT 1
        """),
        {"eid": event_id},
    ).fetchone()

    contact_id = str(contact_row.person_id) if contact_row else None

    db.execute(
        text("""
            INSERT INTO commitments (id, org_id, contact_id, text, owner, status, source, confidence, due_signal)
            VALUES (:id, :org_id, :contact_id, :text, :owner, 'OPEN', 'calendar', 0.7, :due_signal)
            ON CONFLICT DO NOTHING
        """),
        {
            "id": str(uuid4()),
            "org_id": org_id,
            "contact_id": contact_id,
            "text": text_val,
            "owner": owner,
            "due_signal": due_signal,
        },
    )
