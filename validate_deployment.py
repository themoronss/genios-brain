#!/usr/bin/env python3
"""
Pre-Deployment Validation Script
Run this before deploying to ensure everything works locally
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv()


def check_env_vars():
    """Check all required environment variables"""
    print("\n🔍 Checking environment variables...")

    required = [
        "GEMINI_API_KEY",
        "QDRANT_URL",
        "QDRANT_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "ORG_ID",
    ]

    missing = []
    for var in required:
        if not os.getenv(var):
            missing.append(var)
            print(f"  ❌ {var} - MISSING")
        else:
            value = os.getenv(var)
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  ✅ {var} - {masked}")

    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        return False

    print("✅ All environment variables present")
    return True


def test_qdrant():
    """Test Qdrant connection"""
    print("\n🔍 Testing Qdrant connection...")
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            url=os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY")
        )
        collections = client.get_collections()

        # Check if genios_context exists
        collection_names = [c.name for c in collections.collections]
        if "genios_context" in collection_names:
            print("  ✅ Collection 'genios_context' exists")

            # Check collection size
            info = client.get_collection("genios_context")
            print(f"  ✅ Collection has {info.points_count} points")
            return True
        else:
            print("  ❌ Collection 'genios_context' not found")
            print("  Run: python3 setup_qdrant.py")
            return False

    except Exception as e:
        print(f"  ❌ Qdrant connection failed: {e}")
        return False


def test_supabase():
    """Test Supabase connection"""
    print("\n🔍 Testing Supabase connection...")
    try:
        from supabase import create_client

        client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

        # Check tables exist
        tables_to_check = ["org_context", "entity_state", "interaction_log"]

        for table in tables_to_check:
            result = client.table(table).select("*").limit(1).execute()
            print(f"  ✅ Table '{table}' accessible")

        # Check seed data
        result = client.table("org_context").select("*").execute()
        if len(result.data) > 0:
            print(f"  ✅ Seed data present ({len(result.data)} records in org_context)")
            return True
        else:
            print("  ⚠️  No seed data found. Run: python3 data/seed.py")
            return False

    except Exception as e:
        print(f"  ❌ Supabase connection failed: {e}")
        return False


def test_api():
    """Test FastAPI endpoints"""
    print("\n🔍 Testing API endpoints...")
    try:
        import httpx

        # Test health
        resp = httpx.get("http://127.0.0.1:8000/health", timeout=5)
        if resp.status_code == 200:
            print("  ✅ /health endpoint working")
        else:
            print(f"  ❌ /health returned {resp.status_code}")
            return False

        # Test enrich
        resp = httpx.post(
            "http://127.0.0.1:8000/v1/enrich",
            json={"org_id": "genios_internal", "raw_message": "test"},
            timeout=30,
        )
        if resp.status_code == 200:
            result = resp.json()
            if "verdict" in result and "enriched_brief" in result:
                print("  ✅ /v1/enrich endpoint working")
                print(f"     Verdict: {result['verdict']}")
                return True
            else:
                print("  ❌ /v1/enrich returned incomplete response")
                return False
        else:
            print(f"  ❌ /v1/enrich returned {resp.status_code}")
            return False

    except httpx.ConnectError:
        print("  ❌ API not running. Start with: uvicorn main:app --reload")
        return False
    except Exception as e:
        print(f"  ❌ API test failed: {e}")
        return False


def run_core_tests():
    """Run core test suite"""
    print("\n🔍 Running core test suite...")
    import subprocess

    try:
        result = subprocess.run(
            ["python3", "test_system.py"], capture_output=True, text=True, timeout=120
        )

        if "10 passed, 0 failed" in result.stdout:
            print("  ✅ All 10 core tests passed")
            return True
        else:
            print("  ❌ Some tests failed")
            print(result.stdout[-500:])  # Show last 500 chars
            return False

    except Exception as e:
        print(f"  ❌ Test execution failed: {e}")
        return False


def main():
    print("=" * 60)
    print("GeniOS Brain - Pre-Deployment Validation")
    print("=" * 60)

    checks = [
        ("Environment Variables", check_env_vars),
        ("Qdrant Connection", test_qdrant),
        ("Supabase Connection", test_supabase),
        ("API Endpoints", test_api),
        ("Core Tests", run_core_tests),
    ]

    results = []

    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} check crashed: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print(f"\nScore: {passed}/{total} checks passed")

    if passed == total:
        print("\n🎉 ALL CHECKS PASSED!")
        print("✅ Ready for deployment")
        print("\nNext steps:")
        print("1. Run: ./deploy.sh (or follow DEPLOYMENT_CHECKLIST.md)")
        print("2. Configure environment variables in Railway")
        print("3. Test deployed API")
        print("4. Run OpenClaw comparison tests")
        return 0
    else:
        print("\n⚠️  SOME CHECKS FAILED")
        print("❌ Fix issues before deploying")
        print("\nReview:")
        print("- Environment variables in .env")
        print("- Qdrant collection: python3 setup_qdrant.py")
        print("- Seed data: python3 data/seed.py")
        print("- API running: uvicorn main:app --reload")
        return 1


if __name__ == "__main__":
    sys.exit(main())
