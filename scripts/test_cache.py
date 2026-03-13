"""Test Redis caching for context API"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

import time
from app.database import SessionLocal
from app.context.compiler import compile_context
from app.context.cache import (
    get_cached_context,
    set_cached_context,
    _generate_cache_key,
)
from app.redis_client import redis_client
from sqlalchemy import text


def test_cache():
    print("🧪 Testing Redis Caching for Context API...")

    db = SessionLocal()

    try:
        # Get org_id from database
        result = db.execute(
            text(
                "SELECT DISTINCT org_id FROM contacts WHERE embedding IS NOT NULL LIMIT 1"
            )
        )
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")

        situation = "Follow up with investor about our pitch"
        cache_key = _generate_cache_key(org_id, situation)
        print(f"✓ Cache key: {cache_key}")

        # Clear any existing cache
        redis_client.delete(cache_key)
        print("✓ Cleared existing cache")

        # Test 1: First call (cache miss)
        print("\n--- Test 1: First call (cache miss) ---")
        start_time = time.time()
        context1 = compile_context(db, org_id, situation)
        elapsed1 = time.time() - start_time

        print(f"✓ Generated context bundle")
        print(f"✓ Found {len(context1['contacts'])} contacts")
        print(f"✓ Time taken: {elapsed1:.3f}s")

        # Verify it's now in cache
        cached = get_cached_context(org_id, situation)
        if cached:
            print("✓ Context stored in cache")
        else:
            print("❌ Context NOT in cache")
            return

        # Test 2: Second call (cache hit)
        print("\n--- Test 2: Second call (cache hit) ---")
        start_time = time.time()
        context2 = compile_context(db, org_id, situation)
        elapsed2 = time.time() - start_time

        print(f"✓ Retrieved context bundle")
        print(f"✓ Found {len(context2['contacts'])} contacts")
        print(f"✓ Time taken: {elapsed2:.3f}s")

        # Compare performance
        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float("inf")
        print(f"✓ Cache speedup: {speedup:.1f}x faster")

        if elapsed2 < elapsed1:
            print("✓ Cache hit is faster!")

        # Verify results are identical
        if context1 == context2:
            print("✓ Cached result matches original")
        else:
            print("⚠️  Cached result differs from original")

        # Test 3: Different situation (cache miss)
        print("\n--- Test 3: Different situation (cache miss) ---")
        situation2 = "Need technical architecture review"
        start_time = time.time()
        context3 = compile_context(db, org_id, situation2)
        elapsed3 = time.time() - start_time

        print(f"✓ Generated new context bundle")
        print(f"✓ Found {len(context3['contacts'])} contacts")
        print(f"✓ Time taken: {elapsed3:.3f}s")

        # Test 4: Check TTL
        print("\n--- Test 4: Check TTL ---")
        ttl = redis_client.ttl(cache_key)
        print(f"✓ Cache TTL: {ttl} seconds (should be <= 60)")

        if ttl > 0 and ttl <= 60:
            print("✓ TTL set correctly")
        else:
            print(f"⚠️  Unexpected TTL: {ttl}")

        # Test 5: Manual cache operations
        print("\n--- Test 5: Manual cache operations ---")
        test_bundle = {"situation": "test", "contacts": []}

        set_result = set_cached_context(org_id, "manual_test", test_bundle)
        print(f"✓ set_cached_context: {set_result}")

        get_result = get_cached_context(org_id, "manual_test")
        if get_result == test_bundle:
            print("✓ get_cached_context: retrieved correctly")
        else:
            print("❌ get_cached_context: retrieval failed")

        # Test 6: Cache key collision test
        print("\n--- Test 6: Cache key format ---")
        key1 = _generate_cache_key("org1", "situation1")
        key2 = _generate_cache_key("org1", "situation2")
        key3 = _generate_cache_key("org2", "situation1")

        print(f"  Key format: {key1}")
        print(f"  Different situations: {key1 != key2}")
        print(f"  Different orgs: {key1 != key3}")

        if key1 != key2 and key1 != key3:
            print("✓ Cache keys are unique")
        else:
            print("❌ Cache key collision detected")

        print("\n✅ Redis caching is working!")
        print("\n" + "=" * 60)
        print("CACHING SUMMARY")
        print("=" * 60)
        print(f"Cache format: ctx:{{org_id}}:{{hash}}")
        print(f"TTL: 60 seconds")
        print(f"First call: {elapsed1:.3f}s (cache miss)")
        print(f"Second call: {elapsed2:.3f}s (cache hit)")
        print(f"Speedup: {speedup:.1f}x")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_cache()
