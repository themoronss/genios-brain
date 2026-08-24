"""
Run migrations 047 (refresh_jobs) and 048 (pgvector 768-dim).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text


def run_migration(filepath: str):
    print(f"\n{'='*60}")
    print(f"Running: {filepath}")
    print(f"{'='*60}")

    with open(filepath, "r") as f:
        migration_sql = f.read()

    with engine.connect() as conn:
        statements = [s.strip() for s in migration_sql.split(";") if s.strip()]

        for statement in statements:
            # Skip comment-only lines
            lines = [l for l in statement.split("\n") if not l.strip().startswith("--")]
            clean = "\n".join(lines).strip()
            if not clean:
                continue

            try:
                conn.execute(text(statement))
                conn.commit()
                preview = statement.replace("\n", " ")[:80]
                print(f"  ✓ {preview}...")
            except Exception as e:
                print(f"  ✗ Error: {e}")
                print(f"    Statement: {statement[:120]}...")


if __name__ == "__main__":
    run_migration("migrations/047_refresh_jobs.sql")
    run_migration("migrations/048_pgvector_768.sql")
    print("\n✓ All migrations completed!")
