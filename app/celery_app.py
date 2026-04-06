"""
Celery configuration for GeniOS background task processing.

Broker: Redis (same Upstash instance, DB 1 to avoid cache collision).
Queues:
  - high_priority: manual syncs, recompute (user-triggered, latency-sensitive)
  - low_priority: nightly refresh, weekly reports, billing (batch work)

Worker start command:
  celery -A app.celery_app worker --loglevel=info -Q high_priority,low_priority

Celery Beat (periodic scheduler):
  celery -A app.celery_app beat --loglevel=info
"""

import os
import ssl
from celery import Celery
from celery.schedules import crontab

# Use Redis DB 1 for Celery broker (DB 0 is used for caching)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Append /1 for broker, /2 for result backend (avoid cache collision)
if REDIS_URL.endswith("/0"):
    BROKER_URL = REDIS_URL[:-2] + "/1"
    RESULT_URL = REDIS_URL[:-2] + "/2"
elif REDIS_URL[-2] == "/":
    BROKER_URL = REDIS_URL
    RESULT_URL = REDIS_URL
else:
    BROKER_URL = REDIS_URL + "/1"
    RESULT_URL = REDIS_URL + "/2"

# Add ssl_cert_reqs for rediss:// (Upstash TLS)
if BROKER_URL.startswith("rediss://"):
    BROKER_URL += "?ssl_cert_reqs=CERT_NONE"
    RESULT_URL += "?ssl_cert_reqs=CERT_NONE"

celery = Celery("genios", broker=BROKER_URL, backend=RESULT_URL)

# SSL config for rediss:// connections
_redis_ssl = REDIS_URL.startswith("rediss://")
_broker_transport_options = {}
if _redis_ssl:
    _broker_transport_options = {
        "ssl": {"ssl_cert_reqs": ssl.CERT_NONE}
    }

celery.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task routing
    task_default_queue="high_priority",
    task_queues={
        "high_priority": {"exchange": "high_priority", "routing_key": "high"},
        "low_priority": {"exchange": "low_priority", "routing_key": "low"},
    },
    # SSL for Upstash/TLS Redis
    broker_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE} if _redis_ssl else None,
    redis_backend_use_ssl={"ssl_cert_reqs": ssl.CERT_NONE} if _redis_ssl else None,
    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Result expiry (24h)
    result_expires=86400,
    # Broker connection retry
    broker_connection_retry_on_startup=True,
)


