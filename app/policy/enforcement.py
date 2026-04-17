"""
Thin enforcement helper — evaluates policy + opens a ledger row.

Callers receive `(decision, ledger_id)`. If `decision` is block/require_approval,
they raise an HTTPException of their choosing (signature kept framework-free).
"""

import logging
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.actions import ledger as action_ledger
from app.policy import engine as policy_engine

logger = logging.getLogger(__name__)


def evaluate_and_open(
    db: Session,
    org_id: str,
    agent_id: str,
    action_type: str,
    risk_tier: str,
    target_ref: Optional[str],
    payload: dict,
    ctx: Optional[dict] = None,
    contact_id: Optional[str] = None,
) -> Tuple[dict, Optional[int]]:
    """
    1) Run policy engine against `ctx` (defaults to payload).
    2) Record a pending ledger row that carries the policy decision + rule_id.
    Returns (decision_dict, ledger_id).

    The ledger row is opened for ALL outcomes (allow, warn, block, require_approval).
    Callers update its outcome based on what happens next.
    """
    evaluation_ctx = dict(ctx or payload)
    evaluation_ctx.setdefault("action_type", action_type)
    evaluation_ctx.setdefault("risk_tier", risk_tier)
    evaluation_ctx.setdefault("agent_id", agent_id)

    decision = policy_engine.evaluate(
        db, org_id, action_type=action_type, risk_tier=risk_tier, ctx=evaluation_ctx
    )

    ledger_id = action_ledger.record(
        db, org_id=org_id, agent_id=agent_id,
        action_type=action_type, risk_tier=risk_tier,
        target_type="contact" if target_ref else None,
        target_ref=target_ref,
        contact_id=contact_id,
        payload=payload,
        policy_decision=decision["decision"],
        policy_rule_id=decision["rule_id"],
        outcome="pending",
    )
    return decision, ledger_id


def close(db: Session, ledger_id: Optional[int], outcome: str, detail: Optional[str] = None) -> None:
    if ledger_id:
        action_ledger.update_outcome(db, ledger_id, outcome, detail)
