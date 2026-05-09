"""
Per-connector sync — Genios actively pulls from external systems on schedule.

Mirrors the existing Gmail OAuth pull pattern, generalised to any registered
provider adapter. For each active pull connector:
  1. decrypt credentials
  2. call adapter.fetch_email(creds, since=last_sync_at)
  3. for each event: reuse the existing /v1/ingest/email insert helpers
  4. mark read on the source side
  5. update last_event_at
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import text

from app.celery_app import celery
from app.database import SessionLocal
from app.ingestion import adapters
from app.policy import connector_crud, trust_crud

logger = logging.getLogger(__name__)


def _insert_canonical_email(db, org_id: str, agent_uuid: str, ev: dict) -> Optional[str]:
    """Reuse the same insert path as POST /v1/ingest/email. Returns interaction_id
    or None if duplicate / invalid."""
    ext = (ev.get("external_id") or "").strip()
    sender = (ev.get("from_address") or "").strip().lower()
    if not ext or not sender:
        return None

    # Idempotency
    dup = db.execute(
        text("SELECT id::text FROM interactions WHERE org_id=:o AND source='email' AND external_id=:e"),
        {"o": org_id, "e": ext},
    ).fetchone()
    if dup:
        return None

    # Upsert contact
    contact_id = db.execute(
        text("SELECT id::text FROM contacts WHERE org_id=:o AND LOWER(email)=:e"),
        {"o": org_id, "e": sender},
    ).scalar()
    if not contact_id:
        contact_id = db.execute(
            text("""
                INSERT INTO contacts (org_id, email, name, segment_source)
                VALUES (:o, :e, :n, 'auto')
                RETURNING id::text
            """),
            {"o": org_id, "e": sender, "n": sender.split("@")[0]},
        ).scalar()

    trusted = trust_crud.is_trusted(db, agent_uuid, sender_email=sender, contact_id=contact_id)

    sent_at = ev.get("sent_at") or ""
    try:
        sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00")) if sent_at else datetime.now(timezone.utc)
    except Exception:
        sent_dt = datetime.now(timezone.utc)

    iid = db.execute(
        text("""
            INSERT INTO interactions
                (org_id, contact_id, agent_uuid, direction, subject, summary,
                 raw_snippet, interaction_at, source, external_id,
                 thread_external_id, interaction_kind, trusted_sender)
            VALUES (:o, :c, :a, :dir, :subj, :sum, :raw, :at, 'email', :ext, :thr, 'email', :tr)
            RETURNING id::text
        """),
        {
            "o": org_id, "c": contact_id, "a": agent_uuid,
            "dir": ev.get("direction", "inbound"),
            "subj": (ev.get("subject") or "")[:500],
            "sum": (ev.get("body_text") or ev.get("body_html") or "")[:2000],
            "raw": (ev.get("body_text") or ev.get("body_html") or "")[:5000],
            "at": sent_dt,
            "ext": ext,
            "thr": ev.get("thread_external_id") or ev.get("in_reply_to_external_id"),
            "tr": trusted,
        },
    ).scalar()
    return iid


def _insert_calendar_event(db, org_id: str, agent_uuid: str, ev: dict) -> Optional[str]:
    """Calendar event → interaction(kind='meeting'). Each attendee becomes
    a contact (upsert) and gets a row pointing at this event's external_id.
    For idempotency we de-dupe per (org, source, external_id, contact)."""
    ext = (ev.get("external_id") or "").strip()
    if not ext:
        return None

    attendees = ev.get("attendees") or []
    organizer = ev.get("organizer")
    contacts_to_record = []
    if organizer:
        contacts_to_record.append(organizer.lower())
    for a in attendees:
        if a:
            contacts_to_record.append(a.lower())
    contacts_to_record = list({c for c in contacts_to_record if c})
    if not contacts_to_record:
        return None

    sent_at = ev.get("start") or ""
    try:
        sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00")) if sent_at else datetime.now(timezone.utc)
    except Exception:
        sent_dt = datetime.now(timezone.utc)

    last_iid = None
    for email in contacts_to_record:
        # idempotency per (contact, external_id)
        contact_id = db.execute(
            text("SELECT id::text FROM contacts WHERE org_id=:o AND LOWER(email)=:e"),
            {"o": org_id, "e": email},
        ).scalar()
        if not contact_id:
            contact_id = db.execute(
                text("""
                    INSERT INTO contacts (org_id, email, name, segment_source)
                    VALUES (:o, :e, :n, 'auto')
                    RETURNING id::text
                """),
                {"o": org_id, "e": email, "n": email.split("@")[0]},
            ).scalar()

        dup = db.execute(
            text("SELECT id FROM interactions WHERE org_id=:o AND source='calendar' AND external_id=:e AND contact_id=:c"),
            {"o": org_id, "e": ext, "c": contact_id},
        ).fetchone()
        if dup:
            continue

        last_iid = db.execute(
            text("""
                INSERT INTO interactions
                    (org_id, contact_id, agent_uuid, direction, subject, summary,
                     raw_snippet, interaction_at, source, external_id, interaction_kind)
                VALUES (:o, :c, :a, 'inbound', :subj, :sum, :raw, :at, 'calendar', :ext, 'meeting')
                RETURNING id::text
            """),
            {
                "o": org_id, "c": contact_id, "a": agent_uuid,
                "subj": (ev.get("summary") or "")[:500],
                "sum":  (ev.get("description") or ev.get("location") or "")[:2000],
                "raw":  (ev.get("description") or "")[:5000],
                "at":   sent_dt,
                "ext":  ext,
            },
        ).scalar()
    return last_iid


@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_sync_connector(self, connector_id: str):
    """Sync one connector. Idempotent — safe to run repeatedly."""
    db = SessionLocal()
    accepted = 0
    duplicates = 0
    try:
        row = db.execute(
            text("""
                SELECT cc.id::text, cc.org_id::text, cc.agent_uuid::text, cc.source,
                       cc.metadata, cc.last_event_at
                FROM connector_credentials cc
                WHERE cc.id = :id AND cc.is_active = TRUE
            """),
            {"id": connector_id},
        ).fetchone()
        if not row:
            logger.warning(f"sync: connector {connector_id} not found / inactive")
            return {"connector_id": connector_id, "status": "missing"}

        provider = (row.metadata or {}).get("provider", "custom")
        ops = adapters.get(provider)
        if not ops:
            logger.warning(f"sync: no adapter for provider={provider}")
            return {"connector_id": connector_id, "status": "no_adapter", "provider": provider}

        creds = connector_crud.decrypt_metadata(row.metadata)
        since = (row.last_event_at or (datetime.now(timezone.utc) - timedelta(days=7))).isoformat()

        # Email path (Inkbox / IMAP / Gmail / Postmark / ...)
        if row.source == "email" and "fetch_email" in ops:
            try:
                events = ops["fetch_email"](creds, since)
            except PermissionError as pe:
                logger.error(f"sync: permission denied for {connector_id}: {pe}")
                return {"connector_id": connector_id, "status": "auth_failed", "error": str(pe)}
            except Exception as e:
                logger.warning(f"sync: fetch failed for {connector_id}: {e}")
                return {"connector_id": connector_id, "status": "fetch_failed", "error": str(e)[:200]}

            for ev in events:
                iid = _insert_canonical_email(db, row.org_id, row.agent_uuid, ev)
                if iid:
                    accepted += 1
                    if "mark_read" in ops:
                        try: ops["mark_read"](creds, ev.get("external_id"))
                        except Exception: pass
                else:
                    duplicates += 1

            if accepted > 0:
                db.execute(
                    text("UPDATE connector_credentials SET last_event_at = NOW() WHERE id = :id"),
                    {"id": connector_id},
                )
            db.commit()

        # Calendar path — events become interactions of kind='meeting'
        elif row.source == "calendar" and "fetch_calendar" in ops:
            try:
                events = ops["fetch_calendar"](creds, since)
            except PermissionError as pe:
                logger.error(f"sync: calendar auth failed for {connector_id}: {pe}")
                return {"connector_id": connector_id, "status": "auth_failed", "error": str(pe)}
            except Exception as e:
                logger.warning(f"sync: calendar fetch failed: {e}")
                return {"connector_id": connector_id, "status": "fetch_failed", "error": str(e)[:200]}

            for ev in events:
                iid = _insert_calendar_event(db, row.org_id, row.agent_uuid, ev)
                if iid:
                    accepted += 1
                else:
                    duplicates += 1

            if accepted > 0:
                db.execute(
                    text("UPDATE connector_credentials SET last_event_at = NOW() WHERE id = :id"),
                    {"id": connector_id},
                )
            db.commit()
        return {
            "connector_id": connector_id,
            "provider": provider,
            "source": row.source,
            "accepted": accepted,
            "duplicates": duplicates,
        }
    except Exception as e:
        db.rollback()
        logger.exception(f"sync_connector {connector_id} failed: {e}")
        try: self.retry(exc=e)
        except Exception: pass
        return {"connector_id": connector_id, "status": "error", "error": str(e)[:200]}
    finally:
        db.close()


@celery.task(queue="low_priority")
def task_sync_all_connectors():
    """Beat-triggered every 5 min. Fans out one sub-task per active connector."""
    db = SessionLocal()
    try:
        rows = db.execute(
            text("""
                SELECT id::text FROM connector_credentials
                WHERE is_active = TRUE
                  AND source IN ('email', 'phone', 'sms')
                  AND metadata ? 'api_key'  -- only pull connectors (have creds)
            """),
        ).fetchall()
        for r in rows:
            task_sync_connector.delay(r[0])
        return {"dispatched": len(rows)}
    finally:
        db.close()
