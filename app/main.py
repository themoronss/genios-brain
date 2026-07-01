import os
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

# Load .env into os.environ BEFORE importing routers. pydantic Settings(env_file)
# only fills the `settings` object, not os.environ — so os.getenv-based config
# (e.g. billing's RAZORPAY_KEY_ID/SECRET, read at import time) would come back
# empty without this. load_dotenv() does NOT override vars already set by the
# host, so production env injection still wins.
from dotenv import load_dotenv
load_dotenv()

# Structured logging — must init before any logger is created
from app.logging_config import setup_logging, generate_request_id, request_id_var
setup_logging()

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
import time
import logging
import jwt as pyjwt

from app.api.routes import health
from app.api.routes import auth
from app.api.routes import context
from app.api.routes import status
from app.api.routes import draft
from app.api.routes import sync
from app.api.routes import agents
from app.api.routes import agent_registry
from app.api.routes import workspace_integrations
from app.api.routes import ingest as ingest_routes
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
from app.api.routes import webhooks_calendar as webhooks_calendar_routes
from app.api.routes import policies as policies_routes
from app.api.routes import approvals as approvals_routes
from app.api.routes import retrieval as retrieval_routes
from app.api.routes import explain as explain_routes
from app.api.routes import live as live_routes
from app.api.routes import billing as billing_routes
from app.api.routes import billing_stream as billing_stream_routes
from app.api.routes import seats as seats_routes
from app.api.routes import tags_disclosure as tags_disclosure_routes
from app.api.routes import proactive as proactive_routes
from app.api.routes import writeback as writeback_routes
from app.api.routes import feedback as feedback_routes
from app.api.routes import admin as admin_routes
from app.api.routes import admin_metrics
from app.api.routes import stream as stream_routes
from app.api.routes import brain_activity as brain_activity_routes
from app.api.routes import mcp as mcp_routes
from app.api.routes import mcp_oauth as mcp_oauth_routes
from app.api.routes import messages as messages_routes
from app.api.routes import benchmarks as benchmarks_routes
from app.api.routes import activity as activity_routes  # Phase 9
from app.api.routes import expertise as expertise_routes  # domain modules (read-only)

