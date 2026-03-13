#!/usr/bin/env python3
"""
Complete System Test - Tests all currently working components
Run this to verify the MVP is functioning correctly
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from sqlalchemy import text
from app.database import SessionLocal, engine
from app.redis_client import redis_client
from app.graph.embedder import embed_text
from app.context.situation_embedder import embed_situation
from app.graph.queries import search_contacts_by_embedding
from app.context.compiler import compile_context

# Test configuration
TEST_ORG_ID = "87b0235e-e29d-468a-b841-522c13546515"


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(test_name, passed, message=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} | {test_name}")
    if message:
        print(f"         {message}")


def test_database_connection():
    """Test 1: Database connectivity"""
    print_section("TEST 1: Database Connection")

    try:
        db = SessionLocal()
        result = db.execute(text("SELECT version()"))
        version = result.fetchone()[0]
        db.close()

        print_result("PostgreSQL Connection", True, f"Connected: {version[:50]}...")
        return True
    except Exception as e:
        print_result("PostgreSQL Connection", False, str(e))
        return False


def test_pgvector_extension():
    """Test 2: pgvector extension"""
    print_section("TEST 2: PGVector Extension")

    try:
        db = SessionLocal()
        result = db.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        )
        version = result.fetchone()
        db.close()

        if version:
            print_result("pgvector Extension", True, f"Version: {version[0]}")
            return True
        else:
            print_result("pgvector Extension", False, "Extension not installed")
            return False
    except Exception as e:
        print_result("pgvector Extension", False, str(e))
        return False


def test_redis_connection():
    """Test 3: Redis connectivity"""
    print_section("TEST 3: Redis Connection")

    try:
        redis_client.ping()
        print_result("Redis Connection", True, "Redis is responding")

        # Test set/get
        redis_client.set("test_key", "test_value", ex=10)
        value = redis_client.get("test_key")

        if value == "test_value":
            print_result(
                "Redis Read/Write", True, "Set and retrieved value successfully"
            )
            return True
        else:
            print_result("Redis Read/Write", False, "Value mismatch")
            return False

    except Exception as e:
        print_result("Redis Connection", False, str(e))
        return False


def test_data_integrity():
    """Test 4: Data in database"""
    print_section("TEST 4: Data Integrity")

    db = SessionLocal()

    try:
        # Check orgs
        result = db.execute(text("SELECT COUNT(*) FROM orgs"))
        org_count = result.fetchone()[0]
        print_result("Organizations Table", org_count > 0, f"{org_count} organizations")

        # Check contacts
        result = db.execute(
            text(f"SELECT COUNT(*) FROM contacts WHERE org_id = '{TEST_ORG_ID}'")
        )
        contact_count = result.fetchone()[0]
        print_result("Contacts Table", contact_count > 0, f"{contact_count} contacts")

        # Check interactions
        result = db.execute(
            text(f"SELECT COUNT(*) FROM interactions WHERE org_id = '{TEST_ORG_ID}'")
        )
        interaction_count = result.fetchone()[0]
        print_result(
            "Interactions Table",
            interaction_count > 0,
            f"{interaction_count} interactions",
        )

        # Check embeddings
        result = db.execute(
            text(
                f"SELECT COUNT(*) FROM contacts WHERE org_id = '{TEST_ORG_ID}' AND embedding IS NOT NULL"
            )
        )
        embedding_count = result.fetchone()[0]
        print_result(
            "Contact Embeddings",
            embedding_count > 0,
            f"{embedding_count} contacts have embeddings",
        )

        # Check OAuth tokens
        result = db.execute(
            text(f"SELECT COUNT(*) FROM oauth_tokens WHERE org_id = '{TEST_ORG_ID}'")
        )
        token_count = result.fetchone()[0]
        print_result(
            "OAuth Tokens", token_count > 0, f"{token_count} OAuth tokens stored"
        )

        db.close()
        return contact_count > 0 and interaction_count > 0

    except Exception as e:
        print_result("Data Integrity", False, str(e))
        db.close()
        return False


def test_embedding_generation():
    """Test 5: Embedding generation"""
    print_section("TEST 5: Embedding Generation")

    try:
        test_text = "Sarah Chen is a partner at Sequoia Capital interested in B2B SaaS"

        start_time = time.time()
        embedding = embed_text(test_text)
        elapsed = (time.time() - start_time) * 1000

        print_result(
            "Gemini Embedding",
            True,
            f"Generated {len(embedding)}-dimensional vector in {elapsed:.2f}ms",
        )
        print_result(
            "Vector Dimensions", len(embedding) == 3072, f"Dimensions: {len(embedding)}"
        )

        return len(embedding) == 3072

    except Exception as e:
        print_result("Embedding Generation", False, str(e))
        return False


def test_situation_embedding():
    """Test 6: Situation embedding"""
    print_section("TEST 6: Situation Embedding")

    try:
        situations = [
            "Follow up with investor about our Series A round",
            "Schedule technical review with engineering candidate",
            "Send partnership proposal to enterprise customer",
        ]

        for situation in situations:
            start_time = time.time()
            embedding = embed_situation(situation)
            elapsed = (time.time() - start_time) * 1000

            print_result(
                f"Situation: '{situation[:40]}...'",
                len(embedding) == 3072,
                f"{len(embedding)} dims, {elapsed:.2f}ms",
            )

        return True

    except Exception as e:
        print_result("Situation Embedding", False, str(e))
        return False


def test_vector_search():
    """Test 7: Vector similarity search"""
    print_section("TEST 7: Vector Similarity Search")

    try:
        db = SessionLocal()

        # Create test query
        query = "investor relations and fundraising discussions"
        query_vector = embed_situation(query)

        start_time = time.time()
        results = search_contacts_by_embedding(db, TEST_ORG_ID, query_vector, limit=5)
        elapsed = (time.time() - start_time) * 1000

        db.close()

        print_result(
            "Vector Search",
            len(results) > 0,
            f"Found {len(results)} contacts in {elapsed:.2f}ms",
        )

        if results:
            print("\n  Top matches:")
            for i, contact in enumerate(results[:3], 1):
                print(f"    {i}. {contact['name']} ({contact['email']})")
                print(f"       Company: {contact.get('company', 'N/A')}")

        return len(results) > 0

    except Exception as e:
        print_result("Vector Search", False, str(e))
        return False


def test_context_compilation():
    """Test 8: Context compilation"""
    print_section("TEST 8: Context Bundle Compilation")

    try:
        db = SessionLocal()

        situations = [
            "Follow up with investors about our pitch deck",
            "Technical architecture review",
            "Partnership discussions for enterprise customers",
        ]

        for situation in situations:
            start_time = time.time()
            context = compile_context(db, TEST_ORG_ID, situation)
            elapsed = (time.time() - start_time) * 1000

            print_result(
                f"Situation: '{situation[:35]}...'",
                "contacts" in context and len(context["contacts"]) > 0,
                f"{len(context['contacts'])} contacts, {elapsed:.2f}ms",
            )

            if context["contacts"]:
                contact = context["contacts"][0]
                print(f"         → Top match: {contact['name']}")
                print(
                    f"         → Recent interactions: {len(contact['recent_interactions'])}"
                )

        db.close()
        return True

    except Exception as e:
        print_result("Context Compilation", False, str(e))
        return False


def test_cache_functionality():
    """Test 9: Redis caching"""
    print_section("TEST 9: Redis Cache Functionality")

    try:
        db = SessionLocal()
        situation = "Test caching for investor meetings"

        # First request (cache miss)
        start_time = time.time()
        context1 = compile_context(db, TEST_ORG_ID, situation)
        elapsed1 = (time.time() - start_time) * 1000

        # Second request (cache hit)
        start_time = time.time()
        context2 = compile_context(db, TEST_ORG_ID, situation)
        elapsed2 = (time.time() - start_time) * 1000

        db.close()

        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else 1

        print_result("First Request (Cache Miss)", True, f"{elapsed1:.2f}ms")
        print_result(
            "Second Request (Cache Hit)",
            elapsed2 < elapsed1,
            f"{elapsed2:.2f}ms ({speedup:.1f}x faster)",
        )

        return elapsed2 < elapsed1

    except Exception as e:
        print_result("Cache Functionality", False, str(e))
        return False


def test_contact_quality():
    """Test 10: Contact data quality"""
    print_section("TEST 10: Contact Data Quality")

    try:
        db = SessionLocal()

        # Get sample contacts
        result = db.execute(
            text(
                f"""
            SELECT 
                c.name,
                c.email,
                c.company,
                c.relationship_stage,
                COUNT(i.id) as interaction_count,
                MAX(i.interaction_at) as last_interaction
            FROM contacts c
            LEFT JOIN interactions i ON i.contact_id = c.id
            WHERE c.org_id = '{TEST_ORG_ID}'
            AND c.embedding IS NOT NULL
            GROUP BY c.id, c.name, c.email, c.company, c.relationship_stage
            ORDER BY COUNT(i.id) DESC
            LIMIT 5
        """
            )
        )

        contacts = result.fetchall()
        db.close()

        print_result(
            "Contact Data Quality",
            len(contacts) > 0,
            f"Analyzing top {len(contacts)} contacts",
        )

        if contacts:
            print("\n  Sample Contacts:")
            for contact in contacts:
                print(f"    • {contact[0]}")
                print(f"      Email: {contact[1]}")
                print(f"      Company: {contact[2] or 'N/A'}")
                print(f"      Stage: {contact[3]}")
                print(f"      Interactions: {contact[4]}")
                print(f"      Last Contact: {contact[5]}")
                print()

        return len(contacts) > 0

    except Exception as e:
        print_result("Contact Quality", False, str(e))
        return False


def run_all_tests():
    """Run all system tests"""
    print("\n" + "#" * 70)
    print("#" + " " * 68 + "#")
    print("#" + "  GeniOS Brain - Complete System Test".center(68) + "#")
    print("#" + " " * 68 + "#")
    print("#" * 70)

    tests = [
        test_database_connection,
        test_pgvector_extension,
        test_redis_connection,
        test_data_integrity,
        test_embedding_generation,
        test_situation_embedding,
        test_vector_search,
        test_context_compilation,
        test_cache_functionality,
        test_contact_quality,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test crashed: {e}")
            results.append(False)
        time.sleep(0.5)  # Brief pause between tests

    # Summary
    print_section("TEST SUMMARY")
    passed = sum(results)
    total = len(results)
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"\n  Tests Passed: {passed}/{total} ({percentage:.1f}%)")
    print(f"  Tests Failed: {total - passed}/{total}")

    if passed == total:
        print("\n  🎉 ALL TESTS PASSED! System is functioning correctly.")
    elif passed >= total * 0.8:
        print("\n  ⚠️  Most tests passed. Review failures above.")
    else:
        print("\n  ❌ Multiple failures detected. System needs attention.")

    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    run_all_tests()
