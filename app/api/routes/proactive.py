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
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db, verify_api_key
from core.delivery.bands import to_band

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
        scores = dict(r.scores_jsonb) if isinstance(r.scores_jsonb, dict) else {}
        # Customer-facing: present the stored raw confidence as a qualitative
        # band (§5 Gate 1). The raw float remains in the proactive_insights row.
        if "confidence" in scores:
            scores["confidence"] = to_band(scores.get("confidence")).value
        # The pipeline writes the human headline + why into scores_jsonb
        # (pipeline.py:821). Older/other producers may put them in the
        # derivation_chain. Read scores first, then chain, then a generic
        # fallback — otherwise the dashboard shows bare "risk: <entity>".
        priority = scores.get("priority") or (
            "high" if r.delivery_route == "push" else (
                "medium" if r.delivery_route == "review" else "low"
            )
        )
        return {
            "id": str(r.id),
            "type": r.type,
            "priority": priority,
            "category": scores.get("category") or chain.get("category") or "general",
            "title": scores.get("title") or chain.get("title") or f"{r.type}: {r.primary_entity}",
            "detail": scores.get("memory_view") or chain.get("summary") or "",
            "contact_name": r.primary_entity,
            "contact_id": None,
            "memory_view": scores.get("memory_view") or chain.get("memory_view"),
            "genios_view": scores.get("genios_view") or chain.get("genios_view"),
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

class OutcomeRequest(BaseModel):
    outcome: str = Field(
        ...,
        description="paid | ignored | dismissed | escalated — what actually happened",
    )
    value_amount: Optional[float] = Field(
        default=None,
        description="If a positive outcome (paid), how much value was recovered (in INR for AR).",
    )
    currency: str = Field(
        default="INR",
        description="ISO currency code for value_amount",
    )
    evidence: Optional[str] = Field(
        default=None,
        description="Free-form text the founder / Hermes can leave to explain HOW we know — e.g. 'paid via NEFT 14 Jun'",
    )


_VALID_OUTCOMES = {"paid", "ignored", "dismissed", "escalated", "acted"}


@router.post("/v1/insights/{insight_id}/outcome", status_code=201)
def record_insight_outcome(
    insight_id: str,
    body: OutcomeRequest,
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Persist the business outcome of an insight — paid, ignored, dismissed.

    Two callers in practice:
      1. The customer's dashboard ("mark paid" button on an AR insight).
      2. Hermes / OpenClaw / a custom adapter, after it ran the suggested
         action and learned the result (e.g. it sent the email, then a
         downstream Stripe webhook said the invoice was paid).

    Writes to `feedback_actions` so the same row also feeds calibration
    (Phase 4). The matching action_ledger rows have their outcome_detail
    appended so anyone reading the delivery audit trail sees the
    eventual business outcome alongside the HTTP success.

    Plan alignment: g-i-7 (outcome attribution on delivery), g-i-8
    (feedback for calibration), g-i-9 (per-user feedback ledger).
    """
    if body.outcome not in _VALID_OUTCOMES:
        raise HTTPException(
            status_code=400,
            detail=f"outcome must be one of {sorted(_VALID_OUTCOMES)}",
        )

    # 1) Verify this insight belongs to the calling org
    row = db.execute(
        text("SELECT id, signature_hash FROM proactive_insights WHERE id = :id AND org_id = :oid"),
        {"id": insight_id, "oid": org_id},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Insight not found")

    # 2) Record feedback — uses the existing feedback_actions shape so
    # downstream calibration / threshold-tuner can read all outcomes
    # from one place.
    import uuid as _uuid
    feedback_id = str(_uuid.uuid4())
    edit_payload = {
        "value_amount": body.value_amount,
        "currency": body.currency,
        "evidence": body.evidence,
        "outcome": body.outcome,
    }
    db.execute(
        text(
            """
            INSERT INTO feedback_actions
                (id, org_id, user_id, decision_id, insight_id, action,
                 edit_diff_jsonb, timestamp)
            VALUES
                (:id, :org_id, :user_id, NULL, :insight_id, :action,
                 CAST(:edits AS jsonb), NOW())
            """
        ),
        {
            "id": feedback_id,
            "org_id": org_id,
            # API-key callers don't have a per-user identity — attribute to
            # the org owner placeholder. Dashboard callers populate this
            # via the cookie session in a later refactor.
            "user_id": "system:api",
            "insight_id": insight_id,
            "action": body.outcome,
            "edits": json.dumps(edit_payload),
        },
    )

    # 3) Append the outcome onto every action_ledger row tied to this
    # insight — keeps the delivery audit trail self-describing.
    db.execute(
        text(
            """
            UPDATE action_ledger
            SET outcome_detail = COALESCE(outcome_detail, '') ||
                                 ' | outcome=' || :outcome ||
                                 COALESCE(' value=' || :val_str, '') ||
                                 COALESCE(' evidence=' || :evidence, ''),
                completed_at = NOW()
            WHERE org_id = :org_id
              AND target_type = 'insight'
              AND target_ref = :insight_id
            """
        ),
        {
            "outcome": body.outcome,
            "val_str": (
                f"{body.value_amount:.2f} {body.currency}"
                if body.value_amount is not None
                else None
            ),
            "evidence": (body.evidence[:200] if body.evidence else None),
            "org_id": org_id,
            "insight_id": insight_id,
        },
    )
    db.commit()
    return {
        "ok": True,
        "feedback_id": feedback_id,
        "insight_id": insight_id,
        "outcome": body.outcome,
    }


@router.get("/v1/insights/stats")
def insight_stats(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Aggregated ROI numbers for the dashboard "Actions GeniOS took" widget.

    Window is the last N days (default 7). Numbers come from:
      * proactive_insights (insights fired)
      * action_ledger      (deliveries attempted + their outcome)
      * feedback_actions   (business outcomes recorded by /outcome)

    Plan alignment: g-i-7 delivery accounting + g-i-8 outcome
    attribution. The widget that consumes this is the closing of the
    "what did GeniOS do for me" loop.
    """
    n_insights = db.execute(
        text(
            "SELECT COUNT(*) FROM proactive_insights "
            "WHERE org_id = :org AND created_at >= NOW() - (:days || ' days')::INTERVAL"
        ),
        {"org": org_id, "days": days},
    ).scalar() or 0

    delivery = db.execute(
        text(
            """
            SELECT
              COUNT(*) AS total_actions,
              COUNT(*) FILTER (WHERE outcome = 'success') AS delivered,
              COUNT(*) FILTER (WHERE outcome = 'failed')  AS failed
            FROM action_ledger
            WHERE org_id = :org
              AND action_type = 'webhook_delivered'
              AND created_at >= NOW() - (:days || ' days')::INTERVAL
            """
        ),
        {"org": org_id, "days": days},
    ).fetchone()

    outcomes_rows = db.execute(
        text(
            """
            SELECT action, COUNT(*),
                   COALESCE(SUM((edit_diff_jsonb->>'value_amount')::NUMERIC), 0)
            FROM feedback_actions
            WHERE org_id = :org
              AND insight_id IS NOT NULL
              AND timestamp >= NOW() - (:days || ' days')::INTERVAL
              AND action IN ('paid', 'ignored', 'dismissed', 'escalated', 'acted')
            GROUP BY action
            """
        ),
        {"org": org_id, "days": days},
    ).fetchall()

    outcomes: dict[str, int] = {
        "paid": 0,
        "ignored": 0,
        "dismissed": 0,
        "escalated": 0,
        "acted": 0,
    }
    value_recovered_inr = 0.0
    for action, count, total_value in outcomes_rows:
        outcomes[action] = int(count)
        if action == "paid":
            value_recovered_inr = float(total_value or 0)

    outcomes_recorded = sum(outcomes.values())

    # Intervention rate — the CTO-brief north star, computed live from
    # feedback_actions (the same rows the calibration tuner reads).
    #
    #   intervention_rate = human_overrides / total_recorded_outcomes
    #
    # human_overrides = dismissed (strongest signal — "this insight was
    # wrong, I rejected it"). `ignored` is excluded from the numerator
    # because absence-of-judgment is not an override per the brief
    # (intentional alignment with calibration.py's outcome window logic).
    #
    # Trending DOWN over weeks means the engine is learning. Flat or up
    # is a red flag and surfaces here so the founder can act on it.
    n_overrides = int(outcomes.get("dismissed", 0))
    n_decisions = outcomes_recorded
    intervention_rate = (
        round(n_overrides / n_decisions, 4) if n_decisions > 0 else 0.0
    )

    # Companion: a 7d-prior window comparison so the dashboard can show
    # direction (↓ / → / ↑). Sample size guard: need >=10 outcomes in BOTH
    # windows before claiming a direction; otherwise "insufficient_data".
    prior_overrides_row = db.execute(
        text(
            """
            SELECT
              COUNT(*) FILTER (WHERE action = 'dismissed') AS overrides,
              COUNT(*) FILTER (WHERE action IN ('paid','ignored','dismissed','escalated','acted')) AS total
            FROM feedback_actions
            WHERE org_id = :org
              AND insight_id IS NOT NULL
              AND timestamp >= NOW() - ((:days * 2) || ' days')::INTERVAL
              AND timestamp <  NOW() - (:days || ' days')::INTERVAL
            """
        ),
        {"org": org_id, "days": days},
    ).fetchone()
    prior_overrides = int(prior_overrides_row[0]) if prior_overrides_row else 0
    prior_total = int(prior_overrides_row[1]) if prior_overrides_row else 0
    prior_rate = (
        round(prior_overrides / prior_total, 4) if prior_total > 0 else None
    )
    if prior_total < 10 or n_decisions < 10:
        direction = "insufficient_data"
    elif prior_rate is None:
        direction = "insufficient_data"
    elif intervention_rate < prior_rate - 0.02:
        direction = "down"
    elif intervention_rate > prior_rate + 0.02:
        direction = "up"
    else:
        direction = "flat"

    return {
        "window_days": days,
        "insights_fired": int(n_insights),
        "actions_taken": int(delivery[0]) if delivery else 0,
        "actions_delivered": int(delivery[1]) if delivery else 0,
        "actions_failed": int(delivery[2]) if delivery else 0,
        "outcomes_recorded": outcomes_recorded,
        "outcomes": outcomes,
        "value_recovered_inr": value_recovered_inr,
        "headline": _stats_headline(int(n_insights), outcomes, value_recovered_inr),
        # North-star block (CTO brief). Direction is a triangle the
        # dashboard renders; "insufficient_data" hides it instead of lying.
        "intervention_rate": intervention_rate,
        "intervention_rate_prior": prior_rate,
        "intervention_rate_direction": direction,
    }


def _stats_headline(insights: int, outcomes: dict[str, int], recovered_inr: float) -> str:
    """One-line summary for the dashboard banner."""
    if insights == 0:
        return "No insights yet — upload data in Resources to get started."
    paid = outcomes.get("paid", 0)
    if paid == 0:
        return (
            f"GeniOS surfaced {insights} insight{'s' if insights != 1 else ''}. "
            "Mark the outcomes to start tracking impact."
        )
    rec_lakh = recovered_inr / 100000
    rec_str = (
        f"₹{rec_lakh:.1f}L"
        if rec_lakh >= 1
        else f"₹{int(recovered_inr):,}"
    )
    return (
        f"GeniOS surfaced {insights} insight{'s' if insights != 1 else ''}, "
        f"{paid} closed paid — {rec_str} attributable to those nudges."
    )


@router.post("/v1/calibration/tune")
def calibration_tune_endpoint(
    auto_apply: bool = Query(default=True),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Manual trigger for the threshold tuner (Phase 4).

    The weekly Celery beat (`task_tune_thresholds`) calls the same
    function. This endpoint exists so an ops engineer can run a tune
    pass on demand after deploying new rules, and so the dashboard
    can offer a "tune now" button after a customer records a batch
    of outcomes.

    `auto_apply=true` (default) writes status=active for any suggestion
    that meets the auto-bar (>=5pp precision improvement AND >=20 outcome
    samples). `auto_apply=false` forces every suggestion to status=shadow
    -- useful for a dry-run preview.

    Plan alignment: g-i-8 (calibration loop), g-i-5 (the rule YAML is
    never mutated -- overrides live in org_rule_overrides instead).
    """
    from core.foundations.threshold_tuner import tune_for_org

    result = tune_for_org(
        db, org_id=org_id, module_id="ar_collection", auto_apply=auto_apply
    )
    db.commit()
    return {"tuner_result": result}


@router.get("/v1/calibration/thresholds")
def calibration_thresholds_endpoint(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """List every per-org rule threshold override visible to this org.

    Returns both active overrides (currently applied at fire time) and
    shadow ones (suggestions the tuner made but didn't meet the auto-bar).
    The dashboard renders this as "GeniOS learned this about your data"
    -- closes the visibility loop on what the system is doing on the
    customer's behalf.
    """
    rows = db.execute(
        text(
            """
            SELECT id, module_id, rule_id, fact_predicate, op, threshold_value,
                   status, source, justification, sample_size,
                   precision_before, precision_after,
                   applied_at, reverted_at, created_at
            FROM org_rule_overrides
            WHERE org_id = :org
            ORDER BY created_at DESC
            LIMIT 100
            """
        ),
        {"org": org_id},
    ).fetchall()

    return {
        "overrides": [
            {
                "id": str(r.id),
                "module_id": r.module_id,
                "rule_id": r.rule_id,
                "fact_predicate": r.fact_predicate,
                "op": r.op,
                "threshold_value": float(r.threshold_value),
                "status": r.status,
                "source": r.source,
                "justification": r.justification,
                "sample_size": r.sample_size,
                "precision_before": r.precision_before,
                "precision_after": r.precision_after,
                "applied_at": r.applied_at.isoformat() if r.applied_at else None,
                "reverted_at": r.reverted_at.isoformat() if r.reverted_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "active_count": sum(1 for r in rows if r.status == "active"),
        "shadow_count": sum(1 for r in rows if r.status == "shadow"),
    }


@router.post("/v1/hypotheses/generate")
def generate_hypotheses_endpoint(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Manual trigger for the LLM hypothesis layer (Phase 3).

    The daily Celery beat calls the same underlying function; this route
    is the dashboard "Find me something I'm missing" button + the ops
    escape hatch. Returns the propose/survivor/emit counts so the caller
    can render a confirmation toast without re-querying the insights list.

    Cost note: each call is 1 Sonnet propose + N Sonnet refutes (N = number
    of proposals). For the AR demo's 35-invoice fact set that's typically
    ~12k input tokens total -> ~₹6 per run. The 7-day signature dedupe
    inside the hypothesizer keeps repeat costs bounded.
    """
    from core.proactive.hypothesizer import generate_hypotheses_for_org

    result = generate_hypotheses_for_org(db, org_id=org_id, window_days=days)
    db.commit()
    return {"hypothesizer_result": result}


@router.post("/v1/scan")
def trigger_scan(
    db: Session = Depends(get_db),
    org_id: str = Depends(verify_api_key),
):
    """Real scan: delegates to `core.proactive.pipeline.run_for_org` so the
    manual path and the event-driven path share one code path.

    Module is hardcoded to `ar_collection` for the AR demo. A future
    install would loop over all installed modules or pick based on the
    org's business_context. This route is the dashboard "Scan now" escape
    hatch — every other trigger (CSV bus event, hourly cron) hits the
    same pipeline function so behavior can't drift.
    """
    from core.proactive.pipeline import run_all_for_org

    result = run_all_for_org(db, org_id=org_id, source="manual")
    db.commit()
    return {"scan_result": result}
