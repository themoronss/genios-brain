"""In-process automatic data-sync scheduler. A single daemon thread runs a cross-org sync sweep
(L1 pull → L2/L3/L5) every `sync_interval_hours`, so connected tools stay fresh WITHOUT a button
click and WITHOUT Celery/Upstash (respects the no-periodic-broker rule — this uses only a plain
thread + the DB). Started from main.py's lifespan on startup; stopped on shutdown.

Multi-instance note: if the engine is scaled to >1 instance each runs its own sweep. That's safe for
data integrity (source_events dedup makes ingestion idempotent) but wasteful; for a multi-instance
deploy set GENIOS_SCHEDULER_ENABLED=false and drive /ingest/all from a single external cron instead.
"""
from __future__ import annotations

import threading

from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.scheduler")
_thread: threading.Thread | None = None
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


def start_scheduler() -> bool:
    """Start the daemon sweep thread. Idempotent; respects settings. Returns True if it started."""
    global _thread
    s = get_settings()
    if not s.scheduler_enabled or s.sync_interval_hours <= 0:
        _log.info("auto-sync scheduler disabled (scheduler_enabled=%s, interval=%sh)",
                  s.scheduler_enabled, s.sync_interval_hours)
        return False
    if _thread is not None and _thread.is_alive():
        return True
    _stop.clear()
    _thread = threading.Thread(
        target=_loop, args=(s.sync_interval_hours * 3600.0, float(s.sync_initial_delay_seconds)),
        daemon=True, name="genios-sync-scheduler")
    _thread.start()
    _log.info("auto-sync scheduler started: sweep every %sh (first run in %ss)",
              s.sync_interval_hours, s.sync_initial_delay_seconds)
    return True


def stop_scheduler() -> None:
    _stop.set()
    global _thread
    _thread = None
