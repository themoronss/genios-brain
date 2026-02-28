"""
Test Supabase connectivity and memory_items table access.

These tests require a valid .env file with SUPABASE_URL and SUPABASE_KEY.
They will be skipped if credentials are not configured.
"""

import pytest
import os
from dotenv import load_dotenv

load_dotenv()

# Skip all tests in this module if Supabase is not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"),
    reason="Supabase credentials not configured (set SUPABASE_URL and SUPABASE_KEY in .env)"
)


def test_supabase_connection():
    """Test that we can connect to Supabase."""
    from core.stores.database import get_supabase_client

    client = get_supabase_client()
    assert client is not None


def test_memory_items_table_accessible():
    """Test that the memory_items table exists and is queryable."""
    from core.stores.database import get_supabase_client

    client = get_supabase_client()
    result = client.table("memory_items").select("*").limit(1).execute()

    # Should not raise an error; data can be empty or have rows
    assert isinstance(result.data, list)


def test_memory_store_get_by_actor():
    """Test MemoryStore retrieves data for an actor."""
    from core.stores.memory_store import MemoryStore

    store = MemoryStore()
    rows = store.get_by_actor("u1")

    assert isinstance(rows, list)
    # If seed data was inserted, we should have results
    if len(rows) > 0:
        assert "actor_id" in rows[0]
        assert rows[0]["actor_id"] == "u1"


def test_retrieval_engine_with_db():
    """Test that RetrievalEngine works with a real MemoryStore."""
    from core.stores.memory_store import MemoryStore
    from layers.layer1_retrieval.retrieval_engine import RetrievalEngine

    store = MemoryStore()
    engine = RetrievalEngine(memory_store=store)

    bundle = engine.run(
        intent="follow_up_investor",
        workspace_id="w1",
        actor_id="u1"
    )

    assert bundle.scope.workspace_id == "w1"
    assert isinstance(bundle.memory.preferences, dict)
    assert isinstance(bundle.memory.entity_data, dict)
