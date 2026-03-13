"""Test vector search functionality"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.graph.embedder import embed_text
from app.graph.queries import search_contacts_by_embedding
import uuid


def test_vector_search():
    print("🧪 Testing Vector Search...")

    db = SessionLocal()

    try:
        # First, check if we have any contacts with embeddings
        from sqlalchemy import text

        result = db.execute(
            text("SELECT COUNT(*) FROM contacts WHERE embedding IS NOT NULL")
        )
        count = result.fetchone()[0]
        print(f"✓ Found {count} contacts with embeddings")

        if count == 0:
            print("⚠️  No contacts with embeddings found. Run test_embeddings.py first.")
            return

        # Get an org_id from existing contacts
        result = db.execute(
            text(
                "SELECT DISTINCT org_id FROM contacts WHERE embedding IS NOT NULL LIMIT 1"
            )
        )
        org_id = result.fetchone()[0]
        print(f"✓ Using org_id: {org_id}")

        # Test 1: Search with a sample query
        print("\n--- Test 1: Search for 'project manager' ---")
        query_vector = embed_text("project manager from tech company")
        results = search_contacts_by_embedding(db, org_id, query_vector, limit=3)

        print(f"✓ Found {len(results)} contacts:")
        for i, contact in enumerate(results, 1):
            print(f"  {i}. {contact['name']} ({contact['email']})")
            print(f"     Company: {contact['company']}")
            print(f"     Stage: {contact['relationship_stage']}")

        # Test 2: Search with another query
        print("\n--- Test 2: Search for 'business development' ---")
        query_vector = embed_text("business development executive")
        results = search_contacts_by_embedding(db, org_id, query_vector, limit=2)

        print(f"✓ Found {len(results)} contacts:")
        for i, contact in enumerate(results, 1):
            print(f"  {i}. {contact['name']} ({contact['email']})")

        print("\n✅ Vector search is working!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_vector_search()
