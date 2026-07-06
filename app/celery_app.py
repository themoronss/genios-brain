"""
Celery configuration for GeniOS background task processing.

Broker: Redis (same Upstash instance; keys namespaced via global_keyprefix so
they don't collide with the app cache). No result backend — task return values
are discarded (nothing calls .get()), which roughly halves Redis traffic.
Queues:
  - high_priority: manual syncs, recompute (user-triggered, latency-sensitive)
  - low_priority: nightly refresh, weekly reports, billing (batch work)
  - brain_router: the event-stream router tick

Worker start command (must include brain_router; --without-* cuts Redis chatter):
  celery -A app.celery_app worker --loglevel=info \
      -Q high_priority,low_priority,brain_router \
      --without-gossip --without-mingle --without-heartbeat

Celery Beat (periodic scheduler):
  celery -A app.celery_app beat --loglevel=info
"""

import logging
import os
import ssl
from celery import Celery
from celery.schedules import crontab

logger = logging.getLogger(__name__)


# The direct-HTTP PostHog sender (app/core/analytics.py) needs no per-process
# setup inside forked Celery workers — it uses a plain urllib POST, not the
# posthog library's background thread (which doesn't survive fork). The old
# worker_process_init sync_mode hook was removed along with the posthog dep.

# Single-DB Redis: managed providers like Upstash only expose DB 0.
# Celery namespaces its broker keys via `global_keyprefix` so they don't
# collide with the cache.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BROKER_URL = REDIS_URL

# TLS cert verification for rediss:// (Upstash etc.). Default is CERT_NONE to
# preserve existing behaviour (and avoid a hard outage if the provider's cert
# chain isn't in the system CA bundle). Once verified, set
# REDIS_SSL_CERT_REQS=required in the environment to silence the MITM warning.
_SSL_CERT_REQS = {
    "none":     ssl.CERT_NONE,
    "optional": ssl.CERT_OPTIONAL,
    "required": ssl.CERT_REQUIRED,
}
_ssl_cert_reqs = _SSL_CERT_REQS.get(os.getenv("REDIS_SSL_CERT_REQS", "none").lower(), ssl.CERT_NONE)
_ssl_cert_reqs_name = {ssl.CERT_NONE: "CERT_NONE", ssl.CERT_OPTIONAL: "CERT_OPTIONAL", ssl.CERT_REQUIRED: "CERT_REQUIRED"}[_ssl_cert_reqs]
_redis_ssl = REDIS_URL.startswith("rediss://")
if _redis_ssl:
    sep = "&" if "?" in BROKER_URL else "?"
    BROKER_URL += f"{sep}ssl_cert_reqs={_ssl_cert_reqs_name}"

# No result backend: we never call .get()/.ready() on task results anywhere,
# and writing every task's result to Redis (with a 24h TTL) was the single
# biggest consumer of the Upstash request quota. Disabling it cuts Redis
# traffic roughly in half. Tasks return values are simply discarded.
celery = Celery(
    "genios",
    broker=BROKER_URL,
    backend=None,
    # app.tasks.sync_connector was the v1 per-connector pull module — it was
    # deleted in the g-i-1 migration when v2 sync_runner replaced it. Worker
    # was still trying to `include` it at startup, which raises
    # ModuleNotFoundError and Celery exits non-zero before any task runs.
    # task_scheduled_sync (v2) lives in this file and is autoloaded.
    include=[],
)

# How often the brain router polls the event stream, and how often pending
# webhooks are flushed. Both were sub-minute (15s / 30s) — together ~8.6k
# task dispatches/day, each costing several Redis commands. Bumped to 60s by
# default (override via env if you need lower latency). The event_log debounce
# window is 30s and webhook delivery has durable retry, so this only adds a few
# tens of seconds of latency, not correctness.
BRAIN_ROUTER_INTERVAL_SEC = float(os.getenv("BRAIN_ROUTER_INTERVAL_SEC", "60"))
WEBHOOK_DELIVERY_INTERVAL_SEC = float(os.getenv("WEBHOOK_DELIVERY_INTERVAL_SEC", "60"))

