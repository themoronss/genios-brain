"""
Entity Resolver + Merge Queue API — PDF spec: Fuzzy name+company matching,
merge queue management for human review of low-confidence deduplication.

Endpoints:
  POST /v1/merge/{org_id}/scan          — run entity resolution scan, populate queue
  GET  /v1/merge/{org_id}/queue         — list pending merge candidates
  GET  /v1/merge/{org_id}/queue/{id}    — get single merge candidate detail
  POST /v1/merge/{org_id}/queue/{id}/merge   — merge contact_a into contact_b
  POST /v1/merge/{org_id}/queue/{id}/reject  — reject merge (mark as not a duplicate)
  POST /v1/merge/{org_id}/queue/{id}/defer   — defer for later review
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from typing import Optional
import uuid
import re

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Models ─────────────────────────────────────────────────────────────────

class MergeDecisionRequest(BaseModel):
    reviewed_by: str = "user"


# ── Fuzzy matching helpers ────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """Normalize a name for comparison: lowercase, strip punctuation."""
    if not name:
        return ""
    return re.sub(r"[^a-z0-9 ]", "", name.lower().strip())


def _name_similarity(a: str, b: str) -> float:
    """
    Simple name similarity: exact match = 1.0, first+last swap = 0.9,
    first name only match = 0.6, no match = 0.0.
    """
    na = _normalize_name(a)
    nb = _normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # Check word set overlap
    words_a = set(na.split())
    words_b = set(nb.split())
    if not words_a or not words_b:
        return 0.0
    overlap = len(words_a & words_b)
    total = len(words_a | words_b)
    return overlap / total


def _compute_match_score(
    name_a: str, email_a: str, company_a: str,
    name_b: str, email_b: str, company_b: str,
) -> tuple[float, str]:
    """
    Compute match score between two contacts.
    Returns (score, reason) where score 0.0-1.0.
    """
    # Exact email match (excluding domain variations)
    if email_a and email_b:
        local_a = email_a.split("@")[0].lower() if "@" in email_a else email_a.lower()
        local_b = email_b.split("@")[0].lower() if "@" in email_b else email_b.lower()
        if local_a == local_b and email_a.lower() != email_b.lower():
            return 0.92, "same_email_local_diff_domain"
        if email_a.lower() == email_b.lower():
            return 1.0, "identical_email"

    name_score = _name_similarity(name_a, name_b)

    # Same company + high name similarity
    if company_a and company_b:
        company_match = _normalize_name(company_a) == _normalize_name(company_b)
        if company_match and name_score >= 0.8:
            return 0.90, "same_name_same_company"
        if company_match and name_score >= 0.6:
            return 0.75, "similar_name_same_company"

    if name_score >= 0.95:
        return 0.80, "near_identical_name"

    if name_score >= 0.80:
        return 0.65, "similar_name"

    return 0.0, "no_match"


# ── Routes ─────────────────────────────────────────────────────────────────

@router.post("/v1/merge/{org_id}/scan")
def run_entity_resolution_scan(org_id: str, db: Session = Depends(get_db)):
    """
    Run entity resolution scan: find likely duplicate contacts and add to merge queue.
    Compares contacts with 3+ interactions for fuzzy name+company overlap.
    Only adds new candidates not already in the queue.
    """
    # Fetch all active contacts with some history
    contacts = db.execute(
        text("""
            SELECT id, name, email, company
            FROM contacts
            WHERE org_id = :org_id
            AND interaction_count >= 3
            AND (is_archived = FALSE OR is_archived IS NULL)
            AND entity_type != 'self'
            ORDER BY name
        """),
        {"org_id": org_id}
    ).fetchall()

    # Get existing queue pairs to avoid duplicates
    existing = db.execute(
        text("SELECT contact_id_a, contact_id_b FROM merge_queue WHERE org_id = :org_id"),
        {"org_id": org_id}
    ).fetchall()
    existing_pairs = {(str(r[0]), str(r[1])) for r in existing}
    existing_pairs |= {(str(r[1]), str(r[0])) for r in existing}

    added = 0
    contacts_list = list(contacts)

    for i, ca in enumerate(contacts_list):
        for cb in contacts_list[i + 1:]:
            id_a = str(ca[0])
            id_b = str(cb[0])

            # Skip already queued
            if (id_a, id_b) in existing_pairs:
                continue

            score, reason = _compute_match_score(
                ca[1], ca[2], ca[3],
                cb[1], cb[2], cb[3],
            )

            if score >= 0.65:
                try:
                    db.execute(
                        text("""
                            INSERT INTO merge_queue
                                (id, org_id, contact_id_a, contact_id_b, match_score, match_reason)
                            VALUES (:id, :org_id, :a, :b, :score, :reason)
                            ON CONFLICT (org_id, contact_id_a, contact_id_b) DO NOTHING
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "org_id": org_id,
                            "a": id_a,
                            "b": id_b,
                            "score": score,
                            "reason": reason,
                        }
                    )
                    added += 1
                    existing_pairs.add((id_a, id_b))
                except Exception:
                    continue

    db.commit()
    return {"scanned": len(contacts_list), "new_candidates": added}


