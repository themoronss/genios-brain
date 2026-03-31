"""
Entity Tagging & Disclosure Control — Phase 7.
Both features are Hustler+ only (gated via require_operation).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.plan_enforcer import require_operation
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

_VALID_DISCLOSURE = {"public", "private", "restricted"}


class TagsUpdate(BaseModel):
    tags: List[str]


class DisclosureUpdate(BaseModel):
    disclosure_level: str  # public | private | restricted
    restricted_to_agents: Optional[List[str]] = None


# ── Tags ─────────────────────────────────────────────────────────────────────

@router.patch("/api/org/{org_id}/contacts/{contact_id}/tags")
def update_contact_tags(
    org_id: str,
    contact_id: str,
    body: TagsUpdate,
    db: Session = Depends(get_db),
):
    """Set tags for a contact. Hustler+ only."""
    require_operation(db, org_id, "manual_context")

    # Sanitize: lowercase, strip, dedupe, max 20 tags, max 50 chars each
    tags = list({t.lower().strip()[:50] for t in body.tags if t.strip()})[:20]

    result = db.execute(
        text("""
            UPDATE contacts SET tags = :tags
            WHERE id = :id AND org_id = :org_id
            RETURNING id
        """),
        {"tags": tags, "id": contact_id, "org_id": org_id},
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.commit()
    return {"updated": True, "tags": tags}


@router.get("/api/org/{org_id}/contacts")
def list_contacts(
    org_id: str,
    tag: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List contacts, optionally filtered by tag. Private contacts excluded."""
    try:
        params: dict = {"org_id": org_id, "limit": min(limit, 200)}
        if tag:
            tag_clean = tag.lower().strip()
            rows = db.execute(
                text("""
                    SELECT id, name, email, company, relationship_stage,
                           tags, disclosure_level, composite_score
                    FROM contacts
                    WHERE org_id = :org_id
                      AND disclosure_level != 'private'
                      AND tags @> ARRAY[:tag]::text[]
                    ORDER BY composite_score DESC NULLS LAST
                    LIMIT :limit
                """),
                {**params, "tag": tag_clean},
            ).fetchall()
        else:
            rows = db.execute(
                text("""
                    SELECT id, name, email, company, relationship_stage,
                           tags, disclosure_level, composite_score
                    FROM contacts
                    WHERE org_id = :org_id
                      AND disclosure_level != 'private'
                    ORDER BY composite_score DESC NULLS LAST
                    LIMIT :limit
                """),
                params,
            ).fetchall()

        return {
            "contacts": [
                {
                    "id": str(r[0]),
                    "name": r[1],
                    "email": r[2],
                    "company": r[3],
                    "relationship_stage": r[4],
                    "tags": r[5] or [],
                    "disclosure_level": r[6] or "public",
                    "composite_score": float(r[7] or 0.5),
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"List contacts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Disclosure ────────────────────────────────────────────────────────────────

@router.patch("/api/org/{org_id}/contacts/{contact_id}/disclosure")
def update_contact_disclosure(
    org_id: str,
    contact_id: str,
    body: DisclosureUpdate,
    db: Session = Depends(get_db),
):
    """Set disclosure level for a contact. Hustler+ only."""
    require_operation(db, org_id, "manual_context")

    if body.disclosure_level not in _VALID_DISCLOSURE:
        raise HTTPException(
            status_code=400,
            detail=f"disclosure_level must be one of: {', '.join(_VALID_DISCLOSURE)}",
        )

    restricted_to = body.restricted_to_agents or []

    result = db.execute(
        text("""
            UPDATE contacts
            SET disclosure_level = :level,
                restricted_to_agents = :restricted_to
            WHERE id = :id AND org_id = :org_id
            RETURNING id
        """),
        {
            "level": body.disclosure_level,
            "restricted_to": restricted_to,
            "id": contact_id,
            "org_id": org_id,
        },
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Contact not found")

    db.commit()
    return {"updated": True, "disclosure_level": body.disclosure_level}
