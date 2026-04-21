"""
Graph Segment (Dept Cluster) CRUD API — Phase 4.
  POST   /v1/segment               — create segment (plan-limited: 1/3/10)
  GET    /v1/segments              — list all segments for org
  PUT    /v1/segment/{id}          — update name/type/config
  DELETE /v1/segment/{id}          — delete segment
  POST   /v1/segment/{id}/members  — assign contacts to segment
  DELETE /v1/segment/{id}/members/{contact_id} — remove contact from segment
  POST   /v1/segment/{id}/sync     — manual sync trigger (Trial plan only)

Segment types per PDF spec: Investor / Customer / Team / Vendor / Admin / Other
Plan limits (max_clusters): Trial=1, Hustler=3, Startup=10
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.plan_enforcer import get_org_plan

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_CLUSTER_TYPES = {"Investor", "Customer", "Team", "Vendor", "Admin", "Other"}


def _get_segment_or_404(db: Session, segment_id: str, org_id: str):
    row = db.execute(
        text("SELECT id, org_id, name, cluster_type, config, sync_interval_hours, last_synced_at, created_at FROM graph_segments WHERE id = :sid AND org_id = :org_id"),
        {"sid": segment_id, "org_id": org_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail={"error": "SEGMENT_NOT_FOUND", "message": "Segment not found"})
    return row


def _format_segment(row, member_count: int = 0) -> dict:
    return {
        "id": str(row.id),
        "name": row.name,
        "cluster_type": row.cluster_type,
        "config": row.config or {},
        "sync_interval_hours": row.sync_interval_hours,
        "last_synced_at": row.last_synced_at.isoformat() if row.last_synced_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "member_count": member_count,
    }


# ── POST /v1/segment ──────────────────────────────────────────────────────────

class CreateSegmentRequest(BaseModel):
    name: str
    cluster_type: str
    config: dict = {}
    sync_interval_hours: int = None  # None = manual; 6/12/18/24 for scheduled


@router.post("/v1/segment", status_code=201)
def create_segment(
    request: CreateSegmentRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Create a named dept cluster. Enforces plan's max_clusters limit."""
    if not request.name or len(request.name.strip()) < 2:
        raise HTTPException(status_code=400, detail={"error": "INVALID_NAME", "message": "Segment name must be at least 2 characters"})

    if request.cluster_type not in VALID_CLUSTER_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_TYPE", "message": f"cluster_type must be one of: {', '.join(sorted(VALID_CLUSTER_TYPES))}"},
        )

    plan_info = get_org_plan(db, org_id)
    max_clusters = plan_info["config"]["max_clusters"]
    tier = plan_info["tier"]

    current_count = db.execute(
        text("SELECT COUNT(*) FROM graph_segments WHERE org_id = :org_id"),
        {"org_id": org_id},
    ).scalar() or 0

    if current_count >= max_clusters:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PLAN_LIMIT",
                "message": f"Max {max_clusters} segment(s) allowed on {tier} plan.",
                "current_count": current_count,
                "max_allowed": max_clusters,
                "upgrade_required": tier != "startup",
            },
        )

    # Validate sync_interval_hours against plan
    sync_hours = _validated_sync_interval(request.sync_interval_hours, tier)

    result = db.execute(
        text("""
            INSERT INTO graph_segments (org_id, name, cluster_type, config, sync_interval_hours, created_at)
            VALUES (:org_id, :name, :type, CAST(:config AS jsonb), :sync_hours, NOW())
            RETURNING id, org_id, name, cluster_type, config, sync_interval_hours, last_synced_at, created_at
        """),
        {
            "org_id": org_id,
            "name": request.name.strip(),
            "type": request.cluster_type,
            "config": __import__("json").dumps(request.config),
            "sync_hours": sync_hours,
        },
    ).fetchone()
    db.commit()

    return _format_segment(result, member_count=0)


# ── GET /v1/segments ──────────────────────────────────────────────────────────

