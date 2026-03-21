"""
Authority Graph API — PDF spec: Role nodes, permission edges, escalation chain.

Endpoints:
  GET  /v1/authority/{org_id}/roles              — list all roles
  POST /v1/authority/{org_id}/roles              — create a role
  GET  /v1/authority/{org_id}/roles/{role_id}    — get role + permissions
  POST /v1/authority/{org_id}/permissions        — add permission to role
  GET  /v1/authority/{org_id}/contacts/{contact_id}/roles — contact's authority roles
  POST /v1/authority/{org_id}/contacts/{contact_id}/assign — assign role to contact
  GET  /v1/authority/{org_id}/check              — check if action is authorized
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from typing import Optional, List
import uuid

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Pydantic Models ────────────────────────────────────────────────────────

class CreateRoleRequest(BaseModel):
    role_name: str
    description: Optional[str] = None
    trust_level: int = 50


class CreatePermissionRequest(BaseModel):
    role_id: str
    action_type: str
    max_value: Optional[float] = None
    requires_approval: bool = False
    escalate_to_role: Optional[str] = None


class AssignRoleRequest(BaseModel):
    role_id: str
    confidence: float = 0.7


class AuthorityCheckRequest(BaseModel):
    contact_id: str
    action_type: str
    value: Optional[float] = None


# ── Routes ─────────────────────────────────────────────────────────────────

@router.get("/v1/authority/{org_id}/roles")
def list_roles(org_id: str, db: Session = Depends(get_db)):
    """List all authority roles for an org."""
    rows = db.execute(
        text("""
            SELECT ar.id, ar.role_name, ar.description, ar.trust_level, ar.created_at,
                COUNT(aa.id) AS assigned_count
            FROM authority_roles ar
            LEFT JOIN authority_assignments aa ON aa.role_id = ar.id
            WHERE ar.org_id = :org_id
            GROUP BY ar.id
            ORDER BY ar.trust_level DESC, ar.role_name
        """),
        {"org_id": org_id}
    ).fetchall()

    return {"roles": [
        {
            "id": str(r[0]),
            "role_name": r[1],
            "description": r[2],
            "trust_level": r[3],
            "created_at": str(r[4]),
            "assigned_count": int(r[5]),
        }
        for r in rows
    ]}


@router.post("/v1/authority/{org_id}/roles")
def create_role(org_id: str, req: CreateRoleRequest, db: Session = Depends(get_db)):
    """Create a new authority role."""
    role_id = str(uuid.uuid4())
    try:
        db.execute(
            text("""
                INSERT INTO authority_roles (id, org_id, role_name, description, trust_level)
                VALUES (:id, :org_id, :role_name, :description, :trust_level)
                ON CONFLICT (org_id, role_name) DO UPDATE SET
                    description = EXCLUDED.description,
                    trust_level = EXCLUDED.trust_level
            """),
            {
                "id": role_id,
                "org_id": org_id,
                "role_name": req.role_name,
                "description": req.description,
                "trust_level": req.trust_level,
            }
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"id": role_id, "role_name": req.role_name, "status": "created"}


@router.get("/v1/authority/{org_id}/roles/{role_id}")
def get_role(org_id: str, role_id: str, db: Session = Depends(get_db)):
    """Get role details with all permissions."""
    role = db.execute(
        text("SELECT id, role_name, description, trust_level, created_at FROM authority_roles WHERE id = :id AND org_id = :org_id"),
        {"id": role_id, "org_id": org_id}
    ).fetchone()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    permissions = db.execute(
        text("""
            SELECT ap.id, ap.action_type, ap.max_value, ap.requires_approval,
                ar.role_name AS escalate_to_name
            FROM authority_permissions ap
            LEFT JOIN authority_roles ar ON ar.id = ap.escalate_to_role
            WHERE ap.role_id = :role_id
            ORDER BY ap.action_type
        """),
        {"role_id": role_id}
    ).fetchall()

    return {
        "id": str(role[0]),
        "role_name": role[1],
        "description": role[2],
        "trust_level": role[3],
        "created_at": str(role[4]),
        "permissions": [
            {
                "id": str(p[0]),
                "action_type": p[1],
                "max_value": float(p[2]) if p[2] is not None else None,
                "requires_approval": p[3],
                "escalate_to": p[4],
            }
            for p in permissions
        ],
    }


@router.post("/v1/authority/{org_id}/permissions")
def add_permission(org_id: str, req: CreatePermissionRequest, db: Session = Depends(get_db)):
    """Add a permission entry to a role."""
    perm_id = str(uuid.uuid4())
    try:
        db.execute(
            text("""
                INSERT INTO authority_permissions
                    (id, org_id, role_id, action_type, max_value, requires_approval, escalate_to_role)
                VALUES (:id, :org_id, :role_id, :action_type, :max_value, :requires_approval, :escalate_to_role)
            """),
            {
                "id": perm_id,
                "org_id": org_id,
                "role_id": req.role_id,
                "action_type": req.action_type,
                "max_value": req.max_value,
                "requires_approval": req.requires_approval,
                "escalate_to_role": req.escalate_to_role,
            }
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"id": perm_id, "status": "created"}


@router.get("/v1/authority/{org_id}/contacts/{contact_id}/roles")
def get_contact_roles(org_id: str, contact_id: str, db: Session = Depends(get_db)):
    """Get all authority roles assigned to a contact."""
    rows = db.execute(
        text("""
            SELECT ar.id, ar.role_name, ar.description, ar.trust_level,
                aa.confidence, aa.assigned_at
            FROM authority_assignments aa
            JOIN authority_roles ar ON ar.id = aa.role_id
            WHERE aa.org_id = :org_id AND aa.contact_id = :contact_id
            ORDER BY ar.trust_level DESC
        """),
        {"org_id": org_id, "contact_id": contact_id}
    ).fetchall()

    return {"roles": [
        {
            "id": str(r[0]),
            "role_name": r[1],
            "description": r[2],
            "trust_level": r[3],
            "confidence": float(r[4]),
            "assigned_at": str(r[5]),
        }
        for r in rows
    ]}


@router.post("/v1/authority/{org_id}/contacts/{contact_id}/assign")
def assign_role(org_id: str, contact_id: str, req: AssignRoleRequest, db: Session = Depends(get_db)):
    """Assign an authority role to a contact."""
    try:
        db.execute(
            text("""
                INSERT INTO authority_assignments (id, org_id, contact_id, role_id, confidence)
                VALUES (:id, :org_id, :contact_id, :role_id, :confidence)
                ON CONFLICT (org_id, contact_id, role_id) DO UPDATE SET
                    confidence = EXCLUDED.confidence,
                    assigned_at = NOW()
            """),
            {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "contact_id": contact_id,
                "role_id": req.role_id,
                "confidence": req.confidence,
            }
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "assigned"}


@router.post("/v1/authority/{org_id}/check")
def check_authority(org_id: str, req: AuthorityCheckRequest, db: Session = Depends(get_db)):
    """
    Check if a contact is authorized to approve/initiate an action.
    Returns: authorized (bool), requires_approval (bool), max_value, escalate_to.
    """
    # Find the highest-trust role this contact has that covers the action_type
    row = db.execute(
        text("""
            SELECT ap.max_value, ap.requires_approval, ar2.role_name AS escalate_to,
                ar.trust_level
            FROM authority_assignments aa
            JOIN authority_roles ar ON ar.id = aa.role_id
            JOIN authority_permissions ap ON ap.role_id = ar.id AND ap.action_type = :action_type
            LEFT JOIN authority_roles ar2 ON ar2.id = ap.escalate_to_role
            WHERE aa.org_id = :org_id AND aa.contact_id = :contact_id
            ORDER BY ar.trust_level DESC
            LIMIT 1
        """),
        {"org_id": org_id, "contact_id": req.contact_id, "action_type": req.action_type}
    ).fetchone()

    if not row:
        return {
            "authorized": False,
            "requires_approval": True,
            "max_value": None,
            "escalate_to": None,
            "reason": "No matching permission found for this contact",
        }

    max_value = float(row[0]) if row[0] is not None else None
    within_limit = (
        req.value is None or
        max_value is None or
        req.value <= max_value
    )

    return {
        "authorized": within_limit and not row[1],
        "requires_approval": bool(row[1]) or not within_limit,
        "max_value": max_value,
        "escalate_to": row[2],
        "trust_level": int(row[3]),
    }
