"""
OAuth health-check — daily probe each stored token, surface broken ones.

Why this matters for a brain (not a CRM):
  Sync silently failing on an expired token = brain reasons over stale data
  for days/weeks without knowing it. Every insight, every priority, every
  recommendation degrades. The brain MUST know the freshness of its own
  inputs and report degradation to the user.

What it does:
  - For every (org_id, account_email) in oauth_tokens, ask Google whether
    the credential still works (cheap getProfile call).
  - On failure, write a short status entry to Redis with a 25h TTL so the
    /v1/sync surface can render `health: degraded` until the next probe.
  - Best-effort only: failures here never block the daily sync — they just
    inform the user that something needs attention.

Schedule: daily, low priority queue (see app/celery_app.py beat_schedule).
"""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

from app.database import SessionLocal
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

HEALTH_TTL_SEC = 25 * 3600  # 25h — outlives the daily run with a small overlap
_HEALTH_PREFIX = "oauth:health:"


def _key(org_id: str, account_email: str) -> str:
    return f"{_HEALTH_PREFIX}{org_id}:{account_email}"


def get_health(org_id: str, account_email: str) -> dict[str, Any] | None:
    """Read cached health status for (org, email). Returns None if never probed."""
    raw = redis_client.get(_key(org_id, account_email))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _probe_google(access_token: str, refresh_token: str | None) -> tuple[str, str | None]:
    """Probe a Google credential. Returns (status, error_message).

    status ∈ {"healthy", "refreshed", "broken"}
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError as e:
        return "broken", f"missing google deps: {e}"

    try:
        # Build credentials from stored tokens. The Google client auto-refreshes
        # access_token using refresh_token when expired — capture whether that
        # actually happened so we can report "refreshed" distinctly.
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
        )
        was_expired = creds.expired
        if was_expired and refresh_token:
            creds.refresh(Request())

        # Cheapest possible call that exercises auth: gmail users.getProfile.
        svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
        svc.users().getProfile(userId="me").execute(num_retries=0)
        return ("refreshed" if was_expired else "healthy"), None
    except Exception as e:  # noqa: BLE001 — surface as health=broken
        return "broken", str(e)[:200]


def run_oauth_healthcheck(org_id: str | None = None) -> dict[str, int]:
    """Probe every Google oauth_tokens row; cache result.

    Returns a small summary {"checked": N, "healthy": A, "refreshed": B, "broken": C}.
    """
    db = SessionLocal()
    summary = {"checked": 0, "healthy": 0, "refreshed": 0, "broken": 0}
    try:
        where = "WHERE provider = 'google' OR provider IS NULL"
        params: dict[str, Any] = {}
        if org_id:
            where += " AND org_id = :org_id"
            params["org_id"] = org_id

        rows = db.execute(
            text(f"""
                SELECT org_id,
                       COALESCE(account_email, 'default') AS account_email,
                       access_token,
                       refresh_token
                FROM oauth_tokens
                {where}
            """),
            params,
        ).fetchall()

        for r in rows:
            summary["checked"] += 1
            status, err = _probe_google(r.access_token, r.refresh_token)
            summary[status] = summary.get(status, 0) + 1

            payload = {
                "status": status,
                "checked_at": _now_iso(),
                "error": err,
            }
            try:
                redis_client.setex(_key(str(r.org_id), r.account_email), HEALTH_TTL_SEC, json.dumps(payload))
            except Exception as e:
                logger.warning("oauth_healthcheck cache write failed: %s", e)

        logger.info("oauth_healthcheck: %s", summary)
        return summary
    finally:
        db.close()


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
