"""
Morning Digest — BUILD-1.

Every hour, for each org where local time = `digest_hour` AND today's digest
hasn't been sent yet, compose the top 3–5 pending recommendations from the
last 24h into ONE webhook event `digest.daily`.

Why:
- Individual recs fire as they happen (hard triggers). Those are for agents.
- A founder wants one morning package: "3 things you should know today."
- This hits brain benchmark B1 — the "brain watching while you slept" moment.

Invariants (non-negotiable):
- Does NOT mark individual recs as delivered. Each rec still fires via its
  own webhook if configured — the digest is purely a SUMMARY channel.
- Only webhook_config rows whose `events` array includes 'digest.daily'
  receive the digest. Existing consumers are untouched.
- Idempotent per (org, local_date) via `orgs.last_digest_sent_at` + utc_date
  comparison. Re-running the task safely skips already-sent orgs.
- Skips orgs with `digest_enabled = FALSE`.
- Degrades silently — any single-org failure doesn't break the loop.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
DIGEST_ENABLED = os.getenv("GENIOS_DIGEST_ENABLED", "true").lower() in ("1", "true", "yes")
MIN_PRIORITY = float(os.getenv("GENIOS_DIGEST_MIN_PRIORITY", "0.5"))
TOP_N = int(os.getenv("GENIOS_DIGEST_TOP_N", "5"))
LOOKBACK_HOURS = int(os.getenv("GENIOS_DIGEST_LOOKBACK_HOURS", "24"))
WEBHOOK_TIMEOUT = float(os.getenv("GENIOS_WEBHOOK_TIMEOUT", "8"))


# ── Timezone helpers ──────────────────────────────────────────────────────────
def _local_hour_and_date(tz_name: str) -> tuple[int, str]:
    """Return (local_hour [0-23], local_date ISO 'YYYY-MM-DD') for IANA tz.
    Falls back to UTC if tz is invalid."""
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name or "UTC")
    except Exception:
        tz = timezone.utc
    now_local = datetime.now(tz)
    return now_local.hour, now_local.date().isoformat()


def _utc_today_for(tz_name: str) -> datetime:
    """Midnight-today in the given timezone, returned as a UTC-aware datetime.
    Used to check whether `last_digest_sent_at` was already within today."""
    from datetime import datetime as _dt
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name or "UTC")
    except Exception:
        tz = timezone.utc
    now_local = _dt.now(tz)
    midnight_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight_local.astimezone(timezone.utc)


# ── Entry points ──────────────────────────────────────────────────────────────
def run_morning_digest(org_id: Optional[str] = None) -> dict:
    """Celery-callable entry. If org_id given, runs just that org (for testing).
    Otherwise iterates every digest-enabled org."""
    if not DIGEST_ENABLED:
        return {"skipped": "disabled"}

    db = SessionLocal()
    counters = {"processed": 0, "sent": 0, "skipped_wrong_hour": 0,
                "skipped_already_sent": 0, "skipped_no_recs": 0, "errors": 0}
    try:
        orgs = _fetch_candidate_orgs(db, org_id)
        for org in orgs:
            counters["processed"] += 1
            try:
                result = _process_one_org(db, org)
                counters[result] = counters.get(result, 0) + 1
            except Exception as e:
                counters["errors"] += 1
                logger.warning(f"digest failed org={org['id']}: {e}")
        return counters
    finally:
        db.close()


def _fetch_candidate_orgs(db: Session, org_id: Optional[str]) -> list[dict]:
    """Orgs eligible for digest: enabled + timezone set. Narrowed to org_id if
    provided (useful for manual runs)."""
    where = "digest_enabled = TRUE AND timezone IS NOT NULL"
    params: dict = {}
    if org_id:
        where += " AND id = :oid"
        params["oid"] = org_id

    rows = db.execute(
        text(f"""
            SELECT id, name, email, timezone, digest_hour, last_digest_sent_at
            FROM orgs
            WHERE {where}
        """),
        params,
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def _process_one_org(db: Session, org: dict) -> str:
    """Returns the counter bucket to increment: 'sent' | 'skipped_wrong_hour'
    | 'skipped_already_sent' | 'skipped_no_recs'."""
    tz_name = org.get("timezone") or "UTC"
    digest_hour = int(org.get("digest_hour") or 7)
    local_hour, _local_date = _local_hour_and_date(tz_name)

    if local_hour != digest_hour:
        return "skipped_wrong_hour"

    # Already sent today (local date)?
    last_sent = org.get("last_digest_sent_at")
    if last_sent:
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        if last_sent >= _utc_today_for(tz_name):
            return "skipped_already_sent"

    recs = _fetch_digest_recs(db, str(org["id"]))
    if not recs:
        # Mark as sent even with no recs so we don't re-check the same hour
        _mark_sent(db, str(org["id"]))
        return "skipped_no_recs"

    payload = _build_digest_payload(str(org["id"]), org.get("name"), tz_name, recs)

    # Find webhook_configs that subscribe to digest.daily
    endpoints = _fetch_digest_subscribers(db, str(org["id"]))
    for ep in endpoints:
        _deliver(ep, payload, org_id=str(org["id"]))

    _mark_sent(db, str(org["id"]))
    return "sent"


def _fetch_digest_recs(db: Session, org_id: str) -> list[dict]:
    """Top N pending/recent recs over last 24h, priority-ranked.
    Includes already-delivered individual recs — digest is a SUMMARY, not a
    replacement channel."""
    since = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    rows = db.execute(
        text("""
            SELECT r.id, r.insight_type, r.category, r.priority, r.confidence,
                   r.confidence_level, r.title, r.rationale, r.reason, r.action,
                   r.suggested_action, r.evidence, r.precedent_links,
                   r.subject_entity_id, r.created_at,
                   c.name AS contact_name, c.email AS contact_email
            FROM recommendations r
            LEFT JOIN contacts c ON c.id = r.subject_entity_id
            WHERE r.org_id = :oid
              AND r.created_at >= :since
              AND r.priority >= :min_p
              AND r.outcome IS NULL  -- open items only; acted/dismissed
                                     -- aren't digest-worthy anymore
            ORDER BY r.priority DESC, r.confidence DESC
            LIMIT :n
        """),
        {"oid": org_id, "since": since, "min_p": MIN_PRIORITY, "n": TOP_N},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def _fetch_digest_subscribers(db: Session, org_id: str) -> list[dict]:
    """webhook_config rows where `events` includes 'digest.daily'."""
    rows = db.execute(
        text("""
            SELECT id, url, secret
            FROM webhook_config
            WHERE org_id = :oid
              AND is_active = TRUE
              AND 'digest.daily' = ANY(events)
        """),
        {"oid": org_id},
    ).fetchall()
    return [dict(r._mapping) for r in rows]


def _build_digest_payload(org_id: str, org_name: Optional[str],
                          tz_name: str, recs: list[dict]) -> dict:
    """The webhook body an agent receives. v2-compatible shape: each rec
    keeps its full v2 payload fields (evidence, suggested_action, …)."""
    items = []
    for r in recs:
        items.append({
            "recommendation_id": str(r["id"]),
            "insight_type": r["insight_type"],
            "category": r.get("category"),
            "priority": float(r.get("priority") or 0),
            "confidence": float(r.get("confidence") or 0),
            "confidence_level": r.get("confidence_level"),
            "title": r.get("title"),
            "rationale": r.get("rationale") or r.get("reason"),
            "action_draft": r.get("action"),
            "suggested_action": r.get("suggested_action"),
            "evidence": r.get("evidence") or [],
            "precedent_links": r.get("precedent_links") or [],
            "subject": {
                "entity_id": str(r["subject_entity_id"]) if r.get("subject_entity_id") else None,
                "name": r.get("contact_name"),
                "email": r.get("contact_email"),
            },
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
        })
    return {
        "event": "digest.daily",
        "payload_version": 2,
        "digest_id": str(uuid.uuid4()),
        "org_id": org_id,
        "org_name": org_name,
        "timezone": tz_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": LOOKBACK_HOURS,
        "count": len(items),
        "items": items,
    }


def _deliver(endpoint: dict, payload: dict, *, org_id: str) -> None:
    """Fire-and-log one webhook. Errors are swallowed (per-endpoint isolation)."""
    body = json.dumps(payload, default=str)
    sig = hmac.new(
        (endpoint.get("secret") or "").encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    try:
        resp = requests.post(
            endpoint["url"],
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Genios-Signature": f"sha256={sig}",
                "X-Genios-Event": "digest.daily",
                "X-Genios-Payload-Version": "2",
            },
            timeout=WEBHOOK_TIMEOUT,
        )
        logger.info(
            f"digest delivery org={org_id} url={endpoint['url']} "
            f"status={resp.status_code} items={payload['count']}"
        )
    except Exception as e:
        logger.warning(f"digest delivery FAILED org={org_id} url={endpoint['url']}: {e}")


def _mark_sent(db: Session, org_id: str) -> None:
    try:
        db.execute(
            text("UPDATE orgs SET last_digest_sent_at = NOW() WHERE id = :oid"),
            {"oid": org_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"last_digest_sent_at update failed org={org_id}: {e}")
