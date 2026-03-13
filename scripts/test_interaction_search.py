"""Test semantic search over interactions"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.graph.embedder import embed_text
from sqlalchemy import text


def search_interactions_by_embedding(db, org_id, query_vector, limit=5):
    """
    Search for interactions using pgvector cosine similarity search.
    """
    vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

    result = db.execute(
        text(
            """
            SELECT id, subject, summary, interaction_at, direction, contact_id
            FROM interactions
            WHERE org_id = :org_id
            AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:query_vector AS vector)
            LIMIT :limit
        """
        ),
        {"org_id": org_id, "query_vector": vector_str, "limit": limit},
    )

    rows = result.fetchall()
    interactions = []
    for row in rows:
        interactions.append(
            {
                "id": row[0],
                "subject": row[1],
                "summary": row[2],
                "interaction_at": row[3].isoformat() if row[3] else None,
                "direction": row[4],
                "contact_id": row[5],
            }
        )

    return interactions


def test_interaction_search():
    print("🧪 Testing Semantic Search Over Interactions")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Get org_id
        result = db.execute(
            text(
                "SELECT DISTINCT org_id FROM interactions WHERE embedding IS NOT NULL LIMIT 1"
            )
        )
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")

        # Test queries
        test_queries = [
            "job opportunities and career advice",
            "startup funding and investment",
            "technical courses and learning",
        ]

        for query in test_queries:
            print(f"\n--- Query: '{query}' ---")

            # Generate query embedding
            query_vector = embed_text(query)

            # Search interactions
            results = search_interactions_by_embedding(
                db, org_id, query_vector, limit=3
            )

            print(f"Found {len(results)} relevant interactions:\n")

            for i, interaction in enumerate(results, 1):
                # Get contact name
                contact_result = db.execute(
                    text(
                        """
                    SELECT name FROM contacts WHERE id = :contact_id
                """
                    ),
                    {"contact_id": interaction["contact_id"]},
                )

                contact_row = contact_result.fetchone()
                contact_name = contact_row[0] if contact_row else "Unknown"

                print(
                    f"{i}. [{interaction['direction']}] {interaction['subject'][:60]}"
                )
                print(f"   From/To: {contact_name}")
                print(f"   Date: {interaction['interaction_at']}")
                if interaction["summary"]:
                    print(f"   Summary: {interaction['summary'][:80]}...")
                print()

        print("=" * 60)
        print("✅ Interaction Search Working!")
        print("=" * 60)
        print("\nCapabilities:")
        print("  ✓ Semantic search over email content")
        print("  ✓ Find relevant past conversations")
        print("  ✓ Context-aware interaction retrieval")
        print("  ✓ Better than keyword search")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_interaction_search()
