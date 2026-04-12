"""
Precedent Graph — search document chunks for similar past situations.
Per Graph Enrichment spec: ANN query against embedded document chunks,
returns precedents[] for context bundles.
"""

import logging
from typing import List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.graph.embedder import embed_text

logger = logging.getLogger(__name__)


def search_precedents(
    db: Session,
    org_id: str,
    situation: str,
    limit: int = 3,
    similarity_threshold: float = 0.70,
) -> List[Dict]:
    """
    Find document chunks similar to the given situation.

    Args:
        db: Database session
        org_id: Organization ID
        situation: The situation text to find precedents for
        limit: Max precedents to return
        similarity_threshold: Minimum cosine similarity (0-1)

    Returns:
        List of precedent dicts with similarity, situation, chunk_text, doc_title, metadata
    """
    try:
        query_embedding = embed_text(situation)
    except Exception as e:
        logger.warning(f"Precedent search embedding failed: {e}")
        return []

    try:
        results = db.execute(
            text("""
                SELECT
                    dc.chunk_text,
                    dc.doc_title,
                    dc.metadata,
                    1 - (dc.embedding <=> :embedding::vector) AS similarity
                FROM document_chunks dc
                WHERE dc.org_id = :org_id
                  AND dc.embedding IS NOT NULL
                  AND 1 - (dc.embedding <=> :embedding::vector) >= :threshold
                ORDER BY dc.embedding <=> :embedding::vector
                LIMIT :limit
            """),
            {
                "org_id": org_id,
                "embedding": str(query_embedding),
                "threshold": similarity_threshold,
                "limit": limit,
            },
        ).fetchall()

        precedents = []
        for r in results:
            precedents.append({
                "similarity": round(float(r.similarity), 2),
                "situation": r.chunk_text[:200],
                "doc_title": r.doc_title,
                "metadata": r.metadata or {},
            })

        return precedents

    except Exception as e:
        logger.warning(f"Precedent search query failed: {e}")
        return []


def store_document_chunks(
    db: Session,
    org_id: str,
    doc_id: str,
    doc_title: str,
    chunks: List[str],
    doc_type: str = "upload",
    metadata: Optional[Dict] = None,
):
    """
    Embed and store document chunks for precedent search.

    Args:
        db: Database session
        org_id: Organization ID
        doc_id: Source document identifier
        doc_title: Document title
        chunks: List of text chunks to embed and store
        doc_type: Source type (upload, gdocs, notion)
        metadata: Additional metadata per chunk
    """
    import json

    stored = 0
    for i, chunk in enumerate(chunks):
        if not chunk or len(chunk.strip()) < 50:
            continue

        try:
            embedding = embed_text(chunk)
        except Exception as e:
            logger.warning(f"Chunk embedding failed for doc {doc_id} chunk {i}: {e}")
            continue

        try:
            db.execute(
                text("""
                    INSERT INTO document_chunks (
                        org_id, doc_id, doc_type, doc_title,
                        chunk_index, chunk_text, embedding, metadata
                    )
                    VALUES (
                        :org_id, :doc_id, :doc_type, :doc_title,
                        :chunk_index, :chunk_text, :embedding::vector,
                        :metadata::jsonb
                    )
                    ON CONFLICT (org_id, doc_id, chunk_index) DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding,
                        metadata = EXCLUDED.metadata,
                        doc_title = EXCLUDED.doc_title
                """),
                {
                    "org_id": org_id,
                    "doc_id": doc_id,
                    "doc_type": doc_type,
                    "doc_title": doc_title,
                    "chunk_index": i,
                    "chunk_text": chunk[:2000],
                    "embedding": str(embedding),
                    "metadata": json.dumps(metadata or {}),
                },
            )
            stored += 1
        except Exception as e:
            logger.warning(f"Chunk store failed for doc {doc_id} chunk {i}: {e}")

    db.commit()
    logger.info(f"Stored {stored}/{len(chunks)} chunks for doc {doc_id}")
    return stored
