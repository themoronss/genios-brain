"""
VectorStore — thin interface over pgvector.

Purpose: callers depend on this interface, not on pgvector-specific SQL.
When we migrate to Qdrant/Turbopuffer, only this module changes.
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def search(
    db: Session,
    org_id: str,
    query_embedding: list,
    limit: int = 50,
    min_similarity: float = 0.0,
    contact_id: Optional[str] = None,
) -> list:
    """
    K-NN on interactions.embedding using cosine distance (pgvector `<=>`).
    Returns ordered by similarity desc. Filters by org (always) and by
    contact if given.
    """
    if not query_embedding:
        return []

    where = ["org_id = :org"]
    params = {
        "org": org_id,
        "vec": str(query_embedding),
        "limit": limit,
        "min_sim": min_similarity,
    }
    if contact_id:
        where.append("contact_id = :cid")
        params["cid"] = contact_id

    sql = f"""
        SELECT id, contact_id, subject, raw_body AS body, summary,
               interaction_at AS sent_at,
               1 - (embedding <=> :vec::vector) AS similarity
        FROM interactions
        WHERE {' AND '.join(where)}
          AND embedding IS NOT NULL
          AND 1 - (embedding <=> :vec::vector) >= :min_sim
        ORDER BY embedding <=> :vec::vector
        LIMIT :limit
    """
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        logger.warning(f"VectorStore.search failed: {e}")
        return []

    return [
        {
            "id": str(r.id),
            "contact_id": str(r.contact_id) if r.contact_id else None,
            "subject": r.subject,
            "body": r.body,
            "summary": r.summary,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "score": float(r.similarity or 0),
            "source": "vector",
        }
        for r in rows
    ]
