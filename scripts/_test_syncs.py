#!/usr/bin/env python3
"""
Quick smoke test — trigger 4 small Gmail syncs back-to-back and report
status after each. Detects whether the new attachment-extraction code or
detector wiring throws on production data.

Usage:
  python scripts/_test_syncs.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"
RUNS = 4
GAP_SECONDS = 90  # gap between triggering each run
WAIT_PER_RUN_MAX = 240  # 4 min max per run (small syncs should finish faster)


def get_status():
    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT sync_status, sync_processed, sync_total, sync_error,
                       last_synced_at,
                       (SELECT COUNT(*) FROM interactions WHERE org_id = :oid) AS ints,
                       (SELECT COUNT(*) FROM interactions
                          WHERE org_id = :oid AND extraction_status = 'failed') AS failed,
                       (SELECT COUNT(*) FROM interactions
                          WHERE org_id = :oid AND extraction_status = 'pending') AS pending
                FROM oauth_tokens WHERE org_id = :oid LIMIT 1
            """),
            {"oid": ORG_ID},
        ).fetchone()
        return row
    finally:
        db.close()


def trigger_one():
    from app.celery_app import task_gmail_sync
    from app.config import SYNC_MAX_EMAILS

    db = SessionLocal()
    try:
        db.execute(
            text("UPDATE oauth_tokens SET sync_status = 'running' WHERE org_id = :oid"),
            {"oid": ORG_ID},
        )
        db.commit()
    finally:
        db.close()

    res = task_gmail_sync.delay(ORG_ID, max_emails=SYNC_MAX_EMAILS, account_email=None)
    return res.id


def wait_done(label):
    deadline = time.time() + WAIT_PER_RUN_MAX
    while time.time() < deadline:
        s = get_status()
        if not s:
            print(f"  [{label}] no oauth row — abort")
            return False, None
        st = s.sync_status or "unknown"
        if st == "completed":
            return True, s
        if st == "error":
            print(f"  [{label}] ❌ ERROR: {s.sync_error}")
            return False, s
        time.sleep(15)
    print(f"  [{label}] ⏱  timeout")
    return False, None


def main():
    print("=" * 70)
    print(f"  Smoke test — {RUNS} sequential syncs on Rohit's org")
    print("=" * 70)

    s0 = get_status()
    print(f"\nBaseline interactions={s0.ints} failed={s0.failed} pending={s0.pending}")
    print(f"Baseline status={s0.sync_status} last_sync={s0.last_synced_at}\n")

    results = []
    for i in range(1, RUNS + 1):
        print(f"--- Run {i}/{RUNS} ---")

        # If a sync is already running, wait for it
        s = get_status()
        if s and s.sync_status == "running":
            print(f"  prior sync still running — waiting...")
            ok, _ = wait_done(f"pre-{i}")
            if not ok:
                print(f"  prior sync stuck — aborting test")
                results.append({"run": i, "status": "blocked-by-prior"})
                break

        task_id = trigger_one()
        print(f"  queued task_id={task_id}")
        ok, end = wait_done(f"run-{i}")
        if not ok:
            results.append({"run": i, "status": "failed", "error": end.sync_error if end else None})
            break

        results.append({
            "run": i,
            "status": "ok",
            "processed": end.sync_processed,
            "total": end.sync_total,
            "interactions_now": end.ints,
            "failed_extracts": end.failed,
        })
        print(f"  ✅ ok processed={end.sync_processed}/{end.sync_total} "
              f"interactions={end.ints} failed_extracts={end.failed}")

        if i < RUNS:
            print(f"  sleeping {GAP_SECONDS}s before next run...\n")
            time.sleep(GAP_SECONDS)

    print()
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)
    for r in results:
        print(f"  run {r['run']}: {r}")

    s_end = get_status()
    print(f"\nFinal interactions={s_end.ints} failed={s_end.failed} pending={s_end.pending}")
    print(f"Final status={s_end.sync_status} last_sync={s_end.last_synced_at}")

    all_ok = all(r["status"] == "ok" for r in results)
    print(f"\n{'✅ ALL CLEAN' if all_ok else '❌ ISSUES FOUND'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
