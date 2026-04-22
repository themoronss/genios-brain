"""
Indirect relationship inference — finds A->B->C paths and warm intro opportunities.
Runs during nightly refresh.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def compute_inferred_edges(db: Session, org_id: str):
    """
    Find contacts that are indirectly connected through shared email threads (CC).
    Two contacts who appear on the same CC'd email are likely to know each other.
    Store these as inferred relationships with lower confidence.
    """
    try:
        # Find contact pairs connected through shared email CC threads OR calendar co-attendance
        inferred = db.execute(
            text("""
                WITH co_occurrence AS (
                    -- Email CC co-occurrence
                    SELECT i1.contact_id as contact_a, i2.contact_id as contact_b, COUNT(*) as shared_threads
                    FROM interactions i1
                    JOIN interactions i2 ON i1.gmail_message_id = i2.gmail_message_id
                        AND i1.contact_id < i2.contact_id
                        AND i1.org_id = i2.org_id
                    WHERE i1.org_id = :org_id AND i1.gmail_message_id IS NOT NULL
                    GROUP BY i1.contact_id, i2.contact_id

                    UNION ALL

                    -- Calendar co-attendee
                    SELECT i1.contact_id as contact_a, i2.contact_id as contact_b, COUNT(*) as shared_threads
                    FROM interactions i1
                    JOIN interactions i2 ON i1.calendar_event_id = i2.calendar_event_id
                        AND i1.contact_id < i2.contact_id
                        AND i1.org_id = i2.org_id
                    WHERE i1.org_id = :org_id AND i1.calendar_event_id IS NOT NULL
                    GROUP BY i1.contact_id, i2.contact_id
                ),
                cc_pairs AS (
                    SELECT contact_a, contact_b, SUM(shared_threads) as shared_threads
                    FROM co_occurrence
                    GROUP BY contact_a, contact_b
                )
                SELECT
                    cp.contact_a, cp.contact_b, cp.shared_threads,
                    ca.name as name_a, cb.name as name_b
                FROM cc_pairs cp
                JOIN contacts ca ON cp.contact_a = ca.id
                JOIN contacts cb ON cp.contact_b = cb.id
                WHERE cp.shared_threads >= 1
            """),
            {"org_id": org_id},
        ).fetchall()

        count = 0
        for row in inferred:
            contact_a, contact_b, shared_count, name_a, name_b = row
            confidence = min(0.3 + (shared_count * 0.1), 0.7)  # More shared threads = higher confidence

            # Log as activity for visibility
            if shared_count >= 2:  # Only log significant connections
                db.execute(
                    text("""
                        INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
                        VALUES (gen_random_uuid(), :org_id, 'inferred_connection',
                                :data, NOW())
                        ON CONFLICT DO NOTHING
                    """),
                    {
                        "org_id": org_id,
                        "data": f"{name_a} and {name_b} appear connected ({shared_count} shared threads, confidence: {confidence:.0%})",
                    },
                )
                count += 1

        db.commit()
        logger.info(f"Computed {count} inferred edges for org {org_id}")
        return count

    except Exception as e:
        logger.error(f"Inferred edge computation failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0


def compute_mentioned_in_edges(db: Session, org_id: str):
    """
    Create MENTIONED_IN edges when a contact's name appears in an email
    sent to/from a different contact. Per Graph Enrichment spec:
    cross-category M2M relationships discovered from mentions.
    """
    try:
        # Get contacts with names long enough to match reliably (>= 4 chars)
        contacts = db.execute(
            text("""
                SELECT id, LOWER(name) as name, entity_type
                FROM contacts
                WHERE org_id = :org_id AND name IS NOT NULL AND LENGTH(name) >= 4
            """),
            {"org_id": org_id},
        ).fetchall()

        if not contacts:
            return 0

        contact_map = {str(c.id): {"name": c.name, "entity_type": c.entity_type} for c in contacts}
        count = 0

        # For each interaction that has mentioned_people[], resolve to contact IDs
        mentions = db.execute(
            text("""
                SELECT i.id, i.contact_id, i.mentioned_people
                FROM interactions i
                WHERE i.org_id = :org_id
                  AND i.mentioned_people IS NOT NULL
                  AND array_length(i.mentioned_people, 1) > 0
                  AND NOT EXISTS (
                      SELECT 1 FROM activity_log al
                      WHERE al.org_id = :org_id
                        AND al.event_type = 'mentioned_in_processed'
                        AND al.event_data::text LIKE '%' || i.id::text || '%'
                  )
                LIMIT 500
            """),
            {"org_id": org_id},
        ).fetchall()

        for m in mentions:
            interaction_id = str(m.id)
            source_contact_id = str(m.contact_id)
            mentioned_names = m.mentioned_people or []

            for mentioned_name in mentioned_names:
                mentioned_lower = mentioned_name.lower().strip()
                if len(mentioned_lower) < 4:
                    continue

                # Find matching contact by name
                for cid, cinfo in contact_map.items():
                    if cid == source_contact_id:
                        continue
                    if mentioned_lower in cinfo["name"] or cinfo["name"] in mentioned_lower:
                        # Log MENTIONED_IN edge as activity
                        source_name = contact_map.get(source_contact_id, {}).get("name", "unknown")
                        db.execute(
                            text("""
                                INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
                                VALUES (gen_random_uuid(), :org_id, 'mentioned_in',
                                        :data, NOW())
                                ON CONFLICT DO NOTHING
                            """),
                            {
                                "org_id": org_id,
                                "data": f"{cinfo['name']} mentioned in email with {source_name} (interaction: {interaction_id})",
                            },
                        )
                        count += 1
                        break  # One match per mentioned name is enough

            # Mark interaction as processed for mention detection
            db.execute(
                text("""
                    INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
                    VALUES (gen_random_uuid(), :org_id, 'mentioned_in_processed', :data, NOW())
                    ON CONFLICT DO NOTHING
                """),
                {"org_id": org_id, "data": interaction_id},
            )

        db.commit()
        logger.info(f"Computed {count} MENTIONED_IN edges for org {org_id}")
        return count

    except Exception as e:
        logger.error(f"MENTIONED_IN edge computation failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0


def find_warm_intro_path(db: Session, org_id: str, target_contact_id: str):
    """
    Given a target contact, find if any of the user's ACTIVE/WARM contacts
    are connected to the target through shared email threads.
    Returns a list of potential introducers.
    """
    try:
        results = db.execute(
            text("""
                WITH shared_threads AS (
                    SELECT DISTINCT
                        i1.contact_id as introducer_id,
                        COUNT(*) as shared_count
                    FROM interactions i1
                    JOIN interactions i2 ON i1.gmail_message_id = i2.gmail_message_id
                        AND i1.contact_id != i2.contact_id
                        AND i1.org_id = i2.org_id
                    WHERE i2.contact_id = :target_id
                        AND i1.org_id = :org_id
                        AND i1.gmail_message_id IS NOT NULL
                        AND i1.contact_id != :target_id
                    GROUP BY i1.contact_id
                )
                SELECT
                    c.id, c.name, c.company, c.relationship_stage,
                    c.sentiment_avg, st.shared_count
                FROM shared_threads st
                JOIN contacts c ON st.introducer_id = c.id
                WHERE c.relationship_stage IN ('ACTIVE', 'WARM')
                ORDER BY
                    CASE c.relationship_stage WHEN 'ACTIVE' THEN 1 WHEN 'WARM' THEN 2 ELSE 3 END,
                    st.shared_count DESC
                LIMIT 5
            """),
            {"org_id": org_id, "target_id": target_contact_id},
        ).fetchall()

        return [
            {
                "id": str(r[0]),
                "name": r[1],
                "company": r[2],
                "relationship_stage": r[3],
                "sentiment": float(r[4]) if r[4] else 0,
                "shared_threads": r[5],
                "confidence": min(0.3 + (r[5] * 0.1), 0.7),
            }
            for r in results
        ]

    except Exception as e:
        logger.error(f"Warm intro path search failed: {e}")
        return []
