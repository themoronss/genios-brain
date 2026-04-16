"""
V1 canonical API endpoints per PDF spec.
  GET  /v1/sync                 — sync status for authenticated org
  GET  /v1/org                  — org profile, plan, usage, graph stats
  GET  /v1/contacts             — search / list contacts (partial name, email, company)
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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from app.plan_enforcer import get_org_plan
from app.tunables import (
    BROADCAST_MIN_ONEWAY_COUNT,
    broadcast_local_sql_regex,
    broadcast_domain_sql_regex,
)

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


# ── GET /v1/contacts ──────────────────────────────────────────────────────────

@router.get("/v1/contacts")
def v1_search_contacts(
    q: Optional[str] = Query(None, description="Partial name, email, or company. Empty = recent contacts."),
    stage: Optional[str] = Query(None, description="Filter by relationship_stage (ACTIVE, WARM, COLD, etc)."),
    needs_attention: bool = Query(False, description="Shortcut: only contacts with stage=NEEDS_ATTENTION."),
    recent_days: Optional[int] = Query(None, ge=1, le=365, description="Only contacts with last_interaction within N days."),
    silent_days: Optional[int] = Query(None, ge=1, le=365, description="Only contacts we've NOT interacted with in >= N days (re-engagement list)."),
    overdue: bool = Query(False, description="Only contacts with at least one OVERDUE commitment."),
    exclude_broadcast: bool = Query(True, description="Exclude one-way/marketing senders (noreply, info@, etc). Default true."),
    has_anomaly: bool = Query(False, description="Only contacts with active anomalies (L5 detection)."),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """
    Search or list contacts in the org's graph.

    Agents use this to resolve "Alice at Acme" or "Ashish from HDFC" into
    a canonical contact before calling /v1/context. Also supports
    "who needs attention" queries for dashboard-style prompts.

    Ranking: exact-email > exact-name > fuzzy match > recent interaction.
    """
    where = ["c.org_id = :org_id", "(c.is_archived IS FALSE OR c.is_archived IS NULL)"]
    params: dict = {"org_id": org_id, "limit": limit}

    if q:
        q_clean = q.strip()
        params["q_exact"] = q_clean.lower()
        params["q_like"] = f"%{q_clean.lower()}%"
        where.append(
            "(LOWER(c.email) = :q_exact "
            "OR LOWER(c.name) = :q_exact "
            "OR LOWER(c.email) LIKE :q_like "
            "OR LOWER(c.name) LIKE :q_like "
            "OR LOWER(COALESCE(c.company, '')) LIKE :q_like)"
        )

    if needs_attention:
        where.append("c.relationship_stage = 'NEEDS_ATTENTION'")
    elif stage:
        params["stage"] = stage.upper()
        where.append("UPPER(c.relationship_stage) = :stage")

    if recent_days is not None:
        params["recent_days"] = recent_days
        where.append("c.last_interaction_at >= NOW() - (:recent_days || ' days')::interval")

    if silent_days is not None:
        params["silent_days"] = silent_days
        where.append(
            "(c.last_interaction_at IS NULL "
            "OR c.last_interaction_at < NOW() - (:silent_days || ' days')::interval)"
        )

    if overdue:
        where.append(
            "EXISTS (SELECT 1 FROM commitments cm WHERE cm.contact_id = c.id "
            "AND cm.status = 'OPEN' AND cm.due_date IS NOT NULL AND cm.due_date < NOW())"
        )

    # ── Broadcast detection — Phase 3.4: prefer DB classification column,
    # fall back to regex for contacts not yet classified.
    params["broadcast_local_re"] = broadcast_local_sql_regex()
    params["broadcast_domain_re"] = broadcast_domain_sql_regex()
    params["broadcast_min_count"] = BROADCAST_MIN_ONEWAY_COUNT

    broadcast_sql = """
        (
          -- Prefer persisted classification (from header parse or LLM)
          COALESCE(c.classification_override, c.classification) IN ('newsletter', 'bot', 'transactional')
          -- Fall back to regex for unclassified contacts
          OR (
            COALESCE(c.classification_override, c.classification, 'unknown') = 'unknown'
            AND (
              LOWER(COALESCE(c.email, '')) ~ :broadcast_local_re
              OR LOWER(COALESCE(c.email, '')) ~ :broadcast_domain_re
              OR (
                c.is_bidirectional IS NOT TRUE
                AND COALESCE(c.interaction_count, 0) >= :broadcast_min_count
              )
            )
          )
        )
    """

    if exclude_broadcast:
        where.append(f"NOT {broadcast_sql}")

    if has_anomaly:
        where.append(
            "EXISTS (SELECT 1 FROM contact_anomalies ca "
            "WHERE ca.contact_id = c.id AND ca.status = 'active')"
        )

    select_cols = f"""
        c.id, c.name, c.email, c.company,
        c.relationship_stage, c.sentiment_trend,
        c.last_interaction_at, c.interaction_count,
        c.context_score, c.confidence_score,
        COALESCE(c.classification_override, c.classification, 'unknown') AS classification,
        {broadcast_sql} AS is_broadcast,
        (SELECT COUNT(*) FROM commitments cm
            WHERE cm.contact_id = c.id AND cm.status = 'OPEN') AS open_commitments
    """

    sql = f"""
        SELECT {select_cols}
        FROM contacts c
        WHERE {' AND '.join(where)}
        ORDER BY
            -- exact email match first
            CASE WHEN LOWER(c.email) = :q_exact THEN 0
                 WHEN LOWER(c.name) = :q_exact THEN 1
                 ELSE 2 END,
            c.last_interaction_at DESC NULLS LAST,
            c.interaction_count DESC NULLS LAST
        LIMIT :limit
    """ if q else f"""
        SELECT {select_cols}
        FROM contacts c
        WHERE {' AND '.join(where)}
        ORDER BY c.last_interaction_at DESC NULLS LAST
        LIMIT :limit
    """

    rows = db.execute(text(sql), params).fetchall()

    contacts = []
    for r in rows:
        last_at = r.last_interaction_at
        days_ago = None
        if last_at:
            if hasattr(last_at, "tzinfo") and last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            days_ago = (datetime.now(timezone.utc) - last_at).days
        contacts.append({
            "id": str(r.id),
            "name": r.name,
            "email": r.email,
            "company": r.company,
            "relationship_stage": r.relationship_stage,
            "sentiment_trend": r.sentiment_trend,
            "last_interaction_days_ago": days_ago,
            "interaction_count": r.interaction_count or 0,
            "open_commitments": r.open_commitments or 0,
            "context_score": round(float(r.context_score or 0), 3),
            "classification": r.classification or "unknown",
            "is_broadcast": bool(r.is_broadcast),
        })

    return {"contacts": contacts, "count": len(contacts), "query": q or None}


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
        from app.core.analytics import capture
        capture(org_id, "plan_limit_hit", {"feature": "agents", "plan": plan_info["tier"]})
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

    from app.core.analytics import capture
    capture(org_id, "agent_registered", {"agent_id": agent_id})

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
        from app.core.analytics import capture
        capture(org_id, "plan_limit_hit", {"feature": "api_keys", "plan": tier})
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

    from app.core.analytics import capture
    capture(org_id, "api_key_created", {})

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

    # Entity enrichment + Precedent Graph embedding
    # Upgraded: documents now CREATE contacts (not just enrich existing ones)
    # and add lightweight 'document_mention' interactions so the graph builds.
    entities_found = 0
    contacts_created = 0
    chunks_stored = 0
    if text_content and len(text_content) > 20:
        # 1. Entity extraction — create OR enrich contacts + add document interaction
        try:
            from app.ingestion.entity_extractor import extract_email_intelligence
            from app.ingestion.graph_builder import upsert_contact

            intelligence = extract_email_intelligence(text_content[:3000], f"Document: {file.filename}")
            doc_topics = intelligence.get("topics", [])
            doc_summary = intelligence.get("summary", f"Mentioned in document: {file.filename}")

            for entity_info in intelligence.get("entities", []):
                entity_name = entity_info if isinstance(entity_info, str) else entity_info.get("name", "")
                if not entity_name or len(entity_name) < 2:
                    continue

                # Check if contact exists
                existing = db.execute(
                    text("SELECT id FROM contacts WHERE org_id = :org_id AND LOWER(name) = LOWER(:name) LIMIT 1"),
                    {"org_id": org_id, "name": entity_name},
                ).fetchone()

                if existing:
                    contact_id = str(existing[0])
                    # Enrich existing: add 'docs' source + merge topics
                    db.execute(
                        text("""
                            UPDATE contacts SET
                                sources = array_cat(
                                    COALESCE(sources, '{}'),
                                    CASE WHEN NOT ('docs' = ANY(COALESCE(sources, '{}'))) THEN ARRAY['docs'] ELSE '{}' END
                                ),
                                topics_aggregate = (
                                    SELECT ARRAY(SELECT DISTINCT unnest(
                                        array_cat(COALESCE(topics_aggregate, '{}'), :topics)
                                    ) LIMIT 10)
                                )
                            WHERE id = :cid AND org_id = :org_id
                        """),
                        {"cid": contact_id, "org_id": org_id, "topics": doc_topics[:5]},
                    )
                    entities_found += 1
                else:
                    # CREATE new contact from document mention
                    contact_id = upsert_contact(
                        db, org_id,
                        email=None,  # no email from document — name only
                        name=entity_name,
                        entity_type=intelligence.get("contact_role"),
                    )
                    if contact_id:
                        # Add topics + source
                        db.execute(
                            text("""
                                UPDATE contacts SET
                                    sources = ARRAY['docs'],
                                    topics_aggregate = :topics
                                WHERE id = :cid AND org_id = :org_id
                            """),
                            {"cid": str(contact_id), "org_id": org_id, "topics": doc_topics[:5]},
                        )
                        contacts_created += 1
                        entities_found += 1

                # Create a lightweight interaction so the contact shows in the graph
                if contact_id:
                    try:
                        interaction_id = str(uuid.uuid4())
                        db.execute(
                            text("""
                                INSERT INTO interactions (
                                    id, org_id, contact_id, direction, subject,
                                    summary, interaction_at, sentiment, intent,
                                    source, topics, interaction_type
                                )
                                VALUES (
                                    :id, :org_id, :cid, 'inbound', :subject,
                                    :summary, NOW(), 0.0, 'reference',
                                    'document', :topics, 'document_mention'
                                )
                                ON CONFLICT DO NOTHING
                            """),
                            {
                                "id": interaction_id,
                                "org_id": org_id,
                                "cid": str(contact_id),
                                "subject": f"Document: {file.filename}",
                                "summary": f"Mentioned in {file.filename}: {doc_summary[:200]}",
                                "topics": doc_topics[:5],
                            },
                        )
                    except Exception:
                        pass  # duplicate or constraint — safe to skip

            db.commit()
        except Exception as e:
            logger.warning(f"v1 document entity extraction failed: {e}")
            try:
                db.rollback()
            except Exception:
                pass

        # 2. Precedent Graph — chunk and embed document for vector search
        try:
            from app.context.precedent_search import store_document_chunks
            # Simple chunking: split by paragraphs, target ~400-600 tokens
            paragraphs = [p.strip() for p in text_content.split("\n\n") if len(p.strip()) > 50]
            chunks = []
            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) > 2000:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = para
                else:
                    current_chunk = current_chunk + "\n\n" + para if current_chunk else para
            if current_chunk:
                chunks.append(current_chunk)

            chunks_stored = store_document_chunks(
                db, org_id, file_id, file.filename or "Untitled",
                chunks, doc_type="upload", metadata={"tag": tag},
            )
        except Exception as e:
            logger.warning(f"v1 document chunk embedding failed: {e}")

    from app.core.analytics import capture
    capture(org_id, "document_uploaded", {
        "file_type": file_ext.lstrip("."),
        "entities_found": entities_found,
        "chunks_stored": chunks_stored,
        "size_bytes": len(content),
    })

    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "file_type": file_ext.lstrip("."),
        "tag": tag,
        "size_bytes": len(content),
        "text_extracted": len(text_content) > 0,
        "entities_found": entities_found,
        "chunks_stored": chunks_stored,
        "status": "indexed" if text_content else "queued",
    }
