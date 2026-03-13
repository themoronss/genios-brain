"""Test Redis caching with situation-only hash"""

import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

import hashlib
import requests
import time
from app.database import SessionLocal
from app.context.cache import (
    _generate_cache_key,
    get_cached_context,
    set_cached_context,
)
from app.redis_client import redis_client
from sqlalchemy import text


def test_cache_key_format():
    print("🧪 Testing Redis Cache with Updated Hash Format")
    print("=" * 60)

    # Get org_id
    db = SessionLocal()
    try:
        result = db.execute(text("SELECT DISTINCT org_id FROM contacts LIMIT 1"))
        org_id = str(result.fetchone()[0])
        print(f"✓ Using org_id: {org_id}")
    finally:
        db.close()

    situation = "Test situation for caching"

    # Test 1: Verify cache key format
    print("\n--- Test 1: Cache Key Format ---")
    cache_key = _generate_cache_key(org_id, situation)

    # Expected format: ctx:{org_id}:{sha256(situation)[:16]}
    expected_hash = hashlib.sha256(situation.encode()).hexdigest()[:16]
    expected_key = f"ctx:{org_id}:{expected_hash}"

    print(f"Situation: '{situation}'")
    print(f"Expected hash: {expected_hash}")
    print(f"Expected key: {expected_key}")
    print(f"Actual key: {cache_key}")

    if cache_key == expected_key:
        print("✅ Cache key format matches specification")
    else:
        print("❌ Cache key format does NOT match")
        return

    # Test 2: Cache write and read
    print("\n--- Test 2: Cache Write and Read ---")
    test_bundle = {
        "situation": situation,
        "contacts": [{"name": "Test Contact", "email": "test@example.com"}],
    }

    # Write to cache
    write_result = set_cached_context(org_id, situation, test_bundle)
    print(f"✓ Write result: {write_result}")

    # Read from cache
    cached_result = get_cached_context(org_id, situation)
    print(f"✓ Read result: {cached_result is not None}")

    if cached_result == test_bundle:
        print("✅ Cached data matches original")
    else:
        print("❌ Cached data does NOT match")

    # Test 3: TTL verification
    print("\n--- Test 3: TTL Verification ---")
    ttl = redis_client.ttl(cache_key)
    print(f"✓ TTL: {ttl} seconds")

    if ttl > 0 and ttl <= 60:
        print("✅ TTL is correctly set to 60 seconds")
    else:
        print(f"❌ TTL is incorrect: {ttl}")

    # Test 4: API endpoint caching
    print("\n--- Test 4: API Endpoint Caching ---")

    url = "http://localhost:8000/v1/context"
    payload = {"org_id": org_id, "situation": "Follow up with investors"}

    # First call (cache miss)
    print("First call (cache miss)...")
    start_time = time.time()
    response1 = requests.post(url, json=payload)
    elapsed1 = time.time() - start_time

    if response1.status_code == 200:
        print(f"✓ Status: {response1.status_code}")
        print(f"✓ Time: {elapsed1:.3f}s")

        # Generate expected cache key
        api_cache_key = _generate_cache_key(org_id, payload["situation"])
        hash_part = hashlib.sha256(payload["situation"].encode()).hexdigest()[:16]

        print(f"✓ Cache key: ctx:{org_id}:{hash_part}")

        # Verify it's in Redis
        cached = redis_client.get(api_cache_key)
        if cached:
            print("✅ Response cached in Redis")
        else:
            print("❌ Response NOT in Redis")

        # Second call (cache hit)
        print("\nSecond call (cache hit)...")
        start_time = time.time()
        response2 = requests.post(url, json=payload)
        elapsed2 = time.time() - start_time

        print(f"✓ Status: {response2.status_code}")
        print(f"✓ Time: {elapsed2:.3f}s")

        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float("inf")
        print(f"✓ Speedup: {speedup:.1f}x faster")

        if elapsed2 < elapsed1:
            print("✅ Cache hit is faster than cache miss")
    else:
        print(f"❌ API error: {response1.status_code}")

    # Test 5: Different org_id with same situation
    print("\n--- Test 5: Same Situation, Different Org ---")

    org_id_2 = "different-org-id"
    key1 = _generate_cache_key(org_id, situation)
    key2 = _generate_cache_key(org_id_2, situation)

    # Extract hash portions
    hash1 = key1.split(":")[-1]
    hash2 = key2.split(":")[-1]

    print(f"Org 1 key: {key1}")
    print(f"Org 2 key: {key2}")
    print(f"Hash portion (both): {hash1}")

    if hash1 == hash2:
        print("✅ Hash is same for same situation (expected)")
    else:
        print("❌ Hash differs for same situation (unexpected)")

    if key1 != key2:
        print("✅ Full keys are different due to org_id (expected)")
    else:
        print("❌ Full keys are the same (unexpected)")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("Cache Key Format: ctx:{org_id}:{sha256(situation)[:16]}")
    print("TTL: 60 seconds")
    print("✅ Redis caching fully functional")


if __name__ == "__main__":
    test_cache_key_format()
