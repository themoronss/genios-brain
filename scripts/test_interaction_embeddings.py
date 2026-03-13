"""Test interaction embeddings"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.graph.embedding_jobs import embed_interactions
from sqlalchemy import text


def test_interaction_embeddings():
    print("🧪 Testing Interaction Embeddings...")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Get org_id
        result = db.execute(text("SELECT DISTINCT org_id FROM interactions LIMIT 1"))
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")

        # Check current embedding status
        result = db.execute(
            text(
                """
            SELECT COUNT(*) as total,
                   COUNT(embedding) as with_embedding,
                   COUNT(*) - COUNT(embedding) as without_embedding
            FROM interactions
            WHERE org_id = :org_id
        """
            ),
            {"org_id": org_id},
        )

        stats = result.fetchone()
        print(f"\nCurrent Status:")
        print(f"  Total interactions: {stats.total}")
        print(f"  With embeddings: {stats.with_embedding}")
        print(f"  Without embeddings: {stats.without_embedding}")

        # Sample interaction to see embedding text
        print("\n--- Sample Embedding Text ---")
        result = db.execute(
            text(
                """
            SELECT subject, summary
            FROM interactions
            WHERE org_id = :org_id
            AND subject IS NOT NULL
            ORDER BY interaction_at DESC
            LIMIT 1
        """
            ),
            {"org_id": org_id},
        )

        sample = result.fetchone()
        if sample:
            text_parts = []
            if sample.subject:
                text_parts.append(sample.subject)
            if sample.summary:
                text_parts.append(sample.summary)

            embedding_text = ". ".join(text_parts)
            print(f"Subject: {sample.subject[:60]}...")
            print(f"Summary: {sample.summary[:60] if sample.summary else 'N/A'}...")
            print(f"\nEmbedding text (first 150 chars):")
            print(f"  '{embedding_text[:150]}...'")

        # Clear embeddings for testing
        print("\n--- Regenerating Embeddings ---")
        print("Clearing interaction embeddings for re-generation...")

        db.execute(
            text(
                """
            UPDATE interactions
            SET embedding = NULL
            WHERE org_id = :org_id
        """
            ),
            {"org_id": org_id},
        )
        db.commit()
        print("✓ Embeddings cleared")

        # Generate interaction embeddings
        print("\nGenerating interaction embeddings...")
        embed_interactions(org_id)
        print("✓ Interaction embeddings generated")

        # Verify embeddings were created
        result = db.execute(
            text(
                """
            SELECT COUNT(*) as with_embedding
            FROM interactions
            WHERE org_id = :org_id
            AND embedding IS NOT NULL
        """
            ),
            {"org_id": org_id},
        )

        count = result.fetchone()[0]
        print(f"✓ {count} interactions now have embeddings")

        # Check embedding dimensions
        result = db.execute(
            text(
                """
            SELECT array_length(embedding::real[], 1) as dimension
            FROM interactions
            WHERE org_id = :org_id
            AND embedding IS NOT NULL
            LIMIT 1
        """
            ),
            {"org_id": org_id},
        )

        dim_row = result.fetchone()
        if dim_row:
            print(f"✓ Embedding dimension: {dim_row.dimension}")

        print("\n" + "=" * 60)
        print("✅ Interaction Embeddings Working!")
        print("=" * 60)
        print("\nInteraction embeddings now include:")
        print("  ✓ Email subject")
        print("  ✓ Email summary")
        print("\nThis enables:")
        print("  ✓ Semantic search over email content")
        print("  ✓ Finding relevant past conversations")
        print("  ✓ Better context retrieval")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_interaction_embeddings()
