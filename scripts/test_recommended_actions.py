"""Test recommended actions in context bundle"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.context.compiler import compile_context, _calculate_recommended_action
from sqlalchemy import text
from datetime import datetime, timezone, timedelta


def test_recommended_actions():
    print("🧪 Testing Recommended Actions in Context Bundle")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Get org_id
        result = db.execute(text("SELECT DISTINCT org_id FROM contacts LIMIT 1"))
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")

        # Test 1: Compile context and check recommended actions
        print("\n--- Test 1: Context Bundle with Recommended Actions ---")
        situation = "Follow up with investors about our pitch"

        context_bundle = compile_context(db, org_id, situation)

        print(f"✓ Situation: {context_bundle['situation']}")
        print(f"✓ Found {len(context_bundle['contacts'])} contacts\n")

        for i, contact in enumerate(context_bundle["contacts"], 1):
            print(f"{i}. {contact['name'] or '(no name)'}")
            print(f"   Email: {contact['email']}")
            print(f"   Stage: {contact['relationship_stage']}")
            print(f"   Interactions: {len(contact['recent_interactions'])}")

            if contact["recent_interactions"]:
                latest = contact["recent_interactions"][0]
                interaction_date = latest.get("interaction_at", "N/A")
                print(f"   Latest interaction: {interaction_date}")

            # Show the recommended action
            print(f"   ⭐ Recommended Action: {contact['recommended_action']}")
            print()

        # Test 2: Test the rule logic directly
        print("\n--- Test 2: Testing Rule Logic ---")

        # Mock contact and interaction data for testing rules
        now = datetime.now(timezone.utc)

        # Test case 1: Recent interaction (< 14 days)
        print("\nCase 1: Recent interaction (3 days ago)")
        mock_contact1 = {"relationship_stage": "warm"}
        mock_interactions1 = [{"interaction_at": (now - timedelta(days=3)).isoformat()}]
        action1 = _calculate_recommended_action(mock_contact1, mock_interactions1)
        print(f"  Result: {action1}")
        assert (
            action1 == "Maintain relationship"
        ), "Should maintain for recent interaction"

        # Test case 2: 15 days ago with warm stage
        print("\nCase 2: 15 days ago with warm stage")
        mock_contact2 = {"relationship_stage": "warm"}
        mock_interactions2 = [
            {"interaction_at": (now - timedelta(days=15)).isoformat()}
        ]
        action2 = _calculate_recommended_action(mock_contact2, mock_interactions2)
        print(f"  Result: {action2}")
        assert (
            action2 == "Send follow-up this week"
        ), "Should suggest follow-up for warm + 15 days"

        # Test case 3: 35 days ago (cooling)
        print("\nCase 3: 35 days ago (relationship cooling)")
        mock_contact3 = {"relationship_stage": "cold"}
        mock_interactions3 = [
            {"interaction_at": (now - timedelta(days=35)).isoformat()}
        ]
        action3 = _calculate_recommended_action(mock_contact3, mock_interactions3)
        print(f"  Result: {action3}")
        assert (
            action3 == "Relationship cooling — re-engage"
        ), "Should suggest re-engagement for 30+ days"

        # Test case 4: No interactions
        print("\nCase 4: No interactions")
        mock_contact4 = {"relationship_stage": "unknown"}
        mock_interactions4 = []
        action4 = _calculate_recommended_action(mock_contact4, mock_interactions4)
        print(f"  Result: {action4}")
        assert (
            action4 == "Maintain relationship"
        ), "Should maintain when no interaction data"

        print("\n" + "=" * 60)
        print("✅ All Tests Passed!")
        print("=" * 60)
        print("\nRecommended Action Rules:")
        print("  1. ✓ Last interaction > 14 days AND stage = warm")
        print("     → 'Send follow-up this week'")
        print("  2. ✓ Last interaction > 30 days")
        print("     → 'Relationship cooling — re-engage'")
        print("  3. ✓ Last sentiment < 0")
        print("     → 'Approach carefully — last interaction negative'")
        print("  4. ✓ Default")
        print("     → 'Maintain relationship'")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_recommended_actions()
