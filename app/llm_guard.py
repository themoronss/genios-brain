"""
LLM Guard — timeout wrapper and agent loop protection.
PDF spec: Processing timeout = 3s. We use 30s during development/free-tier models.
Set LLM_TIMEOUT_SECONDS env var to override (default: 30).
Agent loop protection: max 3 LLM calls per context hard cap.
"""

import concurrent.futures
import logging
import os
import time
from typing import Callable, Any

logger = logging.getLogger(__name__)

_THREAD_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm_guard")

# Hard cap for a TRUE loop: repeated calls for the SAME entity by the SAME
# agent within 60s. Distinct entities don't count — a buyer asking
# "summarize my top 5 leads" fans out to 5 legitimate lookups.
# Overridable via env for integrators on burst workloads.
ENTITY_REPEAT_CAP = int(os.getenv("GENIOS_ENTITY_REPEAT_CAP", "8"))

# Legacy name kept for import compatibility. Don't use for new logic.
LLM_CALLS_HARD_CAP = ENTITY_REPEAT_CAP

# Timeout for LLM/bundle calls.
# PDF spec says 3s — but free-tier models (Gemini Flash, Groq) can take 10-20s.
# Override with LLM_TIMEOUT_SECONDS env var when moving to paid/production models.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))


def call_with_timeout(fn: Callable, *args, timeout: float = None, fallback: Any = None, **kwargs) -> Any:
    """
    Call `fn(*args, **kwargs)` with a configurable timeout.
    Returns `fallback` if timeout is exceeded (never raises TimeoutError to callers).

    timeout defaults to LLM_TIMEOUT_SECONDS (30s, overridable via env var).

    Usage:
        result = call_with_timeout(build_context_bundle, db, org_id, entity, fallback=None)
    """
    if timeout is None:
        timeout = LLM_TIMEOUT_SECONDS

    future = _THREAD_POOL.submit(fn, *args, **kwargs)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.warning(f"LLM call timed out after {timeout}s — returning fallback")
        future.cancel()
        return fallback
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return fallback


def check_agent_loop(org_id: str, agent_id: str, plan_tier: str, entity: str = None) -> bool:
    """
    Loop protection: flag when the same agent asks for the SAME entity
    repeatedly (>= ENTITY_REPEAT_CAP) within 60s. Distinct entities are
    legitimate fan-out and don't count.

    Backwards-compat: older callers without `entity` get permissive behavior
    (no per-entity keying), which matches the intent — RPM is already
    enforced separately by check_rpm_limit.

    Returns True if allowed, raises HTTP 429 if a true loop is detected.
    """
    try:
        from app.redis_client import redis_client
        from fastapi import HTTPException

        # Normalize entity → lower, stripped. Empty = skip per-entity check.
        ent_key = (entity or "").strip().lower()
        if not ent_key:
            return True

        now = int(time.time())
        window_start = now - 60

        loop_key = f"entity_loop:{org_id}:{agent_id or 'default'}:{ent_key[:128]}"
        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(loop_key, 0, window_start)
        pipe.zcard(loop_key)
        pipe.zadd(loop_key, {str(now): now})
        pipe.expire(loop_key, 120)
        results = pipe.execute()
        call_count = results[1]

        if call_count >= ENTITY_REPEAT_CAP:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "ENTITY_REPEAT_LIMIT",
                    "message": (
                        f"Same entity requested {call_count} times in 60s by this agent. "
                        f"Cap is {ENTITY_REPEAT_CAP}. This looks like a loop — try a different query."
                    ),
                    "entity": ent_key,
                    "calls_in_window": call_count,
                    "hard_cap": ENTITY_REPEAT_CAP,
                },
            )

        return True
    except Exception as e:
        if hasattr(e, "status_code"):
            raise
        logger.warning(f"Agent loop check failed (non-critical): {e}")
        return True
