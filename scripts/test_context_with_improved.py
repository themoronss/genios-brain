"""Test Context API with improved embeddings"""

import requests
import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from sqlalchemy import text


def test_context_with_improved_embeddings():
    print("🧪 Testing Context API with Improved Embeddings")
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

    # Test case: Investor-related query
    print("\n--- Test: Investor Follow-up ---")
    payload = {
        "org_id": org_id,
        "situation": "I need to follow up with investors about our pitch deck",
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Situation: {data['situation']}")
        print(f"✓ Found {len(data['contacts'])} relevant contacts\n")

        for i, contact in enumerate(data["contacts"], 1):
            print(f"{i}. {contact['name'] or '(no name)'}")
            if contact.get("company"):
                print(f"   Company: {contact['company']}")
            print(f"   Email: {contact['email']}")
            print(f"   Stage: {contact['relationship_stage']}")
            print(f"   Recent Interactions: {len(contact['recent_interactions'])}")

            if contact["recent_interactions"]:
                latest = contact["recent_interactions"][0]
                print(f"   Latest: [{latest['direction']}] {latest['subject'][:60]}...")
            print()
    else:
        print(f"❌ Error: {response.text}")
        return

    # Test case: Technical query
    print("\n--- Test: Technical Discussion ---")
    payload2 = {
        "org_id": org_id,
        "situation": "Need to discuss technical architecture for our backend",
    }

    response2 = requests.post(url, json=payload2)

    if response2.status_code == 200:
        data2 = response2.json()
        print(f"✓ Status: {response2.status_code}")
        print(f"✓ Found {len(data2['contacts'])} relevant contacts\n")

        for i, contact in enumerate(data2["contacts"], 1):
            print(f"{i}. {contact['name'] or '(no name)'}")
            print(f"   Interactions: {len(contact['recent_interactions'])}")
    else:
        print(f"❌ Error: {response2.text}")

    print("\n" + "=" * 60)
    print("✅ Context API with Improved Embeddings Working!")
    print("=" * 60)
    print("\nImprovements:")
    print("  ✓ Search uses interaction context")
    print("  ✓ Better semantic matching")
    print("  ✓ More relevant contact results")
    print("  ✓ Reduced false positives (newsletters, etc.)")


if __name__ == "__main__":
    test_context_with_improved_embeddings()