@router.get("/v1/merge/{org_id}/queue")
def list_merge_queue(
    org_id: str,
    status: str = Query("pending"),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List merge queue candidates."""
    rows = db.execute(
        text("""
            SELECT mq.id, mq.match_score, mq.match_reason, mq.status, mq.created_at,
                ca.id, ca.name, ca.email, ca.company, ca.entity_type, ca.interaction_count,
                cb.id, cb.name, cb.email, cb.company, cb.entity_type, cb.interaction_count
            FROM merge_queue mq
            JOIN contacts ca ON ca.id = mq.contact_id_a
            JOIN contacts cb ON cb.id = mq.contact_id_b
            WHERE mq.org_id = :org_id AND mq.status = :status
            ORDER BY mq.match_score DESC, mq.created_at ASC
            LIMIT :limit
        """),
        {"org_id": org_id, "status": status, "limit": limit}
    ).fetchall()

    return {"queue": [
        {
            "id": str(r[0]),
            "match_score": float(r[1]),
            "match_reason": r[2],
            "status": r[3],
            "created_at": str(r[4]),
            "contact_a": {
                "id": str(r[5]), "name": r[6], "email": r[7],
                "company": r[8], "entity_type": r[9], "interaction_count": r[10],
            },
            "contact_b": {
                "id": str(r[11]), "name": r[12], "email": r[13],
                "company": r[14], "entity_type": r[15], "interaction_count": r[16],
            },
        }
        for r in rows
    ]}


@router.get("/v1/merge/{org_id}/queue/{merge_id}")
def get_merge_candidate(org_id: str, merge_id: str, db: Session = Depends(get_db)):
    """Get a single merge candidate with full contact details."""
    row = db.execute(
        text("""
            SELECT mq.id, mq.match_score, mq.match_reason, mq.status,
                ca.id, ca.name, ca.email, ca.company, ca.entity_type,
                ca.interaction_count, ca.last_interaction_at, ca.sentiment_ewma,
                cb.id, cb.name, cb.email, cb.company, cb.entity_type,
                cb.interaction_count, cb.last_interaction_at, cb.sentiment_ewma
            FROM merge_queue mq
            JOIN contacts ca ON ca.id = mq.contact_id_a
            JOIN contacts cb ON cb.id = mq.contact_id_b
            WHERE mq.id = :id AND mq.org_id = :org_id
        """),
        {"id": merge_id, "org_id": org_id}
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Merge candidate not found")

    return {
        "id": str(row[0]),
        "match_score": float(row[1]),
        "match_reason": row[2],
        "status": row[3],
        "contact_a": {
            "id": str(row[4]), "name": row[5], "email": row[6],
            "company": row[7], "entity_type": row[8],
            "interaction_count": row[9], "last_interaction_at": str(row[10]) if row[10] else None,
            "sentiment_ewma": float(row[11]) if row[11] else None,
        },
        "contact_b": {
            "id": str(row[12]), "name": row[13], "email": row[14],
            "company": row[15], "entity_type": row[16],
            "interaction_count": row[17], "last_interaction_at": str(row[18]) if row[18] else None,
            "sentiment_ewma": float(row[19]) if row[19] else None,
        },
    }


@router.post("/v1/merge/{org_id}/queue/{merge_id}/merge")
def execute_merge(
    org_id: str,
    merge_id: str,
    req: MergeDecisionRequest,
    db: Session = Depends(get_db),
):
    """
    Merge contact_a into contact_b: reassign all interactions/commitments
    from contact_a to contact_b, then archive contact_a.
    """
    row = db.execute(
        text("SELECT contact_id_a, contact_id_b FROM merge_queue WHERE id = :id AND org_id = :org_id"),
        {"id": merge_id, "org_id": org_id}
    ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Merge candidate not found")

    id_a, id_b = str(row[0]), str(row[1])

    try:
        # Reassign interactions
        db.execute(
            text("UPDATE interactions SET contact_id = :b WHERE contact_id = :a AND org_id = :org_id"),
            {"a": id_a, "b": id_b, "org_id": org_id}
        )
        # Reassign commitments
        db.execute(
            text("UPDATE commitments SET contact_id = :b WHERE contact_id = :a AND org_id = :org_id"),
            {"a": id_a, "b": id_b, "org_id": org_id}
        )
        # Update introduced_by references
        db.execute(
            text("UPDATE contacts SET introduced_by = :b WHERE introduced_by = :a AND org_id = :org_id"),
            {"a": id_a, "b": id_b, "org_id": org_id}
        )
        # Archive contact_a
        db.execute(
            text("UPDATE contacts SET is_archived = TRUE WHERE id = :a AND org_id = :org_id"),
            {"a": id_a, "org_id": org_id}
        )
        # Update merge queue status
        db.execute(
            text("""
                UPDATE merge_queue SET status = 'merged', reviewed_by = :reviewed_by, reviewed_at = NOW()
                WHERE id = :id
            """),
            {"id": merge_id, "reviewed_by": req.reviewed_by}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "merged", "kept": id_b, "archived": id_a}


@router.post("/v1/merge/{org_id}/queue/{merge_id}/reject")
def reject_merge(
    org_id: str,
    merge_id: str,
    req: MergeDecisionRequest,
    db: Session = Depends(get_db),
):
    """Reject merge — contacts are not duplicates."""
    try:
        db.execute(
            text("""
                UPDATE merge_queue SET status = 'rejected', reviewed_by = :reviewed_by, reviewed_at = NOW()
                WHERE id = :id AND org_id = :org_id
            """),
            {"id": merge_id, "org_id": org_id, "reviewed_by": req.reviewed_by}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "rejected"}


@router.post("/v1/merge/{org_id}/queue/{merge_id}/defer")
def defer_merge(
    org_id: str,
    merge_id: str,
    req: MergeDecisionRequest,
    db: Session = Depends(get_db),
):
    """Defer merge decision for later review."""
    try:
        db.execute(
            text("""
                UPDATE merge_queue SET status = 'deferred', reviewed_by = :reviewed_by, reviewed_at = NOW()
                WHERE id = :id AND org_id = :org_id
            """),
            {"id": merge_id, "org_id": org_id, "reviewed_by": req.reviewed_by}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "deferred"}
