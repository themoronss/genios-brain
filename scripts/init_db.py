"""
init_db.py — Initialize tables in Supabase and insert seed data.

Usage:
    python scripts/init_db.py

This script uses the Supabase client to insert seed data.
Tables must be created via the Supabase SQL Editor first.

=================================================================
  RUN THIS SQL IN SUPABASE DASHBOARD -> SQL EDITOR -> NEW QUERY
=================================================================

-- 1. Memory items table (from Phase 1)
CREATE TABLE IF NOT EXISTS memory_items (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content JSONB NOT NULL,
    confidence FLOAT DEFAULT 1.0
);

ALTER TABLE memory_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access on memory_items" ON memory_items
    FOR ALL USING (true) WITH CHECK (true);

-- 2. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 3. Knowledge chunks table (for vector search)
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(3072),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access on knowledge_chunks" ON knowledge_chunks
    FOR ALL USING (true) WITH CHECK (true);

-- 4. Similarity search function
CREATE OR REPLACE FUNCTION match_knowledge_chunks(
    query_embedding VECTOR(3072),
    match_workspace_id TEXT,
    match_count INT DEFAULT 5,
    match_threshold FLOAT DEFAULT 0.5
)
RETURNS TABLE (
    id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        kc.id,
        kc.content,
        kc.metadata,
        1 - (kc.embedding <=> query_embedding) AS similarity
    FROM knowledge_chunks kc
    WHERE kc.workspace_id = match_workspace_id
        AND 1 - (kc.embedding <=> query_embedding) > match_threshold
    ORDER BY kc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

=================================================================
"""

import sys
import os

# Add project root to path so we can import core modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.stores.database import get_supabase_client


# ---------- Memory Seeds ----------

MEMORY_SEEDS = [
    {
        "workspace_id": "w1",
        "actor_id": "u1",
        "memory_type": "preference",
        "content": {"tone": "confident"},
        "confidence": 1.0,
    },
    {
        "workspace_id": "w1",
        "actor_id": "u1",
        "memory_type": "entity",
        "content": {"Investor X": {"tier": "VIP"}},
        "confidence": 1.0,
    },
]


# ---------- Knowledge Chunk Seeds ----------
# These will be embedded at insert time via VectorStore

KNOWLEDGE_SEEDS = [
    {
        "workspace_id": "w1",
        "content": "Investor X is a VIP tier investor who prefers confident, direct communication. They have invested in 3 previous rounds.",
        "metadata": {"type": "investor_profile", "entity": "Investor X"},
    },
    {
        "workspace_id": "w1",
        "content": "Follow-up emails to VIP investors should be sent within 48 hours of a meeting. Tone should be professional yet warm.",
        "metadata": {"type": "policy_guideline", "category": "communication"},
    },
    {
        "workspace_id": "w1",
        "content": "The last meeting with Investor X discussed Series A terms. Key points: valuation cap of $10M, 20% equity stake, board seat requirement.",
        "metadata": {"type": "meeting_notes", "entity": "Investor X"},
    },
    {
        "workspace_id": "w1",
        "content": "Cold outreach to new investors should include a one-pager, pitch deck link, and a specific ask. Avoid generic introductions.",
        "metadata": {"type": "policy_guideline", "category": "outreach"},
    },
]


def seed_memory(client):
    """Insert memory seed data."""
    print("Inserting memory seeds...")
    result = client.table("memory_items").insert(MEMORY_SEEDS).execute()
    if result.data:
        print(f"  ✓ {len(result.data)} memory rows inserted.")
    else:
        print("  ✗ Memory insert returned no data. Check table/RLS.")


def seed_knowledge(client):
    """Insert knowledge chunks with embeddings."""
    print("Inserting knowledge chunks with Gemini embeddings...")

    try:
        from core.stores.embedding_service import EmbeddingService
        from core.stores.vector_store import VectorStore

        embedding_service = EmbeddingService()
        vector_store = VectorStore(embedding_service=embedding_service, client=client)

        for chunk in KNOWLEDGE_SEEDS:
            result = vector_store.insert(
                workspace_id=chunk["workspace_id"],
                content=chunk["content"],
                metadata=chunk["metadata"],
            )
            if result:
                print(f"  ✓ Inserted: {chunk['content'][:60]}...")
            else:
                print(f"  ✗ Failed: {chunk['content'][:60]}...")

        print(f"  ✓ {len(KNOWLEDGE_SEEDS)} knowledge chunks inserted with embeddings.")

    except ValueError as e:
        print(f"  ✗ Skipping knowledge seeds: {e}")
        print("    Set GEMINI_API_KEY in .env to enable embedding generation.")


def main():
    print("Connecting to Supabase...")
    client = get_supabase_client()

    seed_memory(client)
    seed_knowledge(client)

    print("\nDone.")


if __name__ == "__main__":
    main()
