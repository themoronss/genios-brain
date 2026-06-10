"""
Related outbound — cross-contact surface of the user's own recent sends.

Answers: "what else has this org sent on this topic in the last N days?"
Called from build_context_bundle when composing for a new recipient so the
agent sees prior outreach on the same theme — instead of asking the user.

Two retrieval paths, always OR'd in SQL (not sequential fallback):
  - topics && :topics_array   (array overlap, GIN-indexed)
  - embedding <=> :situation_embedding  (pgvector cosine)

Always scoped `direction='outbound' AND org_id=:org` and excludes the current
contact. Respects disclosure_level — private/restricted contacts never surface.
"""

import logging
import os
from typing import List, Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    # Default-on as of Phase 3 Task 3.2 — surfacing prior outbound on the
    # same topic is core to "approve, don't think" UX. Tenants can opt out
    # by setting GENIOS_RELATED_OUTBOUND_ENABLED=false.
    return os.getenv("GENIOS_RELATED_OUTBOUND_ENABLED", "true").lower() in ("1", "true", "yes")


def get_related_outbound(
    db: Session,
    org_id: str,
    *,
    contact_id_to_exclude: Optional[str],
    topics: Optional[List[str]] = None,
    situation_embedding: Optional[list] = None,
    window_days: int = 14,
    limit: int = 5,
    min_similarity: float = 0.70,
) -> List[Dict]:
    """
    Return recent outbound interactions from this org that match topic overlap
    or semantic similarity to the current situation.

    Args:
        db: Session
        org_id: Caller's org (mandatory, non-negotiable isolation)
        contact_id_to_exclude: The recipient we're composing for — skip their own history
        topics: Topic strings from the current contact / situation
        situation_embedding: Optional pgvector for semantic fallback
        window_days: Recency window
        limit: Max rows
        min_similarity: Cosine similarity floor when embedding path is used

    Returns:
        [{ contact_id, contact_name, subject, excerpt, topics, interaction_at,
           match_reason: "topic" | "semantic" | "both" }]
    """
    if not _enabled():
        return []
    if not org_id:
        return []
    if not topics and not situation_embedding:
        return []

    topics_list = [t for t in (topics or []) if t] or None
    emb_str = str(situation_embedding) if situation_embedding else None

    try:
        rows = db.execute(
            text("""
                WITH scored AS (
                    SELECT
                        i.id,
                        i.contact_id,
                        c.name AS contact_name,
                        c.disclosure_level,
                        i.subject,
                        i.raw_snippet,
                        i.summary,
                        i.topics,
                        i.interaction_at,
                        -- topic overlap flag
                        (CASE
                           WHEN :topics IS NOT NULL AND i.topics && CAST(:topics AS text[])
                           THEN 1 ELSE 0
                         END) AS topic_hit,
                        -- semantic similarity when embedding supplied
                        (CASE
                           WHEN :emb IS NOT NULL AND i.embedding IS NOT NULL
                           THEN 1 - (i.embedding <=> CAST(:emb AS vector))
                           ELSE 0
                         END) AS sim
                    FROM interactions i
                    JOIN contacts c ON c.id = i.contact_id
                    WHERE i.org_id = :org_id
                      AND i.direction = 'outbound'
                      AND i.interaction_at > NOW() - (:window_days || ' days')::interval
                      AND (:exclude_id IS NULL OR i.contact_id != CAST(:exclude_id AS uuid))
                      AND COALESCE(c.disclosure_level, 'public') = 'public'
                )
                SELECT *
                FROM scored
                WHERE topic_hit = 1 OR sim >= :min_sim
                ORDER BY
                    (topic_hit * 0.6 + sim * 0.4) DESC,
                    interaction_at DESC
                LIMIT :lim
            """),
            {
                "org_id": org_id,
                "topics": topics_list,
                "emb": emb_str,
                "window_days": str(window_days),
                "exclude_id": contact_id_to_exclude,
                "min_sim": min_similarity,
                "lim": limit,
            },
        ).fetchall()

        out: List[Dict] = []
        for r in rows:
            topic_hit = bool(r.topic_hit)
            sim = float(r.sim or 0)
            if topic_hit and sim >= min_similarity:
                reason = "both"
            elif topic_hit:
                reason = "topic"
            else:
                reason = "semantic"

            excerpt_src = r.raw_snippet or r.summary or ""
            excerpt = excerpt_src[:300].strip()
            if len(excerpt_src) > 300:
                excerpt += "…"

            out.append({
                "contact_id": str(r.contact_id) if r.contact_id else None,
                "contact_name": r.contact_name,
                "subject": r.subject,
                "excerpt": excerpt,
                "topics": list(r.topics or []),
                "interaction_at": r.interaction_at.isoformat() if r.interaction_at else None,
                "similarity": round(sim, 2),
                "match_reason": reason,
            })
        return out

    except Exception as e:
        # Additive feature — NEVER fail the bundle on error.
        logger.debug(f"related_outbound query failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return []


def format_related_outbound_line(related: List[Dict]) -> str:
    """One-line narrative snippet for context_for_agent. Empty string if too few rows."""
    if not related or len(related) < 2:
        # Only surface when there's actually a pattern (>=2 recipients).
        return ""
    refs = []
    for r in related[:3]:
        name = r.get("contact_name") or "a contact"
        when = _short_when(r.get("interaction_at"))
        refs.append(f"{name}{(' ' + when) if when else ''}")
    return f" Related recent outbound: {', '.join(refs)}."


def _short_when(iso_ts: Optional[str]) -> str:
    if not iso_ts:
        return ""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = max(0, (datetime.now(timezone.utc) - dt).days)
        if days == 0:
            return "(today)"
        if days == 1:
            return "(1d ago)"
        return f"({days}d ago)"
    except Exception:
        return ""
