"""
Write-back API — agents log what they DID back into the brain.

POST /v1/interaction  — agent reports: "I sent an email to Arjun about pricing"
POST /v1/outcome      — agent reports: "The context I got led to a positive result"

Without these, the brain only knows what Gmail sync captures.
With these, the brain stays fresh in real-time and learns from outcomes.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.api.routes.approvals import enqueue as enqueue_approval
from app.memory import event_log
from app.policy import enforcement as policy_enforcement

logger = logging.getLogger(__name__)

router = APIRouter()


# ── POST /v1/interaction — agent logs an action ─────────────────────────────

class LogInteractionRequest(BaseModel):
    entity: str                        # email or name of the contact
    direction: str = "outbound"        # outbound (agent sent) | inbound (received)
    summary: str                       # "Sent follow-up email about Q2 pricing"
    channel: str = "email"             # email | slack | call | meeting | other
    sentiment: Optional[float] = None  # -1.0 to 1.0 (agent's assessment)
    topics: Optional[list[str]] = None
    agent_id: Optional[str] = None


@router.post("/v1/interaction", status_code=201)
def log_interaction(
    req: LogInteractionRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    Agent write-back: log an action the agent took (or observed).

    This creates an interaction row in the graph so the brain stays fresh
    without waiting for the next Gmail/Calendar sync. The relationship
    calculator will pick it up on the next recalc cycle.
    """
    entity = req.entity.strip()
    if not entity:
        raise HTTPException(status_code=400, detail="entity is required")

    # Phase 3 policy gate — writeback is internal_write risk tier.
    payload = {
        "entity": entity, "direction": req.direction, "channel": req.channel,
        "summary": req.summary, "topics": req.topics or [],
    }
    decision, ledger_id = policy_enforcement.evaluate_and_open(
        db, org_id=org_id, agent_id=req.agent_id or "unknown",
        action_type="writeback", risk_tier="internal_write",
        target_ref=entity, payload=payload,
    )
    if decision["decision"] == "block":
        policy_enforcement.close(db, ledger_id, "failed", f"policy_block:{decision.get('rule_name')}")
        raise HTTPException(status_code=403, detail={
            "error": "POLICY_BLOCK", "rule_id": decision["rule_id"],
            "rule_name": decision["rule_name"],
        })
    if decision["decision"] == "require_approval":
        approval_id = enqueue_approval(
            db, org_id=org_id, agent_id=req.agent_id or "unknown",
            action_type="writeback", risk_tier="internal_write",
            target_ref=entity, payload=payload,
            action_ledger_id=ledger_id, triggered_rule_id=decision["rule_id"],
            reason=f"matched rule {decision.get('rule_name')}",
        )
        raise HTTPException(status_code=202, detail={
            "status": "awaiting_approval", "approval_id": approval_id,
            "rule_id": decision["rule_id"], "rule_name": decision["rule_name"],
        })

    # Try email exact match first, then name fuzzy
    contact = None
    if "@" in entity:
        contact = db.execute(
            text("SELECT id FROM contacts WHERE org_id = :oid AND LOWER(email) = LOWER(:email) LIMIT 1"),
            {"oid": org_id, "email": entity},
        ).fetchone()

    if not contact:
        contact = db.execute(
            text("SELECT id FROM contacts WHERE org_id = :oid AND LOWER(name) = LOWER(:name) LIMIT 1"),
            {"oid": org_id, "name": entity},
        ).fetchone()

    if not contact:
        # Create new contact from the entity
        from app.ingestion.graph_builder import upsert_contact
        email = entity if "@" in entity else None
        name = entity if "@" not in entity else entity.split("@")[0].replace(".", " ").title()
        contact_id = upsert_contact(db, org_id, email, name)
        if not contact_id:
            raise HTTPException(status_code=400, detail=f"Could not resolve or create contact for '{entity}'")
    else:
        contact_id = str(contact[0])

    # Map channel to interaction_type
    type_map = {
        "email": "email_one_way",
        "slack": "slack_message",
        "call": "phone_call",
        "meeting": "meeting",
        "other": "other",
    }

    interaction_id = str(uuid.uuid4())
    try:
        db.execute(
            text("""
                INSERT INTO interactions (
                    id, org_id, contact_id, direction, subject,
                    summary, interaction_at, sentiment, intent,
                    source, topics, interaction_type
                )
                VALUES (
                    :id, :oid, :cid, :direction, :subject,
                    :summary, NOW(), :sentiment, 'outreach',
                    :source, :topics, :itype
                )
            """),
            {
                "id": interaction_id,
                "oid": org_id,
                "cid": contact_id,
                "direction": req.direction,
                "subject": req.summary[:100],
                "summary": req.summary[:500],
                "sentiment": req.sentiment,
                "source": f"agent:{req.agent_id or 'unknown'}",
                "topics": req.topics or [],
                "itype": type_map.get(req.channel, "other"),
            },
        )
        db.commit()
    except Exception as e:
        db.rollback()
        policy_enforcement.close(db, ledger_id, "failed", str(e)[:500])
        raise HTTPException(status_code=500, detail=f"Failed to log interaction: {e}")

    # Mirror into canonical event_log + finalize ledger.
    event_log.append(
        db, org_id=org_id, source="agent", verb=req.direction,
        actor=req.agent_id or "unknown", object_type="interaction",
        object_id=interaction_id, payload=payload,
    )
    policy_enforcement.close(db, ledger_id, "success")

    return {
        "logged": True,
        "interaction_id": interaction_id,
        "contact_id": contact_id,
        "entity": entity,
        "summary": req.summary,
    }


# ── POST /v1/outcome — agent reports feedback on context quality ────────────

class OutcomeRequest(BaseModel):
    context_id: str                    # bundle_id from the /v1/context response
    outcome: str                       # positive | negative | neutral
    details: Optional[str] = None      # "Customer replied within 1 hour"
    agent_id: Optional[str] = None


@router.post("/v1/outcome", status_code=201, deprecated=True)
def log_outcome(
    req: OutcomeRequest,
    response: Response,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    DEPRECATED — prefer POST /v1/feedback (Phase 3.2). Kept live as an alias
    until the SDK 1.0 migration completes. Responds with a `Sunset` header
    per RFC 8594.

    Feedback loop: agent reports whether the context bundle was useful.
    """
    response.headers["Sunset"] = "Wed, 31 Dec 2026 23:59:59 GMT"
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = '</v1/feedback>; rel="successor-version"'
    if req.outcome not in ("positive", "negative", "neutral"):
        raise HTTPException(status_code=400, detail="outcome must be: positive | negative | neutral")

    # DB constraint uses success/failure/partial — map from user-friendly names
    outcome_map = {"positive": "success", "negative": "failure", "neutral": "partial"}
    db_outcome = outcome_map[req.outcome]

    outcome_id = str(uuid.uuid4())
    try:
        db.execute(
            text("""
                INSERT INTO context_outcomes (
                    id, org_id, context_id, outcome, outcome_notes, created_at
                )
                VALUES (:id, :oid, CAST(:cid AS uuid), :outcome, :notes, NOW())
                ON CONFLICT DO NOTHING
            """),
            {
                "id": outcome_id,
                "oid": org_id,
                "cid": req.context_id,
                "outcome": db_outcome,
                "notes": req.details[:500] if req.details else None,
            },
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to log outcome: {e}")

    return {
        "logged": True,
        "outcome_id": outcome_id,
        "context_id": req.context_id,
        "outcome": req.outcome,
    }