# v2 brain routers — single backend, single process. Routes mounted at /v1/*
# (intelligence, metrics, persona, mapping, audit, ingest). Auth is shared
# via the JWT cookie/Bearer + api_keys table (see core/api/deps.py).
# `core` and `app` are sibling top-level packages at the brain repo root.
from core.api import audit as v2_audit_router
from core.api import health as v2_health_router
from core.api import ingestion as v2_ingestion_router
from core.api import intelligence as v2_intelligence_router
from core.api import mapping as v2_mapping_router
from core.api import metrics as v2_metrics_router
from core.api import predicates as v2_predicates_router
from core.api import usage as v2_usage_router
from core.api import usermodel as v2_usermodel_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App lifecycle manager.
    Scheduling is handled by Celery Beat (see app/celery_app.py).
    The in-process scheduler loop has been removed — all sync/refresh
    work now runs in separate Celery worker processes.
    """
    logger.info("✓ App started. Sync scheduling handled by Celery Beat.")

    # v2 brain — load every installed module and register its query +
    # graph_view handlers with the intelligence router. Without this,
    # POST /v1/intelligence/query returns 503 ("module ... has no handler").
    try:
        from core.modules_framework.bootstrap import bootstrap_modules
        loaded = bootstrap_modules()
        logger.info(f"✓ Loaded {len(loaded)} v2 module(s): {sorted(loaded.keys())}")
    except Exception as e:
        logger.exception(f"v2 module bootstrap failed (non-fatal): {e}")

    # v2 brain — register the g-i-3 worldmodel-ingest subscriber on emit() bus.
    # After this, every MemoryItem from core/memory/sync_runner.py flows through
    # extract → resolve → upsert FactRow/NodeRow/EdgeRow.
    try:
        from core.worldmodel.ingest_subscriber import register_ingest_subscriber
        register_ingest_subscriber()
        logger.info("✓ v2 ingest subscriber registered on emit() bus")
    except Exception as e:
        logger.exception(f"v2 ingest subscriber registration failed (non-fatal): {e}")

    # v2 brain — register the g-i-4 proactive event subscriber. Same bus,
    # different subscriber: each MemoryItem schedules a debounced (5-sec)
    # per-org proactive scan. After the burst (CSV upload, Gmail sync) settles,
    # the pipeline runs once, dedupes against the last 24h of insights, and
    # fires webhooks. Customer doesn't have to call /v1/scan manually.
    try:
        from core.proactive.event_subscriber import register_proactive_event_subscriber
        register_proactive_event_subscriber()
        logger.info("✓ v2 proactive event subscriber registered on emit() bus")
    except Exception as e:
        logger.exception(f"v2 proactive event subscriber registration failed (non-fatal): {e}")

    yield
    logger.info("App shutting down.")
    # Flush queued analytics events so the last batch isn't lost on restart.
    from app.core.analytics import flush
    flush()


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

# ── Request ID Middleware — attaches a unique ID to every request ────────────
class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or generate_request_id()
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

app.add_middleware(RequestIdMiddleware)

# ── JWT Auth Middleware — protects dashboard routes ──────────────────────────
_JWT_SECRET = os.getenv("JWT_SECRET", "genios-secret-key-replace-in-production")
_PROTECTED_PREFIXES = ("/api/org/", "/dashboard/", "/activity")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip non-protected routes and OPTIONS (CORS preflight)
        if request.method == "OPTIONS" or not any(path.startswith(p) for p in _PROTECTED_PREFIXES):
            return await call_next(request)

        # API-key Bearer (gn_live_*) is handled downstream by
        # core.api.deps.require_org_and_policy which resolves the agent's
        # scope policy from api_keys → agent_scopes. This middleware ONLY
        # gates dashboard JWT users; let API-key calls pass through.
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer gn_live_") or auth_header.startswith("Bearer gn_test_"):
            return await call_next(request)

        # Dashboard JWT path — header first, then HttpOnly cookie.
        token = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        elif request.cookies.get("genios_token"):
            token = request.cookies["genios_token"]

        if not token:
            return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        try:
            payload = pyjwt.decode(token, _JWT_SECRET, algorithms=["HS256"])
            request.state.jwt_org_id = payload.get("org_id")
        except pyjwt.ExpiredSignatureError:
            response = JSONResponse(status_code=401, content={"detail": "Token expired"})
            response.delete_cookie("genios_token", path="/")
            return response
        except pyjwt.InvalidTokenError:
            response = JSONResponse(status_code=401, content={"detail": "Invalid token"})
            response.delete_cookie("genios_token", path="/")
            return response

        return await call_next(request)


app.add_middleware(JWTAuthMiddleware)


# ── API Analytics Middleware — one `api_call` PostHog event per /v1 request ───
# Captures per-agent API hits, latency, status, and the LLM cost incurred
# during the request (via the llm_cost_var accumulator). distinct_id = org_id.
class ApiAnalyticsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or not path.startswith("/v1/"):
            return await call_next(request)

        from app.core.analytics import llm_cost_var, capture

        acc = {"cost_usd": 0.0, "tokens": 0}
        cv_token = llm_cost_var.set(acc)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            llm_cost_var.reset(cv_token)

        try:
            auth = getattr(request.state, "auth", None)
            org_id = getattr(auth, "org_id", None)
            if org_id:
                route = request.scope.get("route")
                capture(org_id, "api_call", {
                    "agent_id": getattr(auth, "agent_id", None) or "default",
                    "endpoint": getattr(route, "path", path),
                    "method": request.method,
                    "status": response.status_code,
                    "ok": response.status_code < 400,
                    "latency_ms": int((time.perf_counter() - start) * 1000),
                    "cost_usd": round(acc["cost_usd"], 6),
                    "tokens": acc["tokens"],
                })
        except Exception:
            pass  # analytics must never break the response
        return response


app.add_middleware(ApiAnalyticsMiddleware)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(context.router)
app.include_router(status.router)
app.include_router(draft.router)
app.include_router(sync.router)
app.include_router(agents.router)
app.include_router(agent_registry.router)
app.include_router(workspace_integrations.router)
app.include_router(ingest_routes.router)
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
app.include_router(webhooks_calendar_routes.router)
app.include_router(policies_routes.router)
app.include_router(approvals_routes.router)
app.include_router(retrieval_routes.router)
app.include_router(explain_routes.router)
app.include_router(live_routes.router)
app.include_router(billing_routes.router)
app.include_router(billing_stream_routes.router)
app.include_router(seats_routes.router)
app.include_router(tags_disclosure_routes.router)
app.include_router(proactive_routes.router)
app.include_router(writeback_routes.router)
app.include_router(feedback_routes.router)
app.include_router(admin_routes.router)
app.include_router(admin_metrics.router)
app.include_router(stream_routes.router)
app.include_router(brain_activity_routes.router)
app.include_router(mcp_routes.router)
app.include_router(mcp_oauth_routes.router)
app.include_router(messages_routes.router)
app.include_router(benchmarks_routes.router)
app.include_router(activity_routes.router)  # Phase 9 — live SSE feed
app.include_router(expertise_routes.router)  # Expertise — domain modules (read-only)

# ── v2 brain mounted ───────────────────────────────────────────────────────
app.include_router(v2_intelligence_router.router)
app.include_router(v2_metrics_router.router)
app.include_router(v2_usermodel_router.router)
app.include_router(v2_mapping_router.router)
app.include_router(v2_ingestion_router.router)
app.include_router(v2_audit_router.router)
app.include_router(v2_predicates_router.router)
app.include_router(v2_usage_router.router)
app.include_router(v2_health_router.router)


@app.get("/")
def root():
    return {"message": "GeniOS Brain running"}


@app.post("/v1/decide")
def decide_stub():
    raise HTTPException(status_code=501, detail="This endpoint is planned for V3. Use /v1/context for context delivery.")
