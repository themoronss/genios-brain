"""
BM25 keyword retrieval over interactions.search_tsv (Postgres full-text).

Postgres `ts_rank_cd` is BM25-like in spirit; adequate at our scale. Uses
plainto_tsquery to handle casual inputs like "pricing objection in Q3".

When `expanded_query` is supplied, both queries are OR'd: the user's natural
phrase plus the expansion's alias hits. The score uses ts_rank_cd against
whichever tsquery produced more matches, keeping ranking signal intact.
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
    expanded_query: Optional[str] = None,
) -> list:
    if not query or not query.strip():
        return []

    # Two tsqueries: the natural phrase via plainto, and the expansion via
    # to_tsquery. Match if either one hits. Rank by the natural query when it
    # matches; fall back to the expanded query rank otherwise.
    use_expansion = bool(expanded_query and expanded_query.strip())

    where = ["org_id = :org"]
    params = {"org": org_id, "q": query, "limit": limit}

    if use_expansion:
        params["qx"] = expanded_query
        where.append(
            "(search_tsv @@ plainto_tsquery('english', :q) "
            " OR search_tsv @@ to_tsquery('english', :qx))"
        )
        rank_expr = (
            "GREATEST("
            "  ts_rank_cd(search_tsv, plainto_tsquery('english', :q)),"
            "  ts_rank_cd(search_tsv, to_tsquery('english', :qx))"
            ") AS rank"
        )
    else:
        where.append("search_tsv @@ plainto_tsquery('english', :q)")
        rank_expr = "ts_rank_cd(search_tsv, plainto_tsquery('english', :q)) AS rank"

    if contact_id:
        where.append("contact_id = :cid")
        params["cid"] = contact_id

    sql = f"""
        SELECT id, contact_id, subject, raw_body AS body, summary,
               interaction_at AS sent_at,
               {rank_expr}
        FROM interactions
        WHERE {' AND '.join(where)}
        ORDER BY rank DESC
        LIMIT :limit
    """
    try:
        rows = db.execute(text(sql), params).fetchall()
    except Exception as e:
        logger.warning(f"BM25.search failed: {e}")
        # If the expanded tsquery was malformed, retry without it.
        if use_expansion:
            return search(db, org_id, query, limit, contact_id, expanded_query=None)
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
