#!/usr/bin/env python3
"""
Rohit's org — controlled re-sync runner.

What it does (sequence, with confirmations between phases):
  Phase A: Gmail sync     → fetch new emails (uses new 200 cap + attachment extraction)
  Phase B: Wait + monitor → polls oauth_tokens.sync_status until 'completed'
  Phase C: Reextract      → re-runs LLM on stale rows (PROCESSING_VERSION = 4)

Rate limits: Groq 30 RPM is enforced inside the workers via time.sleep(2).
This script just triggers + monitors.

Usage:
  cd ~/Desktop/genios/genios-brain
  source venv/bin/activate
  python scripts/resync_rohit.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"  # Rohit's org


def banner(msg: str) -> None:
    print()
    print("=" * 70)
    print(f"  {msg}")
    print("=" * 70)


def confirm(msg: str) -> bool:
    """Ask y/N, default N."""
    ans = input(f"\n{msg} [y/N]: ").strip().lower()
    return ans == "y"


def show_state(db) -> dict:
    """Snapshot of contacts / interactions / sync status / extraction backlog."""
    row = db.execute(
        text("""
            SELECT
              (SELECT COUNT(*) FROM contacts WHERE org_id = :oid) AS contacts,
              (SELECT COUNT(*) FROM interactions WHERE org_id = :oid) AS interactions,
              (SELECT COUNT(*) FROM interactions
                 WHERE org_id = :oid AND (summary IS NULL OR summary = '')) AS blank_summaries,
              (SELECT COUNT(*) FROM interactions
                 WHERE org_id = :oid AND extraction_status = 'pending') AS pending_extracts,
              (SELECT sync_status FROM oauth_tokens WHERE org_id = :oid LIMIT 1) AS sync_status,
              (SELECT last_synced_at FROM oauth_tokens WHERE org_id = :oid LIMIT 1) AS last_sync
        """),
        {"oid": ORG_ID},
    ).fetchone()
    state = {
        "contacts": row.contacts,
        "interactions": row.interactions,
        "blank_summaries": row.blank_summaries,
        "pending_extracts": row.pending_extracts,
        "sync_status": row.sync_status,
        "last_sync": row.last_sync,
    }
    print(f"  contacts          : {state['contacts']}")
    print(f"  interactions      : {state['interactions']}")
    print(f"  blank summaries   : {state['blank_summaries']}")
    print(f"  pending extracts  : {state['pending_extracts']}")
    print(f"  sync_status       : {state['sync_status']}")
    print(f"  last_synced_at    : {state['last_sync']}")
    return state


def trigger_sync():
    """Queue task_gmail_sync on the production Celery worker."""
    from app.celery_app import task_gmail_sync
    from app.config import SYNC_MAX_EMAILS

    # Mark as running in DB so the dashboard reflects it immediately
    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE oauth_tokens SET sync_status = 'running' WHERE org_id = :oid"),
            {"oid": ORG_ID},
        )
        db.commit()
    finally:
        db.close()

    # Queue the task — production worker picks it up
    res = task_gmail_sync.delay(ORG_ID, max_emails=SYNC_MAX_EMAILS, account_email=None)
    print(f"  queued task id    : {res.id}")
    print(f"  max_emails cap    : {SYNC_MAX_EMAILS}")


def wait_for_sync(timeout_minutes: int = 15) -> bool:
    """Poll oauth_tokens.sync_status every 30s until 'completed' or timeout."""
    deadline = time.time() + timeout_minutes * 60
    db = SessionLocal()
    try:
        while time.time() < deadline:
            row = db.execute(
                text("""
                    SELECT sync_status, sync_processed, sync_total, sync_error
                    FROM oauth_tokens WHERE org_id = :oid LIMIT 1
                """),
                {"oid": ORG_ID},
            ).fetchone()
            if not row:
                print("  (no oauth_tokens row?)")
                return False

            status = row.sync_status or "unknown"
            print(f"  [{time.strftime('%H:%M:%S')}] status={status} "
                  f"processed={row.sync_processed or 0}/{row.sync_total or 0}")

            if status == "completed":
                return True
            if status == "error":
                print(f"  ❌ sync_error: {row.sync_error}")
                return False

            time.sleep(30)
        print("  ⏱  timed out waiting for sync")
        return False
    finally:
        db.close()


def trigger_reextract():
    """Queue task_reextract on the production Celery worker."""
    from app.celery_app import task_reextract
    res = task_reextract.delay(ORG_ID)
    print(f"  queued task id    : {res.id}")
    print("  Note: reextract runs at ~30 RPM (Groq cap). For ~600 rows, expect 20-30 min.")


def main() -> int:
    banner(f"Rohit's org resync — {ORG_ID}")

    db = SessionLocal()
    try:
        banner("STATE BEFORE")
        before = show_state(db)
    finally:
        db.close()

    if before["sync_status"] == "running":
        print("\n⚠  A sync is already running. Wait for it to finish before retrying.")
        return 1

    # ── Phase A: Gmail sync ────────────────────────────────────────────────
    if not confirm("Phase A — trigger Gmail sync now?"):
        print("aborted before Phase A")
        return 0

    banner("PHASE A — Gmail sync")
    trigger_sync()

    banner("PHASE B — wait for sync to complete")
    ok = wait_for_sync(timeout_minutes=15)
    if not ok:
        print("Sync did not complete cleanly. Inspect logs and retry.")
        return 2

    db = SessionLocal()
    try:
        banner("STATE AFTER SYNC")
        after_sync = show_state(db)
    finally:
        db.close()

    # ── Phase C: Reextract (optional) ──────────────────────────────────────
    blank = after_sync["blank_summaries"]
    print(f"\nBlank summaries remaining: {blank}")
    if blank == 0:
        print("Nothing to reextract. Done.")
        return 0

    if not confirm(f"Phase C — trigger reextract on {blank} stale rows? (LLM cost ~${blank * 0.001:.2f}-${blank * 0.005:.2f})"):
        print("aborted before Phase C")
        return 0

    banner("PHASE C — reextract")
    trigger_reextract()
    print("\nReextract queued. Monitor via: python scripts/resync_rohit.py status")
    return 0


def status_only() -> int:
    """Quick state snapshot — no triggers."""
    banner(f"Rohit's org status — {ORG_ID}")
    db = SessionLocal()
    try:
        show_state(db)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        sys.exit(status_only())
    sys.exit(main())
