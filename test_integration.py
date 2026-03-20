"""
Integration test for full v1.1 pipeline:
Email → Classification → Scoring → Storage
"""

import os
import sys
sys.path.insert(0, '/home/harshtripathi/Desktop/genios-brain')

# Set up environment
os.environ['GROQ_API_KEY'] = os.getenv('GROQ_API_KEY', 'test-key')

from app.ingestion.email_classifier import classify_email
from app.ingestion.entity_extractor import compute_signal_score
from app.graph.relationship_calculator import compute_freshness

print("\n" + "="*70)
print("Integration Test: Full v1.1 Classification Pipeline")
print("="*70 + "\n")

# Test emails simulating real workflows
test_emails = [
    {
        "name": "STRONG - Commitment from colleague",
        "subject": "Project Update - Will Complete by Friday",
        "body": """Hi,

I wanted to give you an update on the project. I've reviewed all the requirements 
and I will definitely have the implementation completed by Friday as discussed. 
I've also identified some edge cases that we should address. Can we sync up tomorrow 
to discuss the approach?

Looking forward to your feedback.

Best regards""",
        "sender": "john@company.com",
        "expected_class": "STRONG",
    },
    {
        "name": "WEAK - Short greeting",
        "subject": "Thanks",
        "body": "Thanks for the update.",
        "sender": "jane@company.com",
        "expected_class": "WEAK",
    },
    {
        "name": "SYSTEM - GST Payment",
        "subject": "Payment Received - INR 50000",
        "body": """Your payment of INR 50000 from Acme Corp has been received.
        
GST Invoice #INV-2024-001456
Amount: ₹50,000 + GST: ₹9,000 = ₹59,000
        
Transaction confirmed. ARN: AA1234567890123""",
        "sender": "payments@vendor.com",
        "expected_class": "SYSTEM",
    },
    {
        "name": "DISCARD - Marketing email",
        "subject": "Weekly Newsletter - Exclusive Offers Inside",
        "body": "Click here to see this week's exclusive offers. Unsubscribe here.",
        "sender": "newsletter@marketing.com",
        "expected_class": "DISCARD",
        "headers": {"List-Unsubscribe": "<mailto:unsubscribe@marketing.com>"},
    },
]

results = {
    "STRONG": {"total": 0, "correct": 0},
    "WEAK": {"total": 0, "correct": 0},
    "SYSTEM": {"total": 0, "correct": 0},
    "DISCARD": {"total": 0, "correct": 0},
}

for email in test_emails:
    category = classify_email(
        email["subject"],
        email["sender"],
        email["body"],
        email.get("headers"),
    )
    
    expected = email["expected_class"]
    is_correct = category == expected
    results[expected]["total"] += 1
    if is_correct:
        results[expected]["correct"] += 1
    
    status = "✅" if is_correct else "❌"
    print(f"{status} {email['name']}")
    print(f"   Expected: {expected}, Got: {category}")
    
    # For STRONG emails, also show signal score
    if category == "STRONG" and is_correct:
        signal = compute_signal_score(
            {"intent": "commitment", "engagement_level": "high"},
            email["body"]
        )
        freshness = compute_freshness(1, "ACTIVE")
        print(f"   Signal Score: {signal:.3f}")
        print(f"   Freshness Score: {freshness:.3f}")
    
    print()

# Summary
print("="*70)
print("Classification Summary")
print("="*70)
total_tests = sum(r["total"] for r in results.values())
total_correct = sum(r["correct"] for r in results.values())

for cat, res in results.items():
    if res["total"] > 0:
        pct = (res["correct"] / res["total"]) * 100
        print(f"{cat:12} {res['correct']}/{res['total']} ({pct:.0f}%)")

print(f"\nTotal: {total_correct}/{total_tests} ({(total_correct/total_tests)*100:.0f}%)")
print("="*70)

if total_correct == total_tests:
    print("✅ All integration tests PASSED!")
else:
    print("⚠️ Some tests failed. Check output above.")
print("="*70)
