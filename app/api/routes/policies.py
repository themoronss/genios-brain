"""
Policy CRUD + dry-run endpoints (Phase 3).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.policy import engine as policy_engine
from app.policy import store as policy_store

logger = logging.getLogger(__name__)
router = APIRouter()


def _jwt_org(request: Request) -> str:
    oid = getattr(request.state, "jwt_org_id", None)
    if not oid:
        raise HTTPException(status_code=401, detail="Authentication required")
    return oid


# ── Request models ───────────────────────────────────────────────────────────

class PolicyIn(BaseModel):
    name: str
    action_type: str
    rule_json: dict
    description: Optional[str] = None
    risk_tier: Optional[str] = None
    priority: int = 100
    mode: str = "enforce"


class PolicyPatch(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    action_type: Optional[str] = None
    risk_tier: Optional[str] = None
    rule_json: Optional[dict] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None
    mode: Optional[str] = None


class DryRunIn(BaseModel):
    rule_json: dict
    samples: list
    action_type: str = "*"
    risk_tier: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/api/org/{org_id}/policies")
def list_policies(
    org_id: str,
    request: Request,
    enabled_only: bool = False,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    return {"rules": policy_store.list_rules(db, org_id, enabled_only=enabled_only)}


@router.post("/api/org/{org_id}/policies")
def create_policy(
    org_id: str,
    body: PolicyIn,
    request: Request,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    try:
        rule = policy_store.create_rule(
            db, org_id=org_id,
            name=body.name, action_type=body.action_type,
            rule_json=body.rule_json, description=body.description,
            risk_tier=body.risk_tier, priority=body.priority, mode=body.mode,
            created_by=_jwt_org(request),
        )
    except Exception as e:
        logger.warning(f"create_policy failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    return rule


@router.get("/api/org/{org_id}/policies/{rule_id}")
def get_policy(
    org_id: str,
    rule_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    rule = policy_store.get_rule(db, org_id, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="rule not found")
    return rule


@router.patch("/api/org/{org_id}/policies/{rule_id}")
def update_policy(
    org_id: str,
    rule_id: str,
    body: PolicyPatch,
    request: Request,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    updated = policy_store.update_rule(db, org_id, rule_id, **body.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="rule not found")
    return updated


@router.delete("/api/org/{org_id}/policies/{rule_id}")
def delete_policy(
    org_id: str,
    rule_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    ok = policy_store.delete_rule(db, org_id, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="rule not found")
    return {"deleted": True}


@router.post("/api/org/{org_id}/policies/dry-run")
def dry_run(
    org_id: str,
    body: DryRunIn,
    request: Request,
    db: Session = Depends(get_db),
):
    if _jwt_org(request) != org_id:
        raise HTTPException(status_code=403, detail="org mismatch")
    return policy_engine.dry_run(
        db, org_id,
        rule_json=body.rule_json, samples=body.samples,
        action_type=body.action_type, risk_tier=body.risk_tier,
    )
