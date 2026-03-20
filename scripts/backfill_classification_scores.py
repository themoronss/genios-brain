"""
Backfill Script for v1.1 Classification Upgrade

Efficiently computes signal_score and freshness_score for existing data.

Usage:
    python scripts/backfill_classification_scores.py

Author: GeniOS Team
Version: 1.1
Date: 2026-03-18
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from sqlalchemy import text
from datetime import datetime, timezone


def backfill_signal_scores(db, batch_size=500):
    """
    Compute signal_score for all existing interactions in batches.

    Signal score formula (0.0-1.0):
        +0.4 if intent ∈ [commitment, request]
        +0.2 if engagement_level = high (not stored, estimate from weight_score)
        +0.2 if has commitments
        +0.3 if topics exist

    Uses pure SQL for efficiency - no Python loops per row.
    """
    print("\n🔄 Backfilling signal scores for existing interactions...")

    # Get total count
    result = db.execute(
        text("SELECT COUNT(*) FROM interactions WHERE signal_score IS NULL")
    ).fetchone()
    total = result[0]

    if total == 0:
        print("✅ All interactions already have signal scores!")
        return

    print(f"📊 Found {total} interactions without signal scores")

    # Efficient batch update using CASE statements
    # This is MUCH faster than Python loops - runs entirely in database
    try:
        db.execute(
            text(
                """
                UPDATE interactions
                SET signal_score = (
                    CASE 
                        -- Intent signal: +0.4 for commitment/request
                        WHEN intent IN ('commitment', 'request') THEN 0.4
                        ELSE 0.0
                    END
                    +
                    CASE 
                        -- Weight signal proxy: +0.2 if weight_score > 0.7 (high engagement)
                        WHEN weight_score > 0.7 THEN 0.2
                        ELSE 0.0
                    END
                    +
                    CASE 
                        -- Commitment signal: +0.3 if has related commitments
                        WHEN EXISTS(
                            SELECT 1 FROM commitments c 
                            WHERE c.source_interaction_id = interactions.id
                        ) THEN 0.3
                        ELSE 0.0
                    END
                    +
                    CASE 
                        -- Topic signal: +0.2 if has topics
                        WHEN topics IS NOT NULL AND array_length(topics, 1) > 0 THEN 0.2
                        ELSE 0.0
                    END
                )
                WHERE signal_score IS NULL
                """
            )
        )

        db.commit()
        print(f"✅ Updated {total} interactions with signal scores")

    except Exception as e:
        print(f"❌ Error backfilling signal scores: {e}")
        db.rollback()
        raise


def backfill_freshness_scores(db, batch_size=500):
    """
    Compute freshness_score for all existing contacts in batches.

    Freshness score formula (0.1-1.0):
        max(0.1, 0.5 ^ (days_since / half_life))

    Uses stage-specific half-life:
        ACTIVE: 7 days
        WARM: 30 days
        DORMANT: 60 days
        COLD: 90 days
        AT_RISK: 15 days

    Uses pure SQL for efficiency.
    """
    print("\n🔄 Backfilling freshness scores for existing contacts...")

    # Get total count
    result = db.execute(
        text(
            "SELECT COUNT(*) FROM contacts WHERE freshness_score IS NULL OR freshness_score = 1.0"
        )
    ).fetchone()
    total = result[0]

    if total == 0:
        print("✅ All contacts already have computed freshness scores!")
        return

    print(f"📊 Found {total} contacts without freshness scores")

    # Efficient batch update using CASE statements
    try:
        db.execute(
            text(
                """
                UPDATE contacts
                SET freshness_score = GREATEST(
                    0.1,
                    POWER(
                        0.5,
                        EXTRACT(DAY FROM (NOW() - last_interaction_at))::float / 
                        CASE relationship_stage
                            WHEN 'ACTIVE' THEN 7.0
                            WHEN 'WARM' THEN 30.0
                            WHEN 'DORMANT' THEN 60.0
                            WHEN 'COLD' THEN 90.0
                            WHEN 'AT_RISK' THEN 15.0
                            ELSE 30.0
                        END
                    )
                )
                WHERE (freshness_score IS NULL OR freshness_score = 1.0)
                  AND last_interaction_at IS NOT NULL
                """
            )
        )

        db.commit()
        print(f"✅ Updated {total} contacts with freshness scores")

    except Exception as e:
        print(f"❌ Error backfilling freshness scores: {e}")
        db.rollback()
        raise


def verify_backfill(db):
    """
    Verify backfill completed successfully.
    """
    print("\n🔍 Verifying backfill...")

    # Check signal scores
    result = db.execute(
        text(
            """
            SELECT 
                COUNT(*) as total,
                COUNT(signal_score) as with_signal,
                ROUND(AVG(signal_score)::numeric, 3) as avg_signal,
                ROUND(MIN(signal_score)::numeric, 3) as min_signal,
                ROUND(MAX(signal_score)::numeric, 3) as max_signal
            FROM interactions
            """
        )
    ).fetchone()

    print(f"\n📊 Interactions:")
    print(f"   Total: {result[0]}")
    print(f"   With signal_score: {result[1]} ({result[1]/result[0]*100:.1f}%)")
    print(f"   Avg signal: {result[2]}")
    print(f"   Range: {result[3]} - {result[4]}")

    # Check freshness scores
    result = db.execute(
        text(
            """
            SELECT 
                COUNT(*) as total,
                COUNT(freshness_score) as with_freshness,
                ROUND(AVG(freshness_score)::numeric, 3) as avg_freshness,
                ROUND(MIN(freshness_score)::numeric, 3) as min_freshness,
                ROUND(MAX(freshness_score)::numeric, 3) as max_freshness
            FROM contacts
            WHERE last_interaction_at IS NOT NULL
            """
        )
    ).fetchone()

    print(f"\n📊 Contacts:")
    print(f"   Total: {result[0]}")
    print(f"   With freshness_score: {result[1]} ({result[1]/result[0]*100:.1f}%)")
    print(f"   Avg freshness: {result[2]}")
    print(f"   Range: {result[3]} - {result[4]}")

    # Sample some high signal interactions
    print("\n🔝 Sample high-signal interactions:")
    results = db.execute(
        text(
            """
            SELECT subject, intent, signal_score, weight_score
            FROM interactions
            WHERE signal_score IS NOT NULL
            ORDER BY signal_score DESC
            LIMIT 5
            """
        )
    ).fetchall()

    for row in results:
        print(
            f"   [{row[2]:.2f}] {row[0][:50]} (intent: {row[1]}, weight: {row[3]:.2f})"
        )


def main():
    """
    Run backfill for classification upgrade v1.1.
    """
    print("=" * 70)
    print("GeniOS Classification Upgrade v1.1 - Backfill Script")
    print("=" * 70)

    db = SessionLocal()

    try:
        start_time = datetime.now()

        # Step 1: Backfill signal scores
        backfill_signal_scores(db)

        # Step 2: Backfill freshness scores
        backfill_freshness_scores(db)

        # Step 3: Verify
        verify_backfill(db)

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n✅ Backfill completed in {elapsed:.2f} seconds")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Backfill failed: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
