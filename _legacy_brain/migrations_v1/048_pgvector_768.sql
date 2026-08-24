-- Switch embeddings from 3072-dim to 768-dim (Gemini MRL output_dimensionality=768)
-- This enables pgvector HNSW indexing (limit: 2000 dims)
-- Quality loss: 0.26% — negligible

-- Step 1: NULL out existing 3072-dim embeddings (incompatible with new column size)
UPDATE contacts SET embedding = NULL WHERE embedding IS NOT NULL;
UPDATE interactions SET embedding = NULL WHERE embedding IS NOT NULL;

-- Step 2: Alter column types to vector(768)
ALTER TABLE contacts ALTER COLUMN embedding TYPE vector(768);
ALTER TABLE interactions ALTER COLUMN embedding TYPE vector(768);

-- Step 3: Create HNSW indexes (now possible with 768 dims)
CREATE INDEX IF NOT EXISTS idx_contacts_embedding
    ON contacts USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_interactions_embedding
    ON interactions USING hnsw (embedding vector_cosine_ops);

-- Post-migration: run embed_contacts() and embed_interactions() for all orgs
-- to regenerate embeddings at 768 dims. Gemini free tier: 1500 req/min.
