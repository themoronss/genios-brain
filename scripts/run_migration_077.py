"""
Run migration 077 — concurrent index build on interactions.

CREATE INDEX CONCURRENTLY cannot run inside a transaction, so this runner
opens an AUTOCOMMIT connection and executes each statement standalone.
Safe to re-run — statements are IF NOT EXISTS.

Usage:
    python scripts/run_migration_077.py

Env: reads DATABASE_URL from .env via app.database.engine.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text


MIGRATION_PATH = "migrations/077_outbound_topic_perf.sql"


def _split_statements(sql: str):
    """Yield non-comment statements from a SQL file."""
    # Strip line comments, then split on ;
    lines = []
    for raw in sql.splitlines():
        stripped = raw.strip()
        if stripped.startswith("--"):
            continue
        lines.append(raw)
    joined = "\n".join(lines)
    for stmt in joined.split(";"):
        clean = stmt.strip()
        if clean:
            yield clean


def main():
    with open(MIGRATION_PATH, "r") as f:
        sql = f.read()

    # AUTOCOMMIT is required for CREATE INDEX CONCURRENTLY.
    autocommit_engine = engine.execution_options(isolation_level="AUTOCOMMIT")

    print(f"Running: {MIGRATION_PATH}")
    print("=" * 60)

    with autocommit_engine.connect() as conn:
        for i, stmt in enumerate(_split_statements(sql), start=1):
            preview = stmt.replace("\n", " ")[:90]
            print(f"[{i}] {preview}...")
            t0 = time.time()
            try:
                conn.execute(text(stmt))
                dt = time.time() - t0
                print(f"    ✓ done in {dt:.2f}s")
            except Exception as e:
                print(f"    ✗ FAILED: {e}")
                sys.exit(1)

    print("=" * 60)
    print("Migration 077 complete.")


if __name__ == "__main__":
    main()