# ── Task wrappers ────────────────────────────────────────────────────────────
# Each task wraps the existing sync function with retry logic.
# The actual sync logic stays in app/tasks/*.py — unchanged.


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_gmail_sync(self, org_id: str, max_emails: int = None, account_email: str = None):
    """Gmail sync — high priority (user-triggered)."""
    try:
        from app.tasks.gmail_sync import run_gmail_sync
        run_gmail_sync(org_id, max_emails=max_emails, account_email=account_email)
    except Exception as exc:
        _mark_sync_error(org_id, str(exc))
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_calendar_sync(self, org_id: str, max_results: int = None):
    """Calendar sync — high priority."""
    try:
        from app.tasks.calendar_sync import run_calendar_sync
        run_calendar_sync(org_id, max_results=max_results)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_slack_sync(self, org_id: str):
    """Slack sync — high priority."""
    try:
        from app.tasks.slack_sync import run_slack_backfill
        run_slack_backfill(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_jira_sync(self, org_id: str):
    """Jira sync — high priority."""
    try:
        from app.tasks.jira_sync import run_jira_sync
        run_jira_sync(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_notion_sync(self, org_id: str):
    """Notion sync — high priority."""
    try:
        from app.tasks.notion_sync import run_notion_sync
        run_notion_sync(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_sheets_sync(self, org_id: str):
    """Google Sheets sync — high priority."""
    try:
        from app.tasks.sheets_sync import run_sheets_sync
        run_sheets_sync(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_drive_sync(self, org_id: str):
    """Google Drive sync — high priority."""
    try:
        from app.tasks.drive_sync import run_drive_sync
        run_drive_sync(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_docs_sync(self, org_id: str):
    """Google Docs sync — high priority."""
    try:
        from app.tasks.docs_sync import run_docs_sync
        run_docs_sync(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_hubspot_sync(self, org_id: str):
    """HubSpot sync — high priority."""
    try:
        from app.tasks.hubspot_sync import run_hubspot_sync
        run_hubspot_sync(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_recompute(self, org_id: str):
    """Tier 1 recompute — high priority."""
    try:
        from app.tasks.reextract import run_recompute
        run_recompute(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_reextract(self, org_id: str):
    """Tier 2 re-extract — high priority."""
    try:
        from app.tasks.reextract import run_reextract
        run_reextract(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_nightly_refresh(self, org_id: str = None):
    """Nightly refresh — low priority (batch work)."""
    try:
        from app.tasks.nightly_refresh import run_nightly_refresh
        run_nightly_refresh(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=1, default_retry_delay=300, queue="low_priority")
def task_weekly_reports(self, org_id: str = None):
    """Weekly reports — low priority."""
    try:
        from app.tasks.weekly_report import run_weekly_reports
        run_weekly_reports(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=1, default_retry_delay=300, queue="low_priority")
def task_billing_jobs(self):
    """Billing jobs (trial expiry emails + overage invoices) — low priority."""
    try:
        from app.database import SessionLocal
        from app.tasks.billing_jobs import run_trial_expiry_emails, run_overage_invoices
        db = SessionLocal()
        try:
            run_trial_expiry_emails(db)
            run_overage_invoices(db)
        finally:
            db.close()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(queue="low_priority")
def task_expire_plans():
    """Expire stale plans — low priority."""
    from app.database import SessionLocal
    from app.plan_enforcer import expire_stale_plans
    db = SessionLocal()
    try:
        expired = expire_stale_plans(db)
        if expired:
            print(f"Plan expiry: marked {expired} plan(s) as expired")
    finally:
        db.close()


@celery.task(queue="high_priority")
def task_sync_all_tools(org_id: str):
    """Sync all connected tools for an org (called by scheduler)."""
    from app.main import _sync_connected_tools
    _sync_connected_tools(org_id, cron=True)


# ── Celery Beat schedule (replaces sync_scheduler_loop) ──────────────────────

celery.conf.beat_schedule = {
    # Check all orgs for sync every hour
    "hourly-sync-check": {
        "task": "app.celery_app.task_scheduled_sync",
        "schedule": 3600.0,  # every hour
        "options": {"queue": "low_priority"},
    },
    # Expire stale plans every hour
    "hourly-plan-expiry": {
        "task": "app.celery_app.task_expire_plans",
        "schedule": 3600.0,
        "options": {"queue": "low_priority"},
    },
    # Billing jobs every 6 hours
    "billing-jobs": {
        "task": "app.celery_app.task_billing_jobs",
        "schedule": 21600.0,  # 6 hours
        "options": {"queue": "low_priority"},
    },
}


@celery.task(queue="low_priority")
def task_scheduled_sync():
    """
    Hourly scheduler: check each org's sync interval and trigger sync + refresh
    if overdue. Replaces the sync_scheduler_loop from main.py.
    """
    from app.database import SessionLocal
    from sqlalchemy import text as sa_text
    from datetime import datetime, timezone
    import logging

    logger = logging.getLogger(__name__)
    db = SessionLocal()

    try:
        orgs = db.execute(sa_text(
            "SELECT id, COALESCE(sync_interval_hours, 24) AS interval_hours, "
            "COALESCE(subscription_tier, 'trial') AS subscription_tier FROM orgs"
        )).fetchall()

        for org in orgs:
            plan_tier = org.subscription_tier if hasattr(org, "subscription_tier") else "trial"
            if plan_tier == "trial":
                continue  # Trial orgs: manual sync only

            last_sync = db.execute(sa_text(
                "SELECT MIN(last_synced_at) FROM oauth_tokens WHERE org_id = :oid"
            ), {"oid": str(org.id)}).scalar()

            effective_interval = org.interval_hours
            if plan_tier == "hustler":
                effective_interval = min(org.interval_hours, 6)
            interval_seconds = effective_interval * 3600

            should_run = (
                not last_sync or
                (datetime.now(timezone.utc) - last_sync.replace(tzinfo=timezone.utc)).total_seconds() >= interval_seconds
            )

            if should_run:
                logger.info(f"Queuing scheduled sync + refresh for org {org.id} (tier: {plan_tier})")
                # Queue sync + refresh as separate tasks
                task_sync_all_tools.delay(str(org.id))
                task_nightly_refresh.delay(str(org.id))
    finally:
        db.close()


def _mark_sync_error(org_id: str, error: str):
    """Mark sync status as error in DB (best-effort)."""
    try:
        from app.database import SessionLocal
        from sqlalchemy import text as sa_text
        db = SessionLocal()
        try:
            db.execute(
                sa_text("UPDATE oauth_tokens SET sync_status = 'error', sync_error = :err WHERE org_id = :oid"),
                {"oid": org_id, "err": error[:500]},
            )
            db.commit()
        finally:
            db.close()
    except Exception:
        pass
