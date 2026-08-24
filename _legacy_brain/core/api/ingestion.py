"""Ingestion route — /v1/ingest for customer-deployed memory adapters.

Customer adapters live outside the brain (per architecture decision: adapters
are client-deployed templates, not GeniOS infra). They poll their source, hash
records to stable item_ids, and POST normalized MemoryItems here.

POST /v1/ingest    accept a batch of MemoryItems, emit to the bus + persist FactRow

The brain trusts the org_id from auth, NOT the body. Records are passed through
the same normalize → ScopeEnforcer-style validation as built-in adapters.

This is the customer-controlled half of the "two adapter paths" model:
- Built-in adapters (Gmail/Slack/Notion in core/memory/adapters/known/) run
  inside the brain.
- Custom adapters use the propose-confirm-freeze flow + ship a normalize step
  client-side, then POST here.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org
from core.foundations.telemetry import get_logger
from core.memory.emit import emit
from core.memory.types import MemoryItem

router = APIRouter(prefix="/v1/ingest", tags=["ingestion"])
log = get_logger(__name__)


class IngestBatchRequest(BaseModel):
    items: list[MemoryItem] = Field(..., min_length=1, max_length=500)


class IngestBatchResponse(BaseModel):
    accepted: int
    rejected: int
    rejected_reasons: list[dict[str, Any]]


@router.post("", response_model=IngestBatchResponse)
def ingest_batch(
    body: IngestBatchRequest,
    org_id: str = Depends(require_org),
    _session: Session = Depends(db_session),
) -> IngestBatchResponse:
    """Accept a batch of normalized MemoryItems and route them to the bus.

    Per-item failures are isolated — one bad item doesn't fail the batch.
    Subscribers (fact extractor + indexer) pick them up async via the bus.
    """
    accepted = 0
    rejected = 0
    reasons: list[dict[str, Any]] = []
    for item in body.items:
        try:
            if not item.item_id:
                raise ValueError("item_id required")
            emit(item, org_id=org_id)
            accepted += 1
        except Exception as e:
            rejected += 1
            reasons.append(
                {"item_id": item.item_id or "<missing>", "reason": str(e)}
            )
    log.info(
        "ingest_batch_processed",
        org_id=org_id,
        accepted=accepted,
        rejected=rejected,
    )
    if accepted == 0 and rejected == len(body.items):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "every item rejected", "rejected_reasons": reasons},
        )
    return IngestBatchResponse(
        accepted=accepted, rejected=rejected, rejected_reasons=reasons
    )
