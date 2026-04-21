"""Phase 3.2 — POST /v1/feedback

Operator tells us whether a recommendation was acted on. Writes outcome to
`recommendations` row, supports idempotency keys, publishes
`genios.events.feedback.recorded` on the event bus for the (future)
calibration worker in Phase 4.

Legacy alias: `/v1/outcome` stays live in [writeback.py](writeback.py) with a
Sunset header.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_OUTCOMES = {"acted", "dismissed", "ignored"}
_IDEMPOTENCY_TTL = 24 * 3600


class FeedbackRequest(BaseModel):
    recommendation_id: str
    outcome: str
    notes: Optional[str] = None


def _mark_idempotency(key: Optional[str], org_id: str) -> bool:
    """Return True when key is fresh (or absent), False if already used."""
    if not key:
        return True
    redis_key = f"feedback:idem:{org_id}:{key}"
    # SET NX — returns True if newly set, None/False if exists
    return bool(redis_client.set(redis_key, "1", ex=_IDEMPOTENCY_TTL, nx=True))


@router.post("/v1/feedback", status_code=201)
def post_feedback(
    req: FeedbackRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    if req.outcome not in _VALID_OUTCOMES:
        raise HTTPException(
            status_code=400,
            detail=f"outcome must be one of: {sorted(_VALID_OUTCOMES)}",
        )

    if not _mark_idempotency(idempotency_key, org_id):
        raise HTTPException(
            status_code=409,
            detail={"error": "DUPLICATE", "message": "Idempotency-Key already used"},
        )

    row = db.execute(
        text("""
            UPDATE recommendations
            SET outcome       = :o,
                outcome_notes = :n,
                outcome_at    = NOW()
            WHERE id = :id AND org_id = :oid
            RETURNING id, insight_type, priority
        """),
        {
            "id": req.recommendation_id, "oid": org_id,
            "o": req.outcome, "n": (req.notes or "")[:1000] or None,
        },
    ).fetchone()
    if not row:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail={"error": "NOT_FOUND", "message": "recommendation_id not found for this org"},
        )
    db.commit()

    # Publish for future calibration worker. Bus outage must not fail the write.
    try:
        from app.brain import event_bus
        event_bus.publish("feedback.recorded", {
            "org_id": org_id,
            "recommendation_id": str(row[0]),
            "insight_type": row[1],
            "priority": float(row[2] or 0.0),
            "outcome": req.outcome,
        })
    except Exception as e:
        logger.debug(f"feedback event publish failed: {e}")

    return {"recorded": True, "recommendation_id": str(row[0]), "outcome": req.outcome}
