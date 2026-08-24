"""
Expire stale approvals (Phase 3 cleanup).

Runs every 5 min from Celery beat. For every `approvals_queue` row that is
still `pending` past its `expires_at`, mark it `expired` and close the
linked `action_ledger` row with a clear reason. Keeps the live queue honest
and prevents the Approvals page from showing rows that nobody will ever act on.
"""

import logging
from typing import Optional

from sqlalchemy import text

from app.actions import ledger as action_ledger
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def run_expire_approvals() -> dict:
    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                UPDATE approvals_queue
                SET status = 'expired'
                WHERE status = 'pending'
                  AND expires_at < NOW()
                RETURNING id, action_ledger_id
            """),
        ).fetchall()
        db.commit()
    except Exception as e:
        logger.warning(f"expire_approvals UPDATE failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        db.close()
        return {"expired": 0, "error": str(e)[:200]}

    expired = len(rows)
    ledger_closed = 0
    for r in rows:
        lid = r[1]
        if not lid:
            continue
        if action_ledger.update_outcome(
            db, int(lid), "failed", "expired_without_decision"
        ):
            ledger_closed += 1

    db.close()
    if expired:
        logger.info(f"expire_approvals: marked {expired} rows expired, closed {ledger_closed} ledgers")
    return {"expired": expired, "ledger_closed": ledger_closed}
