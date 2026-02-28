"""
Test vector search and embedding functionality.

These tests require valid .env credentials for both Supabase and Gemini.
They will be skipped if credentials are not configured.
"""

import pytest
import os
from dotenv import load_dotenv

load_dotenv()

# Skip all tests in this module if credentials are not configured
has_supabase = os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY")
has_gemini = os.getenv("GEMINI_API_KEY")

skip_no_supabase = pytest.mark.skipif(
    not has_supabase,
    reason="Supabase credentials not configured"
)
skip_no_gemini = pytest.mark.skipif(
    not has_gemini,
    reason="GEMINI_API_KEY not configured"
)
skip_no_credentials = pytest.mark.skipif(
    not (has_supabase and has_gemini),
    reason="Supabase and/or Gemini credentials not configured"
)


@skip_no_gemini
def test_embedding_service_generates_vector():
    """Test that EmbeddingService returns a 3072-dim vector."""
    from core.stores.embedding_service import EmbeddingService

    service = EmbeddingService()
    vector = service.embed("Hello world")

    assert isinstance(vector, list)
    assert len(vector) == 3072
    assert all(isinstance(v, float) for v in vector)


@skip_no_gemini
def test_embedding_query_vs_document():
    """Test that query and document embeddings produce different vectors."""
    from core.stores.embedding_service import EmbeddingService

    service = EmbeddingService()
    doc_vec = service.embed("Investor X is a VIP")
    query_vec = service.embed_query("Investor X is a VIP")

    assert isinstance(doc_vec, list)
    assert isinstance(query_vec, list)
    assert len(doc_vec) == len(query_vec) == 3072
    # They should be similar but not identical (different task_type)
    assert doc_vec != query_vec


@skip_no_credentials
def test_vector_store_search():
    """Test that VectorStore can perform a search (may return empty if no data)."""
    from core.stores.vector_store import VectorStore

    store = VectorStore()
    results = store.search(
        query="follow up with investor",
        workspace_id="w1",
        top_k=3
    )

    assert isinstance(results, list)
    # If seed data exists, validate structure
    if len(results) > 0:
        assert "content" in results[0]
        assert "similarity" in results[0]


@skip_no_credentials
def test_retrieval_engine_with_vector_store():
    """Test RetrievalEngine with a real VectorStore."""
    from core.stores.vector_store import VectorStore
    from layers.layer1_retrieval.retrieval_engine import RetrievalEngine

    store = VectorStore()
    engine = RetrievalEngine(vector_store=store)

    bundle = engine.run(
        intent="follow_up_investor",
        workspace_id="w1",
        actor_id="u1"
    )

    assert bundle.scope.workspace_id == "w1"
    assert isinstance(bundle.relevant_chunks, list)
    # Chunks may be empty if no seed data, but should not error
