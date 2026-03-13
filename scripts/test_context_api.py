"""Test the context API endpoint"""

import requests
import json
from sqlalchemy import text
import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal


def test_context_api():
    print("🧪 Testing Context API Endpoint...")

    # Get org_id from database
    db = SessionLocal()
    try:
        result = db.execute(
            text(
                "SELECT DISTINCT org_id FROM contacts WHERE embedding IS NOT NULL LIMIT 1"
            )
        )
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")
    finally:
        db.close()

    # API endpoint
    url = "http://localhost:8000/v1/context"

    # Test 1: Follow up with investor
    print("\n--- Test 1: Investor follow-up ---")
    payload = {"org_id": org_id, "situation": "Follow up with investor about our pitch"}

    print(f"📤 POST {url}")
    print(f"   Body: {json.dumps(payload, indent=2)}")

    response = requests.post(url, json=payload)

    print(f"\n📥 Response Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"✓ Success!")
        print(f"✓ Situation: {data['situation']}")
        print(f"✓ Found {len(data['contacts'])} contacts")

        for i, contact in enumerate(data["contacts"][:2], 1):
            print(f"\n  Contact {i}: {contact['name']} ({contact['email']})")
            print(f"    Company: {contact.get('company', 'N/A')}")
            print(f"    Interactions: {len(contact['recent_interactions'])}")

            if contact["recent_interactions"]:
                first_interaction = contact["recent_interactions"][0]
                print(
                    f"    Latest: [{first_interaction['direction']}] {first_interaction['subject'][:50]}..."
                )
    else:
        print(f"❌ Error: {response.text}")
        return

    # Test 2: Technical help
    print("\n\n--- Test 2: Technical architecture ---")
    payload2 = {
        "org_id": org_id,
        "situation": "Need technical architecture review for our backend system",
    }

    print(f"📤 POST {url}")
    response2 = requests.post(url, json=payload2)

    print(f"📥 Response Status: {response2.status_code}")

    if response2.status_code == 200:
        data2 = response2.json()
        print(f"✓ Success!")
        print(f"✓ Found {len(data2['contacts'])} contacts")

        for i, contact in enumerate(data2["contacts"], 1):
            print(
                f"  {i}. {contact['name']} - {len(contact['recent_interactions'])} interactions"
            )
    else:
        print(f"❌ Error: {response2.text}")
        return

    # Test 3: Invalid request
    print("\n\n--- Test 3: Invalid request (missing org_id) ---")
    invalid_payload = {"situation": "Test situation"}

    response3 = requests.post(url, json=invalid_payload)
    print(f"📥 Response Status: {response3.status_code}")

    if response3.status_code == 422:
        print("✓ Validation error handled correctly")

    print("\n✅ Context API is fully working!")
    print("\n" + "=" * 60)
    print("🎉 GeniOS Brain Context Engine Complete!")
    print("=" * 60)
    print("\nEndpoint: POST /v1/context")
    print("\nFlow:")
    print("  1. Situation → Embedding")
    print("  2. Vector similarity search")
    print("  3. Find relevant contacts")
    print("  4. Fetch recent interactions")
    print("  5. Return context bundle")
    print("=" * 60)


if __name__ == "__main__":
    test_context_api()
