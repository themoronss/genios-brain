"""
Action ledger — append-only record of every agent-initiated action.

Every action is classified by risk_tier:
  internal_read, internal_write, external_draft, external_send, irreversible

Each entry tracks policy_decision + outcome. Reverts are new rows that set
reverted_by on the original, so the chain is auditable and never destructive.
"""

import json
import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


RISK_TIERS = (
    "internal_read",
    "internal_write",
    "external_draft",
    "external_send",
    "irreversible",
)


def record(
    db: Session,
    org_id: str,
    agent_id: str,
    action_type: str,
    risk_tier: str,
    target_type: Optional[str] = None,
    target_ref: Optional[str] = None,
    contact_id: Optional[str] = None,
    payload: Optional[dict] = None,
    policy_decision: Optional[str] = None,
    policy_rule_id: Optional[str] = None,
    outcome: str = "pending",
    outcome_detail: Optional[str] = None,
) -> Optional[int]:
    """
    Insert a new ledger entry. Returns the row id.
    Safe to call before the action actually runs — set outcome='pending',
    then update_outcome() once complete.
    """
    if risk_tier not in RISK_TIERS:
        logger.warning(f"action_ledger.record: unknown risk_tier {risk_tier}")
        risk_tier = "internal_write"  # safe fallback

    try:
        row = db.execute(
            text("""
                INSERT INTO action_ledger
                    (org_id, agent_id, action_type, risk_tier,
                     target_type, target_ref, contact_id, payload,
                     policy_decision, policy_rule_id, outcome, outcome_detail,
                     created_at,
                     completed_at)
                VALUES
                    (:org_id, :agent_id, :action_type, :risk_tier,
                     :target_type, :target_ref, :contact_id, CAST(:payload AS jsonb),
                     :policy_decision, :policy_rule_id, :outcome, :outcome_detail,
                     NOW(),
                     CASE WHEN :outcome IN ('success','failed') THEN NOW() ELSE NULL END)
                RETURNING id
            """),
            {
                "org_id": org_id,
                "agent_id": agent_id,
                "action_type": action_type,
                "risk_tier": risk_tier,
                "target_type": target_type,
                "target_ref": target_ref,
                "contact_id": contact_id,
                "payload": json.dumps(payload or {}, default=str),
                "policy_decision": policy_decision,
                "policy_rule_id": policy_rule_id,
                "outcome": outcome,
                "outcome_detail": (outcome_detail[:1000] if outcome_detail else None),
            },
        ).fetchone()
        db.commit()
        return int(row[0]) if row else None
    except Exception as e:
        logger.warning(f"action_ledger.record failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def update_outcome(
    db: Session,
    action_id: int,
    outcome: str,
    outcome_detail: Optional[str] = None,
) -> bool:
    """Finalize a pending ledger row."""
    try:
        db.execute(
            text("""
                UPDATE action_ledger
                SET outcome        = :outcome,
                    outcome_detail = :detail,
                    completed_at   = CASE WHEN :outcome IN ('success','failed','reverted')
                                          THEN NOW() ELSE completed_at END
                WHERE id = :id
            """),
            {
                "outcome": outcome,
                "detail": (outcome_detail[:1000] if outcome_detail else None),
                "id": action_id,
            },
        )
        db.commit()
        return True
    except Exception as e:
        logger.warning(f"action_ledger.update_outcome failed for id={action_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False


def revert(
    db: Session,
    original_id: int,
    agent_id: str,
    reason: str,
) -> Optional[int]:
    """
    Record a compensating action that logically reverses `original_id`.
    The compensating row is appended (not a delete); the original is marked
    'reverted' via reverted_by on the NEW row + outcome flip on original.
    """
    orig = db.execute(
        text("""
            SELECT org_id, action_type, risk_tier, target_type, target_ref, contact_id, payload
            FROM action_ledger WHERE id = :id
        """),
        {"id": original_id},
    ).fetchone()
    if not orig:
        return None

    try:
        row = db.execute(
            text("""
                INSERT INTO action_ledger
                    (org_id, agent_id, action_type, risk_tier,
                     target_type, target_ref, contact_id, payload,
                     outcome, outcome_detail, reverted_by, created_at, completed_at)
                VALUES
                    (:org_id, :agent_id, :action_type, 'internal_write',
                     :target_type, :target_ref, :contact_id, CAST(:payload AS jsonb),
                     'success', :reason, :reverted_by, NOW(), NOW())
                RETURNING id
            """),
            {
                "org_id": str(orig.org_id),
                "agent_id": agent_id,
                "action_type": f"revert:{orig.action_type}",
                "target_type": orig.target_type,
                "target_ref": orig.target_ref,
                "contact_id": str(orig.contact_id) if orig.contact_id else None,
                "payload": json.dumps({"reverts": original_id, "reason": reason}),
                "reason": reason[:1000] if reason else None,
                "reverted_by": original_id,
            },
        ).fetchone()
        # Flip the original's outcome so downstream queries see reverted state
        db.execute(
            text("UPDATE action_ledger SET outcome='reverted', outcome_detail=:r WHERE id=:id"),
            {"r": reason[:1000] if reason else None, "id": original_id},
        )
        db.commit()
        return int(row[0]) if row else None
    except Exception as e:
        logger.warning(f"action_ledger.revert failed for id={original_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def list_recent(db: Session, org_id: str, limit: int = 50) -> list:
    rows = db.execute(
        text("""
            SELECT id, agent_id, action_type, risk_tier, target_ref,
                   policy_decision, outcome, created_at, completed_at
            FROM action_ledger
            WHERE org_id = :org_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"org_id": org_id, "limit": limit},
    ).fetchall()
    return [
        {
            "id": int(r.id),
            "agent_id": r.agent_id,
            "action_type": r.action_type,
            "risk_tier": r.risk_tier,
            "target_ref": r.target_ref,
            "policy_decision": r.policy_decision,
            "outcome": r.outcome,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in rows
    ]
