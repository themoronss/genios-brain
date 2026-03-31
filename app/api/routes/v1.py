"""
V1 canonical API endpoints per PDF spec.
  GET  /v1/sync                 — sync status for authenticated org
  GET  /v1/org                  — org profile, plan, usage, graph stats
  POST /v1/agent                — register agent ID (plan-limited)
  GET  /v1/agent/{agent_id}     — describe a registered agent
  GET  /v1/keys                 — list API keys
  POST /v1/keys                 — create additional API key (plan-limited)
  DELETE /v1/keys/{key_id}      — revoke an additional API key
  POST /v1/documents/upload     — upload PDF/DOCX/TXT for context extraction (Startup only)
"""

import hashlib
import json
import os
import secrets
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.plan_enforcer import get_org_plan

logger = logging.getLogger(__name__)

router = APIRouter()


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


# ── GET /v1/sync ───────────────────────────────────────────────────────────────

@router.get("/v1/sync")
def v1_sync_status(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Sync status for the authenticated org (API key auth)."""
    rows = db.execute(
        text("""
            SELECT COALESCE(account_email, 'default') AS account_email,
                   sync_status, last_synced_at, sync_total, sync_processed, sync_error
            FROM oauth_tokens WHERE org_id = :org_id
        """),
        {"org_id": org_id},
    ).fetchall()

    if not rows:
        return {"synced": False, "last_sync": None, "sync_status": "idle", "accounts": []}

    statuses = [r.sync_status or "idle" for r in rows]
    last_times = [r.last_synced_at for r in rows if r.last_synced_at]
    overall_last = max(last_times).isoformat() if last_times else None

    if "running" in statuses:
        overall = "running"
    elif "error" in statuses:
        overall = "error"
    elif all(s == "completed" for s in statuses):
        overall = "completed"
    else:
        overall = "idle"

    return {
        "synced": bool(last_times),
        "last_sync": overall_last,
        "sync_status": overall,
        "accounts": [
            {
                "account_email": r.account_email,
                "sync_status": r.sync_status or "idle",
                "last_sync": r.last_synced_at.isoformat() if r.last_synced_at else None,
                "sync_total": r.sync_total or 0,
                "sync_processed": r.sync_processed or 0,
                "sync_error": r.sync_error,
            }
            for r in rows
        ],
    }


# ── GET /v1/org ────────────────────────────────────────────────────────────────

@router.get("/v1/org")
def v1_org_info(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Org profile, plan info, usage stats, and graph counts (API key auth)."""
    row = db.execute(
        text("""
            SELECT name, email, plan_expires_at
            FROM orgs WHERE id = :org_id
        """),
        {"org_id": org_id},
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": "ORG_NOT_FOUND", "message": "Organisation not found"},
        )

    plan_info = get_org_plan(db, org_id)
    tier = plan_info["tier"]
    config = plan_info["config"]

    # Contact + cluster counts
    contact_count = db.execute(
        text("""
            SELECT COUNT(*) FROM contacts
            WHERE org_id = :org_id AND (is_archived IS FALSE OR is_archived IS NULL)
        """),
        {"org_id": org_id},
    ).scalar() or 0

    cluster_count = db.execute(
        text("""
            SELECT COUNT(DISTINCT community_id) FROM contacts
            WHERE org_id = :org_id AND community_id IS NOT NULL
        """),
        {"org_id": org_id},
    ).scalar() or 0

    # Period context usage
    period_reset_at = plan_info.get("period_reset_at")
    if period_reset_at:
        period_used = db.execute(
            text("""
                SELECT COUNT(*) FROM context_calls
                WHERE org_id = :org_id AND called_at >= :reset_at
                  AND (source = 'api' OR source IS NULL)
            """),
            {"org_id": org_id, "reset_at": period_reset_at},
        ).scalar() or 0
    else:
        period_used = plan_info["period_context_count"]

    expires_at = plan_info.get("expires_at")
    days_remaining = None
    if expires_at:
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        days_remaining = max(0, (expires_at - now).days)

    return {
        "org_id": org_id,
        "name": row.name,
        "email": row.email,
        "plan": {
            "tier": tier,
            "status": plan_info["plan_status"],
            "expires_at": expires_at.isoformat() if expires_at else None,
            "days_remaining": days_remaining,
            "period_context_limit": config["period_contexts"],
            "period_context_used": period_used,
            "daily_context_limit": config["daily_contexts"],
            "max_contacts": config["max_contacts"],
            "max_agent_ids": config["max_agent_ids"],
            "max_api_keys": config["max_api_keys"],
            "context_depth": config["context_depth"],
        },
        "graph": {
            "contact_count": contact_count,
            "cluster_count": cluster_count,
            "max_contacts": config["max_contacts"],
            "max_clusters": config["max_clusters"],
        },
    }


# ── POST /v1/agent  /  GET /v1/agent/{agent_id} ────────────────────────────────

class RegisterAgentRequest(BaseModel):
    agent_id: str
    name: str = None


@router.post("/v1/agent", status_code=201)
def register_agent(
    request: RegisterAgentRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Register an agent ID for this org. Enforces plan's max_agent_ids limit."""
    if not request.agent_id or len(request.agent_id.strip()) < 2:
        raise HTTPException(status_code=400, detail={"error": "INVALID_AGENT_ID", "message": "agent_id must be at least 2 characters"})

    agent_id = request.agent_id.strip()
    plan_info = get_org_plan(db, org_id)
    max_agents = plan_info["config"]["max_agent_ids"]

    # Already registered?
    existing = db.execute(
        text("SELECT id FROM registered_agents WHERE org_id = :org_id AND agent_id = :aid"),
        {"org_id": org_id, "aid": agent_id},
    ).fetchone()

    if existing:
        return {
            "registered": False,
            "already_exists": True,
            "agent_id": agent_id,
            "message": "Agent ID already registered",
        }

    # Count current registrations
    count = db.execute(
        text("SELECT COUNT(*) FROM registered_agents WHERE org_id = :org_id"),
        {"org_id": org_id},
    ).scalar() or 0

    if count >= max_agents:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PLAN_LIMIT",
                "message": f"Max {max_agents} agent ID(s) allowed on {plan_info['tier']} plan.",
                "current_count": count,
                "max_allowed": max_agents,
                "upgrade_required": True,
            },
        )

    db.execute(
        text("""
            INSERT INTO registered_agents (org_id, agent_id, name, created_at)
            VALUES (:org_id, :aid, :name, NOW())
        """),
        {"org_id": org_id, "aid": agent_id, "name": request.name},
    )
    db.commit()

    return {
        "registered": True,
        "agent_id": agent_id,
        "name": request.name,
        "org_id": org_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/v1/agent/{agent_id}")
def describe_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Get registration info for a specific agent."""
    row = db.execute(
        text("""
            SELECT agent_id, name, created_at FROM registered_agents
            WHERE org_id = :org_id AND agent_id = :aid
        """),
        {"org_id": org_id, "aid": agent_id},
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": "AGENT_NOT_FOUND", "message": f"Agent '{agent_id}' is not registered for this org"},
        )

    return {
        "agent_id": row.agent_id,
        "name": row.name,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "org_id": org_id,
    }


# ── GET/POST/DELETE /v1/keys ───────────────────────────────────────────────────

@router.get("/v1/keys")
def list_keys(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """List all API keys for this org. Full key is never returned after creation."""
    plan_info = get_org_plan(db, org_id)
    max_keys = plan_info["config"]["max_api_keys"]

    # Primary key (orgs table)
    primary = db.execute(
        text("SELECT api_key, created_at FROM orgs WHERE id = :org_id"),
        {"org_id": org_id},
    ).fetchone()

    keys = []
    if primary and primary.api_key:
        keys.append({
            "id": "primary",
            "prefix": primary.api_key[:16] + "...",
            "name": "Primary Key",
            "created_at": primary.created_at.isoformat() if primary.created_at else None,
            "last_used_at": None,
            "is_active": True,
        })

    # Additional keys (api_keys table)
    rows = db.execute(
        text("""
            SELECT id, key_prefix, name, created_at, last_used_at
            FROM api_keys WHERE org_id = :org_id AND is_active = TRUE
            ORDER BY created_at ASC
        """),
        {"org_id": org_id},
    ).fetchall()

    for r in rows:
        keys.append({
            "id": str(r.id),
            "prefix": r.key_prefix,
            "name": r.name or "API Key",
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
            "is_active": True,
        })

    return {"keys": keys, "count": len(keys), "max_allowed": max_keys}


class CreateKeyRequest(BaseModel):
    name: str = None


@router.post("/v1/keys", status_code=201)
def create_key(
    request: CreateKeyRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Create an additional API key. Enforces plan's max_api_keys limit."""
    plan_info = get_org_plan(db, org_id)
    max_keys = plan_info["config"]["max_api_keys"]
    tier = plan_info["tier"]

    # Primary key counts as 1
    has_primary = db.execute(
        text("SELECT 1 FROM orgs WHERE id = :org_id AND api_key IS NOT NULL"),
        {"org_id": org_id},
    ).fetchone()

    additional_count = db.execute(
        text("SELECT COUNT(*) FROM api_keys WHERE org_id = :org_id AND is_active = TRUE"),
        {"org_id": org_id},
    ).scalar() or 0

    total = (1 if has_primary else 0) + additional_count

    if total >= max_keys:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "PLAN_LIMIT",
                "message": f"Max {max_keys} API key(s) allowed on {tier} plan.",
                "current_count": total,
                "max_allowed": max_keys,
                "upgrade_required": tier != "startup",
            },
        )

    raw_key = f"gn_live_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    prefix = raw_key[:16] + "..."

    result = db.execute(
        text("""
            INSERT INTO api_keys (org_id, key_hash, key_prefix, name, created_at, is_active)
            VALUES (:org_id, :key_hash, :prefix, :name, NOW(), TRUE)
            RETURNING id
        """),
        {
            "org_id": org_id,
            "key_hash": key_hash,
            "prefix": prefix,
            "name": request.name or "API Key",
        },
    )
    key_id = result.fetchone()[0]
    db.commit()

    return {
        "id": str(key_id),
        "key": raw_key,
        "prefix": prefix,
        "name": request.name or "API Key",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "warning": "Store this key securely — it will not be shown again.",
    }


