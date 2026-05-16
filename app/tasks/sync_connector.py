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

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import text

from app.celery_app import celery
from app.database import SessionLocal
from app.ingestion import adapters
from app.policy import connector_crud, trust_crud

logger = logging.getLogger(__name__)


def _parse_ts(s) -> datetime:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else datetime.now(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _upsert_contact_by_phone(db, org_id: str, phone: str) -> Optional[str]:
    p = (phone or "").strip()
    if not p:
        return None
    cid = db.execute(
        text("SELECT id::text FROM contacts WHERE org_id=:o AND metadata @> :m LIMIT 1"),
        {"o": org_id, "m": json.dumps({"phone": p})},
    ).scalar()
    if cid:
        return cid
    return db.execute(
        text("""
            INSERT INTO contacts (org_id, email, name, metadata, segment_source)
            VALUES (:o, :n, :n, :m, 'auto')
            RETURNING id::text
        """),
        {"o": org_id, "n": p, "m": json.dumps({"phone": p})},
    ).scalar()


def _insert_canonical_email(db, org_id: str, agent_uuid: Optional[str],
                            account_id: Optional[str], ev: dict) -> Optional[str]:
    """Phase 12: workspace-keyed insert. account_id is the connector_credentials.id
    of the source — read-time scope filter joins against agent_account_grants.
    `agent_uuid` is kept for forensic audit only."""
    ext = (ev.get("external_id") or "").strip()
    sender = (ev.get("from_address") or "").strip().lower()
    if not ext or not sender:
        return None

    dup = db.execute(
        text("SELECT id::text FROM interactions WHERE org_id=:o AND source='email' AND external_id=:e"),
        {"o": org_id, "e": ext},
    ).fetchone()
    if dup:
        return None

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

    sent_at = ev.get("sent_at") or ""
    try:
        sent_dt = datetime.fromisoformat(sent_at.replace("Z", "+00:00")) if sent_at else datetime.now(timezone.utc)
    except Exception:
        sent_dt = datetime.now(timezone.utc)

    iid = db.execute(
        text("""
            INSERT INTO interactions
                (org_id, contact_id, agent_uuid, account_id, direction, subject, summary,
                 raw_snippet, raw_body, interaction_at, source, external_id,
                 thread_external_id, interaction_kind, extraction_status)
            VALUES (:o, :c, :a, :acct, :dir, :subj, :sum, :raw, :body, :at, 'email', :ext, :thr, 'email', 'pending')
            RETURNING id::text
        """),
        {
            "o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
            "dir": ev.get("direction", "inbound"),
            "subj": (ev.get("subject") or "")[:500],
            "sum": (ev.get("body_text") or ev.get("body_html") or "")[:2000],
            "raw": (ev.get("body_text") or ev.get("body_html") or "")[:5000],
            "body": ev.get("body_text") or ev.get("body_html") or "",
            "at": sent_dt,
            "ext": ext,
            "thr": ev.get("thread_external_id") or ev.get("in_reply_to_external_id"),
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


def _insert_canonical_sms(db, org_id: str, agent_uuid: Optional[str],
                          account_id: Optional[str], ev: dict) -> Optional[str]:
    """SMS/MMS event → interaction(kind='sms', source='sms'). Contact keyed by
    the remote phone number. Idempotent on (org, source='sms', external_id)."""
    ext = (ev.get("external_id") or "").strip()
    number = (ev.get("remote_number") or ev.get("from_number") or ev.get("to_number") or "").strip()
    if not ext or not number:
        return None
    if db.execute(
        text("SELECT 1 FROM interactions WHERE org_id=:o AND source='sms' AND external_id=:e"),
        {"o": org_id, "e": ext},
    ).fetchone():
        return None
    contact_id = _upsert_contact_by_phone(db, org_id, number)
    if not contact_id:
        return None
    body = (ev.get("body") or ev.get("text") or "")
    # Item #6: explicitly set interaction_type='sms' so channel recommendation
    # can recognize the channel. Without this, default ('other') was set and
    # the SMS channel was invisible to get_contact_channel_profile().
    return db.execute(
        text("""
            INSERT INTO interactions
                (org_id, contact_id, agent_uuid, account_id, direction, summary,
                 raw_snippet, interaction_at, source, external_id,
                 interaction_kind, interaction_type)
            VALUES (:o, :c, :a, :acct, :dir, :sum, :raw, :at, 'sms', :ext,
                    'sms', 'sms')
            RETURNING id::text
        """),
        {
            "o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
            "dir": ev.get("direction") or "inbound",
            "sum": body[:2000], "raw": body[:5000],
            "at": _parse_ts(ev.get("sent_at")), "ext": ext,
        },
    ).scalar()


def _insert_canonical_call(db, org_id: str, agent_uuid: Optional[str],
                           account_id: Optional[str], ev: dict) -> Optional[str]:
    """Voice-call event → interaction(kind='call', source='phone') with
    duration_sec + transcript. Idempotent on (org, source='phone', external_id)."""
    ext = (ev.get("external_id") or "").strip()
    number = (ev.get("remote_number") or ev.get("from_number") or ev.get("to_number") or "").strip()
    if not ext or not number:
        return None
    if db.execute(
        text("SELECT 1 FROM interactions WHERE org_id=:o AND source='phone' AND external_id=:e"),
        {"o": org_id, "e": ext},
    ).fetchone():
        return None
    contact_id = _upsert_contact_by_phone(db, org_id, number)
    if not contact_id:
        return None
    try:
        dur = int(ev.get("duration_sec") or 0)
    except (TypeError, ValueError):
        dur = 0
    transcript = ev.get("transcript") or ""
    summary = transcript if transcript else f"Call ({dur}s)"
    # Item #6: set interaction_type='call' explicitly so channel
    # recommendation can score the call channel correctly.
    return db.execute(
        text("""
            INSERT INTO interactions
                (org_id, contact_id, agent_uuid, account_id, direction, summary,
                 raw_snippet, interaction_at, source, external_id,
                 interaction_kind, interaction_type, duration_sec, transcript)
            VALUES (:o, :c, :a, :acct, :dir, :sum, :raw, :at, 'phone', :ext,
                    'call', 'call', :dur, :tr)
            RETURNING id::text
        """),
        {
            "o": org_id, "c": contact_id, "a": agent_uuid, "acct": account_id,
            "dir": ev.get("direction") or "inbound",
            "sum": summary[:2000], "raw": transcript[:5000],
            "at": _parse_ts(ev.get("started_at")), "ext": ext,
            "dur": dur, "tr": transcript or None,
        },
    ).scalar()


def _set_sync_status(db, connector_id: str, status: str,
                     error: Optional[str] = None,
                     accepted: int = 0,
                     reset_failures: bool = False):
    """Phase 12 polish: write last_sync_status / error / at on every sync run.
    Bumps consecutive_failures on failure, resets on success."""
    err = (error or "")[:500] if error else None
    if reset_failures or status == "success":
        db.execute(
            text("""
                UPDATE connector_credentials
                SET last_sync_status = :s,
                    last_sync_error  = :e,
                    last_sync_at     = NOW(),
                    last_email_count = :n,
                    consecutive_failures = 0
                WHERE id = :id
            """),
            {"s": status, "e": err, "n": accepted, "id": connector_id},
        )
    else:
        db.execute(
            text("""
                UPDATE connector_credentials
                SET last_sync_status = :s,
                    last_sync_error  = :e,
                    last_sync_at     = NOW(),
                    consecutive_failures = COALESCE(consecutive_failures, 0) + 1
                WHERE id = :id
            """),
            {"s": status, "e": err, "id": connector_id},
        )
    db.commit()


@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_sync_connector(self, connector_id: str):
    """Sync one connector. Idempotent — safe to run repeatedly.
    Writes last_sync_status on every outcome (success / auth_failed / failed)."""
    db = SessionLocal()
    accepted = 0
    duplicates = 0
    try:
        # Concurrency guard: atomically claim the row by flipping
        # last_sync_status -> 'syncing' only if no peer is mid-sync. The
        # 5-minute staleness check breaks the lock if a crashed peer left
        # the flag set. Returning rows here means we won the race; an empty
        # result means a peer is already syncing this connector — return
        # immediately rather than racing and overwriting their status.
        row = db.execute(
            text("""
                UPDATE connector_credentials
                SET last_sync_status = 'syncing',
                    last_sync_at    = NOW()
                WHERE id = :id
                  AND is_active = TRUE
                  AND (
                      last_sync_status IS NULL
                      OR last_sync_status != 'syncing'
                      OR last_sync_at IS NULL
                      OR last_sync_at < NOW() - INTERVAL '5 minutes'
                  )
                RETURNING id::text, org_id::text, agent_uuid::text, source,
                          metadata, last_event_at
            """),
            {"id": connector_id},
        ).fetchone()
        db.commit()
        if not row:
            logger.info(
                f"sync: connector {connector_id} not found / inactive / locked by peer — skipping"
            )
            return {"connector_id": connector_id, "status": "skipped_locked"}

        provider = (row.metadata or {}).get("provider", "custom")
        ops = adapters.get(provider)
        if not ops:
            _set_sync_status(db, connector_id, "failed", error=f"No adapter for provider '{provider}'")
            return {"connector_id": connector_id, "status": "no_adapter", "provider": provider}

        try:
            creds = connector_crud.decrypt_metadata(row.metadata)
        except connector_crud.ConnectorDecryptError as de:
            # Surface the real cause (key mismatch / corrupted token) on the
            # connector row so the dashboard shows a useful error instead of
            # the misleading 'api_key required in credentials' downstream.
            _set_sync_status(db, connector_id, "auth_failed", error=str(de))
            return {"connector_id": connector_id, "status": "decrypt_failed", "error": str(de)}

        # On a cold start (no prior events) reach back 30 days so the mailbox
        # arrives with real history; afterwards we only need what's new.
        since = (row.last_event_at or (datetime.now(timezone.utc) - timedelta(days=30))).isoformat()

        # Email path (Inkbox / IMAP / Gmail / Postmark / ...)
        if row.source == "email" and "fetch_email" in ops:
            try:
                events = ops["fetch_email"](creds, since)
            except PermissionError as pe:
                logger.error(f"sync: permission denied for {connector_id}: {pe}")
                _set_sync_status(db, connector_id, "auth_failed", error=str(pe))
                return {"connector_id": connector_id, "status": "auth_failed", "error": str(pe)}
            except Exception as e:
                logger.warning(f"sync: fetch failed for {connector_id}: {e}")
                _set_sync_status(db, connector_id, "failed", error=str(e))
                return {"connector_id": connector_id, "status": "fetch_failed", "error": str(e)[:200]}

            for ev in events:
                iid = _insert_canonical_email(db, row.org_id, row.agent_uuid, connector_id, ev)
                if iid:
                    accepted += 1
                    # Optional: some adapters (e.g. Gmail) expose mark_read; the
                    # email-server adapters (Inkbox, IMAP) deliberately do not —
                    # the brain doesn't mutate the customer's mailbox.
                    if "mark_read" in ops:
                        try: ops["mark_read"](creds, ev)
                        except Exception: pass
                else:
                    duplicates += 1

            if accepted > 0:
                db.execute(
                    text("UPDATE connector_credentials SET last_event_at = NOW() WHERE id = :id"),
                    {"id": connector_id},
                )
            db.commit()
            _set_sync_status(db, connector_id, "success", accepted=accepted)

        # Calendar path — events become interactions of kind='meeting'
        elif row.source == "calendar" and "fetch_calendar" in ops:
            try:
                events = ops["fetch_calendar"](creds, since)
            except PermissionError as pe:
                _set_sync_status(db, connector_id, "auth_failed", error=str(pe))
                return {"connector_id": connector_id, "status": "auth_failed", "error": str(pe)}
            except Exception as e:
                _set_sync_status(db, connector_id, "failed", error=str(e))
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
            _set_sync_status(db, connector_id, "success", accepted=accepted)

        # SMS path — Inkbox texts become interactions of kind='sms'
        elif row.source == "sms" and "fetch_sms" in ops:
            try:
                events = ops["fetch_sms"](creds, since)
            except PermissionError as pe:
                _set_sync_status(db, connector_id, "auth_failed", error=str(pe))
                return {"connector_id": connector_id, "status": "auth_failed", "error": str(pe)}
            except Exception as e:
                _set_sync_status(db, connector_id, "failed", error=str(e))
                return {"connector_id": connector_id, "status": "fetch_failed", "error": str(e)[:200]}
            for ev in events:
                iid = _insert_canonical_sms(db, row.org_id, row.agent_uuid, connector_id, ev)
                if iid: accepted += 1
                else: duplicates += 1
            if accepted > 0:
                db.execute(text("UPDATE connector_credentials SET last_event_at = NOW() WHERE id = :id"), {"id": connector_id})
            db.commit()
            _set_sync_status(db, connector_id, "success", accepted=accepted)

        # Voice-call path — Inkbox calls (+ transcripts) become kind='call'
        elif row.source == "phone" and "fetch_calls" in ops:
            try:
                events = ops["fetch_calls"](creds, since)
            except PermissionError as pe:
                _set_sync_status(db, connector_id, "auth_failed", error=str(pe))
                return {"connector_id": connector_id, "status": "auth_failed", "error": str(pe)}
            except Exception as e:
                _set_sync_status(db, connector_id, "failed", error=str(e))
                return {"connector_id": connector_id, "status": "fetch_failed", "error": str(e)[:200]}
            for ev in events:
                iid = _insert_canonical_call(db, row.org_id, row.agent_uuid, connector_id, ev)
                if iid: accepted += 1
                else: duplicates += 1
            if accepted > 0:
                db.execute(text("UPDATE connector_credentials SET last_event_at = NOW() WHERE id = :id"), {"id": connector_id})
            db.commit()
            _set_sync_status(db, connector_id, "success", accepted=accepted)

        else:
            _set_sync_status(db, connector_id, "failed", error=f"No fetch handler for source '{row.source}'")

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
        try: _set_sync_status(db, connector_id, "failed", error=str(e))
        except Exception: pass
        try: self.retry(exc=e)
        except Exception: pass
        return {"connector_id": connector_id, "status": "error", "error": str(e)[:200]}
    finally:
        db.close()


def _discover_inkbox_phone_channels(db) -> int:
    """For every active Inkbox email connector, run phone discovery so that
    SMS + voice connector rows show up automatically when the client provisions
    a phone number AFTER initial connect. Idempotent: skips numbers already
    represented in connector_credentials. Returns count of newly created rows."""
    from app.policy import connector_crud
    from app.ingestion.adapters import inkbox as _inkbox
    rows = db.execute(text("""
        SELECT org_id::text, metadata
        FROM connector_credentials
        WHERE is_active = TRUE
          AND source = 'email'
          AND metadata->>'provider' = 'inkbox'
    """)).fetchall()
    created = 0
    for org_id, meta in rows:
        try:
            creds = connector_crud.decrypt_metadata(meta)
        except connector_crud.ConnectorDecryptError:
            continue  # key mismatch — surfaced separately via sync error
        api_key = creds.get("api_key")
        if not api_key:
            continue
        try:
            numbers = _inkbox.list_phone_numbers({"api_key": api_key})
        except Exception as e:
            logger.debug(f"inkbox phone discovery skipped for org={org_id}: {e}")
            continue
        for entry in numbers:
            pnid = (entry or {}).get("phone_number_id")
            if not pnid:
                continue
            for src in ("sms", "phone"):
                exists = db.execute(text("""
                    SELECT 1 FROM connector_credentials
                    WHERE org_id = :o AND source = :s AND is_active = TRUE
                      AND metadata->>'provider' = 'inkbox'
                      AND metadata->>'phone_number_id' = :p
                    LIMIT 1
                """), {"o": org_id, "s": src, "p": str(pnid)}).fetchone()
                if exists:
                    continue
                md = {"provider": "inkbox", "api_key": api_key, "phone_number_id": str(pnid)}
                if entry.get("phone_number"):
                    md["phone_number"] = entry["phone_number"]
                connector_crud.upsert(db, org_id, agent_uuid=None, source=src, metadata=md)
                created += 1
    if created:
        db.commit()
        logger.info(f"inkbox phone discovery: created {created} new connector rows")
    return created


@celery.task(queue="low_priority")
def task_sync_all_connectors():
    """Beat-triggered every 5 min. Fans out one sub-task per active workspace
    connector that has pull credentials (Phase 12: workspace-level only —
    legacy per-agent rows still picked up for back-compat until migrated).

    Also runs phone discovery for Inkbox connectors so SMS/voice channels
    auto-provision when the client adds a phone number in Inkbox console
    after the initial email connect."""
    db = SessionLocal()
    try:
        try:
            _discover_inkbox_phone_channels(db)
        except Exception as e:
            logger.warning(f"inkbox phone discovery failed: {e}")
        rows = db.execute(
            text("""
                SELECT id::text FROM connector_credentials
                WHERE is_active = TRUE
                  AND source IN ('email', 'phone', 'sms', 'calendar')
                  AND (metadata ? 'api_key' OR metadata ? 'password')
            """),
        ).fetchall()
        for r in rows:
            task_sync_connector.delay(r[0])
        return {"dispatched": len(rows)}
    finally:
        db.close()
