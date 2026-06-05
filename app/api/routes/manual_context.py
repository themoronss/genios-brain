"""Manual Context & File Upload API — Resources page (v2-native).

Replaces the v1 implementation that wrote to dropped tables (contacts,
interactions, commitments, activity_log). Now wraps each entry as a
MemoryItem and emits it through the same thin pipe the OAuth adapters
use — the worldmodel ingest subscriber extracts entities + facts and
upserts them into graph_nodes / facts. UI-only metadata lives in two
dedicated tables (manual_entries, resource_uploads).

Endpoints retain the v1 URLs so the dashboard works unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from core.api.deps import require_org_and_policy
from core.resources import (
    ManualEntryInput,
    UploadInput,
    create_manual_entry,
    create_upload,
    delete_manual_entry,
    delete_upload,
    list_manual_entries,
    list_uploads,
    retag_upload,
    update_manual_entry,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Auth helper — resolves (org_id, actor_email) from JWT / API key
# ─────────────────────────────────────────────────────────────────────────────


def _ctx(request: Request, session: Session):
    ctx = require_org_and_policy(
        request=request, session=session,
        authorization=request.headers.get("authorization"),
        x_dev_org=request.headers.get("X-Dev-Org"),
    )
    actor_email = request.headers.get("x-user-email") or "system"
    return ctx, actor_email


def _require_path_org_match(path_org: str, ctx_org: str) -> None:
    if path_org != ctx_org:
        raise HTTPException(status_code=403, detail="cross-org access denied")


# ─────────────────────────────────────────────────────────────────────────────
# Manual Context
# ─────────────────────────────────────────────────────────────────────────────


class ManualContextEntry(BaseModel):
    contact_name: str
    contact_email: Optional[str] = None
    context_type: str
    discussion: str
    commitments: Optional[str] = None
    interaction_date: Optional[str] = None


@router.post("/api/org/{org_id}/manual-context")
def add_manual_context(
    org_id: str,
    entry: ManualContextEntry,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx, actor = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    interaction_ts = None
    if entry.interaction_date:
        try:
            interaction_ts = datetime.fromisoformat(
                entry.interaction_date.replace("Z", "+00:00")
            )
        except ValueError:
            interaction_ts = None
    if interaction_ts is None:
        interaction_ts = datetime.now(timezone.utc)
    card = create_manual_entry(
        db,
        org_id=org_id,
        actor_email=actor,
        entry=ManualEntryInput(
            contact_name=entry.contact_name,
            contact_email=entry.contact_email,
            context_type=entry.context_type,
            discussion=entry.discussion,
            commitments=entry.commitments,
            interaction_date=interaction_ts,
        ),
        agent_id=ctx.get("agent_uuid"),
    )
    return {"entry": card}


@router.get("/api/org/{org_id}/manual-context")
def list_manual_context(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
):
    ctx, _ = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    return {"entries": list_manual_entries(db, org_id=org_id, limit=limit, offset=offset)}


@router.patch("/api/org/{org_id}/manual-context/{entry_id}")
def patch_manual_context(
    org_id: str,
    entry_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx, actor = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    updated = update_manual_entry(
        db, org_id=org_id, entry_id=entry_id, actor_email=actor, fields=body,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"entry": updated}


@router.delete("/api/org/{org_id}/manual-context/{entry_id}")
def remove_manual_context(
    org_id: str,
    entry_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx, actor = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    ok = delete_manual_entry(db, org_id=org_id, entry_id=entry_id, actor_email=actor)
    if not ok:
        raise HTTPException(status_code=404, detail="entry not found")
    return {"deleted": True}


# ─────────────────────────────────────────────────────────────────────────────
# File Uploads
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/api/org/{org_id}/upload")
async def upload_resource_file(
    org_id: str,
    request: Request,
    file: UploadFile = File(...),
    tag: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    ctx, actor = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    raw = await file.read()
    ext = (file.filename or "").rsplit(".", 1)[-1] if "." in (file.filename or "") else "bin"
    try:
        card = create_upload(
            db,
            org_id=org_id, actor_email=actor,
            upload=UploadInput(
                file_name=file.filename or "untitled",
                file_type=ext,
                raw=raw,
                tag=tag,
            ),
            agent_id=ctx.get("agent_uuid"),
        )
    except ValueError as e:
        raise HTTPException(status_code=413, detail=str(e)) from e
    return {"upload": card}


@router.get("/api/org/{org_id}/uploads")
def list_resource_uploads(
    org_id: str,
    request: Request,
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
):
    ctx, _ = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    return {"uploads": list_uploads(db, org_id=org_id, limit=limit, offset=offset)}


@router.patch("/api/org/{org_id}/uploads/{file_id}/tag")
def patch_upload_tag(
    org_id: str,
    file_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx, actor = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    tag = body.get("tag")
    if not tag:
        raise HTTPException(status_code=400, detail="tag required")
    updated = retag_upload(db, org_id=org_id, file_id=file_id, tag=tag, actor_email=actor)
    if updated is None:
        raise HTTPException(status_code=404, detail="upload not found")
    return {"upload": updated}


@router.delete("/api/org/{org_id}/uploads/{file_id}")
def remove_resource_upload(
    org_id: str,
    file_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    ctx, actor = _ctx(request, db)
    _require_path_org_match(org_id, ctx["org_id"])
    ok = delete_upload(db, org_id=org_id, file_id=file_id, actor_email=actor)
    if not ok:
        raise HTTPException(status_code=404, detail="upload not found")
    return {"deleted": True}