@router.delete("/v1/keys/{key_id}")
def revoke_key(
    key_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Revoke an additional API key by ID. Cannot revoke the primary key."""
    if key_id == "primary":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "CANNOT_REVOKE_PRIMARY",
                "message": "Cannot revoke the primary key. Use /api/org/{id}/apikey/regenerate instead.",
            },
        )

    result = db.execute(
        text("""
            UPDATE api_keys SET is_active = FALSE
            WHERE id = :key_id AND org_id = :org_id AND is_active = TRUE
            RETURNING id
        """),
        {"key_id": key_id, "org_id": org_id},
    ).fetchone()

    if not result:
        raise HTTPException(
            status_code=404,
            detail={"error": "KEY_NOT_FOUND", "message": "API key not found or already revoked"},
        )

    db.commit()
    return {"revoked": True, "id": key_id}


# ── POST /v1/documents/upload ─────────────────────────────────────────────────

_UPLOAD_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "uploads",
)
os.makedirs(_UPLOAD_DIR, exist_ok=True)
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_ALLOWED_EXT = {".pdf", ".docx", ".txt"}


@router.post("/v1/documents/upload")
async def v1_document_upload(
    file: UploadFile = File(...),
    tag: str = Form(default="other"),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    Upload a document (PDF, DOCX, TXT, max 10 MB) for context extraction.
    Startup plan only. Uses API key auth.
    """
    from app.plan_enforcer import require_integration

    require_integration(db, org_id, "documents")

    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: pdf, docx, txt",
        )

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum size is 10 MB.")

    file_id = str(uuid.uuid4())
    file_path = os.path.join(_UPLOAD_DIR, f"{file_id}{file_ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # Log upload
    db.execute(
        text("""
            INSERT INTO activity_log (id, org_id, event_type, event_data, created_at)
            VALUES (:id, :org_id, 'file_uploaded', :data, NOW())
        """),
        {
            "id": file_id,
            "org_id": org_id,
            "data": json.dumps({
                "filename": file.filename,
                "tag": tag,
                "size_bytes": len(content),
                "file_ext": file_ext,
                "source": "v1_api",
            }),
        },
    )
    db.commit()

    # Extract text
    text_content = ""
    if file_ext == ".txt":
        text_content = content.decode("utf-8", errors="ignore")
    elif file_ext == ".pdf":
        try:
            import fitz
            doc = fitz.open(file_path)
            text_content = "\n".join(page.get_text() for page in doc)
            doc.close()
        except ImportError:
            pass
    elif file_ext == ".docx":
        try:
            import docx
            doc = docx.Document(file_path)
            text_content = "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            pass

    # Entity extraction
    entities_found = 0
    if text_content and len(text_content) > 20:
        try:
            from app.ingestion.entity_extractor import extract_email_intelligence
            intelligence = extract_email_intelligence(text_content[:3000], f"Document: {file.filename}")
            for entity_info in intelligence.get("entities", []):
                entity_name = entity_info if isinstance(entity_info, str) else entity_info.get("name", "")
                if not entity_name:
                    continue
                existing = db.execute(
                    text("SELECT id FROM contacts WHERE org_id = :org_id AND LOWER(name) = LOWER(:name) LIMIT 1"),
                    {"org_id": org_id, "name": entity_name},
                ).fetchone()
                if existing:
                    db.execute(
                        text("""
                            INSERT INTO interactions (id, org_id, contact_id, direction, subject, summary, sentiment, interaction_at, weight_score, signal_score)
                            VALUES (:id, :org_id, :cid, 'inbound', :subj, :summary, 0.5, NOW(), 0.7, 0.5)
                        """),
                        {
                            "id": str(uuid.uuid4()),
                            "org_id": org_id,
                            "cid": str(existing[0]),
                            "subj": f"Upload: {file.filename}",
                            "summary": intelligence.get("summary", text_content[:200]),
                        },
                    )
                    entities_found += 1
            db.commit()
        except Exception as e:
            logger.warning(f"v1 document entity extraction failed: {e}")

    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "file_type": file_ext.lstrip("."),
        "tag": tag,
        "size_bytes": len(content),
        "text_extracted": len(text_content) > 0,
        "entities_found": entities_found,
        "status": "indexed" if text_content else "queued",
    }
