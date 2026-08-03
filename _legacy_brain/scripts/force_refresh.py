"""
Force full brain refresh for an org.

Steps:
  1. Gmail sync (max 30 new emails)
  2. Extract pending interactions (LLM summaries, sentiment, topics)
  3. Re-extract stale interactions (processed_version < PROCESSING_VERSION)
  4. Recompute scores, stages, graph

Usage:
  python scripts/force_refresh.py                        # all orgs
  python scripts/force_refresh.py --org <org_id>         # specific org
  python scripts/force_refresh.py --org <org_id> --step sync
  python scripts/force_refresh.py --org <org_id> --step extract
  python scripts/force_refresh.py --org <org_id> --step reextract
  python scripts/force_refresh.py --org <org_id> --step recompute
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.database import SessionLocal
from sqlalchemy import text


def get_orgs(db, org_id=None):
    if org_id:
        rows = db.execute(text("SELECT id, name FROM orgs WHERE id = :id"), {"id": org_id}).fetchall()
    else:
        rows = db.execute(text("SELECT id, name FROM orgs")).fetchall()
    return rows


def step_sync(org_id: str, max_emails: int = 30):
    print(f"\n[1/4] Syncing Gmail (max {max_emails} emails)...")
    from app.tasks.gmail_sync import run_gmail_sync
    from app.database import SessionLocal as S
    db = S()
    try:
        tokens = db.execute(
            text("SELECT account_email FROM oauth_tokens WHERE org_id = :oid"),
            {"oid": org_id}
        ).fetchall()
        for t in tokens:
            print(f"  → Syncing {t[0]}...")
            run_gmail_sync(org_id, max_emails=max_emails, account_email=t[0])
    finally:
        db.close()
    print("  ✅ Sync done")


def step_extract(org_id: str):
    print(f"\n[2/4] Extracting pending interactions (LLM summaries)...")
    from app.tasks.extract_interactions import run_pending_extractions
    run_pending_extractions(org_id=org_id)
    print("  ✅ Extraction done")


def step_reextract(org_id: str):
    """Re-extract using stored raw_body — no Gmail API needed."""
    print(f"\n[3/4] Re-extracting stale interactions from stored data...")
    from app.config import PROCESSING_VERSION
    from app.tasks.extract_interactions import extract_email_intelligence
    from app.tasks.reextract import run_recompute
    import json, time as _time

    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT i.id, i.subject, i.raw_body, i.direction,
                   c.name AS contact_name, c.email AS contact_email
            FROM interactions i
            JOIN contacts c ON c.id = i.contact_id
            WHERE i.org_id = :org_id
              AND COALESCE(i.processed_version, 1) < :ver
            ORDER BY i.interaction_at DESC
        """), {"org_id": org_id, "ver": PROCESSING_VERSION}).fetchall()

        print(f"  → {len(rows)} interactions to re-extract")
        processed = failed = 0

        for row in rows:
            iid, subject, raw_body, direction, contact_name, contact_email = row
            try:
                if not raw_body:
                    db.execute(text(
                        "UPDATE interactions SET processed_version=:v WHERE id=:id"),
                        {"v": PROCESSING_VERSION, "id": iid})
                    continue

                intel = extract_email_intelligence(
                    subject or "", raw_body,
                    sender_name=contact_name,
                    is_reply=bool(subject and "re:" in (subject or "").lower()),
                    org_id=org_id,
                )
                db.execute(text("""
                    UPDATE interactions SET
                        summary=:summary, sentiment=:sentiment,
                        intent=:intent, interaction_type=:itype,
                        topics=:topics, processed_version=:ver
                    WHERE id=:id
                """), {
                    "summary": (intel.get("summary") or "")[:500],
                    "sentiment": intel.get("sentiment", 0.0),
                    "intent": intel.get("intent", "other"),
                    "itype": intel.get("interaction_type", "email_one_way"),
                    "topics": intel.get("topics", []),
                    "ver": PROCESSING_VERSION,
                    "id": iid,
                })
                processed += 1
            except Exception as e:
                if "429" in str(e) or "rate" in str(e).lower():
                    print(f"  ⚠️ Rate limit hit, sleeping 60s...")
                    _time.sleep(60)
                    continue  # retry same interaction next loop won't happen but at least we don't skip
                db.execute(text(
                    "UPDATE interactions SET processed_version=:v WHERE id=:id"),
                    {"v": PROCESSING_VERSION, "id": iid})
                failed += 1
            finally:
                _time.sleep(3)  # 20 req/min — safe under Groq 30/min limit

            if (processed + failed) % 10 == 0:
                db.commit()
                print(f"  → {processed} done, {failed} failed...")

        db.commit()
        print(f"  ✅ Re-extraction done: {processed} processed, {failed} failed")
    finally:
        db.close()

    run_recompute(org_id)


def step_recompute(org_id: str):
    print(f"\n[4/4] Recomputing scores, stages, graph...")
    from app.tasks.reextract import run_recompute
    run_recompute(org_id=org_id)
    print("  ✅ Recompute done")


def run_all(org_id: str, max_emails: int = 30):
    print(f"\n{'='*50}")
    print(f"Force refresh: org {org_id}")
    print(f"{'='*50}")
    t0 = time.time()
    step_sync(org_id, max_emails=max_emails)
    step_extract(org_id)
    step_reextract(org_id)
    step_recompute(org_id)
    print(f"\n✅ Full refresh done in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", help="Org ID (default: all orgs)")
    parser.add_argument("--max-emails", type=int, default=30, help="Max emails to sync (default 30)")
    parser.add_argument("--step", choices=["sync", "extract", "reextract", "recompute"],
                        help="Run only one step")
    args = parser.parse_args()

    db = SessionLocal()
    orgs = get_orgs(db, args.org)
    db.close()

    if not orgs:
        print("No orgs found.")
        sys.exit(1)

    for org in orgs:
        org_id = str(org[0])
        name = org[1] or org_id
        print(f"\nOrg: {name} ({org_id})")

        if args.step == "sync":
            step_sync(org_id, args.max_emails)
        elif args.step == "extract":
            step_extract(org_id)
        elif args.step == "reextract":
            step_reextract(org_id)
        elif args.step == "recompute":
            step_recompute(org_id)
        else:
            run_all(org_id, args.max_emails)
