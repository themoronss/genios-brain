"""
Seats / Team members routes.
Endpoints:
  GET    /api/org/{org_id}/members              — list active members + pending invites
  POST   /api/org/{org_id}/members/invite        — invite a member (sends email, creates seat_invite)
  DELETE /api/org/{org_id}/members/{member_id}  — remove an accepted member
  DELETE /api/org/{org_id}/invites/{invite_id}  — cancel a pending invite
  POST   /invite/accept/{token}                  — accept invite (public, no auth)

Seat limits per plan:  Trial=1, Hustler=1, Startup=5
"""

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.plan_enforcer import get_org_plan

logger = logging.getLogger(__name__)
router = APIRouter()

SEAT_LIMITS = {"trial": 1, "hustler": 1, "startup": 5}


def _seat_limit(tier: str) -> int:
    return SEAT_LIMITS.get(tier, 1)


def _member_count(db: Session, org_id: str) -> int:
    """Count accepted members (excluding owner — owner is always counted separately)."""
    return db.execute(
        text("SELECT COUNT(*) FROM org_members WHERE org_id = :oid AND accepted_at IS NOT NULL"),
        {"oid": org_id},
    ).scalar() or 0


# ── List members + pending invites ───────────────────────────────────────────

@router.get("/api/org/{org_id}/members")
def list_members(org_id: str, db: Session = Depends(get_db)):
    plan_info = get_org_plan(db, org_id)
    tier      = plan_info["tier"]
    limit     = _seat_limit(tier)

    # Accepted members
    rows = db.execute(
        text("""
            SELECT id, email, name, role, invited_at, accepted_at
            FROM org_members
            WHERE org_id = :oid
            ORDER BY accepted_at ASC NULLS LAST, invited_at ASC
        """),
        {"oid": org_id},
    ).fetchall()

    members = [
        {
            "id":          str(r.id),
            "email":       r.email,
            "name":        r.name or r.email.split("@")[0],
            "role":        r.role,
            "invited_at":  r.invited_at.isoformat() if r.invited_at else None,
            "accepted_at": r.accepted_at.isoformat() if r.accepted_at else None,
            "status":      "active" if r.accepted_at else "pending",
        }
        for r in rows
    ]

    # Pending invites not yet in org_members (created but not accepted)
    invites = db.execute(
        text("""
            SELECT id, email, role, created_at, expires_at
            FROM seat_invites
            WHERE org_id = :oid
              AND accepted_at IS NULL
              AND expires_at > NOW()
            ORDER BY created_at DESC
        """),
        {"oid": org_id},
    ).fetchall()

    pending = [
        {
            "id":         str(i.id),
            "email":      i.email,
            "role":       i.role,
            "created_at": i.created_at.isoformat() if i.created_at else None,
            "expires_at": i.expires_at.isoformat() if i.expires_at else None,
        }
        for i in invites
    ]

    accepted_count = sum(1 for m in members if m["status"] == "active")

    return {
        "members":       members,
        "pending_invites": pending,
        "count":         accepted_count,
        "seat_limit":    limit,
        "plan":          tier,
    }


# ── Invite member ─────────────────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: str
    role:  str = "viewer"   # viewer | editor | admin


@router.post("/api/org/{org_id}/members/invite")
def invite_member(org_id: str, body: InviteRequest, db: Session = Depends(get_db)):
    if body.role not in ("viewer", "editor", "admin"):
        raise HTTPException(status_code=400, detail="Invalid role")

    plan_info = get_org_plan(db, org_id)
    tier      = plan_info["tier"]
    limit     = _seat_limit(tier)

    # Count accepted + pending
    accepted = _member_count(db, org_id)
    pending  = db.execute(
        text("SELECT COUNT(*) FROM seat_invites WHERE org_id = :oid AND accepted_at IS NULL AND expires_at > NOW()"),
        {"oid": org_id},
    ).scalar() or 0

    # Owner is +1 (not in org_members, but counts toward seat limit)
    total_used = accepted + pending + 1  # +1 for owner
    if total_used >= limit:
        raise HTTPException(
            status_code=403,
            detail={
                "error":           "SEAT_LIMIT",
                "message":         f"Seat limit of {limit} reached for {tier} plan.",
                "upgrade_required": tier != "startup",
            },
        )

    # Check duplicate
    existing_invite = db.execute(
        text("SELECT id FROM seat_invites WHERE org_id = :oid AND email = :email AND accepted_at IS NULL AND expires_at > NOW()"),
        {"oid": org_id, "email": body.email},
    ).fetchone()
    if existing_invite:
        raise HTTPException(status_code=400, detail="Invite already sent to this email")

    existing_member = db.execute(
        text("SELECT id FROM org_members WHERE org_id = :oid AND email = :email"),
        {"oid": org_id, "email": body.email},
    ).fetchone()
    if existing_member:
        raise HTTPException(status_code=400, detail="User is already a member")

    token = secrets.token_urlsafe(32)
    db.execute(
        text("""
            INSERT INTO seat_invites (org_id, email, role, token)
            VALUES (:org_id, :email, :role, :token)
        """),
        {"org_id": org_id, "email": body.email, "role": body.role, "token": token},
    )
    db.commit()

    # Send invite email (non-blocking — skip if SMTP not configured)
    try:
        from app.tasks.billing_jobs import send_invite_email
        send_invite_email(body.email, org_id, body.role, token)
    except Exception as e:
        logger.warning(f"Invite email skipped: {e}")

    return {"invited": True, "email": body.email, "role": body.role}


