"""
Health check endpoint — Phase 11.
  GET /health — liveness + readiness (DB + Redis)

Returns 200 OK when healthy, 503 when any dependency is down.
Point Uptime Robot / Better Uptime at /health.
"""

import time
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health():
    checks = {}
    degraded = False

    # DB
    try:
        from app.database import SessionLocal
        t0 = time.monotonic()
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["db"] = {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as e:
        checks["db"] = {"ok": False, "error": str(e)}
        degraded = True

    # Redis
    try:
        from app.redis_client import redis_client
        t0 = time.monotonic()
        redis_client.ping()
        checks["redis"] = {"ok": True, "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as e:
        checks["redis"] = {"ok": False, "error": str(e)}
        degraded = True

    # Kill switch state
    try:
        from app.redis_client import redis_client
        cached = redis_client.get("feature_flag:kill_switch_all")
        checks["kill_switch"] = "active" if cached in (b"0", "0") else "off"
    except Exception:
        checks["kill_switch"] = "unknown"

    return JSONResponse(
        status_code=503 if degraded else 200,
        content={"status": "degraded" if degraded else "ok", "checks": checks},
    )
