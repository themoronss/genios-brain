"""Test context compiler functionality"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.context.compiler import compile_context
from sqlalchemy import text
import json


def test_context_compiler():
    print("🧪 Testing Context Compiler...")

    db = SessionLocal()

    try:
        # Get an org_id from existing contacts
        result = db.execute(
            text(
                "SELECT DISTINCT org_id FROM contacts WHERE embedding IS NOT NULL LIMIT 1"
            )
        )
        org_id = result.fetchone()[0]
        print(f"✓ Using org_id: {org_id}")

        # Test 1: Compile context for a situation
        situation = "Follow up with investor about our pitch"
        print(f"\n📝 Situation: '{situation}'")
        print("🔄 Compiling context...")

        context_bundle = compile_context(db, str(org_id), situation)

        print(f"\n✓ Context bundle generated!")
        print(f"✓ Found {len(context_bundle['contacts'])} relevant contacts")

        # Display results
        print("\n" + "=" * 60)
        print("CONTEXT BUNDLE")
        print("=" * 60)
        print(f"Situation: {context_bundle['situation']}")
        print(f"\nRelevant Contacts ({len(context_bundle['contacts'])}):")

        for i, contact in enumerate(context_bundle["contacts"], 1):
            print(f"\n{i}. {contact['name']} ({contact['email']})")
            if contact["company"]:
                print(f"   Company: {contact['company']}")
            print(f"   Stage: {contact['relationship_stage']}")
            print(f"   Recent Interactions: {len(contact['recent_interactions'])}")

            for j, interaction in enumerate(contact["recent_interactions"][:2], 1):
                print(
                    f"      {j}. [{interaction['direction']}] {interaction['subject']}"
                )
                if interaction["interaction_at"]:
                    print(f"         Date: {interaction['interaction_at']}")

        print("\n" + "=" * 60)

        # Test 2: Another situation
        print("\n--- Test 2: Different situation ---")
        situation2 = "Need help with technical architecture review"
        print(f"📝 Situation: '{situation2}'")

        context_bundle2 = compile_context(db, str(org_id), situation2)
        print(f"✓ Found {len(context_bundle2['contacts'])} contacts")

        for i, contact in enumerate(context_bundle2["contacts"], 1):
            print(
                f"  {i}. {contact['name']} - {len(contact['recent_interactions'])} interactions"
            )

        print("\n✅ Context compiler is working!")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_context_compiler()
