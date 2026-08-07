"""In-process heavy-maintenance and minute-scale delivery schedulers.

One daemon thread runs the cross-org sync/maintenance sweep at ``sync_interval_hours``. A second
thread runs only Layer 5.2 at ``delivery_interval_seconds`` so 5/30/120-minute retry rungs, quiet
hours and attention-window wakeups do not inherit a six-hour ingestion cadence. Both use only a
plain thread plus PostgreSQL. Started from main.py's lifespan; stopped on shutdown.

Multi-instance note: ingestion is idempotent but duplicated work can be wasteful. Delivery is
explicitly replica-safe through due-row ``SKIP LOCKED`` claims and fencing tokens. Deployments that
disable this scheduler must replace both cadences with external workers; a six-hour cron is not a
valid delivery worker.
"""
from __future__ import annotations

import threading

from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.scheduler")
_thread: threading.Thread | None = None
_delivery_thread: threading.Thread | None = None
_stop = threading.Event()


def _loop(interval_seconds: float, initial_delay: float) -> None:
    # lazy import: routes.py wires the stores at import time; importing here avoids a cycle
    from genios_engine.api.routes import run_maintenance_sweep

    if _stop.wait(initial_delay):        # let startup settle; interruptible
        return
    while not _stop.is_set():
        try:
            # heartbeat = sync sweep + card lifecycle (expire/snooze-wake) every tick + weekly L6
            res = run_maintenance_sweep()
            _log.info("scheduled maintenance sweep: %s", res)
        except Exception:                 # noqa: BLE001 — a crashed sweep must not kill the loop
            _log.exception("scheduled maintenance sweep crashed")
        if _stop.wait(interval_seconds):  # sleep until next tick (or until stop)
            return


def _delivery_loop(interval_seconds: float, initial_delay: float) -> None:
    # Separate lazy import avoids both the routes/store bootstrap cycle and the heavy sync path.
    from genios_engine.api.routes import run_delivery_sweep

    if _stop.wait(initial_delay):
        return
    while not _stop.is_set():
        try:
            result = run_delivery_sweep()
            _log.info("scheduled delivery sweep: %s", result)
        except Exception:                 # noqa: BLE001 — a provider/tenant cannot kill the loop
            _log.exception("scheduled delivery sweep crashed")
        if _stop.wait(interval_seconds):
            return


def start_scheduler() -> bool:
    """Start enabled daemon loops. Idempotent; returns true when at least one loop is alive."""
    global _thread, _delivery_thread
    s = get_settings()
    if not s.scheduler_enabled:
        _log.info("in-process schedulers disabled (scheduler_enabled=false)")
        return False
    _stop.clear()
    started = False
    if s.sync_interval_hours > 0 and (_thread is None or not _thread.is_alive()):
        _thread = threading.Thread(
            target=_loop,
            args=(s.sync_interval_hours * 3600.0, float(s.sync_initial_delay_seconds)),
            daemon=True, name="genios-sync-scheduler")
        _thread.start()
        started = True
        _log.info("auto-sync scheduler started: sweep every %sh (first run in %ss)",
                  s.sync_interval_hours, s.sync_initial_delay_seconds)
    if (s.delivery_interval_seconds > 0
            and (_delivery_thread is None or not _delivery_thread.is_alive())):
        _delivery_thread = threading.Thread(
            target=_delivery_loop,
            args=(float(s.delivery_interval_seconds),
                  float(s.delivery_initial_delay_seconds)),
            daemon=True, name="genios-delivery-scheduler")
        _delivery_thread.start()
        started = True
        _log.info("delivery scheduler started: sweep every %ss (first run in %ss)",
                  s.delivery_interval_seconds, s.delivery_initial_delay_seconds)
    if not started and not any(thread is not None and thread.is_alive()
                               for thread in (_thread, _delivery_thread)):
        _log.info("all scheduler intervals are disabled")
        return False
    return True


def stop_scheduler() -> None:
    _stop.set()
    global _thread, _delivery_thread
    _thread = None
    _delivery_thread = None
