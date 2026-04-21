"""GDPR deletion cascade (Phase 4.11).

Removes every trace of one subject from the system:
  - facts, recommendations, interactions, contact embeddings
  - retrieval entries in Redis (best-effort)
  - delivery_attempts for that subject

Usage:
    python scripts/gdpr_delete.py --org <uuid> --entity <contact_id> [--dry-run]

Keeps an anonymized audit entry in `activity_log` so we can prove the action
without retaining PII.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine
from app.redis_client import redis_client

logger = logging.getLogger("gdpr_delete")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


DELETE_QUERIES = [
    ("contact_facts",       "DELETE FROM contact_facts WHERE org_id = :org AND contact_id = :cid"),
    ("interactions",        "DELETE FROM interactions WHERE org_id = :org AND contact_id = :cid"),
    ("commitments",         "DELETE FROM commitments WHERE org_id = :org AND contact_id = :cid"),
    ("recommendations",     "DELETE FROM recommendations WHERE org_id = :org AND subject_entity_id = :cid"),
    ("delivery_attempts",   "DELETE FROM delivery_attempts WHERE org_id = :org AND insight_id IN (SELECT id FROM insights WHERE contact_id = :cid)"),
    ("insights",            "DELETE FROM insights WHERE org_id = :org AND contact_id = :cid"),
    ("context_outcomes",    "DELETE FROM context_outcomes WHERE org_id = :org AND context_id::text IN (SELECT id::text FROM insights WHERE contact_id = :cid)"),
    ("contacts",            "DELETE FROM contacts WHERE org_id = :org AND id = :cid"),
]


def _count(db, org: str, cid: str) -> dict[str, int]:
    """Dry-run preview: how many rows will be deleted per table."""
    preview = {}
    for table, query in DELETE_QUERIES:
        count_sql = query.replace("DELETE FROM", "SELECT COUNT(*) FROM", 1)
        preview[table] = db.execute(text(count_sql), {"org": org, "cid": cid}).scalar() or 0
    return preview


def _audit(db, org: str, cid: str, counts: dict) -> None:
    db.execute(
        text("""
            INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
            VALUES (:id, :org, 'gdpr_delete', CAST(:data AS jsonb), NOW())
        """),
        {
            "id": str(uuid4()),
            "org": org,
            # Anonymized: store the counts but not the entity name/email.
            "data": '{"counts": ' + str(counts).replace("'", '"') + '}',
        },
    )


def _clear_redis(org: str, cid: str) -> int:
    """Best-effort: drop any cached pulls keyed on this contact."""
    try:
        cleared = 0
        for pattern in (f"ctx:{org}:{cid}*", f"narrative:{org}:*{cid}*"):
            for key in redis_client.scan_iter(match=pattern, count=500):
                redis_client.delete(key)
                cleared += 1
        return cleared
    except Exception as e:
        logger.warning(f"redis cache clear failed: {e}")
        return 0


def run(org: str, cid: str, dry_run: bool = True) -> dict:
    with engine.connect() as conn:
        if dry_run:
            preview = _count(conn, org, cid)
            logger.info(f"DRY RUN — would delete: {preview}")
            return {"dry_run": True, "counts": preview}

        counts = {}
        for table, query in DELETE_QUERIES:
            result = conn.execute(text(query), {"org": org, "cid": cid})
            counts[table] = result.rowcount or 0
        _audit(conn, org, cid, counts)
        conn.commit()

    redis_cleared = _clear_redis(org, cid)
    logger.info(f"DELETED: {counts}, redis_keys_cleared={redis_cleared}")
    return {"dry_run": False, "counts": counts, "redis_cleared": redis_cleared}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", required=True, help="org_id (UUID)")
    parser.add_argument("--entity", required=True, help="contact_id (UUID)")
    parser.add_argument("--execute", action="store_true", help="actually delete (default: dry-run)")
    args = parser.parse_args()

    result = run(args.org, args.entity, dry_run=not args.execute)
    print(result)
