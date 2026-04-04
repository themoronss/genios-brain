import os
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

import sentry_sdk
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    traces_sample_rate=0.1,
    environment=os.getenv("ENVIRONMENT", "development"),
)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import logging
import jwt as pyjwt

from app.api.routes import health
from app.api.routes import auth
from app.api.routes import context
from app.api.routes import status
from app.api.routes import draft
from app.api.routes import sync
from app.api.routes import agents
from app.api.routes import events
from app.api.routes import chat
from app.api.routes import authority
from app.api.routes import precedent
from app.api.routes import merge
from app.api.routes import facts
from app.api.routes import manual_context
from app.api.routes import integrations_auth
from app.api.routes import insights
from app.api.routes import v1 as v1_routes
from app.api.routes import segments as segments_routes
from app.api.routes import webhooks as webhooks_routes
from app.api.routes import billing as billing_routes
from app.api.routes import seats as seats_routes
from app.api.routes import tags_disclosure as tags_disclosure_routes

logger = logging.getLogger(__name__)


def _sync_connected_tools(org_id: str, cron: bool = False):
    """
    Re-sync all connected tools for an org. Each tool's sync is incremental —
    Gmail uses history_id, Calendar uses syncToken — so already-synced data is skipped.
    cron=True uses larger batch sizes (SYNC_MAX_EMAILS_CRON / SYNC_MAX_CALENDAR_EVENTS_CRON).
    """
    from app.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # Find which tools are connected by checking oauth_tokens
        tokens = db.execute(
            text("SELECT account_email FROM oauth_tokens WHERE org_id = :oid"),
            {"oid": org_id},
        ).fetchall()

        connected = set()
        for row in tokens:
            email = row.account_email or ""
            if email.startswith("gcal:"):
                connected.add("gcal")
            elif email.startswith("slack:"):
                connected.add("slack")
            elif email.startswith("jira:"):
                connected.add("jira")
            elif email.startswith("notion:"):
                connected.add("notion")
            elif email.startswith("gsheets:"):
                connected.add("gsheets")
            elif email.startswith("gdrive:"):
                connected.add("gdrive")
            elif email.startswith("gdocs:"):
                connected.add("gdocs")
            elif email.startswith("hubspot:"):
                connected.add("hubspot")
            elif ":" not in email and "@" in email:
                connected.add("gmail")
    finally:
        db.close()

    # Map tool → sync function (imported lazily to avoid circular deps)
    tool_sync = {
        "gmail": ("app.tasks.gmail_sync", "run_gmail_sync"),
        "gcal": ("app.tasks.calendar_sync", "run_calendar_sync"),
        "slack": ("app.tasks.slack_sync", "run_slack_backfill"),
        "jira": ("app.tasks.jira_sync", "run_jira_sync"),
        "notion": ("app.tasks.notion_sync", "run_notion_sync"),
        "gsheets": ("app.tasks.sheets_sync", "run_sheets_sync"),
        "gdrive": ("app.tasks.drive_sync", "run_drive_sync"),
        "gdocs": ("app.tasks.docs_sync", "run_docs_sync"),
        "hubspot": ("app.tasks.hubspot_sync", "run_hubspot_sync"),
    }

    import importlib
    from app.config import SYNC_MAX_EMAILS_CRON, SYNC_MAX_EMAILS, SYNC_MAX_CALENDAR_EVENTS_CRON, SYNC_MAX_CALENDAR_EVENTS
    from sqlalchemy import text as sa_text
    cron_kwargs = {
        "gmail": {"max_emails": SYNC_MAX_EMAILS_CRON if cron else SYNC_MAX_EMAILS},
        "gcal": {"max_results": SYNC_MAX_CALENDAR_EVENTS_CRON if cron else SYNC_MAX_CALENDAR_EVENTS},
    }
    # Tool → account_email prefix used in oauth_tokens (for error status update)
    tool_prefix = {
        "gmail": None,  # gmail tokens have no prefix — matched by plain email
        "gcal": "gcal:",
        "slack": "slack:",
        "jira": "jira:",
        "notion": "notion:",
        "gsheets": "gsheets:",
        "gdrive": "gdrive:",
        "gdocs": "gdocs:",
        "hubspot": "hubspot:",
    }
    for tool in connected:
        if tool not in tool_sync:
            continue
        module_path, func_name = tool_sync[tool]
        try:
            module = importlib.import_module(module_path)
            sync_func = getattr(module, func_name)
            kwargs = cron_kwargs.get(tool, {})
            logger.info(f"  ↻ Syncing {tool} for org {org_id}")
            sync_func(org_id, **kwargs)
            logger.info(f"  ✓ {tool} sync complete for org {org_id}")
        except Exception as e:
            logger.error(f"  ✗ {tool} sync failed for org {org_id}: {e}")
            # Mark sync_status=error on the relevant token row so UI reflects failure
            try:
                prefix = tool_prefix.get(tool)
                err_db = SessionLocal()
                try:
                    if prefix:
                        err_db.execute(sa_text(
                            "UPDATE oauth_tokens SET sync_status = 'error', sync_error = :err "
                            "WHERE org_id = :oid AND account_email LIKE :prefix"
                        ), {"oid": org_id, "err": str(e)[:500], "prefix": f"{prefix}%"})
                    else:
                        err_db.execute(sa_text(
                            "UPDATE oauth_tokens SET sync_status = 'error', sync_error = :err "
                            "WHERE org_id = :oid AND account_email NOT LIKE '%:%' AND account_email LIKE '%@%'"
                        ), {"oid": org_id, "err": str(e)[:500]})
                    err_db.commit()
                finally:
                    err_db.close()
            except Exception:
                pass  # Never let error-reporting crash the scheduler