@router.get("/v1/segments")
def list_segments(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """List all segments for the org, with member counts."""
    plan_info = get_org_plan(db, org_id)
    max_clusters = plan_info["config"]["max_clusters"]

    rows = db.execute(
        text("""
            SELECT gs.id, gs.org_id, gs.name, gs.cluster_type, gs.config,
                   gs.sync_interval_hours, gs.last_synced_at, gs.created_at,
                   COUNT(sm.contact_id) AS member_count
            FROM graph_segments gs
            LEFT JOIN segment_members sm ON sm.segment_id = gs.id
            WHERE gs.org_id = :org_id
            GROUP BY gs.id
            ORDER BY gs.created_at ASC
        """),
        {"org_id": org_id},
    ).fetchall()

    segments = []
    for i, row in enumerate(rows):
        seg = _format_segment(row, member_count=row.member_count or 0)
        # Mark clusters beyond plan limit as locked
        seg["locked"] = i >= max_clusters
        segments.append(seg)

    return {
        "segments": segments,
        "count": len(segments),
        "max_allowed": max_clusters,
        "plan_tier": plan_info["tier"],
    }


# ── PUT /v1/segment/{id} ──────────────────────────────────────────────────────

class UpdateSegmentRequest(BaseModel):
    name: str = None
    cluster_type: str = None
    config: dict = None
    sync_interval_hours: int = None


@router.put("/v1/segment/{segment_id}")
def update_segment(
    segment_id: str,
    request: UpdateSegmentRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Update a segment's name, type, or config."""
    _get_segment_or_404(db, segment_id, org_id)

    if request.cluster_type and request.cluster_type not in VALID_CLUSTER_TYPES:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_TYPE", "message": f"cluster_type must be one of: {', '.join(sorted(VALID_CLUSTER_TYPES))}"},
        )

    plan_info = get_org_plan(db, org_id)

    updates = []
    params: dict = {"sid": segment_id, "org_id": org_id}

    if request.name is not None:
        updates.append("name = :name")
        params["name"] = request.name.strip()
    if request.cluster_type is not None:
        updates.append("cluster_type = :cluster_type")
        params["cluster_type"] = request.cluster_type
    if request.config is not None:
        updates.append("config = CAST(:config AS jsonb)")
        params["config"] = __import__("json").dumps(request.config)
    if request.sync_interval_hours is not None:
        sync_hours = _validated_sync_interval(request.sync_interval_hours, plan_info["tier"])
        updates.append("sync_interval_hours = :sync_hours")
        params["sync_hours"] = sync_hours

    if not updates:
        raise HTTPException(status_code=400, detail={"error": "NO_UPDATES", "message": "No fields to update"})

    result = db.execute(
        text(f"""
            UPDATE graph_segments SET {', '.join(updates)}
            WHERE id = :sid AND org_id = :org_id
            RETURNING id, org_id, name, cluster_type, config, sync_interval_hours, last_synced_at, created_at
        """),
        params,
    ).fetchone()
    db.commit()

    member_count = db.execute(
        text("SELECT COUNT(*) FROM segment_members WHERE segment_id = :sid"),
        {"sid": segment_id},
    ).scalar() or 0

    return _format_segment(result, member_count=member_count)


# ── DELETE /v1/segment/{id} ───────────────────────────────────────────────────

@router.delete("/v1/segment/{segment_id}")
def delete_segment(
    segment_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Delete a segment and all its member assignments."""
    _get_segment_or_404(db, segment_id, org_id)

    db.execute(
        text("DELETE FROM graph_segments WHERE id = :sid AND org_id = :org_id"),
        {"sid": segment_id, "org_id": org_id},
    )
    db.commit()
    return {"deleted": True, "id": segment_id}


# ── POST /v1/segment/{id}/members ─────────────────────────────────────────────

class AddMembersRequest(BaseModel):
    contact_ids: list[str]


@router.post("/v1/segment/{segment_id}/members")
def add_members(
    segment_id: str,
    request: AddMembersRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Assign contacts to a segment."""
    _get_segment_or_404(db, segment_id, org_id)

    if not request.contact_ids:
        raise HTTPException(status_code=400, detail={"error": "EMPTY_LIST", "message": "contact_ids cannot be empty"})

    # Verify all contacts belong to this org
    valid = db.execute(
        text("SELECT id FROM contacts WHERE org_id = :org_id AND id = ANY(:ids)"),
        {"org_id": org_id, "ids": request.contact_ids},
    ).fetchall()
    valid_ids = [str(r.id) for r in valid]

    added = 0
    for cid in valid_ids:
        try:
            db.execute(
                text("""
                    INSERT INTO segment_members (segment_id, contact_id, added_at)
                    VALUES (:sid, :cid, NOW())
                    ON CONFLICT (segment_id, contact_id) DO NOTHING
                """),
                {"sid": segment_id, "cid": cid},
            )
            added += 1
        except Exception:
            db.rollback()

    db.commit()
    return {"added": added, "segment_id": segment_id}


# ── DELETE /v1/segment/{id}/members/{contact_id} ─────────────────────────────

@router.delete("/v1/segment/{segment_id}/members/{contact_id}")
def remove_member(
    segment_id: str,
    contact_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Remove a contact from a segment."""
    _get_segment_or_404(db, segment_id, org_id)

    result = db.execute(
        text("DELETE FROM segment_members WHERE segment_id = :sid AND contact_id = :cid RETURNING contact_id"),
        {"sid": segment_id, "cid": contact_id},
    ).fetchone()
    db.commit()

    if not result:
        raise HTTPException(status_code=404, detail={"error": "MEMBER_NOT_FOUND", "message": "Contact is not in this segment"})

    return {"removed": True, "segment_id": segment_id, "contact_id": contact_id}


# ── GET /v1/segment/{id}/members ──────────────────────────────────────────────

@router.get("/v1/segment/{segment_id}/members")
def list_members(
    segment_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """List all contacts in a segment."""
    _get_segment_or_404(db, segment_id, org_id)

    rows = db.execute(
        text("""
            SELECT c.id, c.name, c.email, c.company, c.relationship_stage,
                   c.context_score, sm.added_at
            FROM segment_members sm
            JOIN contacts c ON c.id = sm.contact_id
            WHERE sm.segment_id = :sid
            ORDER BY c.name ASC
        """),
        {"sid": segment_id},
    ).fetchall()

    return {
        "segment_id": segment_id,
        "members": [
            {
                "id": str(r.id),
                "name": r.name,
                "email": r.email,
                "company": r.company,
                "relationship_stage": r.relationship_stage,
                "context_score": float(r.context_score or 0),
                "added_at": r.added_at.isoformat() if r.added_at else None,
            }
            for r in rows
        ],
        "count": len(rows),
    }


# ── POST /v1/segment/{id}/sync ────────────────────────────────────────────────

@router.post("/v1/segment/{segment_id}/sync")
def trigger_segment_sync(
    segment_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    Trigger a manual sync for a segment.
    All plans can trigger manually. Hustler/Startup also have scheduled cron.
    """
    _get_segment_or_404(db, segment_id, org_id)

    # Update last_synced_at to mark it as triggered
    db.execute(
        text("UPDATE graph_segments SET last_synced_at = NOW() WHERE id = :sid AND org_id = :org_id"),
        {"sid": segment_id, "org_id": org_id},
    )
    db.commit()

    # Trigger background sync for the org
    try:
        import threading
        from app.tasks.nightly_refresh import run_nightly_refresh
        t = threading.Thread(target=run_nightly_refresh, args=(org_id,), daemon=True)
        t.start()
        triggered = True
    except Exception as e:
        logger.warning(f"Segment sync background trigger failed: {e}")
        triggered = False

    return {
        "synced": True,
        "triggered": triggered,
        "segment_id": segment_id,
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


# ── PUT /v1/segment/assign/{contact_id} ──────────────────────────────────────

class ManualSegmentAssignRequest(BaseModel):
    segment_id: str


@router.put("/v1/segment/assign/{contact_id}")
def manual_assign_segment(
    contact_id: str,
    request: ManualSegmentAssignRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Manually assign a contact to a segment. Overrides auto-classification."""
    _get_segment_or_404(db, request.segment_id, org_id)

    # Verify contact belongs to org
    contact = db.execute(
        text("SELECT id FROM contacts WHERE id = :cid AND org_id = :org_id"),
        {"cid": contact_id, "org_id": org_id},
    ).fetchone()
    if not contact:
        raise HTTPException(status_code=404, detail={"error": "CONTACT_NOT_FOUND", "message": "Contact not found"})

    # Set segment_id + mark as manual (prevents auto-override)
    db.execute(
        text("""
            UPDATE contacts SET segment_id = :sid, segment_source = 'manual'
            WHERE id = :cid AND org_id = :org_id
        """),
        {"sid": request.segment_id, "cid": contact_id, "org_id": org_id},
    )

    # Also add to segment_members join table
    db.execute(
        text("""
            INSERT INTO segment_members (segment_id, contact_id, added_at)
            VALUES (:sid, :cid, NOW())
            ON CONFLICT (segment_id, contact_id) DO NOTHING
        """),
        {"sid": request.segment_id, "cid": contact_id, "org_id": org_id},
    )
    db.commit()

    return {"assigned": True, "contact_id": contact_id, "segment_id": request.segment_id, "source": "manual"}


# ── POST /v1/segments/backfill ───────────────────────────────────────────────

@router.post("/v1/segments/backfill")
def backfill_segments(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    Backfill auto-segment assignment for all contacts that don't have a segment yet.
    Useful after first enabling segments or adding the feature to an existing org.
    """
    from app.ingestion.segment_assigner import auto_assign_segment

    rows = db.execute(
        text("""
            SELECT id, entity_type FROM contacts
            WHERE org_id = :org_id
              AND (segment_id IS NULL OR segment_source IS NULL)
            LIMIT 500
        """),
        {"org_id": org_id},
    ).fetchall()

    assigned = 0
    for row in rows:
        entity_type = row[1] or "other"
        auto_assign_segment(db, org_id, str(row[0]), entity_type)
        assigned += 1

    db.commit()

    return {"backfilled": assigned, "org_id": org_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validated_sync_interval(hours: int | None, tier: str) -> int | None:
    """
    Validate sync_interval_hours against plan:
    - Trial: only None (manual)
    - Hustler: None or 6/12/18/24
    - Startup: None or 6/12/18/24 (real-time via webhook, cron as fallback)
    """
    if hours is None:
        return None
    if tier == "trial":
        return None  # Trial is manual-only; ignore any interval
    if hours not in (6, 12, 18, 24):
        return 6  # Default to 6h for invalid values
    return hours
