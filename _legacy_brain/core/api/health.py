"""Deep health route (g-i-8 probes).

GET /v1/health/deep    DB + Redis + LLM status with latency

The shallow /health endpoint in core/main.py is a liveness probe (no deps).
This deeper one is for the ops dashboard + readiness checks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from core.foundations.health_check import system_health

router = APIRouter(prefix="/v1/health", tags=["foundations"])


@router.get("/deep")
def deep_health() -> dict[str, Any]:
    """Run every probe + return per-component status."""
    statuses = system_health()
    return {
        component: {
            "status": s.status,
            "latency_ms": s.latency_ms,
            "error": s.error,
            "checked_at": s.checked_at.isoformat(),
        }
        for component, s in statuses.items()
    }
