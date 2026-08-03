#!/usr/bin/env python3
"""Why are new detectors returning 0? Diagnose data shape."""
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
        print("  Data shape diagnosis")
        print("=" * 70)

        # 1. Bidirectional flag
        r = db.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE is_bidirectional IS TRUE) AS bidir_true,
                COUNT(*) FILTER (WHERE is_bidirectional IS FALSE) AS bidir_false,
                COUNT(*) FILTER (WHERE is_bidirectional IS NULL) AS bidir_null,
                COUNT(*) FILTER (WHERE COALESCE(classification_override, classification, 'unknown')
                                 NOT IN ('newsletter','bot','transactional')) AS non_broadcast
            FROM contacts WHERE org_id = :oid
        """), {"oid": ORG_ID}).fetchone()
        print(f"\n1. Contact filters (total {r.total})")
        print(f"   is_bidirectional=TRUE  : {r.bidir_true}")
        print(f"   is_bidirectional=FALSE : {r.bidir_false}")
        print(f"   is_bidirectional=NULL  : {r.bidir_null}")
        print(f"   non-broadcast          : {r.non_broadcast}")

        # 2. Contacts with N interactions (for change_point)
        rows = db.execute(text("""
            SELECT bucket, COUNT(*) AS n FROM (
                SELECT CASE
                  WHEN interaction_count >= 6 THEN '6+'
                  WHEN interaction_count >= 3 THEN '3-5'
                  WHEN interaction_count >= 1 THEN '1-2'
                  ELSE '0'
                END AS bucket
                FROM contacts WHERE org_id = :oid
            ) x
            GROUP BY bucket ORDER BY bucket DESC
        """), {"oid": ORG_ID}).fetchall()
        print(f"\n2. Contact interaction-count distribution")
        for r in rows:
            print(f"   {r.bucket}: {r.n}")

        # 3. Recent inbound (for inbound_ack)
        r = db.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE direction='inbound' AND interaction_at > NOW() - INTERVAL '14 days') AS inbound_14d,
                COUNT(*) FILTER (WHERE direction='inbound' AND interaction_at > NOW() - INTERVAL '14 days'
                                 AND interaction_at < NOW() - INTERVAL '48 hours') AS inbound_eligible_48h,
                COUNT(*) FILTER (WHERE direction='outbound' AND interaction_at > NOW() - INTERVAL '72 hours') AS outbound_72h
            FROM interactions WHERE org_id = :oid
        """), {"oid": ORG_ID}).fetchone()
        print(f"\n3. Direction / recency")
        print(f"   inbound last 14d        : {r.inbound_14d}")
        print(f"   inbound 48h-14d window  : {r.inbound_eligible_48h}")
        print(f"   outbound last 72h       : {r.outbound_72h}")

        # 4. Topic distribution (for campaign)
        rows = db.execute(text("""
            SELECT topic, COUNT(DISTINCT contact_id) AS recipients, COUNT(*) AS msgs
            FROM (
                SELECT i.contact_id, UNNEST(COALESCE(i.topics, ARRAY[]::text[])) AS topic
                FROM interactions i
                WHERE i.org_id = :oid AND i.direction = 'outbound'
                  AND i.interaction_at > NOW() - INTERVAL '72 hours'
            ) x
            WHERE topic IS NOT NULL AND topic <> ''
            GROUP BY topic
            ORDER BY recipients DESC, msgs DESC
            LIMIT 5
        """), {"oid": ORG_ID}).fetchall()
        print(f"\n4. Outbound topics in last 72h")
        if not rows:
            print("   none")
        else:
            for r in rows:
                tag = "← campaign-eligible" if r.recipients >= 2 else ""
                print(f"   {r.topic[:50]:50} recipients={r.recipients} msgs={r.msgs} {tag}")

        # 5. Top contacts by interaction count (sanity)
        rows = db.execute(text("""
            SELECT name, email, interaction_count, is_bidirectional,
                   COALESCE(classification_override, classification, 'unknown') AS clf
            FROM contacts
            WHERE org_id = :oid AND interaction_count > 0
            ORDER BY interaction_count DESC LIMIT 10
        """), {"oid": ORG_ID}).fetchall()
        print(f"\n5. Top contacts by interaction count")
        for r in rows:
            print(f"   {(r.name or '?')[:25]:25} ix={r.interaction_count or 0:3} bidir={r.is_bidirectional} clf={r.clf}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
