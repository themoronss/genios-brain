-- 050: Precedent Graph — document chunks with pgvector embeddings
-- Per Graph Enrichment spec: case studies, research docs, SOPs embedded
-- for ANN query "similar past situation?" in context bundles.

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
    doc_id TEXT NOT NULL,              -- source document ID (upload UUID or gdocs ID)
    doc_type TEXT NOT NULL DEFAULT 'upload',  -- upload, gdocs, notion
    doc_title TEXT,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    chunk_text TEXT NOT NULL,
    embedding vector(768),             -- pgvector 768-dim (matching existing 048 migration)
    metadata JSONB DEFAULT '{}',       -- topics, entities, source_type, etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_doc_chunks_org ON document_chunks(org_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_doc ON document_chunks(org_id, doc_id);

-- HNSW index for fast ANN search
CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
