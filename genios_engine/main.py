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
from genios_engine.api.executive_routes import router as executive_router
from genios_engine.api.expertise_routes import router as expertise_router
from genios_engine.api.identity_routes import router as identity_router
from genios_engine.api.intelligence_routes import router as intelligence_router
from genios_engine.api.knowledge_routes import router as knowledge_router
from genios_engine.api.policy_routes import router as policy_router
from genios_engine.api.routes import router
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
    if get_settings().use_real_db:
        from genios_engine.platform.migrate import apply_migrations
        applied = apply_migrations()
        if applied:
            import logging
            logging.getLogger("genios.boot").info("migrations applied at boot: %s", applied)
    # Start the in-process auto-sync scheduler (cross-org L1→L2/L3/L5 sweep every N hours). Only when
    # a real DB is configured — no point sweeping in-memory dev. Disable via GENIOS_SCHEDULER_ENABLED.
    from genios_engine.platform.scheduler import start_scheduler, stop_scheduler
    if get_settings().use_real_db:
        start_scheduler()
    yield
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

app.include_router(auth_router)
app.include_router(router)
app.include_router(workspace_router)
app.include_router(intelligence_router)
app.include_router(executive_router)
app.include_router(channel_router)
app.include_router(expertise_router)
app.include_router(agent_mgmt_router)
app.include_router(account_router)
app.include_router(upload_router)
app.include_router(knowledge_router)
app.include_router(identity_router)
app.include_router(situation_router)
app.include_router(policy_router)
app.include_router(approval_router)
app.include_router(usermodel_router)
app.include_router(audit_router)


@app.get("/")
def root() -> dict:
    return {"service": "genios-engine", "status": "up"}
