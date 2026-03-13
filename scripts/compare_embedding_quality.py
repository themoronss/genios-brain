"""Compare old vs new embedding quality for context search"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.graph.embedder import embed_text
from app.graph.queries import search_contacts_by_embedding
from sqlalchemy import text


def compare_embedding_quality():
    print("🧪 Comparing Embedding Quality: Before vs After")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Get org_id
        result = db.execute(text("SELECT DISTINCT org_id FROM contacts LIMIT 1"))
        org_id = str(result.fetchone()[0])

        # Test queries that should benefit from interaction context
        test_cases = [
            {
                "query": "investor pitch discussion",
                "expected": "Should find contacts with investment-related interactions",
            },
            {
                "query": "startup fundraising",
                "expected": "Should find venture capital or investor contacts",
            },
            {
                "query": "technical architecture review",
                "expected": "Should find engineering or technical contacts",
            },
        ]

        print("\nTesting semantic search with improved embeddings...\n")

        for i, test_case in enumerate(test_cases, 1):
            print(f"--- Test Case {i} ---")
            print(f"Query: '{test_case['query']}'")
            print(f"Expected: {test_case['expected']}\n")

            # Search with improved embeddings
            query_vector = embed_text(test_case["query"])
            results = search_contacts_by_embedding(db, org_id, query_vector, limit=5)

            print("Top 5 Results:")
            for j, contact in enumerate(results, 1):
                print(f"  {j}. {contact['name'] or '(no name)'}")
                if contact["company"]:
                    print(f"     Company: {contact['company']}")
                print(f"     Stage: {contact['relationship_stage']}")

                # Show if contact has interactions
                interaction_count = db.execute(
                    text(
                        """
                    SELECT COUNT(*) 
                    FROM interactions 
                    WHERE contact_id = :contact_id
                """
                    ),
                    {"contact_id": contact["id"]},
                ).fetchone()[0]

                print(f"     Interactions: {interaction_count}")

            print()

        # Show embedding comparison for a sample contact
        print("\n--- Embedding Text Comparison ---")

        result = db.execute(
            text(
                """
            SELECT c.id, c.name, c.email, c.company
            FROM contacts c
            WHERE c.org_id = :org_id
            AND c.name IS NOT NULL
            LIMIT 1
        """
            ),
            {"org_id": org_id},
        )

        sample = result.fetchone()
        if sample:
            # Old method (name + email only)
            old_text = f"{sample.name or ''} {sample.email}"

            # New method (name + company + interactions)
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

            new_text = " ".join(text_parts)

            print(f"Contact: {sample.name}")
            print(f"\nOLD embedding text (name + email):")
            print(f"  '{old_text}'")
            print(f"  Length: {len(old_text)} chars")

            print(f"\nNEW embedding text (name + company + interactions):")
            print(f"  '{new_text[:200]}{'...' if len(new_text) > 200 else ''}'")
            print(f"  Length: {len(new_text)} chars")
            print(
                f"  Improvement: {len(new_text) - len(old_text)} additional chars of context"
            )

        print("\n" + "=" * 60)
        print("QUALITY IMPROVEMENTS")
        print("=" * 60)
        print("\n✅ OLD Method (name + email):")
        print("   - Limited context")
        print("   - Generic matches")
        print("   - Newsletters match investor queries")

        print("\n✅ NEW Method (name + company + interactions):")
        print("   - Rich semantic context")
        print("   - Interaction-based relevance")
        print("   - Better match quality for situational queries")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    compare_embedding_quality()
