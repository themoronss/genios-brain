"""
Phase 6.3: Webhook delivery — push insights to customer endpoints.

Per L2 spec gap analysis: HMAC-SHA256 signature in X-Genios-Signature header.
Auto-disables webhooks after 10 consecutive failures.
"""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

import requests
from sqlalchemy import text
from app.database import SessionLocal

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = int(os.getenv("GENIOS_WEBHOOK_TIMEOUT_SECONDS", "10"))
MAX_CONSECUTIVE_FAILURES = int(os.getenv("GENIOS_WEBHOOK_MAX_FAILURES", "10"))


def _sign_payload(payload: str, secret: str) -> str:
    """HMAC-SHA256 signature for webhook payload verification."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def deliver_pending_insights(org_id: str = None):
    """
    Find all pending insights and deliver to configured webhooks.
    Each delivery is atomic — one insight per POST.
    """
    db = SessionLocal()
    try:
        where = "i.delivery_status = 'pending' AND i.is_dismissed = FALSE"
        params = {}
        if org_id:
            where += " AND i.org_id = :org_id"
            params["org_id"] = org_id

        pending = db.execute(
            text(f"""
                SELECT i.id, i.org_id, i.insight_type, i.priority, i.category,
                       i.title, i.detail, i.contact_name, i.contact_id,
                       i.memory_view, i.genios_view, i.generated_at
                FROM insights i
                WHERE {where}
                ORDER BY i.generated_at ASC
                LIMIT 50
            """),
            params,
        ).fetchall()

        if not pending:
            return {"delivered": 0, "failed": 0}

        # Group by org → look up webhook config per org
        by_org = {}
        for row in pending:
            oid = str(row.org_id)
            by_org.setdefault(oid, []).append(row)

        delivered = 0
        failed = 0

        for oid, insights in by_org.items():
            # Get active webhook configs for this org
            configs = db.execute(
                text("""
                    SELECT id, url, secret, events, consecutive_failures
                    FROM webhook_config
                    WHERE org_id = :oid AND is_active = TRUE
                """),
                {"oid": oid},
            ).fetchall()

            if not configs:
                # No webhook configured — mark as delivered (nowhere to send)
                for ins in insights:
                    db.execute(
                        text("UPDATE insights SET delivery_status = 'no_webhook' WHERE id = :id"),
                        {"id": str(ins.id)},
                    )
                db.commit()
                continue

            for ins in insights:
                payload = {
                    "event": "insight",
                    "insight_id": str(ins.id),
                    "org_id": oid,
                    "type": ins.insight_type,
                    "priority": ins.priority,
                    "category": ins.category,
                    "title": ins.title,
                    "contact_name": ins.contact_name,
                    "contact_id": str(ins.contact_id) if ins.contact_id else None,
                    "memory_view": ins.memory_view,
                    "genios_view": ins.genios_view,
                    "generated_at": ins.generated_at.isoformat() if ins.generated_at else None,
                }
                payload_json = json.dumps(payload, default=str)

                any_success = False
                for cfg in configs:
                    if "insight" not in (cfg.events or []):
                        continue

                    signature = _sign_payload(payload_json, cfg.secret)
                    try:
                        resp = requests.post(
                            cfg.url,
                            data=payload_json,
                            headers={
                                "Content-Type": "application/json",
                                "X-Genios-Signature": signature,
                                "X-Genios-Event": "insight",
                            },
                            timeout=WEBHOOK_TIMEOUT,
                        )
                        if resp.status_code < 300:
                            any_success = True
                            # Reset failure counter
                            db.execute(
                                text("""
                                    UPDATE webhook_config
                                    SET consecutive_failures = 0, last_delivery_at = NOW()
                                    WHERE id = :wid
                                """),
                                {"wid": str(cfg.id)},
                            )
                        else:
                            logger.warning(f"Webhook {cfg.url} returned {resp.status_code}")
                            _increment_failures(db, cfg)
                    except requests.RequestException as e:
                        logger.warning(f"Webhook delivery failed to {cfg.url}: {e}")
                        _increment_failures(db, cfg)

                # Update insight delivery status
                if any_success:
                    db.execute(
                        text("""
                            UPDATE insights
                            SET delivery_status = 'delivered', delivered_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": str(ins.id)},
                    )
                    delivered += 1
                else:
                    db.execute(
                        text("UPDATE insights SET delivery_status = 'failed' WHERE id = :id"),
                        {"id": str(ins.id)},
                    )
                    failed += 1

            db.commit()

        logger.info(f"Webhook delivery: {delivered} delivered, {failed} failed")
        return {"delivered": delivered, "failed": failed}
    finally:
        db.close()


def _increment_failures(db, cfg):
    """Increment failure counter; auto-disable after MAX_CONSECUTIVE_FAILURES."""
    new_count = (cfg.consecutive_failures or 0) + 1
    if new_count >= MAX_CONSECUTIVE_FAILURES:
        db.execute(
            text("UPDATE webhook_config SET is_active = FALSE, consecutive_failures = :c WHERE id = :wid"),
            {"wid": str(cfg.id), "c": new_count},
        )
        logger.warning(f"Webhook {cfg.url} auto-disabled after {new_count} consecutive failures")
    else:
        db.execute(
            text("UPDATE webhook_config SET consecutive_failures = :c WHERE id = :wid"),
            {"wid": str(cfg.id), "c": new_count},
        )
