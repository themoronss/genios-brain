"""
Nightly Relationship Refresh Job
Recalculates relationship stages for all contacts
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.graph.relationship_calculator import recalculate_all_relationships


def run_nightly_refresh():
    """
    Run nightly refresh job to recalculate all relationship stages.
    """
    print(f"Starting nightly relationship refresh at {datetime.now()}")

    db = SessionLocal()

    try:
        updated_count = recalculate_all_relationships(db)
        print(f"✓ Successfully updated {updated_count} contacts")
    except Exception as e:
        print(f"✗ Error during nightly refresh: {e}")
        raise
    finally:
        db.close()

    print(f"Completed nightly refresh at {datetime.now()}")


if __name__ == "__main__":
    run_nightly_refresh()
