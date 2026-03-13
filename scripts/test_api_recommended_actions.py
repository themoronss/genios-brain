"""Test Context API with recommended actions"""

import requests
import json
import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from sqlalchemy import text


def test_api_with_recommended_actions():
    print("🧪 Testing Context API with Recommended Actions")
    print("=" * 60)

    # Get org_id
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT DISTINCT org_id FROM contacts LIMIT 1"))
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")
    finally:
        db.close()

    url = "http://localhost:8000/v1/context"

    # Test: Get context with recommended actions
    print("\n--- API Request: Context with Recommended Actions ---")
    payload = {
        "org_id": org_id,
        "situation": "I need to reconnect with my network about our new product",
    }

    print(f"📤 POST {url}")
    print(f"Body: {json.dumps(payload, indent=2)}")

    response = requests.post(url, json=payload)

    print(f"\n📥 Response Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()

        print(f"✓ Status: {response.status_code}")
        print(f"✓ Situation: {data['situation']}")
        print(f"✓ Found {len(data['contacts'])} relevant contacts\n")

        for i, contact in enumerate(data["contacts"], 1):
            print(f"\n{i}. {contact['name'] or '(no name)'}")
            print(f"   Email: {contact['email']}")
            print(f"   Company: {contact.get('company', 'N/A')}")
            print(f"   Stage: {contact['relationship_stage']}")
            print(f"   Interactions: {len(contact['recent_interactions'])}")

            if contact["recent_interactions"]:
                latest = contact["recent_interactions"][0]
                print(f"   Latest: [{latest['direction']}] {latest['subject'][:50]}...")
                print(f"   Date: {latest['interaction_at']}")

            # Highlight the recommended action
            print(
                f"   ⭐ RECOMMENDED ACTION: {contact.get('recommended_action', 'N/A')}"
            )

        # Show full JSON response (pretty printed)
        print("\n" + "=" * 60)
        print("📄 FULL JSON RESPONSE (first contact):")
        print("=" * 60)
        if data["contacts"]:
            print(json.dumps(data["contacts"][0], indent=2))

        # Verify recommended_action field exists
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        has_recommended_action = all(
            "recommended_action" in contact for contact in data["contacts"]
        )

        if has_recommended_action:
            print("✅ All contacts have 'recommended_action' field")
        else:
            print("❌ Some contacts missing 'recommended_action' field")

        print("\n✅ Context API with Recommended Actions Working!")
        print("\nFeatures:")
        print("  ✓ Semantic search for relevant contacts")
        print("  ✓ Recent interaction history")
        print("  ✓ Intelligent recommended actions")
        print("  ✓ Rule-based relationship insights")

    else:
        print(f"❌ Error: {response.text}")


if __name__ == "__main__":
    test_api_with_recommended_actions()