async def sync_scheduler_loop():
    """
    Background scheduler that:
    1. Re-syncs all connected tools (incremental — skips existing data)
    2. Runs nightly refresh (recalc scores, insights, bundles)

    Checks every hour; per-org intervals can be 6, 12, 18, or 24 hours.
    """
    await asyncio.sleep(60)  # Wait 60s after startup

    while True:
        try:
            from app.database import SessionLocal
            from app.tasks.nightly_refresh import run_nightly_refresh
            from sqlalchemy import text
            from datetime import datetime, timezone

            db = SessionLocal()
            try:
                orgs = db.execute(text(
                    "SELECT id, COALESCE(sync_interval_hours, 24) AS interval_hours, COALESCE(subscription_tier, 'trial') AS subscription_tier FROM orgs"
                )).fetchall()

                for org in orgs:
                    # Phase 4: Plan-gated sync — Trial = manual only (skip scheduler)
                    plan_tier = org.subscription_tier if hasattr(org, "subscription_tier") else "trial"
                    if plan_tier == "trial":
                        continue  # Trial orgs only sync on manual trigger

                    # Use MIN so we trigger if ANY tool is overdue, not just when all are recent
                    last_sync = db.execute(text(
                        "SELECT MIN(last_synced_at) FROM oauth_tokens WHERE org_id = :oid"
                    ), {"oid": str(org.id)}).scalar()

                    # Hustler: 6h cron. Startup: 6h cron as fallback (real-time via webhook)
                    effective_interval = org.interval_hours
                    if plan_tier == "hustler":
                        effective_interval = min(org.interval_hours, 6)  # cap at 6h per plan
                    interval_seconds = effective_interval * 3600

                    should_run = (
                        not last_sync or
                        (datetime.now(timezone.utc) - last_sync.replace(tzinfo=timezone.utc)).total_seconds() >= interval_seconds
                    )

                    if should_run:
                        logger.info(f"🌙 Running scheduled sync + refresh for org {org.id} (tier: {plan_tier}, interval: {effective_interval}h)")
                        loop = asyncio.get_event_loop()
                        # Step 1: Re-sync all connected tools (incremental)
                        await loop.run_in_executor(None, lambda oid=str(org.id): _sync_connected_tools(oid, cron=True))
                        # Step 2: Recalculate scores, insights, bundles
                        await loop.run_in_executor(None, run_nightly_refresh, str(org.id))
                        logger.info(f"✓ Scheduled sync + refresh complete for org {org.id}")

                # Step 3: Expire stale plans (once per cycle, not per org)
                try:
                    from app.plan_enforcer import expire_stale_plans
                    expired_count = expire_stale_plans(db)
                    if expired_count:
                        logger.info(f"⏱ Plan expiry: marked {expired_count} plan(s) as expired")
                except Exception as exp_err:
                    logger.warning(f"Plan expiry step failed: {exp_err}")

                # Billing jobs: trial expiry emails + overage invoices
                try:
                    from app.tasks.billing_jobs import run_trial_expiry_emails, run_overage_invoices
                    run_trial_expiry_emails(db)
                    run_overage_invoices(db)
                except Exception as billing_err:
                    logger.warning(f"Billing jobs failed: {billing_err}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"✗ Sync scheduler error: {e}")

        await asyncio.sleep(3600)  # Check every hour


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage background tasks for the FastAPI app lifecycle."""
    # Start sync scheduler loop as background task
    refresh_task = asyncio.create_task(sync_scheduler_loop())
    logger.info("✓ Sync scheduler started (checks hourly, per-org intervals)")
    yield
    # Shutdown: cancel the background task cleanly
    refresh_task.cancel()
    try:
        await refresh_task
    except asyncio.CancelledError:
        pass
    logger.info("Sync scheduler stopped")


app = FastAPI(lifespan=lifespan)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://genios-brain.vercel.app", "https://brain.thegenios.com"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── JWT Auth Middleware — protects dashboard routes ──────────────────────────
_JWT_SECRET = os.getenv("JWT_SECRET", "genios-secret-key-replace-in-production")
_PROTECTED_PREFIXES = ("/api/org/", "/dashboard/", "/activity")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip non-protected routes and OPTIONS (CORS preflight)
        if request.method == "OPTIONS" or not any(path.startswith(p) for p in _PROTECTED_PREFIXES):
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header.startswith("Bearer gn_live_"):
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        token = auth_header[7:]
        try:
            payload = pyjwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
            # Attach org_id from JWT to request state for downstream use
            request.state.jwt_org_id = payload.get("org_id")
        except pyjwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content={"detail": "Token expired"})
        except pyjwt.InvalidTokenError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return await call_next(request)


app.add_middleware(JWTAuthMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(context.router)
app.include_router(status.router)
app.include_router(draft.router)
app.include_router(sync.router)
app.include_router(agents.router)
app.include_router(events.router)
app.include_router(chat.router)
app.include_router(authority.router)
app.include_router(precedent.router)
app.include_router(merge.router)
app.include_router(facts.router)
app.include_router(manual_context.router)
app.include_router(integrations_auth.router)
app.include_router(insights.router)
app.include_router(v1_routes.router)
app.include_router(segments_routes.router)
app.include_router(webhooks_routes.router)
app.include_router(billing_routes.router)
app.include_router(seats_routes.router)
app.include_router(tags_disclosure_routes.router)


@app.get("/")
def root():
    return {"message": "GeniOS Brain running"}


@app.post("/v1/decide")
def decide_stub():
    raise HTTPException(status_code=501, detail="This endpoint is planned for V3. Use /v1/context for context delivery.")
