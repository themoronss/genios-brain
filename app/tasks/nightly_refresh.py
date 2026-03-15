"""
Nightly Relationship Refresh Job
Recalculates relationship stages for all contacts.
Can be run directly: python -m app.tasks.nightly_refresh
Or scheduled via cron: 0 2 * * * cd /path/to/genios-brain && venv/bin/python -m app.tasks.nightly_refresh
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.graph.relationship_calculator import recalculate_all_relationships


def run_nightly_refresh(org_id: str = None):
    """
    Run nightly refresh job to recalculate all relationship stages.

    Args:
        org_id: Optional — limit refresh to a single org (used for post-sync refresh).
                If None, recalculates all orgs.
    """
    scope = f"org {org_id}" if org_id else "ALL orgs"
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting nightly relationship refresh for {scope}...")

    db = SessionLocal()

    try:
        updated_count = recalculate_all_relationships(db, org_id)
        print(f"✓ Successfully updated {updated_count} contacts for {scope}")
        return updated_count
    except Exception as e:
        print(f"✗ Error during nightly refresh: {e}")
        raise
    finally:
        db.close()

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Completed nightly refresh for {scope}")


if __name__ == "__main__":
    # Support optional org_id arg: python -m app.tasks.nightly_refresh [org_id]
    org_id_arg = sys.argv[1] if len(sys.argv) > 1 else None
    run_nightly_refresh(org_id_arg)
