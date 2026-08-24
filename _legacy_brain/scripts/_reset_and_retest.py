#!/usr/bin/env python3
"""
Reset stuck sync_status='running' and run a single small test sync with
a generous timeout (10 min). Reports detailed timing / errors.

Usage:
  python scripts/_reset_and_retest.py
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"
TIMEOUT_S = 600  # 10 min


def show(label, db):
    row = db.execute(
        text("""
            SELECT sync_status, sync_processed, sync_total, sync_error,
                   sync_started_at, last_synced_at,
                   EXTRACT(EPOCH FROM (NOW() - sync_started_at))::int AS elapsed
            FROM oauth_tokens WHERE org_id = :oid LIMIT 1
        """),
        {"oid": ORG_ID},
    ).fetchone()
    print(f"  [{label}] status={row.sync_status} "
          f"processed={row.sync_processed}/{row.sync_total} "
          f"elapsed={row.elapsed}s "
          f"err={row.sync_error}")
    return row


def reset_stuck():
    db = SessionLocal()
    try:
        before = show("BEFORE-RESET", db)
        if before.sync_status == "running" and (before.elapsed or 0) > 300:
            print("  → resetting stuck 'running' status to 'idle'")
            db.execute(
                text("""
                    UPDATE oauth_tokens
                    SET sync_status = 'idle', sync_error = 'reset_stuck_test'
                    WHERE org_id = :oid
                """),
                {"oid": ORG_ID},
            )
            db.commit()
            show("AFTER-RESET", db)
        else:
            print("  → not stuck or fresh — skipping reset")
    finally:
        db.close()


def trigger_and_wait():
    from app.celery_app import task_gmail_sync
    from app.config import SYNC_MAX_EMAILS

    db = SessionLocal()
    try:
        db.execute(
            text("""
                UPDATE oauth_tokens
                SET sync_status='running', sync_started_at=NOW(),
                    sync_processed=0, sync_total=0, sync_error=NULL
                WHERE org_id=:oid
            """),
            {"oid": ORG_ID},
        )
        db.commit()
    finally:
        db.close()

    res = task_gmail_sync.delay(ORG_ID, max_emails=SYNC_MAX_EMAILS, account_email=None)
    print(f"  queued task_id={res.id} cap={SYNC_MAX_EMAILS}")

    deadline = time.time() + TIMEOUT_S
    last_processed = -1
    no_progress_seconds = 0

    while time.time() < deadline:
        time.sleep(20)
        db = SessionLocal()
        try:
            row = show(f"poll@{int(time.time() - (deadline - TIMEOUT_S))}s", db)
        finally:
            db.close()

        if row.sync_status == "completed":
            print("  ✅ COMPLETED")
            return True, row
        if row.sync_status == "error":
            print(f"  ❌ ERROR: {row.sync_error}")
            return False, row

        # Detect zero-progress hang
        if row.sync_processed == last_processed:
            no_progress_seconds += 20
        else:
            no_progress_seconds = 0
        last_processed = row.sync_processed
        if no_progress_seconds >= 240:
            print(f"  ⚠  no progress for {no_progress_seconds}s — likely hung")
            return False, row

    print("  ⏱  timed out at 10 min")
    return False, None


def main():
    print("=" * 70)
    print(f"  Reset + small test sync — {ORG_ID}")
    print("=" * 70)

    reset_stuck()
    print()
    print("Triggering a single sync and watching every 20s...")
    ok, end = trigger_and_wait()
    print()
    print("=" * 70)
    if ok:
        print(f"  ✅ Sync clean. processed={end.sync_processed}/{end.sync_total}")
    else:
        print(f"  ❌ Sync did NOT complete cleanly. Inspect DO Runtime Logs.")
    print("=" * 70)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
