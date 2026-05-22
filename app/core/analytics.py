import os
import logging
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# ── PostHog client ───────────────────────────────────────────────────────────
# An explicit Posthog instance with the key passed straight to the constructor.
# Robust across posthog-python versions — the module-level config attribute
# names changed between releases, which silently broke backend events
# ("API key is required"). sync_mode sends events inline, so they also survive
# Celery's prefork model (no background thread to lose on fork).
_POSTHOG_KEY = os.getenv("POSTHOG_API_KEY", "")
_POSTHOG_HOST = "https://eu.i.posthog.com"

_client = None
if _POSTHOG_KEY:
    try:
        from posthog import Posthog
        try:
            _client = Posthog(_POSTHOG_KEY, host=_POSTHOG_HOST, sync_mode=True)
        except TypeError:
            _client = Posthog(_POSTHOG_KEY, host=_POSTHOG_HOST)
        logger.info("analytics: PostHog client ready")
    except Exception as e:
        logger.warning("analytics: PostHog client init failed — %s", e)
else:
    logger.warning("analytics: POSTHOG_API_KEY not set — analytics disabled")

# Per-request LLM-cost accumulator. ApiAnalyticsMiddleware sets a fresh dict
# before the route runs; llm_client._log_usage adds to it; the middleware
# reads it back so the `api_call` event carries cost/tokens per agent.
# default=None means background (Celery) work simply skips accumulation.
llm_cost_var: ContextVar = ContextVar("genios_llm_cost", default=None)

# MRR (INR / month) per plan — keep in sync with billing.PLAN_PRICES_PAISE.
_PLAN_MRR_INR = {"early": 4500, "hustler": 4500, "startup": 25000}


def capture(org_id: str, event: str, properties: dict = None):
    """Fire a PostHog event. Non-blocking — never raises.

    Logs loudly (INFO / WARNING) so backend delivery can be verified in the
    DigitalOcean logs.
    """
    if _client is None:
        logger.warning("analytics: PostHog not configured — '%s' skipped", event)
        return
    try:
        _client.capture(event, distinct_id=org_id, properties=properties or {})
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
    """Flush any queued events (no-op in sync_mode). Safe to call on shutdown."""
    if _client is None:
        return
    try:
        _client.flush()
    except Exception as e:
        logger.debug(f"Analytics flush failed (non-critical): {e}")
