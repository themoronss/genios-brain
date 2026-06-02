"""FastAPI application entry — minimal Phase 1 skeleton.

Endpoints land per module (g-i-1 → /v1/connections, g-i-7 → /v1/intelligence, etc.).
This file wires the app + middleware + health/readiness only.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core import __version__
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


@app.get("/health", tags=["foundations"])
def health() -> dict[str, str]:
    """Liveness probe. Returns 200 if the process is alive (no deps checked)."""
    return {"status": "ok", "version": __version__}


@app.get("/ready", tags=["foundations"])
def ready() -> dict[str, str]:
    """Readiness probe. Returns 200 only if dependencies are reachable.

    Full DB / Redis / LLM checks land in g-i-8 phase (`core/foundations/health_check.py`).
    """
    return {"status": "ready", "version": __version__}
