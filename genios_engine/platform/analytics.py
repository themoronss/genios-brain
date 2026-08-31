"""PostHog emitter — server-side product analytics.

Why this exists at all: the browser already sends pageviews and clicks, but anything an investor
will ask about (revenue, spend, retention, activation) must come from the server. Client events are
blocked by ad-blockers, replayed on refresh, and trivially spoofed; a number that can be inflated by
opening a tab twice is not a number you can put in a deck.

Three design choices, each learned from the previous generation of this code:

1. **Direct HTTP POST, not the posthog-python library.** The library changed its `capture()`
   signature and key handling between releases and silently broke backend delivery twice. A plain
   POST is version-proof and lets us log the exact HTTP status, so "did it actually send?" is
   answerable from the logs.
2. **Off the request path.** The old emitter POSTed inline with a 4s timeout, so a slow PostHog
   added latency to a customer's request. Here events go onto a bounded queue drained by one daemon
   thread; if PostHog is down the queue fills and events are *dropped with a counter*, never
   blocking or backing up.
3. **Definitions come from `platform.metrics`.** The person properties (`plan`, `is_internal`,
   `mrr_inr`) are computed exactly as the admin console computes them — including MRR counting only
   accounts with a settled subscription — so the two surfaces cannot disagree.

Everything here is best-effort: analytics must never break, slow, or fail the action it observes.
"""
from __future__ import annotations

import atexit
import json
import queue
import threading
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.platform import metrics as M
from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.analytics")

# Bounded on purpose: analytics backing up must cost us events, never memory or request latency.
_QUEUE_MAX = 2000
_q: queue.Queue = queue.Queue(maxsize=_QUEUE_MAX)
_worker: threading.Thread | None = None
_lock = threading.Lock()
_dropped = 0


def _enabled() -> bool:
    return bool(get_settings().posthog_api_key)


def _post(payload: dict) -> None:
    s = get_settings()
    try:
        body = json.dumps(payload, default=str).encode("utf-8")
    except Exception as e:                                   # noqa: BLE001
        # An unserialisable property costs exactly one event. Letting it escape would kill the
        # drain thread and silently end ALL analytics for the life of the process.
        _log.warning("analytics: '%s' unserialisable (%s) — dropped",
                     payload.get("event"), type(e).__name__)
        return
    req = urllib.request.Request(f"{s.posthog_host.rstrip('/')}/capture/", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            if resp.status >= 300:
                _log.warning("analytics: '%s' HTTP %s", payload.get("event"), resp.status)
    except urllib.error.HTTPError as e:
        _log.warning("analytics: '%s' REJECTED HTTP %s: %s",
                     payload.get("event"), e.code, e.read()[:200])
    except Exception as e:                                   # noqa: BLE001
        _log.warning("analytics: '%s' FAILED %s: %s", payload.get("event"), type(e).__name__, e)


def _drain() -> None:
    while True:
        item = _q.get()
        if item is None:                                     # shutdown sentinel
            _q.task_done()
            return
        try:
            _post(item)
        except Exception:                                    # noqa: BLE001
            # Defense in depth: this thread must outlive every possible bad event. If it dies,
            # analytics stops for the whole process and nothing tells us.
            _log.warning("analytics: drain error on '%s'", item.get("event"), exc_info=True)
        finally:
            _q.task_done()


def _ensure_worker() -> None:
    global _worker
    if _worker is not None and _worker.is_alive():
        return
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_drain, name="genios-analytics", daemon=True)
            _worker.start()


def capture(org_id: str, event: str, properties: dict[str, Any] | None = None,
            person: dict[str, Any] | None = None) -> None:
    """Queue one event. Never raises, never blocks.

    `distinct_id` is the org: one account = one company, the same unit the admin console counts, so
    "active users" means the same thing in both places. `person` sets person properties on the same
    request ($set), which is how a dashboard filters out our own accounts.
    """
    global _dropped
    if not _enabled() or not org_id or not event:
        return
    s = get_settings()
    props = dict(properties or {})
    # Stamped on EVERY event, always. Local and production both post to the same project, so
    # without this a laptop restart looks like real product usage and there is no way to tell them
    # apart after the fact. Adding it later cannot fix events already stored — it has to be here
    # before the dashboards are built.
    props.setdefault("env", s.env)
    props.setdefault("emitter", "engine")
    payload: dict[str, Any] = {
        "api_key": s.posthog_api_key,
        "event": event,
        "distinct_id": str(org_id),
        "properties": props,
    }
    if person:
        payload["properties"]["$set"] = person
    _ensure_worker()
    try:
        _q.put_nowait(payload)
    except queue.Full:
        _dropped += 1
        if _dropped % 100 == 1:                              # log the first and every 100th
            _log.warning("analytics: queue full, dropped %s event(s)", _dropped)


def identify(org_id: str, person: dict[str, Any]) -> None:
    """Update an account's person properties without recording a product action."""
    capture(org_id, "$identify", {"$set": person})


def person_props(conn, org_id: str) -> dict[str, Any]:
    """The person properties for an account, read from the database so PostHog's cohorts and the
    admin console segment identically. Returns {} on any error — a failed lookup must not stop the
    event itself from being sent."""
    try:
        row = conn.execute(text(
            "select subscription_tier, plan_status, is_internal, created_at, activated_at, "
            "(select count(*) from subscriptions sb where sb.org_id = orgs.id "
            " and sb.status='active' and sb.invoice_type='subscription') paid "
            "from orgs where id = :o"), {"o": org_id}).first()
    except Exception:                                        # noqa: BLE001
        return {}
    if row is None:
        return {}
    # MRR mirrors the console exactly: a plan only counts once money actually settled, so the
    # PostHog MRR tile can never disagree with the admin one.
    mrr = M.mrr_inr(row.subscription_tier, row.plan_status) if int(row.paid or 0) > 0 else 0.0
    return {
        "plan": row.subscription_tier,
        "plan_status": row.plan_status,
        "is_internal": bool(row.is_internal),
        "is_paying": int(row.paid or 0) > 0,
        "mrr_inr": mrr,
        "signup_date": row.created_at.isoformat() if isinstance(row.created_at, datetime) else None,
        "activated_at": row.activated_at.isoformat() if isinstance(row.activated_at, datetime) else None,
    }


def capture_with_person(engine, org_id: str, event: str,
                        properties: dict[str, Any] | None = None) -> None:
    """capture() plus freshly-read person properties. Use on the events that change an account's
    standing (signup, login, activation, payment) rather than on every high-frequency event."""
    if not _enabled():
        return
    person: dict[str, Any] = {}
    try:
        with engine.connect() as c:
            person = person_props(c, org_id)
    except Exception:                                        # noqa: BLE001
        person = {}
    capture(org_id, event, properties, person=person or None)


def stats() -> dict[str, Any]:
    return {"enabled": _enabled(), "queued": _q.qsize(), "dropped": _dropped}


@atexit.register
def _flush_on_exit() -> None:
    """Give queued events a short window to leave on shutdown. Bounded so a redeploy is never held
    up by analytics."""
    if _worker is None or not _worker.is_alive():
        return
    try:
        _q.put_nowait(None)
    except queue.Full:
        return
    _worker.join(timeout=3.0)
