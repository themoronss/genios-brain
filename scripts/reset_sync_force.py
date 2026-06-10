"""
reset_sync_force.py
───────────────────
FORCE resets all synced data for the MOST RECENT org (or first org found).
No prompts — runs immediately.

Clears:
  - interactions  (all for org)
  - contacts      (all for org)  
  - oauth_tokens  sync_status → 'idle' (OAuth token is KEPT)

Usage:
  python scripts/reset_sync_force.py
"""

from sqlalchemy import text
from app.database import SessionLocal


def force_reset():
    db = SessionLocal()
    try:
        # Find the org (if only one org exists, use it)
        orgs = db.execute(
            text("""
                SELECT o.id::text AS org_id, o.name AS org_name, t.sync_status
                FROM orgs o
                JOIN oauth_tokens t ON t.org_id = o.id
                ORDER BY o.created_at DESC
            """)
        ).fetchall()

        if not orgs:
            print("❌ No orgs with OAuth tokens found.")
            return

        print(f"Found {len(orgs)} org(s):")
        for r in orgs:
            print(f"  → org: '{r.org_name}' | id: {r.org_id} | sync_status: {r.sync_status}")

        # Use the first (most recent) org
        org_id = orgs[0].org_id
        org_name = orgs[0].org_name
        print(f"\n🎯 Resetting org: '{org_name}' (id={org_id})")

        # Count before
        ic = db.execute(text("SELECT COUNT(*) FROM interactions WHERE org_id = :oid"), {"oid": org_id}).scalar()
        cc = db.execute(text("SELECT COUNT(*) FROM contacts WHERE org_id = :oid"), {"oid": org_id}).scalar()
        print(f"   Will delete: {ic} interactions, {cc} contacts")

        # Delete interactions (FK first)
        db.execute(text("DELETE FROM interactions WHERE org_id = :oid"), {"oid": org_id})
        print(f"🗑️  Deleted {ic} interactions")

        # Delete contacts
        db.execute(text("DELETE FROM contacts WHERE org_id = :oid"), {"oid": org_id})
        print(f"🗑️  Deleted {cc} contacts")

        # Reset sync status (keep token)
        db.execute(
            text("""
                UPDATE oauth_tokens
                SET sync_status     = 'idle',
                    sync_total      = 0,
                    sync_processed  = 0,
                    sync_error      = NULL,
                    sync_started_at = NULL,
                    last_synced_at  = NULL
                WHERE org_id = :oid
            """),
            {"oid": org_id}
        )
        print("✅ Reset sync_status → 'idle'")

        db.commit()
        print(f"\n🎉 Done! '{org_name}' is clean. Trigger a fresh sync from the dashboard.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    force_reset()
