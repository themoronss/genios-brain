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
    # HTTPS is required in prod. In dev we also allow http://localhost and
    # http://127.0.0.1 so the founder/customer can point a local Hermes /
    # OpenClaw / n8n at the brain without spinning up ngrok every time.
    is_localhost = req.url.startswith(("http://localhost", "http://127.0.0.1"))
    if not (req.url.startswith("https://") or is_localhost):
        raise HTTPException(
            status_code=400,
            detail="Webhook URL must use HTTPS (or http://localhost in dev)",
        )

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


@router.post("/v1/webhooks/{webhook_id}/test")
def test_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Fire a sample, signed insight payload at a registered webhook.

    Built so a Trial customer can verify their Hermes / OpenClaw / n8n
    receiver is wired up correctly without waiting for the engine to
    actually emit an insight. The payload shape matches the real
    `event=insight` delivery in webhook_delivery.py.
    """
    import hashlib
    import hmac
    import uuid as _uuid
    from datetime import datetime, timezone

    import requests

    hooks = _read_hooks(db, org_id)
    hook = next((h for h in hooks if h.get("id") == webhook_id), None)
    if not hook:
        raise HTTPException(status_code=404, detail="Webhook not found")

    payload = {
        "event": "insight",
        "insight_id": str(_uuid.uuid4()),
        "org_id": org_id,
        "type": "test",
        "priority": "high",
        "category": "engagement_risk",
        "title": "Test insight — verify your receiver is wired correctly",
        "contact_name": "Test Contact",
        "contact_id": None,
        "memory_view": "This is a sample memory_view payload from GeniOS.",
        "genios_view": "This is a sample genios_view analysis.",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fact": "Sample fact (alias for memory_view).",
        "analysis": "Sample analysis (alias for genios_view).",
    }
    body = json.dumps(payload, default=str)
    secret = hook.get("secret", "")
    digest_hex = hmac.new(
        secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    try:
        resp = requests.post(
            hook["url"], data=body,
            headers={
                "Content-Type": "application/json",
                # GeniOS-native header (legacy receivers + our own adapters).
                "X-Genios-Signature": "sha256=" + digest_hex,
                "X-Genios-Event": "insight",
                # Hermes routes events by reading X-GitHub-Event; send it so
                # subscriptions filtered to events=["insight"] actually match.
                "X-GitHub-Event": "insight",
                # GitHub-style — Hermes, n8n's HMAC node, and most generic
                # webhook receivers accept this format.
                "X-Hub-Signature-256": "sha256=" + digest_hex,
                # Plain-hex generic header for receivers that don't expect
                # the `sha256=` prefix (Hermes "generic" path).
                "X-Webhook-Signature": digest_hex,
            },
            timeout=10,
        )
        return {
            "ok": 200 <= resp.status_code < 300,
            "status_code": resp.status_code,
            "response_body": resp.text[:500],
            "url": hook["url"],
        }
    except requests.RequestException as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach webhook URL: {str(e)[:200]}",
        )


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

_RULE_PRIORITY = {
    "ar_gentle_first_nudge": "low",
    "ar_firm_second_reminder": "medium",
    "ar_phone_call_escalation": "high",
    "ar_large_invoice_preemptive": "medium",
    "ar_repeat_late_payer_flag": "high",
}

_RULE_TITLE = {
    "ar_gentle_first_nudge": "Polite reminder due",
    "ar_firm_second_reminder": "Firm reminder needed",
    "ar_phone_call_escalation": "Escalate — phone call needed",
    "ar_large_invoice_preemptive": "Large invoice due soon — courtesy check",
    "ar_repeat_late_payer_flag": "Client paid late repeatedly — review terms",
}


def _coerce_fact_value(predicate: str, raw: str):
    """Cast a facts.object string back to the type rules expect."""
    if predicate in (
        "days_past_due",
        "amount_inr",
        "last_reminder_age_days",
        "client_late_count_90d",
    ):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
    if predicate == "is_vip_client":
        return str(raw).lower() in ("true", "1", "yes")
    return raw


def _load_module_chainer(module_id: str):
    """Locate the module directory and return a loaded ForwardChainer."""
    from pathlib import Path
    from core.modules_framework.loader import load_module_package
    from core.reasoning.rule_engine import ForwardChainer

    repo_root = Path(__file__).resolve().parents[3]  # genios-brain root
    module_path = repo_root / "modules" / module_id
    if not module_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Module {module_id} not installed",
        )
    pkg = load_module_package(module_path)
    return ForwardChainer(pkg.ruleset)


def _post_signed(hook: dict, payload: dict) -> dict:
    """Sign + POST a webhook payload using the same multi-format headers as
    the test endpoint. Returns delivery summary for the response."""
    import hashlib
    import hmac
    import requests

    body = json.dumps(payload, default=str)
    secret = hook.get("secret", "")
    digest_hex = hmac.new(
        secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-Genios-Signature": "sha256=" + digest_hex,
        "X-Genios-Event": "insight",
        "X-GitHub-Event": "insight",  # Hermes routes on this
        "X-Hub-Signature-256": "sha256=" + digest_hex,
        "X-Webhook-Signature": digest_hex,
    }
    try:
        resp = requests.post(hook["url"], data=body, headers=headers, timeout=10)
        return {
            "webhook_id": hook["id"],
            "status_code": resp.status_code,
            "ok": 200 <= resp.status_code < 300,
            "response_snippet": resp.text[:200],
        }
    except requests.RequestException as e:
        return {
            "webhook_id": hook["id"],
            "status_code": 0,
            "ok": False,
            "response_snippet": f"network: {str(e)[:200]}",
        }


@router.post("/v1/scan")
def trigger_scan(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Real scan: load the org's facts, run a module's rules, fire each
    insight to every registered webhook.

    Module is hardcoded to `ar_collection` for the AR demo. A real install
    would loop over all installed modules (or pick based on the org's
    business_context). This route exists so a customer can manually retrigger
    after an upload instead of waiting for the periodic engine pass.
    """
    chainer = _load_module_chainer("ar_collection")

    # Group facts by subject (invoice id) — coerce types so numeric rule
    # comparisons (days_past_due > 7) actually work against DB strings.
    rows = db.execute(
        text(
            """
            SELECT subject, predicate, object
            FROM facts
            WHERE org_id = :org
              AND source_item_id LIKE 'upload:%'
            ORDER BY subject, predicate
            """
        ),
        {"org": org_id},
    ).fetchall()

    invoices: dict[str, dict] = {}
    for r in rows:
        invoices.setdefault(r.subject, {})[r.predicate] = _coerce_fact_value(
            r.predicate, r.object
        )

    if not invoices:
        return {
            "scan_result": {
                "insights_fired": 0,
                "webhooks_called": 0,
                "note": "No facts uploaded yet — drop a CSV in Resources first.",
            }
        }

    # Resolve client name per invoice from the graph (faster than re-reading
    # all rows). Cache so we hit DB once per invoice not per firing.
    client_name_for_invoice: dict[str, str] = {}

    def _client_name(invoice_id: str) -> str:
        if invoice_id in client_name_for_invoice:
            return client_name_for_invoice[invoice_id]
        row = db.execute(
            text(
                """
                SELECT n.canonical_name
                FROM graph_nodes n
                JOIN graph_edges e ON e.to_node = n.id
                JOIN graph_nodes i ON i.id = e.from_node
                WHERE i.org_id = :org
                  AND i.canonical_name = :inv
                  AND n.type = 'client'
                LIMIT 1
                """
            ),
            {"org": org_id, "inv": invoice_id},
        ).fetchone()
        client_name_for_invoice[invoice_id] = row[0] if row else "Unknown client"
        return client_name_for_invoice[invoice_id]

    hooks = _read_hooks(db, org_id)
    active_hooks = [h for h in hooks if h.get("is_active", True)]

    firings: list[dict] = []
    webhook_calls: list[dict] = []
    import uuid as _uuid

    for invoice_id, facts in invoices.items():
        result = chainer.run(facts)
        if not result.proof.steps:
            continue
        client_name = _client_name(invoice_id)

        for step in result.proof.steps:
            priority = _RULE_PRIORITY.get(step.rule_id, "medium")
            title = _RULE_TITLE.get(step.rule_id, step.conclusion.replace("_", " ").title())

            # Concise human-readable views — these become the {fact} /
            # {analysis} variables the Hermes prompt template expands.
            memory_view = (
                f"Invoice {invoice_id} for {client_name}: "
                f"₹{facts.get('amount_inr', 0):,} · "
                f"{facts.get('days_past_due', 'n/a')} days past due · "
                f"status={facts.get('payment_status', 'n/a')} · "
                f"reminder_age={facts.get('last_reminder_age_days', -1)} · "
                f"client_late_count_90d={facts.get('client_late_count_90d', 0)} · "
                f"vip={facts.get('is_vip_client', False)}"
            )
            genios_view = step.reason or step.conclusion

            payload = {
                "event": "insight",
                "insight_id": str(_uuid.uuid4()),
                "org_id": org_id,
                "type": "ar_collection",
                "rule_id": step.rule_id,
                "invoice_id": invoice_id,
                "priority": priority,
                "category": step.conclusion,
                "title": title,
                "contact_name": client_name,
                "contact_id": None,
                "memory_view": memory_view,
                "genios_view": genios_view,
                "fact": memory_view,
                "analysis": genios_view,
                "generated_at": __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).isoformat(),
            }

            for hook in active_hooks:
                webhook_calls.append(_post_signed(hook, payload))

            firings.append({
                "invoice_id": invoice_id,
                "client_name": client_name,
                "rule_id": step.rule_id,
                "priority": priority,
                "title": title,
            })

    return {
        "scan_result": {
            "module_id": "ar_collection",
            "invoices_evaluated": len(invoices),
            "insights_fired": len(firings),
            "webhooks_called": len(webhook_calls),
            "webhook_success": sum(1 for w in webhook_calls if w.get("ok")),
            "firings": firings,
            "webhook_responses": webhook_calls,
        }
    }
