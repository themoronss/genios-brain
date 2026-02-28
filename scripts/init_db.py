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

-- 5. Policies table (for Layer 1 R4)
CREATE TABLE IF NOT EXISTS policies (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    policy_type TEXT NOT NULL,
    condition JSONB NOT NULL DEFAULT '{}',
    effect JSONB NOT NULL DEFAULT '{}',
    priority INT DEFAULT 0,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE policies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access on policies" ON policies
    FOR ALL USING (true) WITH CHECK (true);

-- 6. Decision logs table (for Layer 1 R5)
CREATE TABLE IF NOT EXISTS decision_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    intent_type TEXT NOT NULL,
    context_hash TEXT,
    decision_summary TEXT,
    outcome TEXT,
    outcome_score FLOAT DEFAULT 0.0,
    embedding VECTOR(3072),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE decision_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all access on decision_logs" ON decision_logs
    FOR ALL USING (true) WITH CHECK (true);

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


# ---------- Policy Seeds ----------

POLICY_SEEDS = [
    {
        "workspace_id": "w1",
        "policy_type": "org",
        "condition": {"recipient_tier": "VIP"},
        "effect": {"requires_approval": True},
        "priority": 10,
        "active": True,
    },
    {
        "workspace_id": "w1",
        "policy_type": "risk",
        "condition": {"intent_type": "cold_outreach"},
        "effect": {"requires_approval": True, "risk_flag": "external_first_contact"},
        "priority": 8,
        "active": True,
    },
    {
        "workspace_id": "w1",
        "policy_type": "org",
        "condition": {"day_of_week": ["saturday", "sunday"]},
        "effect": {"delay_until": "next_monday"},
        "priority": 5,
        "active": True,
    },
]


# ---------- Decision Log Seeds ----------

DECISION_LOG_SEEDS = [
    {
        "workspace_id": "w1",
        "actor_id": "u1",
        "intent_type": "follow_up",
        "decision_summary": "Drafted follow-up email using warm template, scheduled for 9am.",
        "outcome": "success",
        "outcome_score": 0.9,
        "context_hash": "abc123",
    },
    {
        "workspace_id": "w1",
        "actor_id": "u1",
        "intent_type": "follow_up",
        "decision_summary": "Sent aggressive follow-up. Investor responded negatively.",
        "outcome": "failure",
        "outcome_score": 0.2,
        "context_hash": "def456",
    },
    {
        "workspace_id": "w1",
        "actor_id": "u1",
        "intent_type": "schedule_meeting",
        "decision_summary": "Scheduled meeting at investor's preferred time slot.",
        "outcome": "success",
        "outcome_score": 0.95,
        "context_hash": "ghi789",
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


def seed_policies(client):
    """Insert policy seed data."""
    print("Inserting policy seeds...")
    result = client.table("policies").insert(POLICY_SEEDS).execute()
    if result.data:
        print(f"  ✓ {len(result.data)} policy rows inserted.")
    else:
        print("  ✗ Policy insert returned no data. Check table/RLS.")


def seed_decision_logs(client):
    """Insert decision log seed data (without embeddings for MVP)."""
    print("Inserting decision log seeds...")
    result = client.table("decision_logs").insert(DECISION_LOG_SEEDS).execute()
    if result.data:
        print(f"  ✓ {len(result.data)} decision log rows inserted.")
    else:
        print("  ✗ Decision log insert returned no data. Check table/RLS.")


def main():
    print("Connecting to Supabase...")
    client = get_supabase_client()

    seed_memory(client)
    seed_knowledge(client)
    seed_policies(client)
    seed_decision_logs(client)

    print("\nDone.")


if __name__ == "__main__":
    main()

