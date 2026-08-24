"""
Phase 5: L6 Fingerprint Matching — compress situations into comparable vectors,
find historical precedents for what worked before.

Per L2 spec:
  - Fingerprint = structured feature vector (not an embedding)
  - Matching = weighted nearest-neighbor (not ML)
  - Outcome = RECOVERED | LOST | STALLED | NO_CHANGE

Two main functions:
  - build_fingerprint()  — creates a fingerprint from a contact's current state
  - match_precedents()   — finds historical situations that match, ranked by similarity
  - record_outcome()     — auto-called on stage transitions to build the precedent library
"""
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Weights per L2 spec §L6
SIMILARITY_WEIGHTS = {
    "stage":              0.30,
    "entity_type":        0.20,
    "sentiment_bucket":   0.15,
    "situation_category": 0.15,
    "has_overdue_commit": 0.10,
    "days_bucket":        0.05,
    "sentiment_trend":    0.05,
}

MIN_SIMILARITY = float(os.getenv("GENIOS_PRECEDENT_MIN_SIMILARITY", "0.50"))
MAX_PRECEDENTS = int(os.getenv("GENIOS_PRECEDENT_MAX_RESULTS", "5"))


def _sentiment_bucket(ewma: float) -> str:
    if ewma > 0.2:
        return "POSITIVE"
    if ewma < -0.2:
        return "NEGATIVE"
    return "NEUTRAL"


def _days_bucket(days_since: int) -> str:
    if days_since is None:
        return ">60"
    if days_since < 7:
        return "<7"
    if days_since < 14:
        return "7-14"
    if days_since < 30:
        return "14-30"
    if days_since < 60:
        return "30-60"
    return ">60"


def build_fingerprint(contact: dict, situation_type: str = None) -> dict:
    """
    Compress a contact's current state into a fingerprint for matching.
    All fields are strings/bools for exact comparison.
    """
    days_since = None
    last_at = contact.get("last_interaction_at")
    if last_at:
        if isinstance(last_at, str):
            try:
                last_at = datetime.fromisoformat(last_at)
            except (ValueError, TypeError):
                last_at = None
        if last_at:
            if hasattr(last_at, "tzinfo") and last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            days_since = (datetime.now(timezone.utc) - last_at).days

    return {
        "stage": (contact.get("relationship_stage") or "UNKNOWN").upper(),
        "sentiment_bucket": _sentiment_bucket(float(contact.get("sentiment_ewma") or 0)),
        "days_bucket": _days_bucket(days_since),
        "entity_type": (contact.get("entity_type") or "OTHER").upper(),
        "has_overdue_commit": bool(contact.get("overdue_commitments") or 0),
        "situation_category": (situation_type or "OTHER").upper(),
        "sentiment_trend": (contact.get("sentiment_trend") or "STABLE").upper(),
    }


def _similarity_score(fp1: dict, fp2: dict) -> float:
    """
    Weighted field-by-field comparison. Returns 0.0 (no match) to 1.0 (exact).
    Per L2 spec §L6 — not ML, just structured comparison.
    """
    score = 0.0
    for field, weight in SIMILARITY_WEIGHTS.items():
        v1 = str(fp1.get(field, "")).upper()
        v2 = str(fp2.get(field, "")).upper()
        if v1 == v2:
            score += weight
    return round(score, 3)


def match_precedents(
    db: Session,
    org_id: str,
    fingerprint: dict,
    limit: int = None,
) -> List[dict]:
    """
    Find historical situations matching the given fingerprint.
    Returns list ranked by similarity, with outcome stats.
    """
    if limit is None:
        limit = MAX_PRECEDENTS

    rows = db.execute(
        text("""
            SELECT id, stage, sentiment_bucket, days_bucket, entity_type,
                   has_overdue_commit, situation_category, sentiment_trend,
                   action_taken, outcome, outcome_days, context_summary
            FROM precedent_situations
            WHERE org_id = :oid
            ORDER BY created_at DESC
            LIMIT 200
        """),
        {"oid": org_id},
    ).fetchall()

    if not rows:
        return []

    scored = []
    for r in rows:
        fp2 = {
            "stage": r.stage,
            "sentiment_bucket": r.sentiment_bucket,
            "days_bucket": r.days_bucket,
            "entity_type": r.entity_type or "OTHER",
            "has_overdue_commit": bool(r.has_overdue_commit),
            "situation_category": r.situation_category or "OTHER",
            "sentiment_trend": r.sentiment_trend or "STABLE",
        }
        sim = _similarity_score(fingerprint, fp2)
        if sim >= MIN_SIMILARITY:
            scored.append({
                "similarity": sim,
                "outcome": r.outcome,
                "action_taken": r.action_taken,
                "outcome_days": r.outcome_days,
                "context_summary": r.context_summary,
            })

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    results = scored[:limit]

    # Add aggregate stats
    if results:
        outcomes = [r["outcome"] for r in results]
        recovered = outcomes.count("RECOVERED")
        total = len(outcomes)
        success_rate = round(recovered / total, 2) if total > 0 else 0
        for r in results:
            r["match_pool_size"] = total
            r["success_rate"] = success_rate

    return results


