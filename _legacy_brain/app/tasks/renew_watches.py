"""Renew Google watch channels nightly.

Gmail Pub/Sub push channels expire after 7 days. Calendar push state lived in
v1's `calendar_sync_state` table, which was dropped in migration 0015 — the
v2 thin pipe pulls Calendar on schedule instead. Only Gmail watch renewal
remains here; it reads `oauth_tokens` (v1 auth schema, still authoritative).
"""

import logging
import os

from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)


def _renew_gmail_watches(db) -> dict:
    """Re-subscribe every Gmail account to Pub/Sub push. Idempotent — a new
    watch replaces the old."""
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


def run_renew_watches() -> dict:
    db = SessionLocal()
    try:
        gm = _renew_gmail_watches(db)
        logger.info(f"renew_watches summary: gmail={gm}")
        return {"gmail": gm}
    finally:
        db.close()
