#!/usr/bin/env python3
"""
One-shot: clear a stuck sync_status='running' for Rohit's org.

The earlier task completed (sync_processed = sync_total) but the worker
never wrote sync_status='completed', so the sync row is stuck and any
subsequent /api/org/{id}/sync call returns 429.

This script flips sync_status to 'completed' and updates last_synced_at
ONLY if the task was actually finished (processed >= total).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"


def main():
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT sync_status, sync_processed, sync_total, sync_started_at,
                   EXTRACT(EPOCH FROM (NOW() - sync_started_at))::int AS started_secs_ago
            FROM oauth_tokens WHERE org_id = :oid LIMIT 1
        """), {"oid": ORG_ID}).fetchone()

        print(f"BEFORE: status={row.sync_status} processed={row.sync_processed}/{row.sync_total} "
              f"({row.started_secs_ago}s ago)")

        if row.sync_status != "running":
            print("  not stuck — exiting")
            return 0

        if (row.started_secs_ago or 0) < 600:
            print("  too recent (< 10 min) — leaving alone, may still be running")
            return 0

        if (row.sync_processed or 0) < (row.sync_total or 0):
            print("  processed < total — task may genuinely be running, not stuck")
            return 0

        # Safe to clear: processed == total, but status never updated
        db.execute(text("""
            UPDATE oauth_tokens
            SET sync_status = 'completed',
                last_synced_at = COALESCE(sync_started_at, NOW()),
                sync_error = 'cleared_stuck_status'
            WHERE org_id = :oid
        """), {"oid": ORG_ID})
        db.commit()

        row2 = db.execute(text("""
            SELECT sync_status, last_synced_at FROM oauth_tokens WHERE org_id = :oid LIMIT 1
        """), {"oid": ORG_ID}).fetchone()
        print(f"AFTER:  status={row2.sync_status} last_synced_at={row2.last_synced_at}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
