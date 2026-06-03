"""
Proactive watch-channel renewal (Phase 1.3).

Google's Gmail / Calendar / Drive push channels expire after 7 days. The
existing calendar_sync task renews inline, but only runs when a sync is
scheduled. This task scans all stored channels nightly and renews anything
expiring within the safety window — independent of sync cadence.

Touches Gmail watches (via gmail.users().watch) and Calendar watches.
Drive watches are left for a later phase.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)

# Renew if the watch expires within this window.
RENEWAL_WINDOW_HOURS = 36  # covers >1 missed nightly run


# ── Calendar ──────────────────────────────────────────────────────────────────

def _renew_calendar_watches(db) -> dict:
    """Find calendar watch channels expiring soon and re-subscribe."""
    webhook_url = os.getenv("GOOGLE_CALENDAR_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("renew_watches: GOOGLE_CALENDAR_WEBHOOK_URL not set; skipping calendar")
        return {"checked": 0, "renewed": 0, "skipped_no_env": True}

    cutoff = datetime.now(timezone.utc) + timedelta(hours=RENEWAL_WINDOW_HOURS)

    rows = db.execute(
        text("""
            SELECT org_id, calendar_id, watch_channel_id, watch_expiry
            FROM calendar_sync_state
            WHERE watch_channel_id IS NOT NULL
              AND (watch_expiry IS NULL OR watch_expiry <= :cutoff)
        """),
        {"cutoff": cutoff},
    ).fetchall()

    renewed = 0
    from app.ingestion.calendar_connector import setup_watch_channel
    from app.tasks.calendar_sync import _get_calendar_tokens
    from app.ingestion.calendar_connector import build_calendar_service

    for row in rows:
        org_id = str(row.org_id)
        try:
            tokens = _get_calendar_tokens(db, org_id)
            if not tokens:
                continue
            service = build_calendar_service(tokens.access_token, tokens.refresh_token)
            channel_token = str(uuid.uuid4())
            result = setup_watch_channel(service, row.calendar_id, webhook_url, channel_token=channel_token)
            db.execute(
                text("""
                    UPDATE calendar_sync_state
                    SET watch_channel_id = :cid,
                        watch_expiry = to_timestamp(:expiry_ms / 1000.0),
                        channel_token = :token,
                        updated_at = NOW()
                    WHERE org_id = :oid AND calendar_id = :cal_id
                """),
                {
                    "cid": result.get("id"),
                    "expiry_ms": result.get("expiration", 0),
                    "token": channel_token,
                    "oid": org_id,
                    "cal_id": row.calendar_id,
                },
            )
            db.commit()
            renewed += 1
            logger.info(f"renew_watches: renewed calendar for org={org_id} cal={row.calendar_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"renew_watches: calendar renewal failed for org={org_id}: {e}")

    return {"checked": len(rows), "renewed": renewed}


# ── Gmail ─────────────────────────────────────────────────────────────────────

def _renew_gmail_watches(db) -> dict:
    """
    Re-subscribe every Gmail account to Pub/Sub push. Gmail watches last 7 days
    and Google doesn't expose expiry, so we always renew — the call is idempotent
    (a new watch replaces the old).
    """
    topic = os.getenv("GMAIL_PUBSUB_TOPIC")
    if not topic:
        logger.warning("renew_watches: GMAIL_PUBSUB_TOPIC not set; skipping gmail")
        return {"checked": 0, "renewed": 0, "skipped_no_env": True}

    rows = db.execute(
        text("""
            SELECT org_id, account_email, access_token, refresh_token
            FROM oauth_tokens
            WHERE provider = 'google'
              AND account_email NOT LIKE '%:%'
              AND account_email LIKE '%@%'
        """)
    ).fetchall()

    renewed = 0
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build as google_build

    for row in rows:
        org_id = str(row.org_id)
        try:
            creds = Credentials(
                token=row.access_token,
                refresh_token=row.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            )
            gmail = google_build("gmail", "v1", credentials=creds, cache_discovery=False)
            gmail.users().watch(
                userId="me",
                body={"labelIds": ["INBOX"], "topicName": topic},
            ).execute()
            renewed += 1
            logger.info(f"renew_watches: renewed gmail for org={org_id} ({row.account_email})")
        except Exception as e:
            logger.error(f"renew_watches: gmail renewal failed for org={org_id} ({row.account_email}): {e}")

    return {"checked": len(rows), "renewed": renewed}


# ── Entry point ───────────────────────────────────────────────────────────────

def run_renew_watches() -> dict:
    db = SessionLocal()
    try:
        cal = _renew_calendar_watches(db)
        gm = _renew_gmail_watches(db)
        logger.info(f"renew_watches summary: calendar={cal} gmail={gm}")
        return {"calendar": cal, "gmail": gm}
    finally:
        db.close()
