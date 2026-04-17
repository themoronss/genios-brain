"""
BM25 keyword retrieval over interactions.search_tsv (Postgres full-text).

Postgres `ts_rank_cd` is BM25-like in spirit; adequate at our scale. Uses
plainto_tsquery to handle casual inputs like "pricing objection in Q3".
"""

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def search(
    db: Session,
    org_id: str,
    query: str,
    limit: int = 50,
    contact_id: Optional[str] = None,
) -> list:
    if not query or not query.strip():
        return []

    where = ["org_id = :org", "search_tsv @@ plainto_tsquery('english', :q)"]
    params = {"org": org_id, "q": query, "limit": limit}
    if contact_id:
        where.append("contact_id = :cid")
        params["cid"] = contact_id

    sql = f"""
        SELECT id, contact_id, subject, raw_body AS body, summary, interaction_at AS sent_at,
               ts_rank_cd(search_tsv, plainto_tsquery('english', :q)) AS rank
        FROM interactions
        WHERE {' AND '.join(where)}
        ORDER BY rank DESC
        LIMIT :limit
    """
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        logger.warning(f"BM25.search failed: {e}")
        return []

    return [
        {
            "id": str(r.id),
            "contact_id": str(r.contact_id) if r.contact_id else None,
            "subject": r.subject,
            "body": r.body,
            "summary": r.summary,
            "sent_at": r.sent_at.isoformat() if r.sent_at else None,
            "score": float(r.rank or 0),
            "source": "bm25",
        }
        for r in rows
    ]
