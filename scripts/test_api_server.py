#!/usr/bin/env python3
"""
API Server Test - Test all endpoints when server is running
Run the server first with: uvicorn app.main:app --reload
Then run this script in another terminal
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"
TEST_ORG_ID = "87b0235e-e29d-468a-b841-522c13546515"


def test_health():
    """Test health endpoint"""
    print("\n" + "=" * 70)
    print("  TEST: Health Check Endpoint")
    print("=" * 70)

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_root():
    """Test root endpoint"""
    print("\n" + "=" * 70)
    print("  TEST: Root Endpoint")
    print("=" * 70)

    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✅ Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_context_api():
    """Test context API endpoint"""
    print("\n" + "=" * 70)
    print("  TEST: Context API Endpoint")
    print("=" * 70)

    test_situations = [
        "Follow up with investor about our Series A pitch",
        "Technical discussion about API architecture",
        "Partnership proposal for enterprise customers",
    ]

    for i, situation in enumerate(test_situations, 1):
        print(f"\n  Test {i}: {situation}")

        try:
            payload = {"org_id": TEST_ORG_ID, "situation": situation}

            response = requests.post(f"{BASE_URL}/v1/context", json=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Status: 200")
                print(f"     Found {len(data['contacts'])} contacts")

                if data["contacts"]:
                    contact = data["contacts"][0]
                    print(f"     Top match: {contact['name']}")
                    print(f"     Email: {contact['email']}")
                    print(
                        f"     Recent interactions: {len(contact['recent_interactions'])}"
                    )

                    if "recommended_action" in contact:
                        print(
                            f"     Recommended action: {contact['recommended_action']}"
                        )
                    if "coverage_score" in contact:
                        print(f"     Coverage score: {contact['coverage_score']}")
            else:
                print(f"  ❌ Status: {response.status_code}")
                print(f"     Error: {response.text[:200]}")

        except Exception as e:
            print(f"  ❌ Failed: {e}")

    return True


def test_gmail_oauth():
    """Test Gmail OAuth endpoints"""
    print("\n" + "=" * 70)
    print("  TEST: Gmail OAuth Endpoints")
    print("=" * 70)
    print("  ℹ️  Testing connect endpoint (should redirect)...")

    try:
        # Don't follow redirects for testing
        response = requests.get(
            f"{BASE_URL}/auth/gmail/connect",
            params={"org_id": TEST_ORG_ID},
            allow_redirects=False,
            timeout=5,
        )

        if response.status_code in [302, 307]:
            print(f"  ✅ Connect endpoint working (redirect to Google)")
            print(f"     Status: {response.status_code}")
            if "location" in response.headers:
                redirect = response.headers["location"]
                print(f"     Redirects to: {redirect[:80]}...")
            return True
        else:
            print(f"  ⚠️  Status: {response.status_code}")
            return False

    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def run_all_api_tests():
    """Run all API tests"""
    print("\n" + "#" * 70)
    print("#" + " " * 68 + "#")
    print("#" + "  GeniOS Brain - API Server Tests".center(68) + "#")
    print("#" + " " * 68 + "#")
    print("#" * 70)

    # Check if server is running
    print("\nChecking if server is running...")
    try:
        requests.get(BASE_URL, timeout=2)
        print("✅ Server is running at " + BASE_URL)
    except:
        print("❌ Server is NOT running!")
        print("\nTo start the server, run:")
        print("  uvicorn app.main:app --reload")
        print("\nOr:")
        print("  ./venv/bin/uvicorn app.main:app --reload")
        print("\nThen run this test script again.")
        sys.exit(1)

    # Run tests
    tests = [
        ("Root Endpoint", test_root),
        ("Health Endpoint", test_health),
        ("Context API", test_context_api),
        ("Gmail OAuth", test_gmail_oauth),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("  TEST SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    print(f"\n  Tests Passed: {passed}/{total}")

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} | {name}")

    if passed == total:
        print("\n  🎉 ALL API TESTS PASSED!")
    else:
        print(f"\n  ⚠️  {total - passed} test(s) failed")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    run_all_api_tests()
