import os
import logging
from contextvars import ContextVar

import posthog as _posthog

logger = logging.getLogger(__name__)

_posthog.project_api_key = os.getenv("POSTHOG_API_KEY", "")
_posthog.host = "https://eu.i.posthog.com"
# DIAGNOSTIC: make posthog-python log its own HTTP send activity + errors,
# so backend delivery failures are visible in the DigitalOcean logs.
_posthog.debug = True

# Per-request LLM-cost accumulator. ApiAnalyticsMiddleware sets a fresh dict
# before the route runs; llm_client._log_usage adds to it; the middleware
# reads it back so the `api_call` event carries cost/tokens per agent.
# default=None means background (Celery) work simply skips accumulation.
llm_cost_var: ContextVar = ContextVar("genios_llm_cost", default=None)

# MRR (INR / month) per plan — keep in sync with billing.PLAN_PRICES_PAISE.
_PLAN_MRR_INR = {"early": 4500, "hustler": 4500, "startup": 25000}


def capture(org_id: str, event: str, properties: dict = None):
    """Fire a PostHog event. Non-blocking — never raises.

    Logs loudly (INFO / WARNING) so backend delivery can actually be
    verified in the DigitalOcean logs — `logger.debug` was invisible there.
    """
    try:
        if not _posthog.project_api_key:
            logger.warning("analytics: POSTHOG_API_KEY is empty — '%s' skipped", event)
            return
        _posthog.capture(org_id, event, properties or {})
        _posthog.flush()
        logger.info("analytics: sent '%s' (distinct_id=%s)", event, org_id)
    except Exception as e:
        logger.warning(
            "analytics: capture FAILED for '%s' — %s: %s",
            event, type(e).__name__, e,
        )


def record_llm_cost(cost_usd: float, tokens: int):
    """Add one LLM call's cost to the current request's accumulator, if any."""
    acc = llm_cost_var.get()
    if acc is not None:
        acc["cost_usd"] += cost_usd or 0.0
        acc["tokens"] += tokens or 0


def org_properties(plan: str, credits: int = None, created_at=None) -> dict:
    """PostHog person ($set) properties for an org/account, so DAU / retention
    / revenue can be sliced by plan, MRR and paying status."""
    plan = (plan or "trial").lower()
    props = {
        "plan": plan,
        "is_paying": plan not in ("trial", ""),
        "mrr_inr": _PLAN_MRR_INR.get(plan, 0),
    }
    if credits is not None:
        props["credits_balance"] = credits
    if created_at is not None:
        props["signup_date"] = str(created_at)
    return props


def flush():
    """Send any queued events. Call on app shutdown so the last batch isn't lost."""
    try:
        if _posthog.project_api_key:
            _posthog.flush()
    except Exception as e:
        logger.debug(f"Analytics flush failed (non-critical): {e}")
