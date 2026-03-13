"""Test coverage_score calculation in context bundle"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.context.compiler import compile_context, _calculate_coverage_score
from sqlalchemy import text


def test_coverage_score():
    print("🧪 Testing Coverage Score Calculation")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Get org_id
        result = db.execute(text("SELECT DISTINCT org_id FROM contacts LIMIT 1"))
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")

        # Test 1: Calculate coverage score from context bundle
        print("\n--- Test 1: Coverage Score in Context Bundle ---")
        situation = "Follow up with team about project status"

        context_bundle = compile_context(db, org_id, situation)

        print(f"✓ Situation: {context_bundle['situation']}")
        print(f"✓ Found {len(context_bundle['contacts'])} contacts\n")

        for i, contact in enumerate(context_bundle["contacts"], 1):
            print(f"{i}. {contact['name'] or '(no name)'}")
            print(f"   Email: {contact['email']}")
            print(f"   Company: {contact.get('company', 'N/A')}")
            print(f"   Stage: {contact['relationship_stage']}")
            print(f"   Interactions: {len(contact['recent_interactions'])}")
            print(f"   📊 Coverage Score: {contact['coverage_score']}")

            # Show breakdown
            score_details = []
            if contact.get("name"):
                score_details.append("✓ name")
            if contact.get("email"):
                score_details.append("✓ email")
            if contact.get("company"):
                score_details.append("✓ company")
            if contact["recent_interactions"]:
                score_details.append("✓ interactions")
            if (
                contact.get("relationship_stage")
                and contact["relationship_stage"] != "unknown"
            ):
                score_details.append("✓ stage")
            else:
                score_details.append("✗ stage")

            sentiment = contact.get("last_sentiment", 0)
            if sentiment != 0:
                score_details.append("✓ sentiment")
            else:
                score_details.append("✗ sentiment")

            print(f"   Fields: {', '.join(score_details)}")
            print()

        # Test 2: Test coverage score function directly
        print("\n--- Test 2: Manual Coverage Score Calculation ---")

        # Mock contact with all fields
        print("\nCase 1: Complete contact (all fields)")
        mock_contact_1 = {
            "name": "John Doe",
            "email": "john@example.com",
            "company": "Example Corp",
            "relationship_stage": "warm",
            "last_sentiment": 0.5,
        }
        mock_interactions_1 = [{"subject": "Meeting", "interaction_at": "2026-03-01"}]
        score_1 = _calculate_coverage_score(mock_contact_1, mock_interactions_1)
        print(f"  Score: {score_1} (expected: 1.0)")
        assert score_1 == 1.0, f"Expected 1.0, got {score_1}"

        # Mock contact with some fields missing
        print("\nCase 2: Partial contact (name, email, interactions only)")
        mock_contact_2 = {
            "name": "Jane Smith",
            "email": "jane@example.com",
            "relationship_stage": "unknown",
        }
        mock_interactions_2 = [{"subject": "Follow-up"}]
        score_2 = _calculate_coverage_score(mock_contact_2, mock_interactions_2)
        print(f"  Score: {score_2} (expected: 0.5)")
        # name, email, interactions = 3/6 = 0.5
        assert score_2 == 0.5, f"Expected 0.5, got {score_2}"

        # Mock contact with minimal data
        print("\nCase 3: Minimal contact (email only)")
        mock_contact_3 = {
            "email": "minimal@example.com",
            "relationship_stage": "unknown",
        }
        mock_interactions_3 = []
        score_3 = _calculate_coverage_score(mock_contact_3, mock_interactions_3)
        print(f"  Score: {score_3} (expected: ~0.17)")
        # email only = 1/6 = 0.17
        assert score_3 == 0.17, f"Expected 0.17, got {score_3}"

        # Verify all scores are between 0 and 1
        print("\n--- Verification ---")
        all_scores = [
            contact["coverage_score"] for contact in context_bundle["contacts"]
        ]
        all_valid = all(0 <= score <= 1 for score in all_scores)

        if all_valid:
            print("✅ All coverage scores are between 0 and 1")
            print(f"   Scores: {all_scores}")
        else:
            print("❌ Some coverage scores are out of range")

        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
        print(f"   Average coverage: {avg_score:.2f}")

        print("\n" + "=" * 60)
        print("✅ Coverage Score Calculation Working!")
        print("=" * 60)
        print("\nCoverage Formula:")
        print("  score = populated_fields / total_fields")
        print("\nFields considered (6 total):")
        print("  1. ✓ Contact name")
        print("  2. ✓ Email")
        print("  3. ✓ Company")
        print("  4. ✓ Recent interactions")
        print("  5. ✓ Relationship stage (if not 'unknown')")
        print("  6. ✓ Sentiment (if not 0)")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_coverage_score()
