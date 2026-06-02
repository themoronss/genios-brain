"""
Decision explainer (Phase 5).

  GET /api/org/{org_id}/contacts/{contact_id}/why?field=stage

Returns the evidence trail behind a single derived field on a contact:
recent events, scores, and any policy rules that fired on related actions.
Intended for the "why did it say this?" dashboard drill-down.

Fields supported (extend as you add more):
  - stage              → relationship_stage
  - sentiment          → sentiment_trend
  - action_recommendation
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


FIELD_MAP = {
    # Persistent (stored) derived fields on contacts.
    # NB: `action_recommendation` is computed on-the-fly in bundle_builder
    # and is NOT stored here — exposing it would require running the full
    # bundle build, which belongs behind /v1/context. Omit for now.
    "stage": "relationship_stage",
    "sentiment": "sentiment_trend",
}


def _jwt_org(request: Request) -> str:
    oid = getattr(request.state, "jwt_org_id", None)
    if not oid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return oid


@router.get("/api/org/{org_id}/contacts/{contact_id}/why")
def explain_contact_field(
    org_id: str,
    contact_id: str,
    request: Request,
    field: str = "stage",
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    if field not in FIELD_MAP:
        raise HTTPException(status_code=400, detail=f"unknown field; use one of {list(FIELD_MAP)}")

    # Reject malformed UUIDs early so we return 400, not a Postgres 500.
    import uuid
    try:
        uuid.UUID(contact_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_CONTACT_ID", "message": "contact_id must be a UUID"},
        )

    column = FIELD_MAP[field]

    # 1) Current derived value + stored scores
    contact = db.execute(
        text(f"""
            SELECT id, name, email, company,
                   {column} AS current_value,
                   freshness_score, confidence_score, authority_score,
                   consistency_score, context_score,
                   interaction_count, sentiment_avg
            FROM contacts
            WHERE org_id = :org AND id = :cid
            LIMIT 1
        """),
        {"org": org_id, "cid": contact_id},
    ).fetchone()
    if not contact:
        raise HTTPException(status_code=404, detail="contact not found")

    # 2) Recent interactions that contribute to the value
    interactions = db.execute(
        text("""
            SELECT id, direction, subject, interaction_at AS sent_at,
                   sentiment, topics, interaction_type
            FROM interactions
            WHERE org_id = :org AND contact_id = :cid
            ORDER BY interaction_at DESC NULLS LAST
            LIMIT 10
        """),
        {"org": org_id, "cid": contact_id},
    ).fetchall()

    # 3) Policy rules that fired on actions for this contact.
    # Match EITHER by explicit contact_id OR by target_ref equal to the
    # contact's name/email (legacy rows where we only had the text handle).
    policy_hits = db.execute(
        text("""
            SELECT al.action_type, al.policy_decision, al.policy_rule_id,
                   pr.name AS rule_name, al.created_at
            FROM action_ledger al
            LEFT JOIN policy_rules pr ON pr.id = al.policy_rule_id
            WHERE al.org_id = :org
              AND al.policy_decision IS NOT NULL
              AND (
                   al.contact_id = :cid
                OR LOWER(al.target_ref) = LOWER(:name)
                OR LOWER(al.target_ref) = LOWER(:email)
              )
            ORDER BY al.created_at DESC
            LIMIT 10
        """),
        {
            "org": org_id,
            "cid": contact_id,
            "name": contact.name or "",
            "email": contact.email or "",
        },
    ).fetchall()

    # 4) Recent source events from the canonical log.
    # Same matching strategy — contact_id hit, OR actor/object_id/payload
    # text containing the contact's name or email.
    events = db.execute(
        text("""
            SELECT source, verb, actor, observed_at
            FROM event_log
            WHERE org_id = :org
              AND (
                   object_id = :cid
                OR payload ->> 'contact_id' = :cid
                OR LOWER(actor) = LOWER(:email)
                OR payload::text ILIKE :name_like
                OR payload::text ILIKE :email_like
              )
            ORDER BY observed_at DESC
            LIMIT 10
        """),
        {
            "org": org_id,
            "cid": contact_id,
            "email": contact.email or "",
            "name_like": f"%{contact.name or '__none__'}%",
            "email_like": f"%{contact.email or '__none__'}%",
        },
    ).fetchall()

    return {
        "field": field,
        "column": column,
        "current_value": contact.current_value,
        "contact": {
            "id": str(contact.id),
            "name": contact.name,
            "email": contact.email,
            "company": contact.company,
        },
        "scores": {
            "freshness": float(contact.freshness_score or 0),
            "confidence": float(contact.confidence_score or 0),
            "authority": float(contact.authority_score or 0),
            "consistency": float(contact.consistency_score or 0),
            "context": float(contact.context_score or 0),
            "interaction_count": int(contact.interaction_count or 0),
            "sentiment_avg": float(contact.sentiment_avg or 0),
        },
        "recent_interactions": [
            {
                "id": str(r.id),
                "direction": r.direction,
                "subject": r.subject,
                "sent_at": r.sent_at.isoformat() if r.sent_at else None,
                "sentiment": r.sentiment,
                "topics": r.topics,
                "type": r.interaction_type,
            }
            for r in interactions
        ],
        "policy_hits": [
            {
                "action_type": r.action_type,
                "decision": r.policy_decision,
                "rule_id": str(r.policy_rule_id) if r.policy_rule_id else None,
                "rule_name": r.rule_name,
                "at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in policy_hits
        ],
        "recent_events": [
            {
                "source": e.source, "verb": e.verb, "actor": e.actor,
                "at": e.observed_at.isoformat() if e.observed_at else None,
            }
            for e in events
        ],
    }
