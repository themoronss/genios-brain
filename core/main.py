"""FastAPI application entry — v2 brain HTTP surface.

Routes mounted:
- /health, /ready                shallow liveness/readiness (no deps)
- /v1/health/deep                DB+Redis+LLM deep probes
- /v1/intelligence/*             query / explain / feedback / graph_view
- /v1/metrics/*                  intervention_rate / calibration / roi / resolution
- /v1/usermodel/*                persona CRUD + propose-confirm
- /v1/mapping/*                  custom-source mapping propose + confirm
- /v1/ingest                     customer-deployed adapter ingestion
- /v1/audit/events               immutable audit log read-side
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core import __version__
from core.api import audit as audit_router
from core.api import health as health_router
from core.api import (
    ingestion,
    intelligence,
    mapping,
    metrics,
    usermodel,
)
from core.foundations.config import settings
from core.foundations.telemetry import configure_telemetry, get_logger


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hooks."""
    configure_telemetry()
    log = get_logger("core.main")
    log.info("startup", version=__version__, env=settings.GENIOS_ENV)
    yield
    log.info("shutdown", version=__version__)


app = FastAPI(
    title="GeniOS Brain v2",
    version=__version__,
    description="Hybrid neuro-symbolic intelligence engine",
    lifespan=lifespan,
)

# CORS — explicit allow-list for the dashboard. Customer integrations call
# server-to-server (no browser) so they don't need CORS.
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEV_ORIGINS if settings.GENIOS_ENV != "production" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(intelligence.router)
app.include_router(metrics.router)
app.include_router(usermodel.router)
app.include_router(mapping.router)
app.include_router(ingestion.router)
app.include_router(audit_router.router)
app.include_router(health_router.router)


@app.get("/health", tags=["foundations"])
def health() -> dict[str, str]:
    """Liveness probe. Returns 200 if the process is alive (no deps checked)."""
    return {"status": "ok", "version": __version__}


@app.get("/ready", tags=["foundations"])
def ready() -> dict[str, str]:
    """Readiness probe. Returns 200 if the process can accept traffic.

    For deep dependency health, hit /v1/health/deep.
    """
    return {"status": "ready", "version": __version__}
