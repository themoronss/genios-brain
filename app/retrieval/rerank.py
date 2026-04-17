"""
Reranker client — calls the standalone `genios-reranker` service.

Fail-safe: if the reranker is down, unreachable, or disabled, we fall back
to the input order so the retrieval pipeline never breaks.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

RERANKER_URL = os.getenv("RERANKER_URL", "").rstrip("/")
RERANKER_TIMEOUT_SECONDS = float(os.getenv("RERANKER_TIMEOUT_SECONDS", "3.0"))


def _candidate_text(doc: dict) -> str:
    """Concatenate the fields the reranker should score against."""
    parts = [doc.get("subject") or "", doc.get("summary") or "", doc.get("body") or ""]
    return " ".join(p for p in parts if p)[:2000]


def rerank(
    query: str,
    candidates: list,
    top_k: int = 10,
) -> list:
    """
    Given a fused candidate list, return the top_k reordered by cross-encoder.
    Degrades to head(top_k) on any error.
    """
    if not candidates:
        return []
    if not RERANKER_URL or not query:
        return candidates[:top_k]

    payload = {
        "query": query,
        "candidates": [_candidate_text(c) for c in candidates],
        "top_k": top_k,
    }
    try:
        resp = httpx.post(
            f"{RERANKER_URL}/rerank",
            json=payload,
            timeout=RERANKER_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        order = [r.get("index") for r in data.get("results", []) if r.get("index") is not None]
    except Exception as e:
        logger.warning(f"rerank fallback (reranker unreachable): {e}")
        return candidates[:top_k]

    out: list = []
    for idx in order:
        if 0 <= idx < len(candidates):
            doc = dict(candidates[idx])
            doc["rerank_score"] = next(
                (r.get("score") for r in data.get("results", []) if r.get("index") == idx),
                None,
            )
            out.append(doc)
        if len(out) >= top_k:
            break
    return out or candidates[:top_k]


def hybrid_search(
    db,
    org_id: str,
    query: str,
    query_embedding: Optional[list] = None,
    limit: int = 10,
    contact_id: Optional[str] = None,
) -> list:
    """
    Convenience wrapper: BM25 + vector → RRF → rerank.
    Pass `query_embedding=None` to skip the vector branch (BM25-only).
    """
    from app.retrieval import bm25, fuse, store

    lists = []
    bm = bm25.search(db, org_id, query, limit=50, contact_id=contact_id)
    if bm:
        lists.append(bm)

    if query_embedding:
        vec = store.search(db, org_id, query_embedding, limit=50, contact_id=contact_id)
        if vec:
            lists.append(vec)

    fused = fuse.rrf_fuse(lists, limit=50) if lists else []
    return rerank(query, fused, top_k=limit)
