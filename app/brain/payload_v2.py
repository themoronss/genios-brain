"""
Recommendation Payload v2 builder.

The v1 payload is flat: {title, reason, action}. The Master Build Document
spec requires richer structure so agent integrations can:
 - Trace WHY the recommendation fired (`evidence[]`, `rationale`)
 - See similar past situations (`precedent_links[]`)
 - Receive an actionable, typed next step (`suggested_action`)
 - Consume a confidence BUCKET (high/medium/low) not just a raw number

This module assembles those fields from the candidate, reasoner result, and
the contact's graph state. It is the single source-of-truth for v2 payload
construction — used at insert time in `brain.router.run_once()`.

Additive: v1 fields (title, reason, action) are still written as before.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ── Confidence bucketing ──────────────────────────────────────────────────────
def _bucket(conf: float) -> str:
    if conf is None:
        return "unknown"
    try:
        c = float(conf)
    except (TypeError, ValueError):
        return "unknown"
    if c >= 0.75:
        return "high"
    if c >= 0.50:
        return "medium"
    if c >= 0.25:
        return "low"
    return "very_low"


# ── Evidence extraction ──────────────────────────────────────────────────────
def _extract_evidence(candidate: dict, contact: Optional[dict]) -> list[dict]:
    """The facts that made this candidate fire. Comes from:
      1. candidate.metadata.evidence if the detector already structured it
      2. contact's recent interactions as fallback
    """
    meta = candidate.get("metadata") or {}
    pre_built = meta.get("evidence")
    if isinstance(pre_built, list) and pre_built:
        return pre_built[:5]

    ev: list[dict] = []
    if contact:
        if contact.get("last_interaction_at"):
            ev.append({
                "type": "last_interaction",
                "value": str(contact["last_interaction_at"]),
                "weight": 0.4,
            })
        if contact.get("sentiment_ewma") is not None:
            ev.append({
                "type": "sentiment_ewma",
                "value": float(contact["sentiment_ewma"] or 0),
                "weight": 0.2,
            })
        if contact.get("relationship_stage"):
            ev.append({
                "type": "relationship_stage",
                "value": contact["relationship_stage"],
                "weight": 0.3,
            })
        if contact.get("interaction_count") is not None:
            ev.append({
                "type": "interaction_count",
                "value": int(contact["interaction_count"] or 0),
                "weight": 0.1,
            })
    return ev


# ── Precedent lookup ──────────────────────────────────────────────────────────
def _lookup_precedents(
    db: Session, org_id: str, contact: Optional[dict], insight_type: Optional[str]
) -> list[dict]:
    """Find matching precedent_situations for context."""
    if not contact:
        return []
    try:
        rows = db.execute(
            text("""
                SELECT id, stage, sentiment_bucket, situation_category,
                       action_taken, outcome, outcome_days, context_summary
                FROM precedent_situations
                WHERE org_id = :oid
                  AND stage = :stage
                  AND (
                      situation_category = :sc
                      OR situation_category IS NULL
                      OR :sc IS NULL
                  )
                ORDER BY created_at DESC
                LIMIT 3
            """),
            {
                "oid": org_id,
                "stage": contact.get("relationship_stage") or "UNKNOWN",
                "sc": insight_type,
            },
        ).fetchall()
        return [
            {
                "precedent_id": str(r.id),
                "situation_category": r.situation_category,
                "action_taken": r.action_taken,
                "outcome": r.outcome,
                "outcome_days": r.outcome_days,
                "summary": r.context_summary,
            }
            for r in rows
        ]
    except Exception as e:
        logger.debug(f"precedent lookup failed org={org_id}: {e}")
        return []


# ── Suggested action ──────────────────────────────────────────────────────────
def _build_suggested_action(
    candidate: dict, reason_result: Any, contact: Optional[dict]
) -> dict:
    """Structured next step for the agent. Reasoner.action is a string; we
    promote it to a typed shape."""
    action_str = getattr(reason_result, "action", None) or ""
    meta = candidate.get("metadata") or {}
    verb = meta.get("action_verb") or _infer_verb(candidate.get("insight_type"))

    target = None
    if contact:
        target = contact.get("email") or contact.get("name")

    return {
        "verb": verb,
        "target": target,
        "draft": action_str,
        "reasoning": getattr(reason_result, "reason", None) or candidate.get("title") or "",
    }


def _infer_verb(insight_type: Optional[str]) -> str:
    if not insight_type:
        return "review"
    t = insight_type.lower()
    if "cooling" in t or "risk" in t or "churn" in t:
        return "send_warm_check_in"
    if "commitment" in t or "overdue" in t or "follow" in t:
        return "send_follow_up"
    if "drift" in t or "role" in t or "title" in t:
        return "update_contact_info"
    if "authority" in t:
        return "reassess_authority"
    if "dormant" in t or "cold" in t:
        return "reengage"
    return "review"


# ── Contact fetch (used by multiple helpers) ─────────────────────────────────
def _fetch_contact(db: Session, contact_id: str) -> Optional[dict]:
    try:
        row = db.execute(
            text("""
                SELECT id, name, email, company, entity_type,
                       relationship_stage, sentiment_ewma, sentiment_trend,
                       last_interaction_at, interaction_count
                FROM contacts WHERE id = :cid
            """),
            {"cid": contact_id},
        ).fetchone()
        return dict(row._mapping) if row else None
    except Exception:
        return None


# ── Public entry ──────────────────────────────────────────────────────────────
def build_payload_v2(
    db: Session,
    org_id: str,
    subject_entity_id: str,
    candidate: dict,
    reason_result: Any,
    priority: float,
) -> dict:
    """Compose the five v2 fields. All fields guaranteed present (may be
    empty list / None / empty string) — never raises so the insert can't
    fail on payload assembly."""
    contact = _fetch_contact(db, subject_entity_id) if subject_entity_id else None
    insight_type = candidate.get("insight_type")

    evidence = _extract_evidence(candidate, contact)
    precedent_links = _lookup_precedents(db, org_id, contact, insight_type)
    suggested_action = _build_suggested_action(candidate, reason_result, contact)
    confidence_level = _bucket(getattr(reason_result, "confidence", None))

    rationale = (
        getattr(reason_result, "reason", None)
        or candidate.get("title")
        or f"{insight_type}: priority={priority:.2f}"
    )

    return {
        "evidence": evidence,
        "precedent_links": precedent_links,
        "suggested_action": suggested_action,
        "confidence_level": confidence_level,
        "rationale": rationale,
    }
