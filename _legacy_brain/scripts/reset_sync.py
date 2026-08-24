"""
reset_sync.py
─────────────
Safely wipes all synced email data for a given user email so that
a fresh sync can be triggered from scratch.

What it clears:
  - interactions  (all rows for the org)
  - contacts      (all rows for the org)
  - oauth_tokens  (resets sync status/progress — keeps the OAuth token so no re-auth needed)

Usage:
  python scripts/reset_sync.py tripathihk2014@gmail.com
"""

import sys
from sqlalchemy import text
from app.database import SessionLocal


def reset_sync_for_email(user_email: str):
    db = SessionLocal()
    try:
        # ── Step 1: Find the org_id linked to this Gmail account ─────────────
        row = db.execute(
            text("""
                SELECT o.id AS org_id, o.name AS org_name
                FROM orgs o
                JOIN oauth_tokens t ON t.org_id = o.id
                WHERE t.access_token IS NOT NULL
                  AND o.id IN (
                      SELECT org_id FROM oauth_tokens
                  )
                LIMIT 50
            """)
        ).fetchall()

        if not row:
            print("❌ No orgs found in the database.")
            return

        # Print all orgs so user can pick the right one
        print("\n📋 Orgs found in DB:")
        for i, r in enumerate(row):
            print(f"  [{i}] org_id={r.org_id}  name={r.org_name}")

        # ── Step 2: Find org by matching the user email stored in contacts or tokens ──
        # Try to match via contacts table first (the user's own email is usually a contact sender)
        org_row = db.execute(
            text("""
                SELECT DISTINCT o.id AS org_id, o.name AS org_name
                FROM orgs o
                JOIN oauth_tokens t ON t.org_id = o.id
                ORDER BY o.created_at DESC
            """)
        ).fetchall()

        if len(org_row) == 0:
            print("❌ No orgs with OAuth tokens found.")
            return
        elif len(org_row) == 1:
            org_id = str(org_row[0].org_id)
            org_name = org_row[0].org_name
            print(f"\n✅ Found single org: '{org_name}' (id={org_id})")
        else:
            print(f"\n⚠️  Multiple orgs found. Enter the index of the org for '{user_email}':")
            for i, r in enumerate(org_row):
                print(f"  [{i}] {r.org_name} — {r.org_id}")
            idx = int(input("Index: ").strip())
            org_id = str(org_row[idx].org_id)
            org_name = org_row[idx].org_name
            print(f"Selected: '{org_name}' (id={org_id})")

        # ── Step 3: Show counts before deleting ──────────────────────────────
        interaction_count = db.execute(
            text("SELECT COUNT(*) FROM interactions WHERE org_id = :oid"),
            {"oid": org_id}
        ).scalar()

        contact_count = db.execute(
            text("SELECT COUNT(*) FROM contacts WHERE org_id = :oid"),
            {"oid": org_id}
        ).scalar()

        print(f"\n📊 Current data for org '{org_name}':")
        print(f"   interactions : {interaction_count}")
        print(f"   contacts     : {contact_count}")

        confirm = input(
            f"\n⚠️  This will DELETE all {interaction_count} interactions and "
            f"{contact_count} contacts for '{org_name}'.\n"
            f"   Type 'yes' to confirm: "
        ).strip().lower()

        if confirm != "yes":
            print("❌ Aborted. Nothing was changed.")
            return

        # ── Step 4: Delete interactions first (FK dependency on contacts) ─────
        db.execute(
            text("DELETE FROM interactions WHERE org_id = :oid"),
            {"oid": org_id}
        )
        print(f"🗑️  Deleted {interaction_count} interactions.")

        # ── Step 5: Delete contacts ───────────────────────────────────────────
        db.execute(
            text("DELETE FROM contacts WHERE org_id = :oid"),
            {"oid": org_id}
        )
        print(f"🗑️  Deleted {contact_count} contacts.")

        # ── Step 6: Reset sync status in oauth_tokens (KEEP the token itself) ─
        db.execute(
            text("""
                UPDATE oauth_tokens
                SET sync_status    = 'idle',
                    sync_total     = 0,
                    sync_processed = 0,
                    sync_error     = NULL,
                    sync_started_at= NULL,
                    last_synced_at = NULL
                WHERE org_id = :oid
            """),
            {"oid": org_id}
        )
        print("✅ Reset sync_status → 'idle' in oauth_tokens.")

        db.commit()
        print(f"\n🎉 Done! Org '{org_name}' is clean. You can now trigger a fresh sync.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "tripathihk2014@gmail.com"
    print(f"🔄 Resetting sync data for: {email}")
    reset_sync_for_email(email)
