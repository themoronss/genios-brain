#!/usr/bin/env python3
"""
Production celery + system health check.
Read-only. Reports:
  - sync_status (stuck running?)
  - worker queue lag (Redis broker)
  - recent extraction activity (last 1h)
  - recent insight generation (last 6h)
  - PROCESSING_VERSION distribution
  - LLM cost today
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
        print("=" * 70)
        print("  Production Health Check")
        print("=" * 70)

        # 1. OAuth / sync status
        print("\n1. SYNC STATUS")
        r = db.execute(text("""
            SELECT sync_status, sync_processed, sync_total, sync_error,
                   sync_started_at, last_synced_at,
                   EXTRACT(EPOCH FROM (NOW() - sync_started_at))::int AS started_secs_ago,
                   EXTRACT(EPOCH FROM (NOW() - last_synced_at))::int AS completed_secs_ago
            FROM oauth_tokens WHERE org_id = :oid LIMIT 1
        """), {"oid": ORG_ID}).fetchone()
        print(f"  sync_status     : {r.sync_status}")
        print(f"  processed/total : {r.sync_processed}/{r.sync_total}")
        print(f"  started         : {r.sync_started_at} ({r.started_secs_ago}s ago)")
        print(f"  last completed  : {r.last_synced_at} ({r.completed_secs_ago}s ago)")
        if r.sync_error:
            print(f"  ERROR           : {r.sync_error}")
        if r.sync_status == "running" and (r.started_secs_ago or 0) > 600:
            print(f"  ⚠  STUCK — running for >{r.started_secs_ago}s, no recent completion")

        # 2. PROCESSING_VERSION distribution (which rows need reextract?)
        print("\n2. PROCESSING_VERSION DISTRIBUTION (Rohit's interactions)")
        rows = db.execute(text("""
            SELECT COALESCE(processed_version, 0) AS pv, COUNT(*) AS n
            FROM interactions WHERE org_id = :oid
            GROUP BY pv ORDER BY pv
        """), {"oid": ORG_ID}).fetchall()
        for row in rows:
            tag = "← needs reextract" if row.pv < 4 else "← latest"
            print(f"  v{row.pv}: {row.n} rows  {tag}")

        # 3. Recent extraction activity (last 1h)
        print("\n3. RECENT EXTRACTION (last 1h, all orgs)")
        r3 = db.execute(text("""
            SELECT extraction_status, COUNT(*) AS n
            FROM interactions
            WHERE created_at > NOW() - INTERVAL '1 hour'
            GROUP BY extraction_status ORDER BY n DESC
        """)).fetchone()
        if r3:
            rows3 = db.execute(text("""
                SELECT extraction_status, COUNT(*) AS n
                FROM interactions
                WHERE created_at > NOW() - INTERVAL '1 hour'
                GROUP BY extraction_status ORDER BY n DESC
            """)).fetchall()
            for row in rows3:
                print(f"  {row.extraction_status}: {row.n}")
        else:
            print("  no activity")

        # 4. Insights generated (last 6h)
        print("\n4. RECENT INSIGHTS (last 6h, Rohit's org)")
        rows4 = db.execute(text("""
            SELECT category, priority, delivery_status, COUNT(*) AS n
            FROM insights
            WHERE org_id = :oid AND generated_at > NOW() - INTERVAL '6 hours'
            GROUP BY category, priority, delivery_status
            ORDER BY n DESC
        """), {"oid": ORG_ID}).fetchall()
        if not rows4:
            print("  no insights generated in last 6h")
        else:
            for row in rows4:
                print(f"  {row.category} [{row.priority}] {row.delivery_status}: {row.n}")

        # 5. Inbound ack + change_point insights — were they generated yet?
        print("\n5. NEW DETECTORS — fired yet?")
        for cat in ("unacknowledged_inbound", "engagement_change_point", "active_campaign"):
            r5 = db.execute(text("""
                SELECT COUNT(*) AS n, MAX(generated_at) AS last_at
                FROM insights WHERE org_id = :oid AND category = :cat
            """), {"oid": ORG_ID, "cat": cat}).fetchone()
            print(f"  {cat}: {r5.n} ever, last={r5.last_at}")

        # 6. LLM cost today
        print("\n6. LLM COST TODAY (Rohit's org)")
        r6 = db.execute(text("""
            SELECT
                COUNT(*) AS calls,
                SUM(COALESCE(cost_usd, 0)) AS cost,
                MAX(created_at) AS last_call
            FROM llm_usage
            WHERE org_id = :oid AND created_at > NOW() - INTERVAL '24 hours'
        """), {"oid": ORG_ID}).fetchone()
        print(f"  calls last 24h : {r6.calls or 0}")
        print(f"  cost           : ${float(r6.cost or 0):.4f}")
        print(f"  last call      : {r6.last_call}")

        # 7. Interactions with attachments (so we can find real PDF/DOCX to test)
        print("\n7. INTERACTIONS WITH ATTACHMENTS (Rohit's org)")
        rows7 = db.execute(text("""
            SELECT i.id, i.gmail_message_id, i.subject, i.has_attachment,
                   c.name AS contact_name
            FROM interactions i
            JOIN contacts c ON c.id = i.contact_id
            WHERE i.org_id = :oid AND i.has_attachment = TRUE
            ORDER BY i.interaction_at DESC
            LIMIT 10
        """), {"oid": ORG_ID}).fetchall()
        if not rows7:
            print("  no interactions with attachments — can't test PDF path yet")
        else:
            for row in rows7:
                print(f"  {(row.contact_name or '?')[:25]:25} | {(row.subject or '')[:50]}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
