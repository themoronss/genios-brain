"""Proactive mode API endpoints (v2-native).

GET    /v1/insights              — list fired insights for the org
POST   /v1/insights/:id/dismiss  — dismiss an insight (writes insight_feedback)
GET    /v1/webhooks              — list webhook subscriptions
POST   /v1/webhooks              — register a webhook endpoint
DELETE /v1/webhooks/:id          — remove a webhook
POST   /v1/scan                  — trigger a proactive scan (Hustler/Startup)

v1 tables (`insights`, `webhook_config`) were dropped in mig 0015.
Insights now live in v2 `proactive_insights` (g-i-4); feedback in
`insight_feedback`. Webhook subscriptions are stored in a small
JSONB column on `orgs.metadata` since the dedicated `webhook_config`
table was dropped.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Insights ─────────────────────────────────────────────────────────────────

@router.get("/v1/insights")
def list_insights(
    status: Optional[str] = Query(None, description="Filter: pending | delivered | dismissed (best-effort)"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """List proactive insights for the org from v2 `proactive_insights`."""
    rows = db.execute(
        text("""
            SELECT id, type, primary_entity, derivation_chain_jsonb,
                   scores_jsonb, delivery_route, created_at, signature_hash
            FROM proactive_insights
            WHERE org_id = :org_id
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"org_id": org_id, "limit": limit},
    ).fetchall()

    # Apply dismissed filter via insight_feedback (org-scoped).
    if status == "dismissed":
        dismissed_sigs = {
            r[0] for r in db.execute(
                text("""
                    SELECT signature_hash FROM insight_feedback
                    WHERE org_id = :oid AND action = 'dismissed'
                """),
                {"oid": org_id},
            ).fetchall()
        }
        rows = [r for r in rows if r.signature_hash in dismissed_sigs]
    elif status:
        # No 'pending'/'delivered' tracking in v2 — return all.
        pass
    else:
        dismissed_sigs = {
            r[0] for r in db.execute(
                text("""
                    SELECT signature_hash FROM insight_feedback
                    WHERE org_id = :oid AND action IN ('dismissed', 'never_show')
                """),
                {"oid": org_id},
            ).fetchall()
        }
        rows = [r for r in rows if r.signature_hash not in dismissed_sigs]

    def _shape(r):
        chain = r.derivation_chain_jsonb if isinstance(r.derivation_chain_jsonb, dict) else {}
        scores = r.scores_jsonb if isinstance(r.scores_jsonb, dict) else {}
        priority = "high" if r.delivery_route == "push" else (
            "medium" if r.delivery_route == "review" else "low"
        )
        return {
            "id": str(r.id),
            "type": r.type,
            "priority": priority,
            "category": chain.get("category") or "general",
            "title": chain.get("title") or f"{r.type}: {r.primary_entity}",
            "detail": chain.get("summary") or "",
            "contact_name": r.primary_entity,
            "contact_id": None,
            "memory_view": chain.get("memory_view"),
            "genios_view": chain.get("genios_view"),
            "delivery_status": "delivered",
            "source": "engine",
            "generated_at": r.created_at.isoformat() if r.created_at else None,
            "delivered_at": r.created_at.isoformat() if r.created_at else None,
            "scores": scores,
        }

    return {"insights": [_shape(r) for r in rows[:limit]], "count": min(len(rows), limit)}


@router.post("/v1/insights/{insight_id}/dismiss")
def dismiss_insight(
    insight_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    row = db.execute(
        text("SELECT signature_hash FROM proactive_insights WHERE id = :id AND org_id = :oid"),
        {"id": insight_id, "oid": org_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")
    db.execute(
        text("""
            INSERT INTO insight_feedback
                (id, org_id, user_id, signature_hash, action, created_at)
            VALUES (gen_random_uuid()::text, :oid, :uid, :sig, 'dismissed', NOW())
        """),
        {"oid": org_id, "uid": "__org__", "sig": row[0]},
    )
    db.commit()
    return {"dismissed": True, "id": insight_id}


# ── Webhooks ─────────────────────────────────────────────────────────────────
# v2 doesn't have a dedicated webhook_config table. We persist hooks in Redis
# under one key per org — small list (dashboards rarely have >5 hooks), and
# the dashboard tolerates loss across redis restarts (re-register UI exists).

def _hooks_key(org_id: str) -> str:
    return f"webhooks:{org_id}"


def _read_hooks(db: Session, org_id: str) -> list[dict]:
    try:
        from app.redis_client import redis_client as _r
        raw = _r.get(_hooks_key(org_id))
        return json.loads(raw) if raw else []
    except Exception:
        return []


def _write_hooks(db: Session, org_id: str, hooks: list[dict]) -> None:
    try:
        from app.redis_client import redis_client as _r
        _r.set(_hooks_key(org_id), json.dumps(hooks))
    except Exception as e:
        logger.warning(f"webhook persistence failed (org={org_id}): {e}")


@router.get("/v1/webhooks")
def list_webhooks(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    hooks = _read_hooks(db, org_id)
    return {
        "webhooks": [
            {
                "id": h.get("id"),
                "url": h.get("url"),
                "is_active": h.get("is_active", True),
                "events": h.get("events", []),
                "created_at": h.get("created_at"),
                "last_delivery_at": h.get("last_delivery_at"),
                "consecutive_failures": h.get("consecutive_failures", 0),
            }
            for h in hooks
        ],
        "count": len(hooks),
    }


class CreateWebhookRequest(BaseModel):
    url: str
    events: list[str] = ["insight"]


@router.post("/v1/webhooks", status_code=201)
def create_webhook(
    req: CreateWebhookRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    if not req.url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Webhook URL must use HTTPS")

    hooks = _read_hooks(db, org_id)
    if any(h.get("url") == req.url for h in hooks):
        raise HTTPException(status_code=409, detail="Webhook URL already registered")

    sec = secrets.token_urlsafe(32)
    import uuid as _uuid
    from datetime import datetime, timezone
    new_hook = {
        "id": str(_uuid.uuid4()),
        "url": req.url,
        "secret": sec,
        "events": req.events,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    hooks.append(new_hook)
    _write_hooks(db, org_id, hooks)
    return {
        "id": new_hook["id"],
        "url": req.url,
        "secret": sec,
        "events": req.events,
        "warning": "Store this secret securely — it will not be shown again.",
    }


@router.delete("/v1/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    hooks = _read_hooks(db, org_id)
    if not any(h.get("id") == webhook_id for h in hooks):
        raise HTTPException(status_code=404, detail="Webhook not found")
    _write_hooks(db, org_id, [h for h in hooks if h.get("id") != webhook_id])
    return {"deleted": True, "id": webhook_id}


# ── Manual scan trigger ──────────────────────────────────────────────────────

@router.post("/v1/scan")
def trigger_scan(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Trigger a proactive scan. Hustler/Startup only.

    v1 had a heavy `run_proactive_scan` task; v2 proactive insights fire
    continuously from the engine. The dashboard "scan now" button is now
    a hint — it returns the current insight count so the UI can refresh.
    """
    from app.plan_enforcer import get_org_plan
    plan = get_org_plan(db, org_id)
    if plan["tier"] not in ("startup", "hustler"):
        raise HTTPException(status_code=403, detail="Proactive scanning requires Hustler or Startup plan")

    n = db.execute(
        text("SELECT COUNT(*) FROM proactive_insights WHERE org_id = :oid"),
        {"oid": org_id},
    ).scalar() or 0
    return {"scan_result": {"insights_total": int(n), "note": "Proactive insights stream live from the engine."}}