celery.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # No result backend — see comment above.
    result_backend=None,
    task_ignore_result=True,
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task routing
    task_default_queue="high_priority",
    task_queues={
        "high_priority": {"exchange": "high_priority", "routing_key": "high"},
        "low_priority": {"exchange": "low_priority", "routing_key": "low"},
        "brain_router": {"exchange": "brain_router", "routing_key": "brain"},
    },
    # SSL for Upstash/TLS Redis
    broker_use_ssl={"ssl_cert_reqs": _ssl_cert_reqs} if _redis_ssl else None,
    # Single-DB namespacing (so broker keys don't collide with the cache)
    broker_transport_options={"global_keyprefix": "genios:celery:"},
    # Reliability
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Broker connection retry
    broker_connection_retry_on_startup=True,
)


# ── Task wrappers ────────────────────────────────────────────────────────────
# Each task wraps the existing sync function with retry logic.
# The actual sync logic stays in app/tasks/*.py — unchanged.


def _plan_blocks_sync(org_id: str) -> tuple[bool, str]:
    """Re-check plan status at task EXECUTION time.

    Beat queues tasks based on a 30s plan cache, so a plan that expired
    between queue-time and execution-time would still run and burn credits.
    This helper re-reads the org row directly (cache-bypassing) and reports
    whether the task should bail.

    Returns (blocked: bool, reason: str).
    """
    try:
        from app.database import SessionLocal
        from app.plan_enforcer import (
            _plan_cache_invalidate, get_org_plan,
            is_plan_expired, is_in_grace,
        )
        _plan_cache_invalidate(org_id)
        db = SessionLocal()
        try:
            plan = get_org_plan(db, org_id)
        finally:
            db.close()
        if is_plan_expired(plan):
            return True, "plan_expired"
        if is_in_grace(plan):
            # Grace = read-only. Sync writes new data, so block.
            return True, "plan_grace_readonly"
        return False, ""
    except Exception as e:
        # Fail-open on infra issues so a DB blip doesn't halt all sync work.
        import logging
        logging.getLogger(__name__).warning(f"_plan_blocks_sync errored, fail-open: {e}")
        return False, ""


