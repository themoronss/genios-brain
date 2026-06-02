"""Request-scoped billing toggle.

Dashboard renders are passive — opening a contact page or clicking a graph
node should NOT decrement the user's visible credit meter, even if the
internal pipeline ends up calling an LLM (e.g. to lazily generate a
narrative on first view).

API integrators calling `/v1/context` programmatically DO consume credits,
because they're using GeniOS as a paid service.

The two paths run through the same code, so we can't decide where to
deduct based on the call site. Instead the request handler that knows
the source (header `X-GeniOS-Source`) flips this contextvar for the
duration of the request, and `llm_client.call()` reads it before
deciding whether to call `deduct(...)`.

Usage:
    from app.credits.billing_context import billing_disabled
    if source == 'dashboard':
        with billing_disabled():
            bundle = build_context_bundle(...)
    else:
        bundle = build_context_bundle(...)

Default: billing ON. The fail-safe is to charge — silently free calls
would be a money leak.
"""

from contextlib import contextmanager
from contextvars import ContextVar

# Default True = charge. Anything that wants to opt out must use the
# context manager so the reset is guaranteed even on exceptions.
_bill_credits: ContextVar[bool] = ContextVar("_bill_credits", default=True)


def is_billing_enabled() -> bool:
    """Read the current billing flag. Default True if never set in this
    request (e.g. background tasks, system internals)."""
    return _bill_credits.get()


@contextmanager
def billing_disabled():
    """Disable credit deduction for the duration of the `with` block.

    Use ONLY for dashboard-passive paths. Re-entering with `billing_disabled`
    is a no-op (stays disabled). The contextvar token mechanism ensures
    nested calls restore the previous value, not blindly set True.
    """
    token = _bill_credits.set(False)
    try:
        yield
    finally:
        _bill_credits.reset(token)


def disable_billing_for_request():
    """Imperative form for FastAPI handlers that span hundreds of lines and
    can't be wrapped in a single `with` block. Returns a token that the
    caller MUST pass back to `restore_billing()` in a `finally:` clause.

    Prefer `billing_disabled()` as a `with`-block when the scope is small.
    """
    return _bill_credits.set(False)


def restore_billing(token) -> None:
    """Pair with `disable_billing_for_request()`. Safe to call with a
    None token (no-op) so handlers can do a single restore call regardless
    of whether they actually disabled billing."""
    if token is not None:
        _bill_credits.reset(token)
