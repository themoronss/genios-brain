"""
Get a valid org_id from the database
"""

import sys

sys.path.append("/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Get a valid org_id
result = db.execute(text("SELECT DISTINCT org_id FROM contacts LIMIT 1")).fetchone()
if result:
    print(f"Valid org_id: {result[0]}")
else:
    print("No org_ids found in database")

db.close()
