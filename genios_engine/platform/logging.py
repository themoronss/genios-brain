from __future__ import annotations

import logging
import os

# Minimal structured logging bootstrap. The engine had ZERO application logging (one stray print),
# so every background failure was invisible. This gives an on-call a real log stream. Level via
# GENIOS_LOG_LEVEL (default INFO). Call get_logger(__name__) per module; configure once at import.

_CONFIGURED = False


def _configure() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level = os.getenv("GENIOS_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    _configure()
    return logging.getLogger(name)
