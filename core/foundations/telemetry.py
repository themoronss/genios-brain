"""Structured JSON logging + Sentry integration.

Hard rules (per g-i-8):
- NO content in logs (only refs: decision_id, org_id, source_item_id, counts)
- NO secrets in logs (encrypted before any persistence; never logged in clear)
- Every log line is a single JSON object on stdout (container-friendly)

Use:
    from core.foundations.telemetry import get_logger
    log = get_logger(__name__)
    log.info("decision_emitted", decision_id=did, org_id=oid, route="autonomous")
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import sentry_sdk
import structlog
from sentry_sdk.integrations.logging import LoggingIntegration

from core.foundations.config import settings

_CONFIGURED = False


def configure_telemetry() -> None:
    """Initialize structured logging + Sentry. Call once at process start."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Sentry — errors + perf, but DO NOT capture log payloads (no content rule)
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.GENIOS_ENV,
            traces_sample_rate=0.1,
            integrations=[
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            # belt-and-suspenders: scrub any field that smells like a secret
            send_default_pii=False,
        )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(name: str) -> Any:
    """Return a bound structlog logger. Caller passes __name__."""
    if not _CONFIGURED:
        configure_telemetry()
    return structlog.get_logger(name)
