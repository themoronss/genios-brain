"""
Webhook delivery — durable retry via `delivery_attempts` table.

Flow (Phase 1.7 + Phase 1 fix-set / Item #3):
  1. `schedule_for_insights(org_id)` enqueues a pending row per (insight × webhook).
     If no active webhook is registered, leave the insight 'pending' for up to
     7 days so a later subscription can pick it up (bug 3.1).
  2. `deliver_due(org_id)` picks `status='pending' AND next_attempt_at <= NOW()`,
     attempts POST, records the outcome. Commits per-row (bug 3.2).
  3. On failure, schedules the next attempt from GENIOS_WEBHOOK_RETRY_SCHEDULE,
     unless the response was a permanent 4xx (bug 3.3) in which case the row
     is parked in DLQ immediately. After GENIOS_WEBHOOK_AUTO_DISABLE_THRESHOLD
     consecutive failures the webhook_config is auto-disabled (bug 3.4).
  4. Race-safe: a partial unique index in migration 095 prevents duplicate
     pending attempts on concurrent schedulers (bug 3.5).
  5. Payload size capped at MAX_PAYLOAD_BYTES — runaway LLM outputs hit DLQ
     rather than burning timeouts (bug 3.6).

HMAC-SHA256 signature via X-Genios-Signature (unchanged from old flow).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import requests
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import GENIOS_WEBHOOK_RETRY_SCHEDULE
from app.database import SessionLocal

logger = logging.getLogger(__name__)

WEBHOOK_TIMEOUT = int(os.getenv("GENIOS_WEBHOOK_TIMEOUT_SECONDS", "10"))
AUTO_DISABLE_THRESHOLD = int(os.getenv("GENIOS_WEBHOOK_AUTO_DISABLE_THRESHOLD", "20"))
NO_WEBHOOK_EXPIRY_DAYS = int(os.getenv("GENIOS_NO_WEBHOOK_EXPIRY_DAYS", "7"))
# 64KB ceiling: typical insight payload is <1KB; 64KB catches runaway LLM
# output without rejecting legitimate verbose insights.
MAX_PAYLOAD_BYTES = int(os.getenv("GENIOS_WEBHOOK_MAX_PAYLOAD_BYTES", str(64 * 1024)))

# 4xx that are still worth retrying (transient under load, not client error).
_TRANSIENT_4XX = {408, 425, 429}


def _sign_payload(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def _next_delay(attempt_number: int) -> int | None:
    """Return seconds until next attempt, or None if retries exhausted."""
    idx = attempt_number - 1
    if idx < 0 or idx >= len(GENIOS_WEBHOOK_RETRY_SCHEDULE):
        return None
    return GENIOS_WEBHOOK_RETRY_SCHEDULE[idx]


def _is_permanent_failure(status_code: int | None) -> bool:
    """4xx (except known transient codes) means the request is malformed or
    forbidden — no point retrying. 5xx and connection errors stay retryable.
    """
    if status_code is None:
        return False  # network error → retry
    if 400 <= status_code < 500 and status_code not in _TRANSIENT_4XX:
        return True
    return False


def _maybe_auto_disable_webhook(db, webhook_id: str) -> None:
    """Disable the webhook if it has hit the consecutive-failure threshold.

    Runs after every failed attempt; cheap (single UPDATE with guard).
    """
    db.execute(
        text("""
            UPDATE webhook_config
            SET is_active = FALSE,
                disabled_reason = :reason,
                disabled_at = NOW()
            WHERE id = :wid
              AND is_active = TRUE
              AND consecutive_failures >= :threshold
        """),
        {
            "wid": str(webhook_id),
            "reason": f"auto: {AUTO_DISABLE_THRESHOLD} consecutive failures",
            "threshold": AUTO_DISABLE_THRESHOLD,
        },
    )


# ── Step 1 — enqueue: one row per (insight × active webhook) ──────────────
def schedule_for_insights(org_id: str | None = None) -> int:
    """Insert `delivery_attempts` rows for any insight not yet scheduled.

    Bug 3.1 fix: when there's no active webhook subscribed yet, the insight
    stays 'pending' (not marked terminal) for up to NO_WEBHOOK_EXPIRY_DAYS
    so a customer who subscribes a webhook later still receives recent
    insights. After the grace period it's marked 'no_webhook_expired' so
    we stop scanning it.
    """
    db = SessionLocal()
    try:
        where = (
            "i.delivery_status IN ('pending', 'no_webhook') "
            "AND i.is_dismissed = FALSE"
        )
        params = {}
        if org_id:
            where += " AND i.org_id = :org_id"
            params["org_id"] = org_id

        pending = db.execute(
            text(f"""
                SELECT i.id, i.org_id, i.generated_at, i.delivery_status
                FROM insights i
                WHERE {where}
                  AND NOT EXISTS (
                      SELECT 1 FROM delivery_attempts da
                      WHERE da.insight_id = i.id
                  )
                ORDER BY i.generated_at ASC
                LIMIT 200
            """),
            params,
        ).fetchall()

        if not pending:
            return 0

        enqueued = 0
        for ins in pending:
            oid = str(ins.org_id)
            configs = db.execute(
                text("""
                    SELECT id FROM webhook_config
                    WHERE org_id = :oid AND is_active = TRUE
                      AND 'insight' = ANY(COALESCE(events, ARRAY['insight']))
                """),
                {"oid": oid},
            ).fetchall()

            if not configs:
                # Bug 3.1: leave as 'pending' for grace period; only mark
                # terminal after expiry so re-scans don't loop forever.
                db.execute(
                    text("""
                        UPDATE insights
                        SET delivery_status = CASE
                            WHEN generated_at < NOW() - INTERVAL '1 day' * :grace_days
                                THEN 'no_webhook_expired'
                            ELSE 'no_webhook'
                        END
                        WHERE id = :id
                    """),
                    {"id": str(ins.id), "grace_days": NO_WEBHOOK_EXPIRY_DAYS},
                )
                db.commit()
                continue

            for cfg in configs:
                try:
                    db.execute(
                        text("""
                            INSERT INTO delivery_attempts
                                (id, org_id, webhook_id, insight_id,
                                 attempt_number, status, scheduled_at, next_attempt_at)
                            VALUES
                                (:id, :oid, :wid, :iid,
                                 1, 'pending', NOW(), NOW())
                        """),
                        {"id": str(uuid4()), "oid": oid, "wid": str(cfg.id), "iid": str(ins.id)},
                    )
                    # Bug 3.2: per-row commit so one failure doesn't roll back
                    # the rest of the batch.
                    db.commit()
                    # Webhook subscribed after the fact → re-arm delivery_status.
                    db.execute(
                        text(
                            "UPDATE insights SET delivery_status = 'pending' "
                            "WHERE id = :id AND delivery_status = 'no_webhook'"
                        ),
                        {"id": str(ins.id)},
                    )
                    db.commit()
                    enqueued += 1
                except IntegrityError:
                    # Bug 3.5: partial unique index caught a concurrent insert.
                    db.rollback()
                    logger.debug(
                        f"duplicate pending attempt suppressed insight={ins.id} webhook={cfg.id}"
                    )
        return enqueued
    finally:
        db.close()


# ── Step 2 — deliver attempts whose next_attempt_at is due ────────────────
def deliver_due(org_id: str | None = None) -> dict:
    """Pick due attempts, POST, record outcome, reschedule or mark dead."""
    db = SessionLocal()
    try:
        where = "status = 'pending' AND next_attempt_at <= NOW()"
        params = {}
        if org_id:
            where += " AND org_id = :org_id"
            params["org_id"] = org_id

        due = db.execute(
            text(f"""
                SELECT da.id, da.org_id, da.webhook_id, da.insight_id,
                       da.attempt_number,
                       wc.url, wc.secret,
                       i.id AS i_id, i.insight_type, i.priority, i.category,
                       i.title, i.contact_name, i.contact_id,
                       i.memory_view, i.genios_view, i.generated_at
                FROM delivery_attempts da
                JOIN webhook_config wc ON wc.id = da.webhook_id
                JOIN insights       i  ON i.id  = da.insight_id
                WHERE {where}
                ORDER BY da.next_attempt_at ASC
                LIMIT 50
            """),
            params,
        ).fetchall()

        if not due:
            return {"delivered": 0, "retried": 0, "dead": 0}

        delivered = retried = dead = 0

        for row in due:
            payload = {
                "event": "insight",
                "insight_id": str(row.i_id),
                "org_id": str(row.org_id),
                "type": row.insight_type,
                "priority": row.priority,
                "category": row.category,
                "title": row.title,
                "contact_name": row.contact_name,
                "contact_id": str(row.contact_id) if row.contact_id else None,
                "memory_view": row.memory_view,
                "genios_view": row.genios_view,
                "generated_at": row.generated_at.isoformat() if row.generated_at else None,
            }
            body = json.dumps(payload, default=str)

            # Bug 3.6: payload size guard. Runaway LLM output → straight to DLQ
            # rather than burning a 10s HTTP timeout.
            if len(body.encode("utf-8")) > MAX_PAYLOAD_BYTES:
                logger.error(
                    f"webhook payload too large insight={row.i_id} bytes={len(body)}"
                )
                try:
                    db.execute(
                        text("""
                            UPDATE delivery_attempts
                            SET status = 'dead', error = 'payload_too_large',
                                attempted_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": str(row.id)},
                    )
                    db.execute(
                        text(
                            "UPDATE insights SET delivery_status = 'failed_permanent' "
                            "WHERE id = :id"
                        ),
                        {"id": str(row.i_id)},
                    )
                    db.commit()  # Bug 3.2: per-row commit
                    dead += 1
                except Exception as e:
                    db.rollback()
                    logger.warning(f"payload_too_large commit failed: {e}")
                continue

            signature = _sign_payload(body, row.secret)

            status_code = None
            err = None
            try:
                resp = requests.post(
                    row.url, data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Genios-Signature": signature,
                        "X-Genios-Event": "insight",
                    },
                    timeout=WEBHOOK_TIMEOUT,
                )
                status_code = resp.status_code
            except requests.RequestException as e:
                err = str(e)[:500]

            success = status_code is not None and 200 <= status_code < 300

            try:
                if success:
                    db.execute(
                        text("""
                            UPDATE delivery_attempts
                            SET status = 'succeeded', status_code = :sc, attempted_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": str(row.id), "sc": status_code},
                    )
                    db.execute(
                        text("""
                            UPDATE insights
                            SET delivery_status = 'delivered', delivered_at = NOW()
                            WHERE id = :id
                        """),
                        {"id": str(row.i_id)},
                    )
                    db.execute(
                        text("""
                            UPDATE webhook_config
                            SET consecutive_failures = 0, last_delivery_at = NOW()
                            WHERE id = :wid
                        """),
                        {"wid": str(row.webhook_id)},
                    )
                    db.commit()  # Bug 3.2
                    delivered += 1
                    continue

                # Failure path — close this attempt, schedule next or mark dead
                db.execute(
                    text("""
                        UPDATE delivery_attempts
                        SET status = 'failed', status_code = :sc, error = :err, attempted_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": str(row.id), "sc": status_code, "err": err},
                )
                db.execute(
                    text("""
                        UPDATE webhook_config
                        SET consecutive_failures = COALESCE(consecutive_failures, 0) + 1
                        WHERE id = :wid
                    """),
                    {"wid": str(row.webhook_id)},
                )
                # Bug 3.4: auto-disable the webhook if it has hit threshold.
                _maybe_auto_disable_webhook(db, row.webhook_id)

                # Bug 3.3: permanent 4xx → straight to DLQ (skip retries).
                permanent = _is_permanent_failure(status_code)
                delay_s = None if permanent else _next_delay(row.attempt_number + 1)

                if delay_s is None:
                    db.execute(
                        text("""
                            INSERT INTO delivery_attempts
                                (id, org_id, webhook_id, insight_id,
                                 attempt_number, status, status_code, error,
                                 scheduled_at, attempted_at)
                            VALUES
                                (:id, :oid, :wid, :iid,
                                 :n, 'dead', :sc, :err,
                                 NOW(), NOW())
                        """),
                        {
                            "id": str(uuid4()), "oid": str(row.org_id),
                            "wid": str(row.webhook_id), "iid": str(row.i_id),
                            "n": row.attempt_number + 1, "sc": status_code, "err": err,
                        },
                    )
                    db.execute(
                        text("""
                            UPDATE insights SET delivery_status = 'failed_permanent'
                            WHERE id = :id
                        """),
                        {"id": str(row.i_id)},
                    )
                    db.commit()  # Bug 3.2
                    dead += 1
                else:
                    next_at = datetime.now(timezone.utc) + timedelta(seconds=delay_s)
                    try:
                        db.execute(
                            text("""
                                INSERT INTO delivery_attempts
                                    (id, org_id, webhook_id, insight_id,
                                     attempt_number, status, scheduled_at, next_attempt_at)
                                VALUES
                                    (:id, :oid, :wid, :iid,
                                     :n, 'pending', NOW(), :nxt)
                            """),
                            {
                                "id": str(uuid4()), "oid": str(row.org_id),
                                "wid": str(row.webhook_id), "iid": str(row.i_id),
                                "n": row.attempt_number + 1, "nxt": next_at,
                            },
                        )
                        db.commit()  # Bug 3.2
                        retried += 1
                    except IntegrityError:
                        # Bug 3.5: concurrent scheduler already inserted this.
                        db.rollback()
                        logger.debug(
                            f"duplicate retry attempt suppressed insight={row.i_id}"
                        )
            except Exception as e:
                db.rollback()
                logger.warning(f"webhook delivery row commit failed: {e}")

        logger.info(
            f"Webhook delivery: delivered={delivered} retried={retried} dead={dead}"
        )
        return {"delivered": delivered, "retried": retried, "dead": dead}
    finally:
        db.close()


# ── Phase 3.3 — recommendations path (runs in parallel with legacy insights) ─
def schedule_for_recommendations(org_id: str | None = None) -> int:
    """Insert delivery_attempts for any recommendation not yet scheduled."""
    db = SessionLocal()
    try:
        where = "r.delivered_at IS NULL"
        params = {}
        if org_id:
            where += " AND r.org_id = :org_id"
            params["org_id"] = org_id

        pending = db.execute(
            text(f"""
                SELECT r.id, r.org_id
                FROM recommendations r
                WHERE {where}
                  AND NOT EXISTS (
                      SELECT 1 FROM delivery_attempts da
                      WHERE da.recommendation_id = r.id
                  )
                ORDER BY r.created_at ASC
                LIMIT 200
            """),
            params,
        ).fetchall()
        if not pending:
            return 0

        enqueued = 0
        for rec in pending:
            oid = str(rec.org_id)
            configs = db.execute(
                text("""
                    SELECT id FROM webhook_config
                    WHERE org_id = :oid AND is_active = TRUE
                      AND 'insight' = ANY(COALESCE(events, ARRAY['insight']))
                """),
                {"oid": oid},
            ).fetchall()
            if not configs:
                # Bug 3.1 (recommendations): grace period before terminal.
                # `recommendations` doesn't have a delivery_status column, so
                # we leave delivered_at NULL during grace, then set NOW() to
                # stop scanning after expiry.
                from app.config import GENIOS_WEBHOOK_RETRY_SCHEDULE as _  # noqa: F401 — keep import order

                try:
                    rec_age_days = (
                        datetime.now(timezone.utc) - rec.created_at.replace(tzinfo=timezone.utc)
                    ).days if hasattr(rec, "created_at") and rec.created_at else 0
                except Exception:
                    rec_age_days = 0
                if rec_age_days > NO_WEBHOOK_EXPIRY_DAYS:
                    db.execute(
                        text("UPDATE recommendations SET delivered_at = NOW() WHERE id = :id"),
                        {"id": str(rec.id)},
                    )
                    db.commit()
                continue
            for cfg in configs:
                try:
                    db.execute(
                        text("""
                            INSERT INTO delivery_attempts
                                (id, org_id, webhook_id, recommendation_id,
                                 attempt_number, status, scheduled_at, next_attempt_at)
                            VALUES
                                (:id, :oid, :wid, :rid,
                                 1, 'pending', NOW(), NOW())
                        """),
                        {"id": str(uuid4()), "oid": oid, "wid": str(cfg.id), "rid": str(rec.id)},
                    )
                    db.commit()  # Bug 3.2
                    enqueued += 1
                except IntegrityError:
                    # Bug 3.5
                    db.rollback()
                    logger.debug(
                        f"duplicate pending attempt suppressed rec={rec.id} webhook={cfg.id}"
                    )
        return enqueued
    finally:
        db.close()


def deliver_due_recommendations(org_id: str | None = None) -> dict:
    """Pick due attempts that point at recommendations, POST, record outcome."""
    db = SessionLocal()
    try:
        where = "da.status = 'pending' AND da.next_attempt_at <= NOW() AND da.recommendation_id IS NOT NULL"
        params = {}
        if org_id:
            where += " AND da.org_id = :org_id"
            params["org_id"] = org_id

        due = db.execute(
            text(f"""
                SELECT da.id, da.org_id, da.webhook_id, da.recommendation_id,
                       da.attempt_number,
                       wc.url, wc.secret,
                       r.id AS r_id, r.insight_type, r.priority, r.category,
                       r.title, r.reason, r.action, r.subject_entity_id,
                       r.created_at, r.confidence,
                       r.evidence, r.precedent_links, r.suggested_action,
                       r.confidence_level, r.rationale
                FROM delivery_attempts da
                JOIN webhook_config wc ON wc.id = da.webhook_id
                JOIN recommendations r ON r.id = da.recommendation_id
                WHERE {where}
                ORDER BY da.next_attempt_at ASC
                LIMIT 50
            """),
            params,
        ).fetchall()

        if not due:
            return {"delivered": 0, "retried": 0, "dead": 0}

        delivered = retried = dead = 0
        for row in due:
            # Payload v2 — migration 073. New fields are always emitted;
            # consumers built against v1 can ignore them (additive contract).
            payload = {
                "event": "recommendation",
                "payload_version": 2,
                "recommendation_id": str(row.r_id),
                "org_id": str(row.org_id),
                "type": row.insight_type,
                "priority": float(row.priority or 0.0),
                "confidence": float(row.confidence or 0.0),
                "confidence_level": row.confidence_level,
                "category": row.category,
                "title": row.title,
                "rationale": row.rationale or row.reason,
                "reason": row.reason,  # v1 compat
                "action": row.action,  # v1 compat
                "suggested_action": row.suggested_action,
                "evidence": row.evidence or [],
                "precedent_links": row.precedent_links or [],
                "subject_entity_id": str(row.subject_entity_id) if row.subject_entity_id else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            body = json.dumps(payload, default=str)

            # Bug 3.6: payload size guard for recommendations too.
            if len(body.encode("utf-8")) > MAX_PAYLOAD_BYTES:
                logger.error(
                    f"webhook payload too large rec={row.r_id} bytes={len(body)}"
                )
                try:
                    db.execute(
                        text("""
                            UPDATE delivery_attempts
                            SET status='dead', error='payload_too_large', attempted_at=NOW()
                            WHERE id=:id
                        """),
                        {"id": str(row.id)},
                    )
                    db.commit()
                    dead += 1
                except Exception as e:
                    db.rollback()
                    logger.warning(f"rec payload_too_large commit failed: {e}")
                continue

            signature = _sign_payload(body, row.secret)

            status_code = None
            err = None
            try:
                resp = requests.post(
                    row.url, data=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Genios-Signature": signature,
                        "X-Genios-Event": "recommendation",
                        "X-Genios-Payload-Version": "2",
                    },
                    timeout=WEBHOOK_TIMEOUT,
                )
                status_code = resp.status_code
            except requests.RequestException as e:
                err = str(e)[:500]

            success = status_code is not None and 200 <= status_code < 300

            try:
                if success:
                    db.execute(
                        text("""
                            UPDATE delivery_attempts
                            SET status='succeeded', status_code=:sc, attempted_at=NOW()
                            WHERE id=:id
                        """),
                        {"id": str(row.id), "sc": status_code},
                    )
                    db.execute(
                        text("UPDATE recommendations SET delivered_at = NOW() WHERE id = :id"),
                        {"id": str(row.r_id)},
                    )
                    db.execute(
                        text("""
                            UPDATE webhook_config
                            SET consecutive_failures = 0, last_delivery_at = NOW()
                            WHERE id = :wid
                        """),
                        {"wid": str(row.webhook_id)},
                    )
                    db.commit()  # Bug 3.2
                    delivered += 1
                    continue

                db.execute(
                    text("""
                        UPDATE delivery_attempts
                        SET status='failed', status_code=:sc, error=:err, attempted_at=NOW()
                        WHERE id=:id
                    """),
                    {"id": str(row.id), "sc": status_code, "err": err},
                )
                db.execute(
                    text("""
                        UPDATE webhook_config
                        SET consecutive_failures = COALESCE(consecutive_failures, 0) + 1
                        WHERE id = :wid
                    """),
                    {"wid": str(row.webhook_id)},
                )
                _maybe_auto_disable_webhook(db, row.webhook_id)  # Bug 3.4

                # Bug 3.3: permanent 4xx → straight to DLQ.
                permanent = _is_permanent_failure(status_code)
                delay_s = None if permanent else _next_delay(row.attempt_number + 1)

                if delay_s is None:
                    db.execute(
                        text("""
                            INSERT INTO delivery_attempts
                                (id, org_id, webhook_id, recommendation_id,
                                 attempt_number, status, status_code, error,
                                 scheduled_at, attempted_at)
                            VALUES
                                (:id, :oid, :wid, :rid,
                                 :n, 'dead', :sc, :err,
                                 NOW(), NOW())
                        """),
                        {
                            "id": str(uuid4()), "oid": str(row.org_id),
                            "wid": str(row.webhook_id), "rid": str(row.r_id),
                            "n": row.attempt_number + 1, "sc": status_code, "err": err,
                        },
                    )
                    db.commit()
                    dead += 1
                else:
                    next_at = datetime.now(timezone.utc) + timedelta(seconds=delay_s)
                    try:
                        db.execute(
                            text("""
                                INSERT INTO delivery_attempts
                                    (id, org_id, webhook_id, recommendation_id,
                                     attempt_number, status, scheduled_at, next_attempt_at)
                                VALUES
                                    (:id, :oid, :wid, :rid,
                                     :n, 'pending', NOW(), :nxt)
                            """),
                            {
                                "id": str(uuid4()), "oid": str(row.org_id),
                                "wid": str(row.webhook_id), "rid": str(row.r_id),
                                "n": row.attempt_number + 1, "nxt": next_at,
                            },
                        )
                        db.commit()
                        retried += 1
                    except IntegrityError:
                        db.rollback()
                        logger.debug(
                            f"duplicate retry attempt suppressed rec={row.r_id}"
                        )
            except Exception as e:
                db.rollback()
                logger.warning(f"recommendation delivery row commit failed: {e}")

        return {"delivered": delivered, "retried": retried, "dead": dead}
    finally:
        db.close()


# ── Entry point kept for celery-beat backward compat ──────────────────────
def deliver_pending_insights(org_id: str | None = None) -> dict:
    """Schedule + deliver everything due across both legacy insights and recommendations."""
    enqueued_i = schedule_for_insights(org_id)
    enqueued_r = schedule_for_recommendations(org_id)
    r_insights = deliver_due(org_id)
    r_recs = deliver_due_recommendations(org_id)
    return {
        "enqueued": enqueued_i + enqueued_r,
        "delivered": r_insights["delivered"] + r_recs["delivered"],
        "retried": r_insights["retried"] + r_recs["retried"],
        "dead": r_insights["dead"] + r_recs["dead"],
    }
