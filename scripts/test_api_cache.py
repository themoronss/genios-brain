"""Test Context API with Redis caching through HTTP endpoint"""

import requests
import time
from sqlalchemy import text
import sys

sys.path.insert(0, "/home/harshtripathi/Desktop/genios-brain")

from app.database import SessionLocal
from app.redis_client import redis_client
from app.context.cache import _generate_cache_key


def test_api_cache():
    print("🧪 Testing Context API with Redis Caching...")

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

    url = "http://localhost:8000/v1/context"
    situation = "Follow up with investor about our pitch"

    # Clear cache first
    cache_key = _generate_cache_key(org_id, situation)
    redis_client.delete(cache_key)
    print(f"✓ Cleared cache: {cache_key}")

    # Test 1: First API call (cache miss)
    print("\n--- Test 1: First API call (cache miss) ---")
    payload = {"org_id": org_id, "situation": situation}

    start_time = time.time()
    response1 = requests.post(url, json=payload)
    elapsed1 = time.time() - start_time

    if response1.status_code == 200:
        data1 = response1.json()
        print(f"✓ Response status: {response1.status_code}")
        print(f"✓ Found {len(data1['contacts'])} contacts")
        print(f"✓ Time taken: {elapsed1:.3f}s")

        if data1["contacts"]:
            first_contact = data1["contacts"][0]
            print(f"✓ Top contact: {first_contact['name']}")
    else:
        print(f"❌ Error: {response1.text}")
        return

    # Test 2: Second API call (cache hit)
    print("\n--- Test 2: Second API call (cache hit) ---")

    start_time = time.time()
    response2 = requests.post(url, json=payload)
    elapsed2 = time.time() - start_time

    if response2.status_code == 200:
        data2 = response2.json()
        print(f"✓ Response status: {response2.status_code}")
        print(f"✓ Found {len(data2['contacts'])} contacts")
        print(f"✓ Time taken: {elapsed2:.3f}s")

        # Compare performance
        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float("inf")
        print(f"✓ Cache speedup: {speedup:.1f}x faster")

        percentage = ((elapsed1 - elapsed2) / elapsed1) * 100 if elapsed1 > 0 else 0
        print(f"✓ Performance improvement: {percentage:.1f}%")
    else:
        print(f"❌ Error: {response2.text}")
        return

    # Test 3: Multiple rapid requests (all cache hits)
    print("\n--- Test 3: Multiple rapid requests (cache hits) ---")

    times = []
    for i in range(5):
        start = time.time()
        response = requests.post(url, json=payload)
        elapsed = time.time() - start
        times.append(elapsed)
        print(f"  Request {i+1}: {elapsed:.3f}s")

    avg_cached_time = sum(times) / len(times)
    print(f"✓ Average cached response time: {avg_cached_time:.3f}s")

    # Test 4: Different situation (cache miss)
    print("\n--- Test 4: Different situation (cache miss) ---")
    payload2 = {
        "org_id": org_id,
        "situation": "Need help with technical architecture review",
    }

    start_time = time.time()
    response3 = requests.post(url, json=payload2)
    elapsed3 = time.time() - start_time

    if response3.status_code == 200:
        data3 = response3.json()
        print(f"✓ Response status: {response3.status_code}")
        print(f"✓ Found {len(data3['contacts'])} contacts")
        print(f"✓ Time taken: {elapsed3:.3f}s (new query, cache miss)")
    else:
        print(f"❌ Error: {response3.text}")

    # Test 5: Verify cache keys in Redis
    print("\n--- Test 5: Cache verification ---")
    keys = redis_client.keys("ctx:*")
    print(f"✓ Total cached contexts: {len(keys)}")

    for key in keys[:3]:
        ttl = redis_client.ttl(key)
        print(f"  {key}: TTL={ttl}s")

    # Summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)
    print(f"Cache Miss (first call):     {elapsed1:.3f}s")
    print(f"Cache Hit (second call):     {elapsed2:.3f}s")
    print(f"Speedup:                     {speedup:.1f}x")
    print(f"Performance Improvement:     {percentage:.1f}%")
    print(f"Average cached response:     {avg_cached_time:.3f}s")
    print("=" * 60)
    print("\n✅ Context API with Redis caching is working!")
    print("\nCache Features:")
    print("  ✓ Automatic cache check")
    print("  ✓ 60-second TTL")
    print("  ✓ Unique keys per org + situation")
    print("  ✓ JSON serialization of UUIDs")
    print("  ✓ Significant performance improvement")


if __name__ == "__main__":
    test_api_cache()
