"""
Phase 6: Compose + deliver personalised retention offers.

Triggered after churn_scan flags a high-risk org. For each high-risk org:
  1. Pull the latest engagement_health row (signals + tier).
  2. Pull last 5 friction items (sync errors, dismiss spikes, complaints).
  3. Single Haiku call → JSON offer (subject/body/offer_payload/channel).
  4. Persist to retention_offers table (created here lazily) AND/OR
     publish to pending_alerts so it surfaces in next Claude reply.

Best-effort: failures logged, never raised.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import text

from app.brain.prompts.retention import RETENTION_SYSTEM, RETENTION_USER_TEMPLATE
from app.database import SessionLocal
from app.llm import llm_client

logger = logging.getLogger(__name__)


def _format_signals(payload: dict, breakdown: dict) -> str:
    parts = []
    if breakdown.get("hard", 0) >= 0.3:
        parts.append(f"hard signals: {breakdown.get('hard'):.2f}")
    if breakdown.get("soft", 0) >= 0.3:
        parts.append(f"soft signals: {breakdown.get('soft'):.2f}")
    if breakdown.get("context", 0) >= 0.3:
        parts.append(f"context signals: {breakdown.get('context'):.2f}")
    if (payload.get("sync_errors_7d") or 0) > 0:
        parts.append(f"{payload['sync_errors_7d']} sync errors last week")
    if (payload.get("dismiss_rate_30d") or 0) >= 0.5:
        parts.append(f"dismiss rate {payload['dismiss_rate_30d']*100:.0f}% over 30d")
    if payload.get("api_calls_prev_7d"):
        delta = payload['api_calls_7d'] - payload['api_calls_prev_7d']
        if delta < 0:
            parts.append(
                f"API calls dropped {-delta} in last 7d "
                f"(was {payload['api_calls_prev_7d']}, now {payload['api_calls_7d']})"
            )
    return "\n".join(f"  - {p}" for p in parts) or "  (none specific)"


def _recent_friction(db, org_id: str) -> str:
    """Pull last few free-text complaints / errors for prompt context."""
    snippets = []
    try:
        rows = db.execute(
            text("""
                SELECT sync_error FROM oauth_tokens
                WHERE org_id = :oid AND sync_error IS NOT NULL
                ORDER BY last_synced_at DESC NULLS LAST
                LIMIT 3
            """),
            {"oid": org_id},
        ).fetchall()
        for r in rows:
            if r[0]:
                snippets.append(f"sync error: {r[0][:120]}")
    except Exception:
        pass
    return "\n".join(f"  - {s}" for s in snippets) or "  (no specific complaints captured)"


def _parse_json(raw: str) -> Optional[dict]:
    raw = (raw or "").strip()
    if "```" in raw:
        chunks = raw.split("```")
        raw = chunks[1] if len(chunks) >= 3 else chunks[-1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    if not raw.lstrip().startswith("{"):
        lo, hi = raw.find("{"), raw.rfind("}")
        if lo >= 0 and hi > lo:
            raw = raw[lo:hi + 1]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return None


def compose_offer(org_id: str) -> Optional[dict]:
    """Compose ONE retention offer for an org based on its latest snapshot."""
    db = SessionLocal()
    try:
        row = db.execute(
            text("""
                SELECT churn_score, hard_signal_score, soft_signal_score,
                       context_signal_score, signals_payload
                FROM engagement_health
                WHERE org_id = :oid
                ORDER BY snapshot_date DESC
                LIMIT 1
            """),
            {"oid": org_id},
        ).fetchone()
        if not row:
            return None

        score = float(row.churn_score or 0.0)
        if score >= 0.80:
            tier = "rescue"
        elif score >= 0.60:
            tier = "offer"
        elif score >= 0.30:
            tier = "nudge"
        else:
            return None  # below threshold — no need to act

        plan = "trial"
        try:
            from app.plan_enforcer import get_org_plan
            plan = get_org_plan(db, org_id).get("tier", "trial")
        except Exception:
            pass

        payload = dict(row.signals_payload or {})
        breakdown = {
            "hard": float(row.hard_signal_score or 0),
            "soft": float(row.soft_signal_score or 0),
            "context": float(row.context_signal_score or 0),
        }
        signals_text = _format_signals(payload, breakdown)
        friction_text = _recent_friction(db, org_id)

        try:
            raw = llm_client.call(
                org_id=org_id,
                purpose="compose_retention_offer",
                messages=[
                    {"role": "system", "content": RETENTION_SYSTEM},
                    {"role": "user", "content": RETENTION_USER_TEMPLATE.format(
                        tier=tier, plan=plan,
                        signals=signals_text, friction=friction_text,
                    )},
                ],
                temperature=0.3,
                max_tokens=400,
            )
        except Exception as e:
            logger.debug(f"retention offer LLM error org={org_id}: {e}")
            return None

        offer = _parse_json(raw)
        if not offer:
            return None

        # ── Push into pending_alerts so Claude surfaces it next turn ──
        try:
            db.execute(
                text("""
                    INSERT INTO pending_alerts (
                        org_id, insight_type, title, body,
                        suggested_action, priority, confidence
                    ) VALUES (
                        :oid, 'retention_offer', :title, :body,
                        CAST(:sa AS jsonb), :prio, 0.9
                    )
                """),
                {
                    "oid": org_id,
                    "title": (offer.get("subject") or f"Retention {tier}")[:200],
                    "body": (offer.get("body") or "")[:1000],
                    "sa": json.dumps(offer.get("offer_payload") or {}),
                    "prio": 0.9 if tier == "rescue" else 0.7,
                },
            )
            db.commit()
        except Exception as e:
            logger.debug(f"pending_alerts push for retention failed: {e}")

        offer["org_id"] = org_id
        offer["tier"] = tier
        offer["churn_score"] = score
        return offer
    finally:
        db.close()


def run_retention_offers(org_id: str | None = None) -> dict:
    """Sweep all high-risk orgs (or one) and compose offers."""
    db = SessionLocal()
    try:
        if org_id:
            org_ids = [org_id]
        else:
            rows = db.execute(
                text("""
                    SELECT DISTINCT eh.org_id
                    FROM engagement_health eh
                    WHERE eh.snapshot_date = CURRENT_DATE
                      AND eh.churn_score >= 0.30
                """)
            ).fetchall()
            org_ids = [str(r[0]) for r in rows]
    finally:
        db.close()

    composed = 0
    for oid in org_ids:
        try:
            if compose_offer(oid):
                composed += 1
        except Exception as e:
            logger.warning(f"retention offer for {oid} failed: {e}")

    return {"composed": composed, "candidates": len(org_ids)}
