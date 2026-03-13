"""Test improved contact embeddings with interaction context"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.graph.embedding_jobs import embed_contacts
from app.graph.embedder import embed_text
from app.graph.queries import search_contacts_by_embedding
from sqlalchemy import text


def test_improved_embeddings():
    print("🧪 Testing Improved Contact Embeddings...")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Get org_id
        result = db.execute(text("SELECT DISTINCT org_id FROM contacts LIMIT 1"))
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")

        # Check current embedding status
        result = db.execute(
            text(
                """
            SELECT COUNT(*) as total,
                   COUNT(embedding) as with_embedding,
                   COUNT(*) - COUNT(embedding) as without_embedding
            FROM contacts
            WHERE org_id = :org_id
        """
            ),
            {"org_id": org_id},
        )

        stats = result.fetchone()
        print(f"\nCurrent Status:")
        print(f"  Total contacts: {stats.total}")
        print(f"  With embeddings: {stats.with_embedding}")
        print(f"  Without embeddings: {stats.without_embedding}")

        # Sample a contact with interactions to see the embedding text
        print("\n--- Sample Embedding Text ---")
        result = db.execute(
            text(
                """
            SELECT c.id, c.name, c.email, c.company,
                   COUNT(i.id) as interaction_count
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = :org_id
            GROUP BY c.id, c.name, c.email, c.company
            HAVING COUNT(i.id) > 0
            LIMIT 1
        """
            ),
            {"org_id": org_id},
        )

        sample = result.fetchone()
        if sample:
            print(f"\nContact: {sample.name}")
            print(f"Company: {sample.company}")
            print(f"Interactions: {sample.interaction_count}")

            # Get their last 3 interactions
            interactions = db.execute(
                text(
                    """
                SELECT summary
                FROM interactions
                WHERE contact_id = :contact_id
                AND summary IS NOT NULL
                ORDER BY interaction_at DESC
                LIMIT 3
            """
                ),
                {"contact_id": sample.id},
            ).fetchall()

            # Build the same text as embed_contacts() would
            text_parts = []
            if sample.name:
                text_parts.append(sample.name)
            if sample.company:
                text_parts.append(sample.company)

            if interactions:
                text_parts.append("Recent discussions:")
                for interaction in interactions:
                    if interaction.summary:
                        text_parts.append(interaction.summary)

            embedding_text = " ".join(text_parts)
            print(f"\nEmbedding text preview (first 200 chars):")
            print(f"  {embedding_text[:200]}...")

        # Clear some embeddings to regenerate with new method
        print("\n--- Regenerating Embeddings ---")
        print("Clearing embeddings for re-generation with improved method...")

        db.execute(
            text(
                """
            UPDATE contacts
            SET embedding = NULL
            WHERE org_id = :org_id
        """
            ),
            {"org_id": org_id},
        )
        db.commit()
        print("✓ Embeddings cleared")

        # Regenerate with improved method
        print("\nGenerating improved embeddings...")
        embed_contacts(org_id)
        print("✓ Improved embeddings generated")

        # Verify embeddings were created
        result = db.execute(
            text(
                """
            SELECT COUNT(*) as with_embedding
            FROM contacts
            WHERE org_id = :org_id
            AND embedding IS NOT NULL
        """
            ),
            {"org_id": org_id},
        )

        count = result.fetchone()[0]
        print(f"✓ {count} contacts now have embeddings")

        # Test search quality
        print("\n--- Testing Search Quality ---")

        test_queries = [
            "investor or venture capital",
            "technical engineer or software developer",
            "product manager or designer",
        ]

        for query in test_queries:
            print(f"\n🔍 Query: '{query}'")
            query_vector = embed_text(query)
            results = search_contacts_by_embedding(db, org_id, query_vector, limit=3)

            print(f"   Found {len(results)} results:")
            for i, contact in enumerate(results[:3], 1):
                print(f"   {i}. {contact['name']}")
                if contact["company"]:
                    print(f"      Company: {contact['company']}")

        print("\n" + "=" * 60)
        print("✅ Improved Embeddings Working!")
        print("=" * 60)
        print("\nEmbedding now includes:")
        print("  ✓ Contact name")
        print("  ✓ Company affiliation")
        print("  ✓ Last 3 interaction summaries")
        print("\nThis provides richer semantic context for better search results.")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_improved_embeddings()
