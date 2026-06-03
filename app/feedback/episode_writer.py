"""Feedback episode writer — closes the learning loop.

When an outcome is recorded on a recommendation, this module composes a
short natural-language episode describing what happened and persists it
to `feedback_episodes`. Two downstream consumers benefit:

  - Precedent harvest (Sprint 3) — reads episodes by insight_type+outcome
    to assemble "what worked / what didn't" patterns for new candidates.
  - /v1/context bundle — recent episodes for a contact can be surfaced to
    the LLM so reasoning is informed by past outcomes.

The writer is best-effort: a failure here must not roll back the feedback
write. Idempotent on (recommendation_id) per the UNIQUE constraint.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def to_feedback_episode(
    *,
    org_id: str,
    recommendation: dict,
    contact: Optional[dict],
    outcome: str,
    notes: Optional[str] = None,
) -> str:
    """Compose the episode text. Pure function — no DB."""
    insight_type = recommendation.get("insight_type") or "recommendation"
    title = recommendation.get("title") or recommendation.get("rationale") or insight_type
    contact_label = (
        (contact or {}).get("name")
        or (contact or {}).get("email")
        or "the contact"
    )

    verb_map = {
        "acted":     f"acted on {insight_type} alert about {contact_label}",
        "dismissed": f"dismissed {insight_type} alert about {contact_label}",
        "ignored":   f"ignored {insight_type} alert about {contact_label}",
    }
    verb = verb_map.get(outcome, f"recorded outcome={outcome} on {insight_type}")

    parts = [f"Operator {verb}.", f"Trigger: {str(title)[:240]}"]
    if notes:
        parts.append(f"Notes: {str(notes)[:300]}")
    return " ".join(parts)


def write_episode(
    db: Session,
    *,
    org_id: str,
    recommendation_id: str,
    insight_type: Optional[str],
    contact_id: Optional[str],
    outcome: str,
    episode_text: str,
) -> bool:
    """Insert one episode row. Returns True on success, False on any failure
    (caller treats this as best-effort and never raises through it).
    """
    try:
        db.execute(
            text("""
                INSERT INTO feedback_episodes
                    (org_id, contact_id, recommendation_id, insight_type,
                     outcome, episode_text, created_at)
                VALUES (:oid, :cid, :rid, :itype, :outcome, :etext, NOW())
                ON CONFLICT (recommendation_id) DO UPDATE SET
                    outcome = EXCLUDED.outcome,
                    episode_text = EXCLUDED.episode_text,
                    created_at = NOW()
            """),
            {
                "oid": org_id,
                "cid": str(contact_id) if contact_id else None,
                "rid": str(recommendation_id),
                "itype": insight_type,
                "outcome": outcome,
                "etext": episode_text[:2000],
            },
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.warning(f"feedback episode write failed rec={recommendation_id}: {e}")
        return False


def record_from_feedback(
    db: Session,
    *,
    org_id: str,
    recommendation_id: str,
    outcome: str,
    notes: Optional[str] = None,
) -> bool:
    """Convenience: fetch the recommendation + contact, compose the episode,
    write it. Used inline from the /v1/feedback endpoint after the row UPDATE.
    """
    rec = db.execute(
        text("""
            SELECT r.id, r.insight_type, r.subject_entity_id, r.title, r.rationale,
                   c.name AS contact_name, c.email AS contact_email
            FROM recommendations r
            LEFT JOIN contacts c ON c.id = r.subject_entity_id
            WHERE r.id = :rid AND r.org_id = :oid
        """),
        {"rid": recommendation_id, "oid": org_id},
    ).fetchone()
    if not rec:
        return False

    rec_dict: dict[str, Any] = {
        "id": str(rec.id),
        "insight_type": rec.insight_type,
        "title": rec.title,
        "rationale": rec.rationale,
    }
    contact_dict: Optional[dict] = None
    if rec.subject_entity_id:
        contact_dict = {
            "id": str(rec.subject_entity_id),
            "name": rec.contact_name,
            "email": rec.contact_email,
        }

    episode = to_feedback_episode(
        org_id=org_id,
        recommendation=rec_dict,
        contact=contact_dict,
        outcome=outcome,
        notes=notes,
    )
    return write_episode(
        db,
        org_id=org_id,
        recommendation_id=recommendation_id,
        insight_type=rec.insight_type,
        contact_id=str(rec.subject_entity_id) if rec.subject_entity_id else None,
        outcome=outcome,
        episode_text=episode,
    )
