"""
Nightly Relationship Refresh Job
Recalculates relationship stages, runs insights engine, and pre-computes context bundles.
Can be run directly: python -m app.tasks.nightly_refresh
Or scheduled via cron: 0 2 * * * cd /path/to/genios-brain && venv/bin/python -m app.tasks.nightly_refresh
"""

import sys
import os
import json
import hashlib
from datetime import datetime, timezone

# Add parent directory to path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.graph.relationship_calculator import recalculate_all_relationships


def run_nightly_refresh(org_id: str = None):
    """
    Run nightly refresh job:
    1. Recalculate all relationship stages (sentiment, confidence, freshness, etc.)
    2. Run Louvain community detection
    3. Run insights engine (signal detection queries)
    4. Pre-compute context bundles for active contacts (24h cache)
    5. Mark overdue commitments

    Args:
        org_id: Optional — limit refresh to a single org (used for post-sync refresh).
                If None, recalculates all orgs.
    """
    scope = f"org {org_id}" if org_id else "ALL orgs"
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting nightly relationship refresh for {scope}...")

    db = SessionLocal()

    try:
        # ── Step 1: Recalculate relationships ────────────────────────────
        updated_count = recalculate_all_relationships(db, org_id)
        print(f"✓ Successfully updated {updated_count} contacts for {scope}")

        # ── Step 2: Louvain community detection ──────────────────────────
        try:
            from app.graph.community_detection import run_louvain_detection
            if org_id:
                partition = run_louvain_detection(db, org_id)
                print(f"✓ Louvain: {len(set(partition.values())) if partition else 0} communities for org {org_id}")
            else:
                from sqlalchemy import text
                orgs = db.execute(text("SELECT id FROM orgs")).fetchall()
                for org_row in orgs:
                    partition = run_louvain_detection(db, str(org_row[0]))
                    print(f"  ✓ Louvain: {len(set(partition.values())) if partition else 0} communities for org {org_row[0]}")
        except Exception as e:
            print(f"⚠️ Louvain detection skipped: {e}")

        # ── Step 3: Run insights engine ──────────────────────────────────
        try:
            from app.graph.insights_engine import run_insights_engine
            if org_id:
                insights = run_insights_engine(db, org_id)
                print(f"✓ Insights: {len(insights)} signals detected for org {org_id}")
            else:
                from sqlalchemy import text
                orgs = db.execute(text("SELECT id FROM orgs")).fetchall()
                for org_row in orgs:
                    insights = run_insights_engine(db, str(org_row[0]))
                    print(f"  ✓ Insights: {len(insights)} signals for org {org_row[0]}")
        except Exception as e:
            print(f"⚠️ Insights engine skipped: {e}")

        # ── Step 4: Mark overdue commitments ─────────────────────────────
        try:
            from sqlalchemy import text
            overdue_count = db.execute(
                text("""
                    UPDATE commitments
                    SET status = 'OVERDUE'
                    WHERE status = 'OPEN'
                    AND due_date < NOW()
                    AND due_date IS NOT NULL
                """)
            ).rowcount
            db.commit()
            if overdue_count:
                print(f"✓ Marked {overdue_count} commitments as OVERDUE")
        except Exception as e:
            print(f"⚠️ Overdue marking failed: {e}")

        # ── Step 5: Pre-compute context bundles for active contacts ──────
        try:
            _precompute_bundles(db, org_id)
        except Exception as e:
            print(f"⚠️ Bundle pre-computation skipped: {e}")

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Completed nightly refresh for {scope}")
        return updated_count
    except Exception as e:
        print(f"✗ Error during nightly refresh: {e}")
        raise
    finally:
        db.close()


def _precompute_bundles(db, org_id: str = None):
    """
    Pre-compute context bundles for active/warm contacts.
    Per PDF spec: bundles are pre-computed and cached, not generated on-demand.
    Only recomputes if material change detected (stage, sentiment, commitments).
    """
    from sqlalchemy import text
    from app.context.bundle_builder import build_context_bundle

    # Get active/warm contacts that need bundle refresh
    if org_id:
        contacts = db.execute(
            text("""
                SELECT c.id, c.name, c.org_id, c.relationship_stage,
                    c.sentiment_ewma, c.interaction_count
                FROM contacts c
                WHERE c.org_id = :org_id
                AND c.relationship_stage IN ('ACTIVE', 'WARM', 'NEEDS_ATTENTION')
                AND (c.is_archived = FALSE OR c.is_archived IS NULL)
                ORDER BY c.composite_score DESC NULLS LAST
                LIMIT 100
            """),
            {"org_id": org_id}
        ).fetchall()
    else:
        contacts = db.execute(
            text("""
                SELECT c.id, c.name, c.org_id, c.relationship_stage,
                    c.sentiment_ewma, c.interaction_count
                FROM contacts c
                WHERE c.relationship_stage IN ('ACTIVE', 'WARM', 'NEEDS_ATTENTION')
                AND (c.is_archived = FALSE OR c.is_archived IS NULL)
                ORDER BY c.composite_score DESC NULLS LAST
                LIMIT 500
            """)
        ).fetchall()

    precomputed = 0
    skipped = 0

    for contact in contacts:
        contact_id = str(contact[0])
        contact_name = contact[1]
        contact_org_id = str(contact[2])

        # Compute material hash to detect changes
        material = f"{contact[3]}:{contact[4]}:{contact[5]}"
        material_hash = hashlib.md5(material.encode()).hexdigest()

        # Check if existing bundle is still valid
        existing = db.execute(
            text("""
                SELECT material_hash FROM precomputed_bundles
                WHERE org_id = :org_id AND contact_id = :contact_id
                AND expires_at > NOW()
            """),
            {"org_id": contact_org_id, "contact_id": contact_id}
        ).fetchone()

        if existing and existing[0] == material_hash:
            skipped += 1
            continue

        # Build and store bundle
        try:
            bundle = build_context_bundle(db, contact_org_id, contact_name)
            if not bundle.get("error"):
                db.execute(
                    text("""
                        INSERT INTO precomputed_bundles
                            (org_id, contact_id, bundle, context_paragraph, generated_at, expires_at, material_hash)
                        VALUES
                            (:org_id, :contact_id, :bundle, :context_paragraph, NOW(),
                             NOW() + INTERVAL '24 hours', :material_hash)
                        ON CONFLICT (org_id, contact_id)
                        DO UPDATE SET
                            bundle = EXCLUDED.bundle,
                            context_paragraph = EXCLUDED.context_paragraph,
                            generated_at = NOW(),
                            expires_at = NOW() + INTERVAL '24 hours',
                            material_hash = EXCLUDED.material_hash
                    """),
                    {
                        "org_id": contact_org_id,
                        "contact_id": contact_id,
                        "bundle": json.dumps(bundle, default=str),
                        "context_paragraph": bundle.get("context_for_agent", ""),
                        "material_hash": material_hash,
                    }
                )
                precomputed += 1
        except Exception as e:
            print(f"  ⚠️ Bundle failed for {contact_name}: {e}")

    db.commit()
    print(f"✓ Pre-computed {precomputed} bundles ({skipped} unchanged, skipped)")


if __name__ == "__main__":
    # Support optional org_id arg: python -m app.tasks.nightly_refresh [org_id]
    org_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_nightly_refresh(org_id_arg)
