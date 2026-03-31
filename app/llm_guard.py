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

# Hard cap on LLM calls per context request (PDF spec)
LLM_CALLS_HARD_CAP = 3

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


def check_agent_loop(org_id: str, agent_id: str, plan_tier: str) -> bool:
    """
    Agent loop protection: track consecutive context calls from the same agent.
    Returns True if allowed, raises HTTP 429 if loop detected (>= hard cap).

    Uses Redis sorted set with 60s TTL window.
    Hard cap = 3 LLM calls per context (all plans per PDF spec).
    """
    try:
        from app.redis_client import redis_client
        from app.plan_enforcer import PLAN_CONFIG
        from fastapi import HTTPException

        config = PLAN_CONFIG.get(plan_tier, PLAN_CONFIG["trial"])
        chain_depth_limit = config["max_chain_depth"]

        loop_key = f"agent_loop:{org_id}:{agent_id or 'default'}"
        now = int(time.time())
        window_start = now - 60  # 60-second window

        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(loop_key, 0, window_start)
        pipe.zcard(loop_key)
        pipe.zadd(loop_key, {str(now): now})
        pipe.expire(loop_key, 120)
        results = pipe.execute()
        call_count = results[1]

        if call_count >= LLM_CALLS_HARD_CAP:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "AGENT_LOOP_DETECTED",
                    "message": f"Agent loop detected: {call_count} context calls in 60s window. Max {LLM_CALLS_HARD_CAP} allowed.",
                    "calls_in_window": call_count,
                    "hard_cap": LLM_CALLS_HARD_CAP,
                },
            )

        return True
    except Exception as e:
        if hasattr(e, "status_code"):  # Re-raise HTTPException
            raise
        logger.warning(f"Agent loop check failed (non-critical): {e}")
        return True