def record_stage_transition(
    db: Session,
    org_id: str,
    contact_id: str,
    contact: dict,
    previous_stage: str,
    new_stage: str,
    situation_type: str = None,
):
    """
    Auto-record a precedent when a contact's stage transitions.

    NEEDS_ATTENTION → ACTIVE       = RECOVERED
    NEEDS_ATTENTION → COLD         = LOST
    AT_RISK → ACTIVE/WARM          = RECOVERED
    AT_RISK → COLD                 = LOST
    WARM → NEEDS_ATTENTION         = STALLED
    Any → same stage after 30 days = NO_CHANGE
    """
    if not previous_stage or previous_stage == new_stage:
        return

    # Determine outcome
    recovery_map = {
        ("NEEDS_ATTENTION", "ACTIVE"): "RECOVERED",
        ("NEEDS_ATTENTION", "WARM"): "RECOVERED",
        ("NEEDS_ATTENTION", "COLD"): "LOST",
        ("AT_RISK", "ACTIVE"): "RECOVERED",
        ("AT_RISK", "WARM"): "RECOVERED",
        ("AT_RISK", "COLD"): "LOST",
        ("COLD", "WARM"): "RECOVERED",
        ("COLD", "ACTIVE"): "RECOVERED",
        ("WARM", "NEEDS_ATTENTION"): "STALLED",
        ("WARM", "COLD"): "LOST",
        ("ACTIVE", "NEEDS_ATTENTION"): "STALLED",
        ("ACTIVE", "COLD"): "LOST",
    }

    outcome = recovery_map.get((previous_stage.upper(), new_stage.upper()))
    if not outcome:
        return  # Not a meaningful transition

    fp = build_fingerprint(contact, situation_type)

    # Calculate outcome_days (time spent in previous stage)
    outcome_days = None
    stage_changed_at = contact.get("stage_changed_at")
    if stage_changed_at:
        if isinstance(stage_changed_at, str):
            try:
                stage_changed_at = datetime.fromisoformat(stage_changed_at)
            except (ValueError, TypeError):
                stage_changed_at = None
        if stage_changed_at:
            if hasattr(stage_changed_at, "tzinfo") and stage_changed_at.tzinfo is None:
                stage_changed_at = stage_changed_at.replace(tzinfo=timezone.utc)
            outcome_days = (datetime.now(timezone.utc) - stage_changed_at).days

    try:
        db.execute(
            text("""
                INSERT INTO precedent_situations
                    (org_id, contact_id, stage, sentiment_bucket, days_bucket,
                     entity_type, has_overdue_commit, situation_category,
                     sentiment_trend, outcome, outcome_days,
                     context_summary, source)
                VALUES
                    (:oid, :cid, :stage, :sb, :db, :et, :hoc, :sc, :st,
                     :outcome, :od, :summary, 'auto')
            """),
            {
                "oid": org_id,
                "cid": contact_id,
                "stage": fp["stage"],
                "sb": fp["sentiment_bucket"],
                "db": fp["days_bucket"],
                "et": fp["entity_type"],
                "hoc": fp["has_overdue_commit"],
                "sc": fp["situation_category"],
                "st": fp["sentiment_trend"],
                "outcome": outcome,
                "od": outcome_days,
                "summary": f"{contact.get('name', 'Unknown')}: {previous_stage} → {new_stage}",
            },
        )
        db.commit()
        logger.info(f"Precedent recorded: {contact.get('name')} {previous_stage}→{new_stage} = {outcome}")
    except Exception as e:
        logger.debug(f"Precedent record failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
