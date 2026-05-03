"""
Phase 1: Document chunk vector search.

Uses pgvector cosine similarity over `document_chunks.embedding` (768-dim)
populated when users upload PDFs/docs via /v1/documents/upload. The embedding
model is Gemini's `gemini-embedding-001` — same model used at ingest, so
query-time embedding is comparable.

Returns top-k chunks with similarity score so caller can blend into bundle.
NEVER raises — returns [] on any failure so retrieval falls through cleanly.
"""

from __future__ import annotations

import logging
from typing import List, Dict

from sqlalchemy import text

from app.database import SessionLocal
from app.llm import llm_client

logger = logging.getLogger(__name__)


def live_search(org_id: str, query: str, limit: int = 5) -> List[Dict]:
    """
    Embed query, run vector similarity over document_chunks for this org.

    Args:
        org_id: org UUID (string)
        query: free-text query
        limit: max chunks returned (hard cap 10)

    Returns:
        list of dicts: {chunk_id, doc_id, doc_title, chunk_text, similarity, source}
    """
    if not org_id or not query:
        return []
    limit = min(max(1, int(limit)), 10)

    try:
        embedding = llm_client.embed(org_id=org_id, text_in=query)
    except Exception as e:
        logger.debug(f"doc_search embed failed: {e}")
        return []

    if not embedding:
        return []

    # pgvector expects "[v1,v2,...]" string for the cast to vector
    vec_literal = "[" + ",".join(f"{float(v):.6f}" for v in embedding) + "]"

    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT id, doc_id, doc_title, chunk_text,
                       1 - (embedding <=> CAST(:vec AS vector)) AS similarity
                FROM document_chunks
                WHERE org_id = :oid
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :limit
            """),
            {"oid": org_id, "vec": vec_literal, "limit": limit},
        ).fetchall()
    except Exception as e:
        logger.debug(f"doc_search query failed: {e}")
        return []
    finally:
        db.close()

    out = []
    for r in rows:
        sim = float(r.similarity or 0.0)
        # 0.5 cosine sim is the floor for "actually relevant" with this model
        if sim < 0.50:
            continue
        out.append({
            "chunk_id": str(r.id),
            "doc_id": r.doc_id,
            "doc_title": r.doc_title or "(untitled)",
            "chunk_text": (r.chunk_text or "")[:600],
            "similarity": round(sim, 4),
            "source": "doc_live",
        })
    return out
