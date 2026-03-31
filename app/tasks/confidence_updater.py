"""
Confidence Score Updater — Phase 9.2
Nightly job: applies unapplied context_outcomes to contacts.confidence_score.
Only runs for Startup orgs (active learning).
"""

from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def apply_outcome_confidence_deltas(db, org_id: str = None) -> int:
    """
    Apply unapplied context_outcomes to contacts.confidence_score for Startup orgs.
    Returns total number of contacts updated.
    """
    try:
        # Scope to Startup orgs only — always enforce tier regardless of org_id scope
        if org_id:
            org_filter = "AND co.org_id = :org_id AND o.plan_tier = 'startup' AND o.plan_expires_at > NOW()"
            params: dict = {"org_id": org_id}
        else:
            org_filter = "AND o.plan_tier = 'startup' AND o.plan_expires_at > NOW()"
            params = {}

        # Fetch unapplied outcomes with their linked contact (via context_calls)
        rows = db.execute(
            text(f"""
                SELECT
                    co.id AS outcome_id,
                    co.org_id,
                    co.context_id,
                    co.confidence_delta,
                    c.id AS contact_id
                FROM context_outcomes co
                JOIN orgs o ON o.id = co.org_id
                LEFT JOIN context_calls cc ON cc.id = co.context_id AND cc.org_id = co.org_id
                LEFT JOIN contacts c ON c.name = cc.entity_name AND c.org_id = co.org_id
                WHERE co.applied = FALSE
                  AND co.confidence_delta != 0.0
                  {org_filter}
                ORDER BY co.created_at ASC
                LIMIT 500
            """),
            params,
        ).fetchall()

        if not rows:
            return 0

        updated = 0
        for row in rows:
            outcome_id, oid, context_id, delta, contact_id = row
            try:
                if contact_id:
                    db.execute(
                        text("""
                            UPDATE contacts
                            SET confidence_score = GREATEST(0.0, LEAST(1.0,
                                COALESCE(confidence_score, 0.5) + :delta))
                            WHERE id = :contact_id AND org_id = :org_id
                        """),
                        {"delta": float(delta), "contact_id": str(contact_id), "org_id": str(oid)},
                    )
                    updated += 1

                # Mark applied regardless (even if contact lookup failed — avoids infinite retry)
                db.execute(
                    text("UPDATE context_outcomes SET applied = TRUE WHERE id = :oid"),
                    {"oid": str(outcome_id)},
                )
            except Exception as e:
                logger.warning(f"Failed to apply outcome {outcome_id}: {e}")
                db.rollback()
                continue

        db.commit()
        return updated

    except Exception as e:
        logger.error(f"Confidence updater failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0