@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_gmail_sync(self, org_id: str, max_emails: int = None, account_email: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_gmail_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_gmail_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_calendar_sync(self, org_id: str, max_results: int = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_calendar_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_calendar_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_slack_sync(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_slack_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_slack_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_jira_sync(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_jira_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_jira_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_notion_sync(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_notion_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_notion_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_sheets_sync(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_sheets_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_sheets_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_drive_sync(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_drive_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_drive_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_docs_sync(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_docs_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_docs_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_hubspot_sync(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_hubspot_sync called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_hubspot_sync"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_recompute(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_recompute called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_recompute"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_reextract(self, org_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_reextract called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_reextract"}




@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_nightly_refresh(self, org_id: str = None):
    """Stub — v1 nightly refresh code is gone (read tables dropped in mig 0015).
    Per g-i-1 plan there is no nightly batch refresh; lifecycle + brain router
    keep state hot in-process."""
    import logging
    logging.getLogger(__name__).warning(
        "task_nightly_refresh called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_nightly_refresh"}


@celery.task(bind=True, max_retries=1, default_retry_delay=300, queue="low_priority")
def task_weekly_reports(self, org_id: str = None):
    """Stub — v1 weekly_report read 5 dropped tables (contacts/commitments/
    context_calls/graph_intelligence_reports). No v2 weekly digest yet."""
    import logging
    logging.getLogger(__name__).warning(
        "task_weekly_reports called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_weekly_reports"}


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
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_sync_all_tools called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_sync_all_tools"}




# ── Phase 3-6 background tasks ──────────────────────────────────────────────

@celery.task(bind=True, max_retries=1, default_retry_delay=300, queue="low_priority")
def task_morning_digest(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_morning_digest called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_morning_digest"}




@celery.task(bind=True, max_retries=1, default_retry_delay=600, queue="low_priority")
def task_precedent_writer(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_precedent_writer called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_precedent_writer"}




@celery.task(bind=True, max_retries=1, default_retry_delay=600, queue="low_priority")
def task_hebbian_nightly(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_hebbian_nightly called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_hebbian_nightly"}




@celery.task(bind=True, max_retries=1, default_retry_delay=600, queue="low_priority")
def task_auto_merge(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_auto_merge called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_auto_merge"}




@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_score_writer(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_score_writer called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_score_writer"}




@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_classify_contacts(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_classify_contacts called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_classify_contacts"}




@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_anomaly_scan(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_anomaly_scan called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_anomaly_scan"}


@celery.task(bind=True, max_retries=2, default_retry_delay=120, queue="low_priority")
def task_proactive_scan(self, org_id: str = None):
    """Periodic (hourly) safety net for slow-burn rules.

    The g-i-4 event subscriber fires the proactive pipeline ~5s after the
    last MemoryItem of a CSV/sync burst — that's the fast path. This task
    catches the cases the fast path can't:

      * A rule whose condition changes purely because today's date moved
        (e.g. `client_late_count_90d` crosses 3 because an old invoice
        is now within the 90d window).
      * A run where the in-process Timer was lost (process restart,
        worker bounce, OOM).
      * Re-evaluation if a customer added/edited rules without
        re-uploading data.

    The 24h signature dedupe inside `pipeline.run_for_org` keeps this
    safe to run on every org every hour: insights already fired in the
    last 24h are suppressed, so the customer doesn't get duplicate
    webhooks.

    When called with no `org_id`, iterates over all active orgs in the
    DB. With `org_id`, runs for just that one tenant (used by ops
    tooling + the Beat scheduler in single-org test setups).
    """
    import logging
    from sqlalchemy import text

    from core.foundations.db import get_session
    from core.proactive.pipeline import run_all_for_org

    log = logging.getLogger(__name__)
    summary = {"orgs_scanned": 0, "insights_fired_total": 0, "errors": []}

    try:
        with get_session() as session:
            if org_id:
                org_ids = [org_id]
            else:
                org_ids = [
                    str(row[0])
                    for row in session.execute(text("SELECT id FROM orgs")).fetchall()
                ]
    except Exception as e:
        log.exception(f"task_proactive_scan org lookup failed: {e}")
        raise self.retry(exc=e)

    for oid in org_ids:
        try:
            with get_session() as session:
                result = run_all_for_org(session, org_id=oid, source="cron")
                session.commit()
                summary["orgs_scanned"] += 1
                summary["insights_fired_total"] += int(
                    result.get("insights_fired_total") or 0
                )
        except Exception as e:
            log.warning(f"task_proactive_scan org={oid} failed: {e}")
            summary["errors"].append({"org_id": oid, "error": str(e)[:200]})

    log.info(f"task_proactive_scan complete: {summary}")
    return summary


@celery.task(bind=True, max_retries=2, default_retry_delay=300, queue="low_priority")
def task_generate_hypotheses(self, org_id: str = None):
    """g-i-4 Phase 3 — daily LLM hypothesis pass per org.

    Reads the last 7 days of facts, asks Sonnet for up to 3 non-obvious
    patterns, runs an adversarial refute pass on each, persists
    survivors as proactive_insights with type=risk/opportunity and
    delivery_route=notify (never autonomous — hypotheses always go to
    a human first).

    7-day signature dedupe inside the hypothesizer keeps re-runs cheap;
    re-emitting the same hypothesis within a week is suppressed.
    """
    import logging
    from sqlalchemy import text

    from core.foundations.db import get_session
    from core.proactive.hypothesizer import generate_hypotheses_for_org

    log = logging.getLogger(__name__)
    summary = {"orgs_scanned": 0, "emitted_total": 0, "errors": []}

    try:
        with get_session() as session:
            if org_id:
                org_ids = [org_id]
            else:
                org_ids = [
                    str(row[0])
                    for row in session.execute(text("SELECT id FROM orgs")).fetchall()
                ]
    except Exception as e:
        log.exception(f"task_generate_hypotheses org lookup failed: {e}")
        raise self.retry(exc=e)

    for oid in org_ids:
        try:
            with get_session() as session:
                result = generate_hypotheses_for_org(
                    session, org_id=oid, window_days=7
                )
                session.commit()
                summary["orgs_scanned"] += 1
                summary["emitted_total"] += int(result.get("emitted") or 0)
        except Exception as e:
            log.warning(f"task_generate_hypotheses org={oid} failed: {e}")
            summary["errors"].append({"org_id": oid, "error": str(e)[:200]})

    log.info(f"task_generate_hypotheses complete: {summary}")
    return summary


@celery.task(bind=True, max_retries=2, default_retry_delay=300, queue="low_priority")
def task_tune_thresholds(self, org_id: str = None):
    """g-i-8 Phase 4 — weekly per-org threshold tuner.

    For each rule that ships with a tunable knob, the tuner reads the
    outcome attribution (feedback_actions joined to proactive_insights),
    proposes a per-org threshold, and writes an org_rule_overrides row
    -- status=active when the suggestion meets the auto-bar (>=20
    samples AND >=5pp precision improvement), status=shadow otherwise
    so the dashboard can surface it for manual opt-in.

    Idempotent: re-running on the same outcomes produces the same
    suggestion. The prior active override gets status=reverted with
    reverted_at set so the audit timeline stays append-only.
    """
    import logging
    from sqlalchemy import text

    from core.foundations.db import get_session
    from core.foundations.threshold_tuner import tune_for_org

    log = logging.getLogger(__name__)
    summary = {"orgs_scanned": 0, "auto_applied_total": 0, "shadow_total": 0, "errors": []}

    try:
        with get_session() as session:
            if org_id:
                org_ids = [org_id]
            else:
                org_ids = [
                    str(row[0])
                    for row in session.execute(text("SELECT id FROM orgs")).fetchall()
                ]
    except Exception as e:
        log.exception(f"task_tune_thresholds org lookup failed: {e}")
        raise self.retry(exc=e)

    for oid in org_ids:
        try:
            with get_session() as session:
                result = tune_for_org(
                    session, org_id=oid, module_id="ar_collection", auto_apply=True
                )
                session.commit()
                summary["orgs_scanned"] += 1
                summary["auto_applied_total"] += int(result.get("auto_applied") or 0)
                summary["shadow_total"] += int(result.get("shadow_suggestions") or 0)
        except Exception as e:
            log.warning(f"task_tune_thresholds org={oid} failed: {e}")
            summary["errors"].append({"org_id": oid, "error": str(e)[:200]})

    log.info(f"task_tune_thresholds complete: {summary}")
    return summary


@celery.task(bind=True, max_retries=1, default_retry_delay=300, queue="low_priority")
def task_oauth_healthcheck(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_oauth_healthcheck called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_oauth_healthcheck"}




@celery.task(bind=True, max_retries=3, default_retry_delay=60, queue="high_priority")
def task_deliver_webhooks(self, org_id: str = None):
    """Phase 6.3: Deliver pending insight webhooks."""
    try:
        from app.tasks.webhook_delivery import deliver_pending_insights
        deliver_pending_insights(org_id)
    except Exception as exc:
        raise self.retry(exc=exc)


@celery.task(bind=True, max_retries=2, default_retry_delay=30, queue="high_priority")
def task_refresh_bundle(self, org_id: str, contact_id: str):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_refresh_bundle called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_refresh_bundle"}




@celery.task(bind=True, queue="brain_router")
def task_brain_router(self):
    """Stub — dead System B removed (app/brain/router.py deleted).

    The router consumed the event bus, ran app/graph/detectors/* (which
    queried v1 tables dropped in migration 0015), and wrote to the
    `recommendations` + `pending_alerts` tables (also dropped). It produced
    nothing on the v2 schema and burned an Upstash Redis tick every 60s. The
    `brain-router` beat entry was removed to stop the tick; this stub remains
    only so any straggler enqueue (or worker still bound to the brain_router
    queue) no-ops instead of raising ModuleNotFoundError.

    Proactive intelligence now lives entirely in core/proactive/* (module
    rulesets + hypothesizer + timing_detectors), driven by task_proactive_scan
    and the bus event subscriber, writing proactive_insights.
    """
    logger.warning("task_brain_router called but System B is removed — no-op")
    return {"consumed": 0, "flushed": 0, "pushed": 0, "status": "noop"}


@celery.task(bind=True, queue="low_priority")
def task_lifecycle_hourly(self):
    """Phase 4.5: hourly lifecycle transitions (ingest→validate→live, live↔fade)."""
    try:
        from app.lifecycle import run_hourly
        return run_hourly()
    except Exception as exc:
        logger.exception("lifecycle_hourly failed")
        raise self.retry(exc=exc, countdown=300, max_retries=2)


@celery.task(bind=True, queue="low_priority")
def task_lifecycle_nightly(self):
    """Phase 4.5: nightly lifecycle transitions (fade→dormant→archive)."""
    try:
        from app.lifecycle import run_nightly
        return run_nightly()
    except Exception as exc:
        logger.exception("lifecycle_nightly failed")
        raise self.retry(exc=exc, countdown=600, max_retries=2)


@celery.task(bind=True, queue="low_priority")
def task_calibration_nightly(self):
    """Phase 4.10: per-tenant Platt scaling over recent outcomes (dormant by default)."""
    try:
        from app.brain.calibration import run_nightly
        return run_nightly()
    except Exception as exc:
        logger.exception("calibration_nightly failed")
        raise self.retry(exc=exc, countdown=600, max_retries=2)


@celery.task(bind=True, queue="low_priority")
def task_baseline_writer(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_baseline_writer called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_baseline_writer"}




@celery.task(bind=True, max_retries=2, default_retry_delay=60, queue="low_priority")
def task_extract_pending(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_extract_pending called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_extract_pending"}




# ── Phase 6: Churn scan + retention offer composition ──────────────────────

@celery.task(bind=True, max_retries=1, default_retry_delay=300, queue="low_priority")
def task_churn_scan(self, org_id: str = None):
    """Stub — underlying v1 code deleted. Per g-i-1 plan all ingestion
    is now core.memory.sync_runner (called by task_scheduled_sync)."""
    import logging
    logging.getLogger(__name__).warning(
        "task_churn_scan called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_churn_scan"}




@celery.task(bind=True, max_retries=1, default_retry_delay=300, queue="low_priority")
def task_retention_offers(self, org_id: str = None):
    """Stub — v1 retention/churn modules deleted; pending_alerts table dropped.
    v2 has no in-engine retention loop."""
    import logging
    logging.getLogger(__name__).warning(
        "task_retention_offers called but v1 underlying code is gone — no-op"
    )
    return {"status": "noop", "task": "task_retention_offers"}


@celery.task(bind=True, max_retries=2, default_retry_delay=300, queue="low_priority")
def task_renew_watches(self):
    """Nightly Gmail Pub/Sub watch channel renewal (7-day expiry)."""
    try:
        from app.tasks.renew_watches import run_renew_watches
        return run_renew_watches()
    except Exception as exc:
        raise self.retry(exc=exc)




@celery.task(bind=True, max_retries=1, default_retry_delay=60, queue="low_priority")
def task_expire_approvals(self):
    """Phase 3: Auto-expire stale pending approvals past their expires_at."""
    try:
        from app.tasks.expire_approvals import run_expire_approvals
        return run_expire_approvals()
    except Exception as exc:
        raise self.retry(exc=exc)


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
    # Nightly refresh at 2am — full score recalculation across all nodes
    "nightly-refresh": {
        "task": "app.celery_app.task_nightly_refresh",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": "low_priority"},
    },
    # Phase 1.1: Process pending LLM extractions every 5 minutes
    "extract-pending": {
        "task": "app.celery_app.task_extract_pending",
        "schedule": 300.0,  # 5 min
        "options": {"queue": "low_priority"},
    },
    # Phase 3: LLM contact classification — daily at 3am
    "daily-classify-contacts": {
        "task": "app.celery_app.task_classify_contacts",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "low_priority"},
    },
    # Brain integrity: probe every OAuth credential daily so silent token
    # failures surface in /v1/sync as `health: degraded` instead of letting
    # the brain reason over stale data for days.
    "oauth-healthcheck-daily": {
        "task": "app.celery_app.task_oauth_healthcheck",
        "schedule": crontab(hour=5, minute=15),
        "options": {"queue": "low_priority"},
    },
    # Score writer — recompute per-contact scores every 15 min
    "score-writer-15m": {
        "task": "app.celery_app.task_score_writer",
        "schedule": 900.0,  # 15 min
        "options": {"queue": "low_priority"},
    },
    # Auto-merge — apply high-confidence duplicates every 30 min
    "auto-merge-30m": {
        "task": "app.celery_app.task_auto_merge",
        "schedule": 1800.0,  # 30 min
        "options": {"queue": "low_priority"},
    },
    # Precedent writer — nightly harvest of recommendation outcomes
    "precedent-writer-nightly": {
        "task": "app.celery_app.task_precedent_writer",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "low_priority"},
    },
    # Mig 079: Hebbian edge update — runs after precedent writer so the day's
    # acted recommendations are accounted for. Strengthens facts that wired
    # together; decays the rest (except potentiated).
    "hebbian-nightly": {
        "task": "app.celery_app.task_hebbian_nightly",
        "schedule": crontab(hour=4, minute=30),
        "options": {"queue": "low_priority"},
    },
    # Morning digest — hourly tick; task only sends when local time == digest_hour
    "morning-digest-hourly": {
        "task": "app.celery_app.task_morning_digest",
        "schedule": crontab(minute=5),  # :05 of every hour — offset from syncs
        "options": {"queue": "low_priority"},
    },
    # g-i-4 hourly proactive scan — safety net for slow-burn rules whose
    # condition changes purely because date moved (e.g. client_late_count_90d
    # crossing 3 today). The fast path is the bus event subscriber that
    # fires ~5s after a CSV/sync burst; this is the hourly catch-up. 24h
    # signature dedupe inside the pipeline keeps re-runs safe.
    "proactive-scan-hourly": {
        "task": "app.celery_app.task_proactive_scan",
        "schedule": 3600.0,  # 1 hour
        "options": {"queue": "low_priority"},
    },
    # g-i-4 Phase 3 — daily LLM hypothesis pass at 06:30 UTC. Runs after
    # nightly refresh (02:00) + hebbian (04:30) so we hypothesize over a
    # clean recompute-ed graph. 7-day signature dedupe inside the
    # hypothesizer keeps repeat costs bounded; we still see real net-new
    # hypotheses on each fresh upload.
    "hypothesizer-daily": {
        "task": "app.celery_app.task_generate_hypotheses",
        "schedule": crontab(hour=6, minute=30),
        "options": {"queue": "low_priority"},
    },
    # g-i-8 Phase 4 — weekly threshold tuner at 05:00 UTC Monday. Reads
    # the last 90 days of outcome attribution per (org, rule) and writes
    # any auto-bar-meeting overrides to org_rule_overrides (status=active);
    # everything else is recorded as status=shadow so the dashboard can
    # offer it for manual opt-in. Idempotent.
    "threshold-tuner-weekly": {
        "task": "app.celery_app.task_tune_thresholds",
        "schedule": crontab(day_of_week="mon", hour=5, minute=0),
        "options": {"queue": "low_priority"},
    },
    # DISABLED: task_deliver_webhooks queries webhook_config / delivery_attempts,
    # both dropped in migration 0015 and never recreated — so this beat threw on
    # every 60s tick, delivering nothing while burning quota-limited Upstash
    # dispatches. Proactive webhook delivery already happens INLINE in
    # core/proactive/pipeline.py (registry in Redis `webhooks:<org>`), so removing
    # this dead retry-queue beat loses no delivery. Re-add a v2 durable retry
    # queue later only if inline delivery needs one.
    # Phase 4.5: hourly lifecycle transitions
    "lifecycle-hourly": {
        "task": "app.celery_app.task_lifecycle_hourly",
        "schedule": crontab(minute=17),
        "options": {"queue": "low_priority"},
    },
    # Phase 4.5: nightly lifecycle transitions
    "lifecycle-nightly": {
        "task": "app.celery_app.task_lifecycle_nightly",
        "schedule": crontab(hour=2, minute=30),
        "options": {"queue": "low_priority"},
    },
    # Phase 4.10: nightly calibration fit per tenant (dormant by default)
    "calibration-nightly": {
        "task": "app.celery_app.task_calibration_nightly",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "low_priority"},
    },
    # Phase 1.3: Renew Gmail + Calendar watch channels daily before 7-day expiry.
    "renew-watches-daily": {
        "task": "app.celery_app.task_renew_watches",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": "low_priority"},
    },
    # Phase 3: Expire stale approval requests every 5 min.
    "expire-approvals-5m": {
        "task": "app.celery_app.task_expire_approvals",
        "schedule": 300.0,  # 5 min
        "options": {"queue": "low_priority"},
    },
    # sync-pull-connectors-5m was a v1 Beat entry that dispatched
    # app.tasks.sync_connector.task_sync_all_connectors — that module was
    # deleted in the g-i-1 migration. v2 task_scheduled_sync (already in
    # this file, hourly) drives all per-connector sync now through the
    # generic core.memory.sync_runner. Leaving the orphan entry crashed
    # Beat at startup with ModuleNotFoundError.
}


@celery.task(queue="low_priority")
def task_scheduled_sync():
    """Periodic refresh per g-i-1 plan: walk every active v2 Connection and run
    the thin sync_runner (pull → normalize → emit → subscriber → graph).

    Replaces v1's per-source task_sync_all_tools (gmail/calendar/slack/jira/
    notion/sheets/drive/docs/hubspot dispatch). One generic path now drives
    all sources via the v2 adapter registry.

    Trial orgs are skipped (manual sync only) — matches v1 behavior. Hustler
    tier honors a 6h cap; otherwise the per-org `sync_interval_hours` applies.
    """
    import logging
    from datetime import datetime, timezone

    from sqlalchemy import select
    from sqlalchemy import text as sa_text

    from app.database import SessionLocal
    from app.plan_enforcer import get_org_plan
    from core.foundations.db import get_session as v2_session
    from core.memory.store import Connection, CursorRow
    from core.memory.sync_runner import run_sync_for_connection

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        orgs = db.execute(sa_text(
            "SELECT id, COALESCE(sync_interval_hours, 24) AS interval_hours FROM orgs"
        )).fetchall()

        for org in orgs:
            org_id = str(org.id)
            plan = get_org_plan(db, org_id)
            plan_tier = plan.get("tier", "trial")

            # Plan cadence is the single source (early=6h, startup/enterprise=1h,
            # trial=manual). This replaces the dead `== "hustler"` check (tier is
            # normalized to "early" before this, so that branch never ran and
            # every paid org silently fell back to the 24h default).
            from app.plan_enforcer import sync_interval_hours
            plan_interval = sync_interval_hours(plan_tier)
            if plan_interval is None:
                continue  # manual-only tier (trial) — no scheduled sync
            # An org may sync MORE often via its own override, but never slower
            # than the plan's promised cadence.
            effective_interval = min(org.interval_hours, plan_interval)
            interval_seconds = effective_interval * 3600

            with v2_session() as s:
                conns = s.execute(
                    select(Connection)
                    .where(Connection.org_id == org_id)
                    .where(Connection.status == "active")
                ).scalars().all()

                for conn in conns:
                    last_sync_row = s.execute(
                        select(CursorRow).where(CursorRow.connection_id == conn.id)
                    ).scalar_one_or_none()
                    last_sync = last_sync_row.last_sync_at if last_sync_row else None

                    should_run = (
                        not last_sync
                        or (datetime.now(timezone.utc) - last_sync.replace(tzinfo=timezone.utc)).total_seconds()
                        >= interval_seconds
                    )
                    if not should_run:
                        continue
                    logger.info(
                        f"v2 scheduled sync: org={org_id[:8]} source={conn.source_type} "
                        f"connection={conn.id[:8]} tier={plan_tier}"
                    )
                    try:
                        # Periodic / delta sync — smaller batch than the
                        # initial connect blast. Env-driven via
                        # SYNC_PERIODIC_LIMIT so an operator can dial it
                        # down during a cost incident without code.
                        from app.config import SYNC_PERIODIC_LIMIT
                        result = run_sync_for_connection(
                            s, connection_id=conn.id, limit=SYNC_PERIODIC_LIMIT
                        )
                        logger.info(
                            f"  → emitted={result.items_emitted} dropped={result.items_dropped_scope}"
                        )
                    except Exception as e:
                        logger.exception(
                            f"  → sync failed for {conn.source_type}/{conn.id[:8]}: {e}"
                        )
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
