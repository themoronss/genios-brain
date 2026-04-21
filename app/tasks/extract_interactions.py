"""
Async batch LLM extraction — Phase 1.1 + 1.2.

Picks up interaction rows with extraction_status='pending', runs LLM
extraction in batches of BATCH_SIZE, updates the rows with extracted
data (summary, sentiment, topics, commitments, intent).

Run as a Celery task after each Gmail sync, or on a 5-minute schedule.

Principle P1: raw rows stay in the DB regardless of extraction outcome.
A 'failed' extraction_status still has a visible row — never deleted.
"""
import json
import logging
import os
import time
from datetime import datetime, timezone

from sqlalchemy import text

from app.database import SessionLocal
from app.ingestion.entity_extractor import extract_email_intelligence
from app.ingestion.graph_builder import upsert_contact

logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv("GENIOS_EXTRACTION_BATCH_SIZE", "10"))
MAX_PER_RUN = int(os.getenv("GENIOS_EXTRACTION_MAX_PER_RUN", "100"))


def run_pending_extractions(org_id: str = None):
    """
    Process pending interaction rows through LLM extraction.

    Args:
        org_id: Optional — limit to a single org. If None, processes all orgs.
    """
    db = SessionLocal()
    try:
        where = "i.extraction_status = 'pending'"
        params = {"limit": MAX_PER_RUN}
        if org_id:
            where += " AND i.org_id = :org_id"
            params["org_id"] = org_id

        rows = db.execute(
            text(f"""
                SELECT i.id, i.org_id, i.contact_id, i.subject, i.raw_body,
                       i.direction, i.gmail_message_id,
                       c.name AS contact_name, c.email AS contact_email
                FROM interactions i
                JOIN contacts c ON i.contact_id = c.id
                WHERE {where}
                ORDER BY i.interaction_at DESC
                LIMIT :limit
            """),
            params,
        ).fetchall()

        if not rows:
            logger.info("No pending extractions.")
            return 0

        logger.info(f"Processing {len(rows)} pending extractions...")
        extracted = 0
        failed = 0

        for row in rows:
            try:
                subject = row.subject or ""
                body = row.raw_body or ""
                if not body.strip():
                    # No body to extract — mark as skipped
                    db.execute(
                        text("UPDATE interactions SET extraction_status = 'skipped' WHERE id = :id"),
                        {"id": str(row.id)},
                    )
                    db.commit()
                    continue

                intelligence = extract_email_intelligence(
                    subject,
                    body,
                    sender_name=row.contact_name or "",
                    is_reply="re:" in subject.lower() or "fwd:" in subject.lower(),
                    org_id=str(row.org_id),
                )

                # Update the interaction with extracted data
                db.execute(
                    text("""
                        UPDATE interactions
                        SET summary = :summary,
                            sentiment = :sentiment,
                            intent = :intent,
                            topics = :topics,
                            interaction_type = :interaction_type,
                            extraction_status = 'extracted',
                            raw_body = NULL
                        WHERE id = :id
                    """),
                    {
                        "id": str(row.id),
                        "summary": (intelligence.get("summary") or subject)[:500],
                        "sentiment": intelligence.get("sentiment", 0.0),
                        "intent": intelligence.get("intent", "other"),
                        "topics": intelligence.get("topics", []),
                        "interaction_type": intelligence.get("interaction_type", "email_one_way"),
                    },
                )

                # Update contact with role if LLM extracted it
                contact_role = intelligence.get("contact_role")
                if contact_role:
                    upsert_contact(
                        db, str(row.org_id), row.contact_email, row.contact_name,
                        entity_type=contact_role,
                        thread_topics=intelligence.get("topics", []),
                    )

                # Store commitments
                for commitment in intelligence.get("commitments", []):
                    try:
                        from app.ingestion.graph_builder import _store_commitment
                        _store_commitment(
                            db, str(row.org_id), str(row.contact_id),
                            commitment, str(row.gmail_message_id),
                        )
                    except Exception:
                        pass  # Don't fail the whole extraction for one bad commitment

                # Update what_works / what_to_avoid on contact
                what_works = intelligence.get("what_works")
                what_to_avoid = intelligence.get("what_to_avoid")
                if what_works or what_to_avoid:
                    comm_style = json.dumps({
                        "what_works": what_works,
                        "what_to_avoid": what_to_avoid,
                    })
                    db.execute(
                        text("""
                            UPDATE interactions
                            SET comm_style_signals = :css
                            WHERE id = :id
                        """),
                        {"id": str(row.id), "css": comm_style},
                    )

                db.commit()
                extracted += 1

                # Rate limiting (Groq: 30 req/min → 2s between calls)
                time.sleep(2)

            except Exception as e:
                logger.warning(f"Extraction failed for interaction {row.id}: {e}")
                try:
                    db.rollback()
                    db.execute(
                        text("""
                            UPDATE interactions
                            SET extraction_status = 'failed'
                            WHERE id = :id
                        """),
                        {"id": str(row.id)},
                    )
                    db.commit()
                except Exception:
                    db.rollback()
                failed += 1

        logger.info(f"Extraction complete: {extracted} extracted, {failed} failed, {len(rows) - extracted - failed} skipped")
        return extracted

    finally:
        db.close()
