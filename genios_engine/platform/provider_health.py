"""The alert nobody had when the provider stopped answering.

⛔ WHAT THIS EXISTS BECAUSE OF. Between 25 and 30 September 2026 **every model call in the product
failed**, on every lane, for five days:

    last successful call anywhere:  2026-09-25 11:09:30 UTC
    failures 26 Sep → 30 Sep:       2,062 · 1,836 · 2,993 · 3,152 · 1,240

All of them the same 400: *"You have reached your specified API usage limits."* The account's spend
limit, configured outside this system. It had also happened on 16–17 September and recovered on its
own. **Neither occurrence alerted, and nobody noticed either one.**

The data was never missing. `llm_costs.success` recorded every single failure with its error text.
There was simply no reader. That is this repository's own `not_carried` defect wearing a different
coat: a value computed correctly, written down correctly, and consulted by nothing.

WHY NOTHING ELSE CAUGHT IT. Every lane **fails open**, and that is the right design — a transport
failure must never delete a message. `l1_relevance` keeps the event at authority 3000, extraction
degrades rather than dropping, the screen lane has a rule path. So no queue backed up, no error
page appeared, and the product kept producing output with no judgment in it. There was already an
alert named `platform_llm_cap_hit` — but it watches GeniOS's OWN budget governor, which was
behaving perfectly. Nothing watched whether the provider was answering at all.

WHY A STREAK AND NOT A RATE. A rate needs a window, a denominator and a clock, and every one of
those is a thing to get wrong on a quiet tenant — two calls, one failure, 50%. A streak needs none
of them: twenty consecutive provider refusals cannot happen by chance, and a single success clears
it. It is exact, it needs no clock, and it says the same thing on a busy day and a quiet one.

⛔ ONLY PROVIDER-SIDE REFUSALS COUNT. `unparseable JSON` and `extraction_call_failed` are OUR
failures — a model answered and we could not use the answer. Counting them here would make this
alert cry wolf on a bad prompt, and an alert that fires for two reasons is an alert nobody reads.
Those belong to their own lanes' quality measures, which already exist.

PROCESS-LOCAL, AND DELIBERATELY NOT A TABLE. `llm_costs` is already the record; this is only the
reader. A counter in memory needs no migration, no retention and no cleanup, and the worst case of
losing it on restart is one delayed alert against a condition that lasted five days.
"""

from __future__ import annotations

import threading
import time

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.provider_health")

#: Consecutive provider refusals before the alert fires. Twenty is short enough to catch a real
#: outage within minutes of a normal sweep and long enough that a handful of transient 429s under
#: retry never reaches it.
STREAK_TO_ALERT = 20

#: Seconds before the same condition may alert again. The outage this was written for lasted five
#: days and produced three thousand failures a day; without a cooldown that is three thousand
#: messages. One an hour is enough to keep a live problem visible.
COOLDOWN_S = 3600.0

#: ⛔ THE CLOSED SET OF PROVIDER-SIDE REFUSALS, matched case-insensitively against the error text.
#: Each one means *the request never produced an answer and the reason is on their side or in our
#: account configuration* — not that we sent something malformed.
#:
#: `usage limits` is the one that cost five days. `temperature` is deprecated is deliberately NOT
#: here: that was our bug (we sent a field the model refuses) and it is fixed at the call site, not
#: alerted on — see `context/llm/client.NO_SAMPLING_PREFIXES`.
PROVIDER_REFUSALS = (
    "usage limits",          # the account's configured spend limit — the 25 Sep outage
    "rate_limit",            # 429
    "overloaded",            # 529
    "insufficient_quota",
    "credit balance",
    "authentication_error",  # a rotated or revoked key stops everything just as completely
    "permission_error",
)


def is_provider_refusal(error: str | None) -> bool:
    """Whether this error means the provider refused, rather than that we sent or parsed badly."""
    if not error:
        return False
    text = str(error).lower()
    return any(marker in text for marker in PROVIDER_REFUSALS)


class _Watch:
    """One counter, guarded. `record_cost` is called from the capture lane's worker threads, so
    the read-modify-write has to be atomic for the same reason `RelevancePage` holds a lock."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._streak = 0
        self._last_alert_at = 0.0
        self._last_error = ""

    def observe(self, *, success: bool, error: str | None, model: str, purpose: str) -> bool:
        """Returns True when this observation is the one that should raise the alert.

        A success — any success, on any lane — clears the streak, because the provider is
        demonstrably answering.
        """
        with self._lock:
            if success:
                self._streak = 0
                return False
            if not is_provider_refusal(error):
                # Our failure, not theirs. It does not clear the streak either: a bad prompt in the
                # middle of an outage must not reset the count and hide it.
                return False
            self._streak += 1
            self._last_error = str(error)[:200]
            if self._streak < STREAK_TO_ALERT:
                return False
            now = time.monotonic()
            if now - self._last_alert_at < COOLDOWN_S:
                return False
            self._last_alert_at = now
            return True

    @property
    def streak(self) -> int:
        with self._lock:
            return self._streak

    def reset(self) -> None:
        with self._lock:
            self._streak = 0
            self._last_alert_at = 0.0


_WATCH = _Watch()


def observe(*, success: bool, error: str | None = None, model: str = "",
            purpose: str = "", org_id: str | None = None) -> None:
    """Called once per model call, from the one place every call already lands.

    Best-effort and silent by contract: an alert must never break the caller, and this one sits
    inside the accounting write that the whole ledger depends on.
    """
    try:
        if not _WATCH.observe(success=success, error=error, model=model, purpose=purpose):
            return
        from genios_engine.platform import ops_alert
        ops_alert.notify(
            "provider_refusing_calls",
            streak=_WATCH.streak,
            model=model or "(unknown)",
            purpose=purpose or "(unknown)",
            org_id=org_id or "(unattributed)",
            error=_WATCH._last_error,          # noqa: SLF001 — same module, one object
            what_to_check="the account's spend limit and key in the provider console",
        )
        _log.error("provider refusing calls — %d consecutive: %s", _WATCH.streak,
                   _WATCH._last_error)
    except Exception:      # noqa: BLE001 — an alert must never break the accounting write
        _log.exception("provider health watch failed")


__all__ = ["COOLDOWN_S", "PROVIDER_REFUSALS", "STREAK_TO_ALERT", "is_provider_refusal", "observe"]
