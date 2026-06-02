"""User-model routes — persona seed wizard + view/edit/delete + propose-confirm.

GET    /v1/usermodel/{user_id}           view profile
POST   /v1/usermodel/seed                seed new profile (day-1 wizard)
PATCH  /v1/usermodel/{user_id}/field     update one field (user-driven edit)
DELETE /v1/usermodel/{user_id}           full wipe (GDPR-compliant)
GET    /v1/usermodel/{user_id}/proposals open proposals from distill pipeline
POST   /v1/usermodel/proposals/{id}/decide  confirm or reject a proposal

The user_id is supplied in the path; org_id comes from auth. Cross-user reads
are blocked by org check: a user_model belongs to org_unit, which must match.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api.deps import db_session, require_org
from core.foundations.telemetry import get_logger
from core.usermodel import (
    DecisionPolicy,
    Priorities,
    ProcessHabits,
    RelationshipTag,
    Voice,
    confirm_proposal,
    delete_profile,
    reject_proposal,
    seed_profile,
    update_field,
    view_profile,
)
from core.usermodel.control import ProfileNotFound
from core.usermodel.propose import ProposalError
from core.usermodel.seed import SeedingError, SeedInput
from core.usermodel.store import UserModelProposalRow

router = APIRouter(prefix="/v1/usermodel", tags=["usermodel"])
log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────────────


class SeedRequest(BaseModel):
    user_id: str
    voice: Voice | None = None
    decision_policy: DecisionPolicy | None = None
    process_habits: ProcessHabits | None = None
    priorities: Priorities | None = None
    relationships: dict[str, RelationshipTag] | None = None
    red_lines: list[str] | None = None


class UpdateFieldRequest(BaseModel):
    field: Literal[
        "voice", "decision_policy", "process_habits", "priorities", "relationships", "red_lines"
    ]
    new_value: dict[str, Any] | list[Any] | str | int | float | bool


class ProposalDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    actor: str


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/{user_id}")
def get_profile(
    user_id: str,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    try:
        profile = view_profile(session, user_id=user_id)
    except ProfileNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    _require_org_match(profile.org_unit, org_id)
    return profile.model_dump(mode="json")


@router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed(
    body: SeedRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    try:
        profile = seed_profile(
            session,
            seed=SeedInput(
                user_id=body.user_id,
                org_unit=org_id,
                voice=body.voice,
                decision_policy=body.decision_policy,
                process_habits=body.process_habits,
                priorities=body.priorities,
                relationships=body.relationships,
                red_lines=body.red_lines,
            ),
        )
    except SeedingError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    session.commit()
    return profile.model_dump(mode="json")


@router.patch("/{user_id}/field")
def patch_field(
    user_id: str,
    body: UpdateFieldRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    try:
        existing = view_profile(session, user_id=user_id)
    except ProfileNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    _require_org_match(existing.org_unit, org_id)
    updated = update_field(session, user_id=user_id, field=body.field, new_value=body.new_value)
    session.commit()
    return updated.model_dump(mode="json")


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    user_id: str,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> None:
    try:
        existing = view_profile(session, user_id=user_id)
    except ProfileNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    _require_org_match(existing.org_unit, org_id)
    delete_profile(session, user_id=user_id, actor=org_id)
    session.commit()


@router.get("/{user_id}/proposals")
def list_proposals(
    user_id: str,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> list[dict[str, Any]]:
    try:
        existing = view_profile(session, user_id=user_id)
    except ProfileNotFound as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    _require_org_match(existing.org_unit, org_id)
    proposals = (
        session.query(UserModelProposalRow)
        .filter_by(user_id=user_id, status="pending")
        .order_by(UserModelProposalRow.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "field": p.field,
            "current_value": p.current_value_jsonb,
            "proposed_value": p.proposed_value_jsonb,
            "signal_count": p.signal_count,
            "rationale": p.rationale,
            "created_at": p.created_at.isoformat(),
        }
        for p in proposals
    ]


@router.post("/proposals/{proposal_id}/decide")
def decide_proposal(
    proposal_id: str,
    body: ProposalDecisionRequest,
    org_id: str = Depends(require_org),
    session: Session = Depends(db_session),
) -> dict[str, Any]:
    proposal = session.get(UserModelProposalRow, proposal_id)
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="proposal not found"
        )
    # Cross-org isolation: load owner profile + verify
    try:
        owner_profile = view_profile(session, user_id=proposal.user_id)
    except ProfileNotFound as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="proposal owner has no profile",
        ) from e
    _require_org_match(owner_profile.org_unit, org_id)
    try:
        if body.decision == "approve":
            out = confirm_proposal(session, proposal_id=proposal_id, actor=body.actor)
        else:
            out = reject_proposal(session, proposal_id=proposal_id, actor=body.actor)
    except ProposalError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        ) from e
    session.commit()
    # BigShiftProposal is the post-decide read-back from propose.py — load the
    # underlying row to grab decided_at/decided_by (not on the dataclass).
    row = session.get(UserModelProposalRow, out.id)
    return {
        "id": out.id,
        "status": out.status,
        "decided_by": row.decided_by if row else None,
        "decided_at": row.decided_at.isoformat() if row and row.decided_at else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _require_org_match(profile_org: str, request_org: str) -> None:
    if profile_org != request_org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="profile belongs to a different org",
        )
