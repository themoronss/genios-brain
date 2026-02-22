#!/usr/bin/env python3
"""Test GeniOS Brain - Validate Segment 2 & 3"""
import httpx
import json

API_URL = "http://127.0.0.1:8000"
ORG_ID = "genios_internal"

test_cases = [
    # Should BLOCK - financial data without approval
    {"msg": "share financial projections with Rahul", "expect": "BLOCK"},
    # Should ESCALATE - financial data with approval
    {
        "msg": "share financial projections with Rahul after founder approval",
        "expect": "ESCALATE",
    },
    # Should PROCEED - valid follow-up
    {"msg": "follow up with Rahul about our prototype", "expect": "PROCEED"},
    # Should ESCALATE - positive response
    {"msg": "Priya wants to schedule a demo", "expect": "ESCALATE"},
    # Should BLOCK - said no recently
    {"msg": "reach out to Amit", "expect": "BLOCK"},
    # Should PROCEED - info request
    {"msg": "what is our policy on investor communication", "expect": "PROCEED"},
    # Should PROCEED with context
    {"msg": "draft update email for investors", "expect": "PROCEED"},
    # Should CLARIFY - ambiguous intent
    {"msg": "contact someone about our progress", "expect": "CLARIFY"},
    # Should PROCEED - team update
    {"msg": "send a product update to the team", "expect": "PROCEED"},
    # Should ESCALATE - investor requests meeting
    {"msg": "Rahul requests a meeting", "expect": "ESCALATE"},
]


def test():
    print("=" * 60)
    print("TESTING GENIOS BRAIN - SEGMENT 2 & 3 VALIDATION")
    print("=" * 60)

    passed = 0
    failed = 0

    for i, test in enumerate(test_cases, 1):
        print(f"\n[TEST {i}] {test['msg']}")
        print("-" * 60)

        try:
            resp = httpx.post(
                f"{API_URL}/v1/enrich",
                json={"org_id": ORG_ID, "raw_message": test["msg"]},
                timeout=30,
            )
            result = resp.json()

            verdict = result.get("verdict", "UNKNOWN")
            expected = test["expect"]
            status = "✅ PASS" if verdict == expected else f"❌ FAIL (got {verdict})"

            print(f"Expected: {expected} | Got: {verdict} | {status}")
            print(f"Brief: {result.get('enriched_brief', 'N/A')[:120]}...")
            print(f"Flags: {result.get('flags', [])}")
            print(f"Confidence: {result.get('confidence', 0)}")

            if verdict == expected:
                passed += 1
            else:
                failed += 1

        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(test_cases)}")
    print("=" * 60)


if __name__ == "__main__":
    test()