# ── Remove member ─────────────────────────────────────────────────────────────

@router.delete("/api/org/{org_id}/members/{member_id}")
def remove_member(org_id: str, member_id: str, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT role FROM org_members WHERE id = :mid AND org_id = :oid"),
        {"mid": member_id, "oid": org_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Member not found")
    if row.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove org owner")

    db.execute(
        text("DELETE FROM org_members WHERE id = :mid AND org_id = :oid"),
        {"mid": member_id, "oid": org_id},
    )
    db.commit()
    return {"removed": True}


# ── Cancel invite ─────────────────────────────────────────────────────────────

@router.delete("/api/org/{org_id}/invites/{invite_id}")
def cancel_invite(org_id: str, invite_id: str, db: Session = Depends(get_db)):
    db.execute(
        text("DELETE FROM seat_invites WHERE id = :iid AND org_id = :oid"),
        {"iid": invite_id, "oid": org_id},
    )
    db.commit()
    return {"cancelled": True}


# ── Accept invite (public) ────────────────────────────────────────────────────

class AcceptInviteRequest(BaseModel):
    name:     str
    password: str  # Set password when accepting invite


@router.post("/invite/accept/{token}")
def accept_invite(token: str, body: AcceptInviteRequest, db: Session = Depends(get_db)):
    invite = db.execute(
        text("""
            SELECT id, org_id, email, role
            FROM seat_invites
            WHERE token = :token AND accepted_at IS NULL AND expires_at > NOW()
        """),
        {"token": token},
    ).fetchone()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or expired")

    import bcrypt, jwt, os
    from datetime import datetime, timedelta

    # Create user account for invitee (separate org record — same orgs table)
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    import secrets as _sec
    api_key = f"gn_live_{_sec.token_urlsafe(32)}"

    result = db.execute(
        text("""
            INSERT INTO orgs (name, email, password_hash, api_key, subscription_tier, plan_status)
            VALUES (:name, :email, :pw, :key, 'member', 'active')
            ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """),
        {"name": body.name, "email": invite.email, "pw": pw_hash, "key": api_key},
    )
    user_id = result.fetchone()[0]

    # Add to org_members
    db.execute(
        text("""
            INSERT INTO org_members (org_id, email, name, role, accepted_at)
            VALUES (:org_id, :email, :name, :role, NOW())
            ON CONFLICT (org_id, email) DO UPDATE
                SET accepted_at = NOW(), role = EXCLUDED.role
        """),
        {"org_id": str(invite.org_id), "email": invite.email,
         "name": body.name, "role": invite.role},
    )

    # Mark invite accepted
    db.execute(
        text("UPDATE seat_invites SET accepted_at = NOW() WHERE id = :iid"),
        {"iid": str(invite.id)},
    )
    db.commit()

    JWT_SECRET = os.getenv("JWT_SECRET", "genios-secret-key-replace-in-production")
    token_jwt = jwt.encode(
        {"org_id": str(user_id), "email": invite.email,
         "workspace_org_id": str(invite.org_id),
         "exp": datetime.utcnow() + timedelta(days=7)},
        JWT_SECRET, algorithm="HS256",
    )

    return {
        "accepted":  True,
        "org_id":    str(invite.org_id),
        "token":     token_jwt,
        "email":     invite.email,
        "role":      invite.role,
    }
