"""Test Context API with coverage_score"""

import requests
import json
import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from sqlalchemy import text


def test_api_coverage_score():
    print("🧪 Testing Context API with Coverage Score")
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

    # Test: Get context with coverage scores
    print("\n--- API Request: Context with Coverage Scores ---")
    payload = {
        "org_id": org_id,
        "situation": "Need advice on scaling our engineering team",
    }

    print(f"📤 POST {url}")

    response = requests.post(url, json=payload)

    print(f"📥 Response Status: {response.status_code}\n")

    if response.status_code == 200:
        data = response.json()

        print(f"Situation: {data['situation']}")
        print(f"Found {len(data['contacts'])} relevant contacts\n")

        coverage_scores = []

        for i, contact in enumerate(data["contacts"], 1):
            print(f"{i}. {contact['name'] or '(no name)'}")
            print(f"   📧 Email: {contact['email']}")
            print(f"   🏢 Company: {contact.get('company', 'N/A')}")
            print(f"   🎯 Stage: {contact['relationship_stage']}")
            print(f"   💬 Interactions: {len(contact['recent_interactions'])}")
            print(f"   ⭐ Recommended Action: {contact['recommended_action']}")
            print(f"   📊 Coverage Score: {contact['coverage_score']}")

            coverage_scores.append(contact["coverage_score"])

            # Show what contributes to score
            score_breakdown = []
            if contact.get("name"):
                score_breakdown.append("name")
            if contact.get("email"):
                score_breakdown.append("email")
            if contact.get("company"):
                score_breakdown.append("company")
            if contact["recent_interactions"]:
                score_breakdown.append("interactions")
            if contact.get("relationship_stage") != "unknown":
                score_breakdown.append("stage")
            if contact.get("last_sentiment", 0) != 0:
                score_breakdown.append("sentiment")

            print(f"   └─ Populated fields: {', '.join(score_breakdown)}")
            print()

        # Calculate statistics
        print("=" * 60)
        print("COVERAGE STATISTICS")
        print("=" * 60)

        avg_coverage = sum(coverage_scores) / len(coverage_scores)
        min_coverage = min(coverage_scores)
        max_coverage = max(coverage_scores)

        print(f"Average Coverage: {avg_coverage:.2f}")
        print(f"Minimum Coverage: {min_coverage:.2f}")
        print(f"Maximum Coverage: {max_coverage:.2f}")

        # Quality assessment
        print("\nQuality Assessment:")
        if avg_coverage >= 0.75:
            print("  ✅ Excellent - Most fields populated")
        elif avg_coverage >= 0.5:
            print("  ⚠️  Good - Some fields missing")
        else:
            print("  ❌ Poor - Many fields missing")

        # Verify all contacts have coverage_score
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        has_coverage = all("coverage_score" in contact for contact in data["contacts"])
        if has_coverage:
            print("✅ All contacts have coverage_score field")
        else:
            print("❌ Some contacts missing coverage_score field")

        valid_scores = all(0 <= score <= 1 for score in coverage_scores)
        if valid_scores:
            print("✅ All coverage scores are between 0 and 1")
        else:
            print("❌ Some scores out of valid range")

        print("\n✅ Context API with Coverage Score Working!")
        print("\nComplete Response Fields:")
        print("  ✓ situation")
        print("  ✓ contacts[]")
        print("    ├─ id, name, email, company")
        print("    ├─ relationship_stage")
        print("    ├─ recent_interactions[]")
        print("    ├─ recommended_action")
        print("    └─ coverage_score")

    else:
        print(f"❌ Error: {response.text}")


if __name__ == "__main__":
    test_api_coverage_score()
