"""
Auto-apply for high-confidence merge candidates.

The merge_queue builds proposals (0.65-1.00). Humans review via the /v1/merge
endpoints. For very high scores (>= AUTO_MERGE_THRESHOLD, default 0.95) we
apply the merge automatically so cross-source duplicates don't pollute
scoring, precedent extraction, and bundle quality.

Safety:
- Loser contact is SOFT-deleted (is_archived=TRUE), never hard DELETE
- Every auto-merge stamps `auto_applied_at`; an undo endpoint exists for
  7-day grace window
- Dry-run mode logs decisions without mutating; set env GENIOS_AUTO_MERGE_DRY_RUN=1
- Max MERGES_PER_RUN per tick to prevent one org from monopolizing the worker
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
AUTO_MERGE_THRESHOLD = float(os.getenv("GENIOS_AUTO_MERGE_THRESHOLD", "0.95"))
MERGES_PER_RUN = int(os.getenv("GENIOS_AUTO_MERGE_BATCH", "50"))
DRY_RUN = os.getenv("GENIOS_AUTO_MERGE_DRY_RUN", "0") == "1"


def run_auto_merge(org_id: str | None = None) -> dict:
    """Apply high-confidence merges for one org or all orgs."""
    db = SessionLocal()
    counters = {"eligible": 0, "merged": 0, "failed": 0, "dry_run": DRY_RUN}
    try:
        params: dict = {"threshold": AUTO_MERGE_THRESHOLD, "limit": MERGES_PER_RUN}
        where = "status = 'pending' AND auto_applied_at IS NULL AND match_score >= :threshold"
        if org_id:
            where += " AND org_id = :org_id"
            params["org_id"] = org_id

        rows = db.execute(
            text(f"""
                SELECT id, org_id, contact_id_a, contact_id_b, match_score, match_reason
                FROM merge_queue
                WHERE {where}
                ORDER BY match_score DESC, created_at ASC
                LIMIT :limit
            """),
            params,
        ).fetchall()
        counters["eligible"] = len(rows)

        for r in rows:
            merge_id = str(r.id)
            oid = str(r.org_id)
            id_a = str(r.contact_id_a)
            id_b = str(r.contact_id_b)

            if DRY_RUN:
                logger.info(
                    f"auto_merge DRY_RUN would-apply merge_id={merge_id} "
                    f"org={oid} score={r.match_score} reason={r.match_reason} "
                    f"a={id_a} → b={id_b}"
                )
                continue

            ok = _apply_single_merge(db, oid, merge_id, id_a, id_b)
            if ok:
                counters["merged"] += 1
            else:
                counters["failed"] += 1

        logger.info(f"auto_merge done org={org_id or 'all'} {counters}")
        return counters
    finally:
        db.close()


def _apply_single_merge(
    db: Session, org_id: str, merge_id: str, id_a: str, id_b: str
) -> bool:
    """Reassign interactions + commitments + refs from a→b, archive a.

    Mirrors the logic in app/api/routes/merge.py::execute_merge but stamps
    `auto_applied_at` and keeps contact_a soft-archived (not hard deleted).
    """
    try:
        # Re-check the row is still pending (race-safe)
        still_pending = db.execute(
            text("""
                SELECT 1 FROM merge_queue
                WHERE id = :id AND org_id = :org AND status = 'pending'
                  AND auto_applied_at IS NULL
                FOR UPDATE SKIP LOCKED
            """),
            {"id": merge_id, "org": org_id},
        ).fetchone()
        if not still_pending:
            return False

        db.execute(
            text("UPDATE interactions SET contact_id = :b WHERE contact_id = :a AND org_id = :org"),
            {"a": id_a, "b": id_b, "org": org_id},
        )
        db.execute(
            text("UPDATE commitments SET contact_id = :b WHERE contact_id = :a AND org_id = :org"),
            {"a": id_a, "b": id_b, "org": org_id},
        )
        db.execute(
            text("UPDATE contacts SET introduced_by = :b WHERE introduced_by = :a AND org_id = :org"),
            {"a": id_a, "b": id_b, "org": org_id},
        )
        # Soft-archive loser (never hard DELETE)
        db.execute(
            text("UPDATE contacts SET is_archived = TRUE WHERE id = :a AND org_id = :org"),
            {"a": id_a, "org": org_id},
        )
        db.execute(
            text("""
                UPDATE merge_queue SET
                    status = 'merged',
                    reviewed_by = 'auto_merge',
                    reviewed_at = NOW(),
                    auto_applied_at = NOW()
                WHERE id = :id
            """),
            {"id": merge_id},
        )
        db.commit()
        logger.info(f"auto_merge applied merge_id={merge_id} org={org_id} a={id_a} → b={id_b}")
        return True
    except Exception as e:
        db.rollback()
        logger.warning(f"auto_merge failed merge_id={merge_id} err={e}")
        return False
