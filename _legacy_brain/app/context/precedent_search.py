"""
Precedent Graph — search past situations for ones similar to the current one.

Two search paths:
  - v1 `search_precedents()` — queries embedded `document_chunks` (uploaded
    docs, manual precedent entries). Text-semantic match on `situation`.
  - v2 `search_precedents_v2()` — queries structured `precedent_situations`
    (populated from recommendation outcomes + stage transitions). Matches on
    fingerprint (stage, entity_type, situation_category), surfaces
    `outcome`, `n_cases`, `success_rate`.

The v2 path is the compounding-knowledge moat: every recommendation with an
outcome becomes a learnable precedent the reasoner cites next time. Guarded
by env `GENIOS_PRECEDENTS_V2` so we can roll out per tenant / revert.

`search_precedents_any()` is the resolver that picks v2 when the flag is on
and there's at least one hit, else falls back to v1. Response shape is
additive: v2 rows add `outcome`, `n_cases`, `success_rate`; consumers built
against v1 still see `similarity`, `situation`, `doc_title`, `metadata`.
"""

import logging
import os
from typing import List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.graph.embedder import embed_text

logger = logging.getLogger(__name__)


def _v2_enabled() -> bool:
    return os.getenv("GENIOS_PRECEDENTS_V2", "false").lower() in ("1", "true", "yes")


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
                    1 - (dc.embedding <=> CAST(:embedding AS vector)) AS similarity
                FROM document_chunks dc
                WHERE dc.org_id = :org_id
                  AND dc.embedding IS NOT NULL
                  AND 1 - (dc.embedding <=> CAST(:embedding AS vector)) >= :threshold
                ORDER BY dc.embedding <=> CAST(:embedding AS vector)
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
        # Reset the aborted transaction so subsequent queries on the same
        # session don't fail with InFailedSqlTransaction.
        try:
            db.rollback()
        except Exception:
            pass
        return []


def search_precedents_v2(
    db: Session,
    org_id: str,
    *,
    stage: Optional[str] = None,
    situation_category: Optional[str] = None,
    entity_type: Optional[str] = None,
    sentiment_bucket: Optional[str] = None,
    limit: int = 5,
) -> List[Dict]:
    """Query structured precedent_situations for historically-similar cases.

    Match logic (progressively looser):
      1. Exact stage + situation_category + entity_type
      2. Stage + situation_category (any entity type)
      3. Stage only (any situation_category)

    For each match bucket, aggregate `outcome` and `n_cases` + `success_rate`
    so the reasoner prompt can say "3/4 similar cases recovered when
    warm_touch was sent".
    """
    try:
        rows = db.execute(
            text("""
                WITH matched AS (
                    SELECT stage, situation_category, entity_type,
                           action_taken, outcome, context_summary,
                           created_at,
                           -- Match tightness score (higher = more specific match)
                           (CASE WHEN stage = :stage THEN 1 ELSE 0 END)
                         + (CASE WHEN situation_category = :sc THEN 1 ELSE 0 END)
                         + (CASE WHEN entity_type IS NOT DISTINCT FROM :et THEN 1 ELSE 0 END)
                         + (CASE WHEN sentiment_bucket IS NOT DISTINCT FROM :sb THEN 1 ELSE 0 END)
                           AS match_score
                    FROM precedent_situations
                    WHERE org_id = :oid
                      AND (
                          stage = :stage
                          OR situation_category = :sc
                      )
                )
                SELECT
                    situation_category,
                    stage,
                    action_taken,
                    COUNT(*) AS n_cases,
                    SUM(CASE WHEN outcome = 'RECOVERED' THEN 1 ELSE 0 END) AS recovered,
                    SUM(CASE WHEN outcome = 'LOST' THEN 1 ELSE 0 END)      AS lost,
                    SUM(CASE WHEN outcome = 'STALLED' THEN 1 ELSE 0 END)   AS stalled,
                    AVG(match_score)::float AS avg_match,
                    MAX(created_at)          AS most_recent,
                    (ARRAY_AGG(context_summary ORDER BY created_at DESC))[1] AS latest_summary
                FROM matched
                WHERE match_score >= 1
                GROUP BY situation_category, stage, action_taken
                ORDER BY avg_match DESC, n_cases DESC
                LIMIT :limit
            """),
            {
                "oid": org_id,
                "stage": stage or "",
                "sc": situation_category or "",
                "et": entity_type,
                "sb": sentiment_bucket,
                "limit": limit,
            },
        ).fetchall()

        out: List[Dict] = []
        for r in rows:
            n = int(r.n_cases or 0)
            recovered = int(r.recovered or 0)
            success_rate = round(recovered / n, 2) if n > 0 else 0.0
            out.append({
                # Common fields — additive to v1 shape
                "similarity": round(float(r.avg_match or 0) / 4.0, 2),
                "situation": r.latest_summary or f"{r.stage}/{r.situation_category}",
                "doc_title": f"{r.situation_category} precedent",
                "metadata": {},
                # v2-only enrichment — `outcome` prompt hint for the reasoner
                "outcome": _summarize_outcome(recovered, int(r.lost or 0), int(r.stalled or 0)),
                "n_cases": n,
                "success_rate": success_rate,
                "action_taken": r.action_taken,
                "situation_category": r.situation_category,
                "stage": r.stage,
                "source": "precedent_situations",
            })
        return out
    except Exception as e:
        logger.debug(f"precedent v2 query failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return []


def _summarize_outcome(recovered: int, lost: int, stalled: int) -> str:
    total = recovered + lost + stalled
    if total == 0:
        return "no_history"
    if recovered / total >= 0.6:
        return "mostly_recovered"
    if lost / total >= 0.5:
        return "mostly_lost"
    if stalled / total >= 0.5:
        return "mostly_stalled"
    return "mixed"


def search_precedents_any(
    db: Session,
    org_id: str,
    situation: str,
    *,
    stage: Optional[str] = None,
    situation_category: Optional[str] = None,
    entity_type: Optional[str] = None,
    sentiment_bucket: Optional[str] = None,
    limit: int = 3,
) -> List[Dict]:
    """Resolver: prefer v2 structured lookup when enabled; fall back to v1 text-semantic."""
    if _v2_enabled():
        v2 = search_precedents_v2(
            db, org_id,
            stage=stage,
            situation_category=situation_category,
            entity_type=entity_type,
            sentiment_bucket=sentiment_bucket,
            limit=limit,
        )
        if v2:
            return v2
    # Fallback: v1 (or v2 had no matches)
    return search_precedents(db, org_id, situation, limit=limit)


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
                        :chunk_index, :chunk_text,
                        CAST(:embedding AS vector),
                        CAST(:metadata AS jsonb)
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
