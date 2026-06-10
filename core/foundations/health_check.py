"""System health endpoints (g-i-8) — DB / Redis / LLM probes.

Each probe returns a dict with status, latency_ms, error.
The aggregate `system_health()` returns {component: HealthStatus} for the
ops dashboard + /health HTTP endpoint.

Probes are intentionally lightweight (ms-budget) — they run on every health
poll, so anything network-heavy must time out fast.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from core.foundations.config import settings
from core.foundations.db import get_engine
from core.foundations.telemetry import get_logger

log = get_logger(__name__)

PROBE_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class HealthStatus:
    component: str  # db | redis | llm
    status: str  # green | yellow | red
    latency_ms: int
    error: str | None
    checked_at: datetime


def check_db() -> HealthStatus:
    """`SELECT 1` against the configured Postgres URL."""
    started = time.perf_counter()
    err: str | None = None
    status = "green"
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as e:
        err = type(e).__name__
        status = "red"
    latency_ms = int((time.perf_counter() - started) * 1000)
    if status == "green" and latency_ms > 500:
        status = "yellow"
    return HealthStatus(
        component="db",
        status=status,
        latency_ms=latency_ms,
        error=err,
        checked_at=datetime.now(UTC),
    )


def check_redis(redis_client: Any | None = None) -> HealthStatus:
    """PING against Upstash Redis.

    Accepts an injected client for tests. Production builds the client from
    `settings.REDIS_URL`. The `redis` package is an optional dependency;
    if missing, returns yellow (broker unconfigured but app can run).
    """
    started = time.perf_counter()
    err: str | None = None
    status = "green"
    try:
        if redis_client is None:
            try:
                import redis
            except ImportError:
                latency_ms = int((time.perf_counter() - started) * 1000)
                return HealthStatus(
                    component="redis",
                    status="yellow",
                    latency_ms=latency_ms,
                    error="redis-package-not-installed",
                    checked_at=datetime.now(UTC),
                )
            redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=PROBE_TIMEOUT_SECONDS,
                socket_timeout=PROBE_TIMEOUT_SECONDS,
            )
        pong = redis_client.ping()
        if not pong:
            err = "ping returned falsy"
            status = "red"
    except Exception as e:
        err = type(e).__name__
        status = "red"
    latency_ms = int((time.perf_counter() - started) * 1000)
    if status == "green" and latency_ms > 500:
        status = "yellow"
    return HealthStatus(
        component="redis",
        status=status,
        latency_ms=latency_ms,
        error=err,
        checked_at=datetime.now(UTC),
    )


def check_llm(probe: Any | None = None) -> HealthStatus:
    """Probe the LLM provider (Anthropic).

    Production wires a real provider client through `probe`. When `probe` is
    None we don't make a real call (avoids spend on every health check) —
    instead we verify the key is present and return yellow if it isn't.
    """
    started = time.perf_counter()
    err: str | None = None
    status = "green"
    if probe is not None:
        try:
            probe()
        except Exception as e:
            err = type(e).__name__
            status = "red"
    else:
        if not settings.ANTHROPIC_API_KEY:
            status = "yellow"
            err = "ANTHROPIC_API_KEY not configured"
    latency_ms = int((time.perf_counter() - started) * 1000)
    return HealthStatus(
        component="llm",
        status=status,
        latency_ms=latency_ms,
        error=err,
        checked_at=datetime.now(UTC),
    )


def system_health(
    *,
    redis_client: Any | None = None,
    llm_probe: Any | None = None,
) -> dict[str, HealthStatus]:
    """Aggregate all probes for the /health endpoint and the ops dashboard."""
    return {
        "db": check_db(),
        "redis": check_redis(redis_client=redis_client),
        "llm": check_llm(probe=llm_probe),
    }
