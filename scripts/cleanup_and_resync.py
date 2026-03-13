#!/usr/bin/env python3
"""
Cleanup automated contacts and re-sync with improved filtering.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import SessionLocal
from app.tasks.gmail_sync import run_gmail_sync

ORG_ID = "87b0235e-e29d-468a-b841-522c13546515"

print("=" * 70)
print("  CLEANUP AND RE-SYNC")
print("=" * 70)

db = SessionLocal()

# Step 1: Count current data
print("\n📊 Current Data:")
result = db.execute(
    text("SELECT COUNT(*) FROM contacts WHERE org_id = :org_id"), {"org_id": ORG_ID}
)
contact_count = result.fetchone()[0]
print(f"   Contacts: {contact_count}")

result = db.execute(
    text("SELECT COUNT(*) FROM interactions WHERE org_id = :org_id"), {"org_id": ORG_ID}
)
interaction_count = result.fetchone()[0]
print(f"   Interactions: {interaction_count}")

# Step 2: Delete automated contacts
print("\n🧹 Deleting automated emails...")

automated_patterns = [
    "%noreply%",
    "%no-reply%",
    "%donotreply%",
    "%notification%",
    "%newsletter%",
    "%digest%",
    "%alert%",
    "%jobalert%",
]

deleted_contacts = 0
for pattern in automated_patterns:
    result = db.execute(
        text("DELETE FROM contacts WHERE org_id = :org_id AND email LIKE :pattern"),
        {"org_id": ORG_ID, "pattern": pattern},
    )
    deleted_contacts += result.rowcount

db.commit()
print(f"   Deleted {deleted_contacts} automated contacts")

# Step 3: Re-sync with new filters
print("\n📥 Re-syncing emails with improved filtering...")
print("   This will fetch up to 100 emails and filter automated senders\n")

run_gmail_sync(ORG_ID, max_emails=100)

# Step 4: Show new stats
print("\n📊 After Cleanup:")
result = db.execute(
    text("SELECT COUNT(*) FROM contacts WHERE org_id = :org_id"), {"org_id": ORG_ID}
)
new_contact_count = result.fetchone()[0]
print(f"   Contacts: {new_contact_count}")

result = db.execute(
    text("SELECT COUNT(*) FROM interactions WHERE org_id = :org_id"), {"org_id": ORG_ID}
)
new_interaction_count = result.fetchone()[0]
print(f"   Interactions: {new_interaction_count}")

# Check for contacts with company
result = db.execute(
    text(
        "SELECT COUNT(*) FROM contacts WHERE org_id = :org_id AND company IS NOT NULL"
    ),
    {"org_id": ORG_ID},
)
with_company = result.fetchone()[0]
print(f"   Contacts with company: {with_company}")

print("\n✅ Cleanup and re-sync complete!")
print("   Run: ./venv/bin/python scripts/test_data_quality_deep.py")
print("   To verify data quality improvement")

db.close()
