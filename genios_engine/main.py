from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from genios_engine.api.account_routes import router as account_router
from genios_engine.api.agent_mgmt_routes import router as agent_mgmt_router
from genios_engine.api.approval_routes import router as approval_router
from genios_engine.api.audit_routes import router as audit_router
from genios_engine.api.auth_routes import router as auth_router
from genios_engine.api.channel_routes import router as channel_router
from genios_engine.api.delivery_routes import router as delivery_router
from genios_engine.api.executive_routes import router as executive_router
from genios_engine.api.expertise_routes import router as expertise_router
from genios_engine.api.home_routes import router as home_router
from genios_engine.api.identity_routes import router as identity_router
from genios_engine.api.intelligence_routes import router as intelligence_router
from genios_engine.api.brain_routes import router as brain_router
from genios_engine.api.knowledge_routes import router as knowledge_router
from genios_engine.api.learning_routes import router as learning_router
from genios_engine.api.policy_routes import router as policy_router
from genios_engine.api.routes import router
from genios_engine.api.benchmarks_routes import router as benchmarks_router
from genios_engine.api.billing_routes import router as billing_router
from genios_engine.api.mapping_routes import router as mapping_router
from genios_engine.api.merge_routes import router as merge_router
from genios_engine.api.segments_routes import router as segments_router
from genios_engine.api.admin_routes import router as admin_router
from genios_engine.api.situation_routes import router as situation_router
from genios_engine.api.upload_routes import router as upload_router
from genios_engine.api.usermodel_routes import router as usermodel_router
from genios_engine.api.workspace_routes import router as workspace_router
from genios_engine.platform.config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # MIGRATE FIRST, fail fast. Code and schema deploy together now: new code names
    # columns/tables its migrations create, so serving requests before migrating meant
    # every capture insert + the L2 drain erroring until someone ran migrate by hand.
    # The schema_migrations ledger makes this a cheap no-op when nothing is pending,
    # and a loud crash (restart + retry) beats silently serving broken SQL.
    # ...with ONE exception, which is not a softening of the rule above but a case where the rule
    # inverts. If the database is READ-ONLY, crashing achieves nothing a restart can fix — only a
    # human lifting the write lock can — and it converts a partial outage (writes failing, reads
    # fine) into a total one, because the crash-loop takes the API down too. So: log it as loudly
    # as a crash would, and stay up serving the half that still works.
    if get_settings().use_real_db:
        import logging

        from genios_engine.platform.migrate import ReadOnlyDatabaseError, apply_migrations
        log = logging.getLogger("genios.boot")
        try:
            applied = apply_migrations()
            if applied:
                log.info("migrations applied at boot: %s", applied)
        except ReadOnlyDatabaseError as exc:
            log.error("DEGRADED BOOT — database is read-only, migrations NOT applied: %s", exc)
            log.error("Reads are served; every write will fail until the write lock is lifted.")
            app.state.degraded_read_only = str(exc)
    # Start the in-process auto-sync scheduler (cross-org L1→L2/L3/L5 sweep every N hours). Only when
    # a real DB is configured — no point sweeping in-memory dev. Disable via GENIOS_SCHEDULER_ENABLED.
    from genios_engine.platform.scheduler import start_scheduler, stop_scheduler
    from genios_engine.platform.sync_worker import start_sync_worker, stop_sync_worker
    if get_settings().use_real_db:
        start_scheduler()
        start_sync_worker()          # durable sync-job worker: runs Sync jobs, resumes on restart
    yield
    stop_sync_worker()
    stop_scheduler()


app = FastAPI(title="GeniOS Engine", version="0.1.0", lifespan=lifespan)

# CORS — the dashboard is a cross-origin browser app; without this the browser blocks every call.
# When the origin list is '*' we use a regex so Starlette ECHOES the caller's origin (never a bare
# '*'), which is what lets credentialed requests through too — a bare '*' + credentials is a CORS
# violation the browser rejects ("Unable to connect"). In prod set GENIOS_CORS_ORIGINS to a real
# list (https://app.genios.ai,…) → exact-origin allowlist.
_origins = [o.strip() for o in (get_settings().cors_origins or "*").split(",") if o.strip()]
if _origins == ["*"]:
    app.add_middleware(CORSMiddleware, allow_origin_regex=".*", allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
else:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])

@app.middleware("http")
async def _api_call_analytics(request, call_next):
    """One `api_call` event per authenticated request — the "is this account actually using the
    product?" signal, plus latency.

    Deliberately cheap and side-effect free: it reads the org that the route's own dependency
    already resolved (`request.state.org_id`), so it neither re-authenticates nor learns anything a
    route did not. Unauthenticated and pre-auth failures emit nothing — an anonymous 401 is not
    product usage. The ROUTE TEMPLATE is recorded, never the resolved path, so ids stay out of the
    property values and the breakdown stays groupable.
    """
    import time as _t
    started = _t.perf_counter()
    response = await call_next(request)
    try:
        org_id = getattr(request.state, "org_id", None)
        if org_id:
            route = request.scope.get("route")
            from genios_engine.platform import analytics
            analytics.capture(org_id, "api_call", {
                "path": getattr(route, "path", request.url.path),
                "method": request.method,
                "status": response.status_code,
                "latency_ms": round((_t.perf_counter() - started) * 1000, 1),
            })
    except Exception:            # noqa: BLE001 — telemetry never touches the response
        pass
    return response


app.include_router(auth_router)
app.include_router(router)
app.include_router(workspace_router)
app.include_router(intelligence_router)
app.include_router(executive_router)
app.include_router(delivery_router)
app.include_router(channel_router)
app.include_router(expertise_router)
app.include_router(agent_mgmt_router)
app.include_router(account_router)
app.include_router(upload_router)
app.include_router(knowledge_router)
app.include_router(learning_router)
app.include_router(brain_router)
app.include_router(identity_router)
app.include_router(situation_router)
app.include_router(policy_router)
app.include_router(approval_router)
app.include_router(usermodel_router)
app.include_router(audit_router)
app.include_router(segments_router)
app.include_router(merge_router)
app.include_router(benchmarks_router)
app.include_router(home_router)
app.include_router(mapping_router)
app.include_router(billing_router)
app.include_router(admin_router)     # cross-org admin console (is_internal-gated)


@app.get("/")
def root() -> dict:
    return {"service": "genios-engine", "status": "up"}
