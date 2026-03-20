"""
Test signal_score and freshness_score computation functions
"""

import sys
sys.path.insert(0, '/home/harshtripathi/Desktop/genios-brain')

from app.ingestion.entity_extractor import compute_signal_score
from app.graph.relationship_calculator import compute_freshness
from datetime import datetime, timedelta, timezone

print("\n" + "="*70)
print("Testing Signal Score Computation")
print("="*70 + "\n")

# Test Signal Score with various combinations
test_cases = [
    {
        "name": "High signal (commitment + engagement + long)",
        "intelligence": {
            "intent": "commitment",
            "engagement_level": "high",
            "commitment_keywords": ["will", "shall", "confirm"],
        },
        "body": "I will definitely help you with this long email discussing various aspects and details of our upcoming project that requires careful planning and execution.",
        "expected_range": (0.8, 1.0),
    },
    {
        "name": "Medium signal (request + short)",
        "intelligence": {
            "intent": "request",
            "engagement_level": "medium",
            "commitment_keywords": [],
        },
        "body": "Can you help?",
        "expected_range": (0.3, 0.5),
    },
    {
        "name": "Low signal (casual + short)",
        "intelligence": {
            "intent": "casual",
            "engagement_level": "low",
            "commitment_keywords": [],
        },
        "body": "Hi",
        "expected_range": (0.0, 0.3),
    },
    {
        "name": "High signal (request + long + high engagement)",
        "intelligence": {
            "intent": "request",
            "engagement_level": "high",
            "commitment_keywords": ["will", "confirm"],
        },
        "body": "Can you please help me with this detailed request spanning multiple paragraphs with lots of context and important information about the project timeline and deliverables?",
        "expected_range": (0.6, 1.0),
    },
]

for test in test_cases:
    try:
        score = compute_signal_score(test["intelligence"], test["body"])
        in_range = test["expected_range"][0] <= score <= test["expected_range"][1]
        status = "✅" if in_range else "⚠️"
        print(f"{status} {test['name']}")
        print(f"   Score: {score:.3f} (expected: {test['expected_range']})")
        print()
    except Exception as e:
        print(f"❌ {test['name']}")
        print(f"   Error: {e}\n")

print("="*70)
print("Testing Freshness Score Computation")
print("="*70 + "\n")

# Test Freshness Score with various stage/age combinations
now = datetime.now(timezone.utc)

freshness_tests = [
    {
        "name": "ACTIVE stage, 3 days old",
        "days_since": 3,
        "stage": "ACTIVE",
        "expected": (0.8, 1.0),
    },
    {
        "name": "WARM stage, 15 days old",
        "days_since": 15,
        "stage": "WARM",
        "expected": (0.5, 0.8),
    },
    {
        "name": "DORMANT stage, 45 days old",
        "days_since": 45,
        "stage": "DORMANT",
        "expected": (0.3, 0.7),
    },
    {
        "name": "COLD stage, 120 days old",
        "days_since": 120,
        "stage": "COLD",
        "expected": (0.1, 0.5),
    },
    {
        "name": "AT_RISK stage, 30 days old",
        "days_since": 30,
        "stage": "AT_RISK",
        "expected": (0.1, 0.8),
    },
]

for test in freshness_tests:
    try:
        score = compute_freshness(test["days_since"], test["stage"])
        # Check if in expected range
        in_range = test["expected"][0] <= score <= test["expected"][1]
        status = "✅" if in_range else "⚠️"
        print(f"{status} {test['name']}")
        print(
            f"   Freshness: {score:.3f} (expected: {test['expected']})"
        )
        print()
    except Exception as e:
        print(f"❌ {test['name']}")
        print(f"   Error: {e}\n")

print("="*70)
print("✅ All scoring function tests completed!")
print("="*70)
