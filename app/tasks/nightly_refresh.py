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
from datetime import datetime, timezone, date

# Add parent directory to path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal
from app.graph.relationship_calculator import recalculate_all_relationships
from app.plan_enforcer import get_org_plan


REFRESH_PHASES = [
    "recalculate_relationships",
    "louvain_detection",
    "insights_engine",
    "inferred_edges",
    "overdue_commitments",
    "precompute_bundles",
    "daily_snapshots",
    "weekly_reports",
    "confidence_updater",
]


def _get_org_ids(db, org_id=None):
    """Return list of org IDs to process."""
    if org_id:
        return [org_id]
    rows = db.execute(text("SELECT id FROM orgs")).fetchall()
    return [str(r[0]) for r in rows]


def _is_phase_done(db, org_id: str, phase: str) -> bool:
    """Check if a phase has already completed for this org today."""
    try:
        row = db.execute(
            text("""
                SELECT status FROM refresh_jobs
                WHERE org_id = :org_id AND phase = :phase AND run_date = CURRENT_DATE
            """),
            {"org_id": org_id, "phase": phase},
        ).fetchone()
        return row is not None and row[0] == "completed"
    except Exception:
        return False


def _mark_phase(db, org_id: str, phase: str, status: str, error: str = None):
    """Record phase status in refresh_jobs table."""
    try:
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO refresh_jobs (org_id, phase, run_date, status, started_at, completed_at, error_message)
                VALUES (:org_id, :phase, CURRENT_DATE, :status, :now,
                        CASE WHEN :status IN ('completed', 'failed') THEN :now ELSE NULL END,
                        :error)
                ON CONFLICT (org_id, phase, run_date) DO UPDATE SET
                    status = EXCLUDED.status,
                    completed_at = CASE WHEN EXCLUDED.status IN ('completed', 'failed') THEN :now ELSE refresh_jobs.completed_at END,
                    error_message = EXCLUDED.error_message
            """),
            {"org_id": org_id, "phase": phase, "status": status, "now": now, "error": error},
        )
        db.commit()
    except Exception as e:
        print(f"  ⚠️ Phase tracking write failed ({phase}): {e}")
        try:
            db.rollback()
        except Exception:
            pass


def run_nightly_refresh(org_id: str = None):
    """
    Run nightly refresh job with per-org, per-phase progress tracking.
    Phases are idempotent — completed phases are skipped on restart.

    Phases:
    1. Recalculate all relationship stages
    2. Run Louvain community detection
    3. Run insights engine
    4. Compute inferred edges
    5. Mark overdue commitments
    6. Pre-compute context bundles
    7. Record daily snapshots
    8. Weekly reports (Mondays)
    9. Apply confidence deltas

    Args:
        org_id: Optional — limit refresh to a single org.
    """
    scope = f"org {org_id}" if org_id else "ALL orgs"
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting nightly relationship refresh for {scope}...")

    db = SessionLocal()
    org_ids = _get_org_ids(db, org_id)
    # Use first org_id for phase tracking (or a sentinel for all-org runs)
    track_id = org_ids[0] if len(org_ids) == 1 else org_ids[0]

    try:
        # ── Step 1: Recalculate relationships ────────────────────────────
        phase = "recalculate_relationships"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                updated_count = recalculate_all_relationships(db, org_id)
                print(f"✓ Successfully updated {updated_count} contacts for {scope}")
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Relationship recalc failed: {e}")
                updated_count = 0
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")
            updated_count = 0

        # ── Step 2: Louvain community detection ──────────────────────────
        phase = "louvain_detection"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                from app.graph.community_detection import run_louvain_detection
                for oid in org_ids:
                    plan_info = get_org_plan(db, oid)
                    if not plan_info["config"].get("louvain"):
                        continue
                    partition = run_louvain_detection(db, oid)
                    print(f"  ✓ Louvain: {len(set(partition.values())) if partition else 0} communities for org {oid}")
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Louvain detection skipped: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        # ── Step 3: Run insights engine ──────────────────────────────────
        phase = "insights_engine"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                from app.graph.insights_engine import run_insights_engine
                for oid in org_ids:
                    insights = run_insights_engine(db, oid)
                    print(f"  ✓ Insights: {len(insights)} signals for org {oid}")
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Insights engine skipped: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        # ── Step 4: Compute inferred edges ───────────────────────────────
        phase = "inferred_edges"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                from app.graph.indirect_edges import compute_inferred_edges, compute_mentioned_in_edges
                for oid in org_ids:
                    inferred_count = compute_inferred_edges(db, oid)
                    mentioned_count = compute_mentioned_in_edges(db, oid)
                    print(f"  ✓ Inferred edges: {inferred_count} indirect + {mentioned_count} MENTIONED_IN for org {oid}")
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Inferred edge computation skipped: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        # ── Step 5: Mark overdue commitments ─────────────────────────────
        phase = "overdue_commitments"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
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
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Overdue marking failed: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        # ── Step 6: Pre-compute context bundles ──────────────────────────
        phase = "precompute_bundles"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                _precompute_bundles(db, org_id)
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Bundle pre-computation skipped: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        # ── Step 7: Record daily snapshots ───────────────────────────────
        phase = "daily_snapshots"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                for oid in org_ids:
                    _record_daily_snapshot(db, oid)
                print(f"✓ Daily snapshots recorded for {len(org_ids)} org(s)")
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Daily snapshot failed: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        # ── Step 8: Weekly reports (Mondays only) ────────────────────────
        phase = "weekly_reports"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                if datetime.now(timezone.utc).weekday() == 0:  # Monday
                    from app.tasks.weekly_report import run_weekly_reports
                    run_weekly_reports(org_id)
                    print(f"✓ Weekly graph intelligence reports generated")
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Weekly reports skipped: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        # ── Step 9: Confidence updater ───────────────────────────────────
        phase = "confidence_updater"
        if not _is_phase_done(db, track_id, phase):
            _mark_phase(db, track_id, phase, "running")
            try:
                from app.tasks.confidence_updater import apply_outcome_confidence_deltas
                updated = apply_outcome_confidence_deltas(db, org_id)
                if updated:
                    print(f"✓ Confidence updater: applied deltas to {updated} contact(s)")
                _mark_phase(db, track_id, phase, "completed")
            except Exception as e:
                db.rollback()
                _mark_phase(db, track_id, phase, "failed", str(e))
                print(f"⚠️ Confidence updater skipped: {e}")
        else:
            print(f"  ↩ Skipping {phase} (already completed today)")

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Completed nightly refresh for {scope}")
        return updated_count
    except Exception as e:
        print(f"✗ Error during nightly refresh: {e}")
        raise
    finally:
        db.close()


def _compute_graph_quality_score(db, org_id: str) -> float:
    """
    Stage-aware brain health score (0–1, displayed as 0–100 on frontend).

    Three tiers based on total interactions:
      Early   (<200)  : coverage-based — rewards having contacts + active relationships
      Growth  (200–1K): density normalised to 10 interactions/contact (not 50)
      Mature  (1K+)   : original formula, density normalised to 50

    Components (all tiers):
      40% → active relationship ratio  (ACTIVE/WARM contacts ÷ total contacts)
      35% → interaction density        (avg interactions/contact, tier-scaled)
      25% → data completeness          (contacts with confidence_score > 0.5)
    """
    try:
        row = db.execute(
            text("""
                SELECT
                    COUNT(*)                                                        AS total_contacts,
                    COUNT(*) FILTER (WHERE relationship_stage IN ('ACTIVE','WARM')) AS active_contacts,
                    AVG(COALESCE(interaction_count, 0))                             AS avg_interactions,
                    COUNT(*) FILTER (WHERE confidence_score > 0.5)::float
                        / NULLIF(COUNT(*), 0)                                       AS completeness_pct
                FROM contacts
                WHERE org_id = :org_id AND (is_archived IS NULL OR is_archived = FALSE)
            """),
            {"org_id": org_id},
        ).fetchone()

        total_interactions = db.execute(
            text("SELECT COUNT(*) FROM interactions WHERE org_id = :org_id"),
            {"org_id": org_id},
        ).scalar() or 0

        total_contacts    = int(row[0] or 0)
        active_contacts   = int(row[1] or 0)
        avg_interactions  = float(row[2] or 0)
        completeness_pct  = float(row[3] or 0)

        if total_contacts == 0:
            return 0.0

        # Active relationship ratio
        active_ratio = active_contacts / total_contacts

        # Tier-aware density normalisation
        if total_interactions < 200:
            # Early: normalise to 5 — even 5 emails per contact scores 100%
            density = min(1.0, avg_interactions / 5.0)
        elif total_interactions < 1000:
            # Growth: normalise to 10
            density = min(1.0, avg_interactions / 10.0)
        else:
            # Mature: original 50
            density = min(1.0, avg_interactions / 50.0)

        quality = (
            0.40 * active_ratio +
            0.35 * density +
            0.25 * completeness_pct
        )
        return round(min(1.0, max(0.0, quality)), 4)

    except Exception as e:
        print(f"⚠️ Graph quality computation failed for org {org_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0.0


def _record_daily_snapshot(db, org_id: str):
    """Record daily metrics snapshot for trend sparkline charts."""
    # Compute and persist graph quality score first
    quality_score = _compute_graph_quality_score(db, org_id)
    try:
        db.execute(
            text("UPDATE orgs SET graph_quality_score = :score WHERE id = :oid"),
            {"score": quality_score, "oid": org_id},
        )
        db.commit()
    except Exception:
        db.rollback()

    stats = db.execute(
        text("""
            SELECT
                (SELECT COALESCE(graph_quality_score, 0) FROM orgs WHERE id = :oid),
                (SELECT COALESCE(aer, 0) FROM orgs WHERE id = :oid),
                (SELECT COALESCE(time_saved_hours, 0) FROM orgs WHERE id = :oid),
                (SELECT COUNT(*) FROM context_calls WHERE org_id = :oid AND called_at >= CURRENT_DATE AND (source = 'api' OR source IS NULL))
        """),
        {"oid": org_id},
    ).fetchone()

    db.execute(
        text("""
            INSERT INTO daily_snapshots (org_id, snapshot_date, brain_health, aer, time_saved_hours, context_calls_count)
            VALUES (:oid, CURRENT_DATE, :brain, :aer, :time, :calls)
            ON CONFLICT (org_id, snapshot_date) DO UPDATE SET
                brain_health = EXCLUDED.brain_health,
                aer = EXCLUDED.aer,
                time_saved_hours = EXCLUDED.time_saved_hours,
                context_calls_count = EXCLUDED.context_calls_count
        """),
        {
            "oid": org_id,
            "brain": float(stats[0] or 0),
            "aer": float(stats[1] or 0),
            "time": float(stats[2] or 0),
            "calls": stats[3] or 0,
        },
    )
    db.commit()


def _precompute_bundles(db, org_id: str = None):
    """
    Pre-compute context bundles for active/warm contacts.
    Per PDF spec: bundles are pre-computed and cached, not generated on-demand.
    Only recomputes if material change detected (stage, sentiment, commitments).
    """
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
                ORDER BY c.context_score DESC NULLS LAST
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
                ORDER BY c.context_score DESC NULLS LAST
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
            db.rollback()
            print(f"  ⚠️ Bundle failed for {contact_name}: {e}")

    db.commit()
    print(f"✓ Pre-computed {precomputed} bundles ({skipped} unchanged, skipped)")


if __name__ == "__main__":
    # Support optional org_id arg: python -m app.tasks.nightly_refresh [org_id]
    org_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_nightly_refresh(org_id_arg)
