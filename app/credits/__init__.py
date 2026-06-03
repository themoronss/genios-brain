"""Credit-based billing primitives.

Public API:
    from app.credits import deduct, refund, grant, balance, InsufficientCredits

Single chokepoint: every metered operation (LLM call, ingest item, sync record)
must go through `deduct(...)`. The function performs an atomic UPDATE that
short-circuits when the org's balance is below the requested cost, eliminating
the TOCTOU race that a SELECT-then-UPDATE pattern would introduce.

Idempotency: pass `idempotency_key` so retried Celery tasks / replayed
webhooks don't double-charge. On collision the existing ledger row is
returned and balances are left untouched.
"""

from app.credits.ledger import (
    InsufficientCredits,
    deduct,
    try_deduct,
    refund,
    grant,
    topup,
    balance,
    estimate_cost,
    check_and_increment_sonnet_quota,
    CONTEXT,
    SYNC,
    PROACTIVE,
    GENERIC,
)
from app.credits.billing_context import billing_disabled, is_billing_enabled

__all__ = [
    "InsufficientCredits",
    "deduct",
    "try_deduct",
    "refund",
    "grant",
    "topup",
    "balance",
    "estimate_cost",
    "check_and_increment_sonnet_quota",
    "billing_disabled",
    "is_billing_enabled",
    "CONTEXT",
    "SYNC",
    "PROACTIVE",
    "GENERIC",
]
