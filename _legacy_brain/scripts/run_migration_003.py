"""
Run migration 003 - Add extraction fields
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text

migration_file = "migrations/003_add_extraction_fields.sql"

print(f"Running migration: {migration_file}")

with open(migration_file, "r") as f:
    migration_sql = f.read()

with engine.connect() as conn:
    # Execute each statement separately
    statements = [s.strip() for s in migration_sql.split(";") if s.strip()]

    for statement in statements:
        try:
            conn.execute(text(statement))
            conn.commit()
            print(f"✓ Executed: {statement[:60]}...")
        except Exception as e:
            print(f"✗ Error: {e}")
            print(f"  Statement: {statement[:100]}...")

print("\n✓ Migration 003 completed!")
