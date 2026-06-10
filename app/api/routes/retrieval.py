"""
Hybrid retrieval endpoint (Phase 4).

POST /v1/retrieval/search  — BM25 + optional vector → RRF → cross-encoder rerank.

Callers pass the search text and (optional) precomputed embedding. If no
embedding is supplied we run a vector-less search (BM25 + rerank). This is
intentional: not every caller has/needs an embedding upfront.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.retrieval.rerank import hybrid_search

logger = logging.getLogger(__name__)
router = APIRouter()


class RetrievalRequest(BaseModel):
    query: str
    contact_id: Optional[str] = None
    limit: int = 10
    include_embedding: bool = True   # when True, embed the query server-side
    embedding: Optional[list] = None  # caller-provided embedding (takes precedence)

    @validator("query")
    def _vq(cls, v):
        if not v or not v.strip():
            raise ValueError("query is required")
        if len(v) > 500:
            raise ValueError("query too long (max 500 chars)")
        return v.strip()

    @validator("limit")
    def _vl(cls, v):
        if v < 1 or v > 50:
            raise ValueError("limit must be 1..50")
        return v


def _embed(text: str) -> Optional[list]:
    """Best-effort query embedding using the same model as ingestion."""
    try:
        from app.graph.embedder import embed_text
        return embed_text(text)
    except Exception as e:
        logger.debug(f"query embed failed: {e}")
        return None


@router.post("/v1/retrieval/search")
def retrieval_search(
    req: RetrievalRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    embedding = req.embedding
    if embedding is None and req.include_embedding:
        embedding = _embed(req.query)

    try:
        results = hybrid_search(
            db, org_id=org_id,
            query=req.query,
            query_embedding=embedding,
            limit=req.limit,
            contact_id=req.contact_id,
        )
    except Exception as e:
        logger.error(f"retrieval_search failed: {e}")
        raise HTTPException(status_code=500, detail="retrieval failed")

    for r in results:
        r.pop("body", None)  # keep response small; callers request /interactions/<id> for full body

    return {"query": req.query, "count": len(results), "results": results}
