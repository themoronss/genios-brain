"""
Weekly Graph Intelligence Report Job (Startup plan only)
Runs every Monday — summarises top relationships, at-risk contacts,
stale commitments, and cluster health.

Run directly:  python -m app.tasks.weekly_report
Or add to nightly_refresh.py on Mondays.
"""

import sys
import os
import json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import SessionLocal


def _get_monday(dt: datetime) -> datetime:
    """Return the Monday of the week containing dt."""
    return (dt - timedelta(days=dt.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def generate_report_for_org(db, org_id: str) -> dict:
    """Build the weekly intelligence report payload for one org."""

    # Top 5 strongest relationships (highest context_score)
    top = db.execute(
        text("""
            SELECT name, company, relationship_stage, context_score, interaction_count
            FROM contacts
            WHERE org_id = :oid AND (is_archived = FALSE OR is_archived IS NULL)
            ORDER BY context_score DESC NULLS LAST
            LIMIT 5
        """),
        {"oid": org_id},
    ).fetchall()

    # At-risk contacts: NEEDS_ATTENTION or last interaction > 30 days ago
    at_risk = db.execute(
        text("""
            SELECT name, company, relationship_stage,
                   EXTRACT(DAY FROM NOW() - last_interaction_at)::int AS days_since
            FROM contacts
            WHERE org_id = :oid
            AND (is_archived = FALSE OR is_archived IS NULL)
            AND (
                relationship_stage = 'NEEDS_ATTENTION'
                OR last_interaction_at < NOW() - INTERVAL '30 days'
                OR last_interaction_at IS NULL
            )
            ORDER BY last_interaction_at ASC NULLS FIRST
            LIMIT 5
        """),
        {"oid": org_id},
    ).fetchall()

    # Stale commitments: OPEN and overdue by > 7 days
    stale = db.execute(
        text("""
            SELECT ct.name, cm.description, cm.due_date,
                   EXTRACT(DAY FROM NOW() - cm.due_date)::int AS days_overdue
            FROM commitments cm
            JOIN contacts ct ON cm.contact_id = ct.id
            WHERE cm.org_id = :oid
            AND cm.status IN ('OPEN', 'OVERDUE')
            AND cm.due_date < NOW() - INTERVAL '7 days'
            ORDER BY cm.due_date ASC
            LIMIT 5
        """),
        {"oid": org_id},
    ).fetchall()

    # Cluster health: community sizes + avg composite score
    clusters = db.execute(
        text("""
            SELECT community_id, COUNT(*) AS size,
                   ROUND(AVG(context_score)::numeric, 2) AS avg_score
            FROM contacts
            WHERE org_id = :oid
            AND community_id IS NOT NULL
            AND (is_archived = FALSE OR is_archived IS NULL)
            GROUP BY community_id
            ORDER BY size DESC
            LIMIT 6
        """),
        {"oid": org_id},
    ).fetchall()

    # Period context call count (last 7 days)
    calls_this_week = db.execute(
        text("""
            SELECT COUNT(*) FROM context_calls
            WHERE org_id = :oid
            AND called_at >= NOW() - INTERVAL '7 days'
        """),
        {"oid": org_id},
    ).scalar() or 0

    # Total contacts + avg composite score
    graph_stats = db.execute(
        text("""
            SELECT COUNT(*) AS total,
                   ROUND(AVG(context_score)::numeric, 2) AS avg_score,
                   COUNT(CASE WHEN relationship_stage = 'ACTIVE' THEN 1 END) AS active_count
            FROM contacts
            WHERE org_id = :oid AND (is_archived = FALSE OR is_archived IS NULL)
        """),
        {"oid": org_id},
    ).fetchone()

    return {
        "graph": {
            "total_contacts": int(graph_stats[0] or 0),
            "active_count": int(graph_stats[2] or 0),
            "avg_score": float(graph_stats[1] or 0),
        },
        "top_relationships": [
            {
                "name": r[0],
                "company": r[1],
                "stage": r[2],
                "score": float(r[3] or 0),
                "interactions": r[4] or 0,
            }
            for r in top
        ],
        "at_risk": [
            {
                "name": r[0],
                "company": r[1],
                "stage": r[2],
                "days_since_contact": r[3],
            }
            for r in at_risk
        ],
        "stale_commitments": [
            {
                "contact": r[0],
                "description": r[1],
                "due_date": r[2].isoformat() if r[2] else None,
                "days_overdue": r[3],
            }
            for r in stale
        ],
        "clusters": [
            {
                "community_id": r[0],
                "size": int(r[1]),
                "avg_score": float(r[2] or 0),
            }
            for r in clusters
        ],
        "context_calls_this_week": int(calls_this_week),
    }


def run_weekly_reports(org_id: str = None):
    """
    Generate weekly reports for all Startup orgs (or a single org).
    Skips if a report already exists for this week's Monday.
    """
    db = SessionLocal()
    week_start = _get_monday(datetime.now(timezone.utc)).date()
    print(f"[weekly_report] Running for week starting {week_start}")

    try:
        if org_id:
            orgs = db.execute(
                text("""
                    SELECT id FROM orgs WHERE id = :oid AND subscription_tier = 'startup'
                    AND (plan_status = 'active' OR plan_status IS NULL)
                """),
                {"oid": org_id},
            ).fetchall()
        else:
            orgs = db.execute(
                text("""
                    SELECT id FROM orgs
                    WHERE subscription_tier = 'startup'
                    AND (plan_status = 'active' OR plan_status IS NULL)
                """)
            ).fetchall()

        generated = 0
        skipped = 0

        for row in orgs:
            oid = str(row[0])

            # Skip if report already generated this week
            existing = db.execute(
                text("""
                    SELECT id FROM graph_intelligence_reports
                    WHERE org_id = :oid AND week_start = :ws
                """),
                {"oid": oid, "ws": week_start},
            ).fetchone()

            if existing:
                skipped += 1
                continue

            try:
                summary = generate_report_for_org(db, oid)
                db.execute(
                    text("""
                        INSERT INTO graph_intelligence_reports (org_id, week_start, summary, generated_at)
                        VALUES (:oid, :ws, :summary, NOW())
                        ON CONFLICT (org_id, week_start) DO UPDATE
                        SET summary = EXCLUDED.summary, generated_at = NOW()
                    """),
                    {"oid": oid, "ws": week_start, "summary": json.dumps(summary)},
                )
                db.commit()
                generated += 1
                print(f"  ✓ Report generated for org {oid}")
            except Exception as e:
                db.rollback()
                print(f"  ⚠️ Report failed for org {oid}: {e}")

        print(f"[weekly_report] Done — {generated} generated, {skipped} skipped (already exists)")
    finally:
        db.close()


if __name__ == "__main__":
    org_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_weekly_reports(org_id_arg)
