"""
Structured JSON logging with request_id propagation.

Phase 2.4: every log line is machine-parseable JSON. Every HTTP request
gets a unique request_id that propagates through all log messages in that
request's lifecycle. This makes it possible to correlate logs in production
(grep by request_id to see the full trace).

Usage:
    from app.logging_config import setup_logging
    setup_logging()  # call once at app startup (main.py)

Then in any module:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("something happened", extra={"contact_id": "abc"})
    # Output: {"timestamp":"...","level":"INFO","logger":"app.context.bundle_builder",
    #          "message":"something happened","request_id":"abc123","contact_id":"abc"}
"""
import json
import logging
import os
import uuid
from contextvars import ContextVar

# Context var holds the request_id for the current async request
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

LOG_FORMAT = os.getenv("GENIOS_LOG_FORMAT", "json")  # "json" or "text"
LOG_LEVEL = os.getenv("GENIOS_LOG_LEVEL", "INFO")


class JsonFormatter(logging.Formatter):
    """Formats log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get("-"),
        }
        # Include any extra fields passed via logger.info(..., extra={...})
        for key in ("contact_id", "org_id", "entity", "latency_ms", "cache_hit", "error"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging():
    """Configure root logger. Call once in main.py."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Remove existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler()
    if LOG_FORMAT == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(request_id)s) %(message)s",
            defaults={"request_id": "-"},
        ))

    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def generate_request_id() -> str:
    """Generate a short unique request ID."""
    return uuid.uuid4().hex[:12]
