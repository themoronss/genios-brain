import os
import json
import logging
import urllib.request
import urllib.error
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# ── PostHog ──────────────────────────────────────────────────────────────────
# Events are sent with a direct HTTP POST to PostHog's /capture/ endpoint.
# The posthog-python library changed its capture() signature AND its key
# handling between releases and silently broke backend delivery twice — a plain
# POST is version-proof, works inside forked Celery workers, and lets us log the
# exact HTTP status so delivery is actually verifiable in the logs.
_POSTHOG_KEY = os.getenv("POSTHOG_API_KEY", "")
_POSTHOG_HOST = "https://eu.i.posthog.com"

# Per-request LLM-cost accumulator. ApiAnalyticsMiddleware sets a fresh dict
# before the route runs; llm_client._log_usage adds to it; the middleware reads
# it back so the `api_call` event carries cost/tokens per agent.
llm_cost_var: ContextVar = ContextVar("genios_llm_cost", default=None)

# MRR (INR / month) per plan — keep in sync with billing.PLAN_PRICES_PAISE.
_PLAN_MRR_INR = {"early": 4500, "hustler": 4500, "startup": 25000}

# Fixed INR-per-USD rate used ONLY to normalize multi-gateway revenue into one
# currency for dashboards (Razorpay charges INR, Stripe charges USD). It is NOT
# a live FX feed — the gateway's settled amount is the true ₹. Override per-env
# via INR_PER_USD when the rate drifts materially.
INR_PER_USD = float(os.getenv("INR_PER_USD", "83"))


def to_inr_paise(amount_minor: int, currency: str) -> int:
    """Normalize a charged amount — given in the currency's MINOR unit (paise for
    INR, cents for USD) — to INR paise, so revenue across Razorpay (INR) and
    Stripe (USD) can be summed in one currency without mixing units.

    INR: already paise → returned unchanged.
    USD: cents × INR_PER_USD = INR paise  (e.g. 29900¢ × 83 = 2,481,700 paise).
    """
    if not amount_minor:
        return 0
    if (currency or "INR").upper() == "USD":
        return int(round(amount_minor * INR_PER_USD))
    return int(amount_minor)


def capture(org_id: str, event: str, properties: dict = None):
    """Send one event to PostHog via a direct HTTP POST. Never raises.

    Logs the exact HTTP status so backend delivery is verifiable in the logs.
    """
    if not _POSTHOG_KEY:
        logger.warning("analytics: POSTHOG_API_KEY not set — '%s' skipped", event)
        return
    try:
        body = json.dumps({
            "api_key": _POSTHOG_KEY,
            "event": event,
            "distinct_id": str(org_id),
            "properties": properties or {},
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{_POSTHOG_HOST}/capture/",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            logger.info("analytics: '%s' → PostHog HTTP %s", event, resp.status)
    except urllib.error.HTTPError as e:
        logger.warning("analytics: '%s' REJECTED — HTTP %s: %s",
                       event, e.code, e.read()[:200])
    except Exception as e:
        logger.warning("analytics: capture FAILED for '%s' — %s: %s",
                       event, type(e).__name__, e)


def record_llm_cost(cost_usd: float, tokens: int):
    """Add one LLM call's cost to the current request's accumulator, if any."""
    acc = llm_cost_var.get()
    if acc is not None:
        acc["cost_usd"] += cost_usd or 0.0
        acc["tokens"] += tokens or 0


def org_properties(plan: str, credits: int = None, created_at=None,
                   is_internal: bool = False) -> dict:
    """PostHog person ($set) properties for an org/account, so DAU / retention
    / revenue can be sliced by plan, MRR and paying status.

    `is_internal` flags founder/test/demo accounts. Every dashboard filters on a
    cohort where is_internal != true, so internal traffic never pollutes the
    numbers. Defaults False so real customers are external by default.
    """
    plan = (plan or "trial").lower()
    props = {
        "plan": plan,
        "is_paying": plan not in ("trial", ""),
        "mrr_inr": _PLAN_MRR_INR.get(plan, 0),
        "is_internal": bool(is_internal),
    }
    if credits is not None:
        props["credits_balance"] = credits
    if created_at is not None:
        props["signup_date"] = str(created_at)
    return props


def flush():
    """No-op — events are sent synchronously via direct POST."""
    return
