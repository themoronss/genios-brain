"""
Week 6: Edge Case Testing Script
Tests various edge cases for draft generation and context APIs
"""

import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = "http://localhost:8000"
ORG_ID = "87b0235e-e29d-468a-b841-522c13546515"  # Valid UUID from database


def test_draft_api():
    """Test draft generation endpoint with various edge cases"""
    print("\n" + "=" * 60)
    print("DRAFT API EDGE CASE TESTS")
    print("=" * 60)

    test_cases = [
        {
            "name": "Empty entity name",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "",
                "user_request": "Follow up on meeting",
            },
            "expected": 422,  # Validation error
        },
        {
            "name": "Very short entity name",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "A",
                "user_request": "Follow up on meeting",
            },
            "expected": 422,  # Less than 2 chars
        },
        {
            "name": "Very long entity name",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "A" * 250,
                "user_request": "Follow up",
            },
            "expected": 422,  # More than 200 chars
        },
        {
            "name": "Special characters in name",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "Test@#$%^&*()",
                "user_request": "Follow up",
            },
            "expected": 404,  # Won't find contact with special chars
        },
        {
            "name": "Empty user request",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "Test Person",
                "user_request": "",
            },
            "expected": 422,  # Validation error
        },
        {
            "name": "Very short request",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "Test Person",
                "user_request": "Hi",
            },
            "expected": 422,  # Less than 5 chars
        },
        {
            "name": "Very long request",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "Test",
                "user_request": "A" * 600,
            },
            "expected": 422,  # More than 500 chars
        },
        {
            "name": "Non-existent contact",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "Nonexistent Person XYZ123",
                "user_request": "Follow up",
            },
            "expected": 404,  # Contact not found
        },
        {
            "name": "Whitespace only entity name",
            "data": {
                "org_id": ORG_ID,
                "entity_name": "   ",
                "user_request": "Follow up",
            },
            "expected": 422,  # Should be stripped to empty
        },
        {
            "name": "Whitespace only request",
            "data": {"org_id": ORG_ID, "entity_name": "Test", "user_request": "     "},
            "expected": 422,  # Should be stripped to empty
        },
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Testing: {test['name']}")
        print(
            f"  Data: entity_name='{test['data']['entity_name'][:50]}...', request='{test['data']['user_request'][:50]}...'"
        )

        try:
            response = requests.post(
                f"{API_URL}/api/generate/draft", json=test["data"], timeout=30
            )

            status_code = response.status_code
            expected = test["expected"]

            if status_code == expected:
                print(f"  ✅ PASS: Got expected {status_code}")
            else:
                print(f"  ❌ FAIL: Expected {expected}, got {status_code}")
                print(f"  Response: {response.text[:200]}")

        except requests.exceptions.Timeout:
            print(f"  ⏰ TIMEOUT: Request took too long")
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")

        time.sleep(0.5)  # Rate limiting


def test_context_api():
    """Test context endpoint with various edge cases"""
    print("\n" + "=" * 60)
    print("CONTEXT API EDGE CASE TESTS")
    print("=" * 60)

    test_cases = [
        {
            "name": "Empty entity name",
            "data": {"org_id": ORG_ID, "entity_name": ""},
            "expected": 422,
        },
        {
            "name": "Very short entity name",
            "data": {"org_id": ORG_ID, "entity_name": "A"},
            "expected": 422,
        },
        {
            "name": "Very long entity name",
            "data": {"org_id": ORG_ID, "entity_name": "B" * 250},
            "expected": 422,
        },
        {
            "name": "Non-existent contact",
            "data": {"org_id": ORG_ID, "entity_name": "Nonexistent XYZ999"},
            "expected": 404,
        },
        {
            "name": "Whitespace only entity",
            "data": {"org_id": ORG_ID, "entity_name": "    "},
            "expected": 422,
        },
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Testing: {test['name']}")

        try:
            response = requests.post(
                f"{API_URL}/v1/context",  # Correct endpoint path
                json=test["data"],
                timeout=10,
            )

            status_code = response.status_code
            expected = test["expected"]

            if status_code == expected:
                print(f"  ✅ PASS: Got expected {status_code}")
            else:
                print(f"  ❌ FAIL: Expected {expected}, got {status_code}")
                print(f"  Response: {response.text[:200]}")

        except requests.exceptions.Timeout:
            print(f"  ⏰ TIMEOUT: Request took too long")
        except Exception as e:
            print(f"  ❌ ERROR: {str(e)}")

        time.sleep(0.3)


def test_concurrent_requests():
    """Test concurrent requests to check for race conditions"""
    print("\n" + "=" * 60)
    print("CONCURRENT REQUEST TEST")
    print("=" * 60)

    import concurrent.futures

    def make_request(i):
        try:
            response = requests.post(
                f"{API_URL}/v1/context",  # Correct endpoint path
                json={"org_id": ORG_ID, "entity_name": f"Test{i}"},
                timeout=10,
            )
            return f"Request {i}: {response.status_code}"
        except Exception as e:
            return f"Request {i}: ERROR - {str(e)}"

    print("\nSending 5 concurrent requests...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request, i) for i in range(5)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    for result in results:
        print(f"  {result}")


def main():
    print("\n🧪 Week 6 Edge Case Testing")
    print("Testing production-grade error handling and validation\n")

    # Check if server is running
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        print(f"✅ Server is running at {API_URL}\n")
    except:
        print(f"❌ Server is not running at {API_URL}")
        print("Start the server with: uvicorn app.main:app --reload")
        return

    # Run test suites
    test_draft_api()
    test_context_api()
    test_concurrent_requests()

    print("\n" + "=" * 60)
    print("TESTING COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Review failures above")
    print("2. Fix any unexpected behavior")
    print("3. Ready for first pilot customer! 🚀")


if __name__ == "__main__":
    main()
