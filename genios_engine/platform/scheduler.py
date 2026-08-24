"""In-process automatic data-sync scheduler. A single daemon thread runs a cross-org sync sweep
(L1 pull → L2/L3/L5) every `sync_interval_hours`, so connected tools stay fresh WITHOUT a button
click and WITHOUT Celery/Upstash (respects the no-periodic-broker rule — this uses only a plain
thread + the DB). Started from main.py's lifespan on startup; stopped on shutdown.

Multi-instance note: if the engine is scaled to >1 instance each runs its own sweep. That's safe for
data integrity (source_events dedup makes ingestion idempotent) but wasteful; for a multi-instance
deploy set GENIOS_SCHEDULER_ENABLED=false and drive /ingest/all from a single external cron instead.
"""
from __future__ import annotations

import concurrent.futures as _futures
import threading

from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.scheduler")
_thread: threading.Thread | None = None
_stop = threading.Event()

# Hard wall-clock cap on ONE sweep tick. Root-caused incident (2026-08-18 → 08-21): a Composio call
# with no underlying timeout hung inside one org's sync, and because the whole sweep ran unbounded
# on this single thread, that ONE hang froze every future tick forever — 3 days of total silence,
# every org, with nothing in the logs to explain it (a bare `except Exception` never fires on a
# hang, only on a raise). The Composio timeout itself is fixed (composio_base.py / composio.py),
# but this bound stays as defense-in-depth: whatever hangs next, a tick can time out and the
# scheduler self-heals on the NEXT tick instead of dying silently for days.
_SWEEP_TIMEOUT_S = 1200.0      # 20 min — generous for a real multi-org sweep, still bounded


def _run_sweep_bounded():
    # lazy import: routes.py wires the stores at import time; importing here avoids a cycle
    from genios_engine.api.routes import run_maintenance_sweep

    # NOT a `with ThreadPoolExecutor(...)` block — its __exit__ calls shutdown(wait=True), which
    # re-blocks on the same hung worker the instant .result(timeout=...) gives up, making the
    # deadline cosmetic (the exact bug this incident traced back to in composio_base.py).
    ex = _futures.ThreadPoolExecutor(max_workers=1)
    try:
        return ex.submit(run_maintenance_sweep).result(timeout=_SWEEP_TIMEOUT_S)
    finally:
        ex.shutdown(wait=False)


def _loop(interval_seconds: float, initial_delay: float) -> None:
    if _stop.wait(initial_delay):        # let startup settle; interruptible
        return
    while not _stop.is_set():
        try:
            # heartbeat = sync sweep + card lifecycle (expire/snooze-wake) every tick + weekly L6
            res = _run_sweep_bounded()
            _log.info("scheduled maintenance sweep: %s", res)
        except _futures.TimeoutError:
            _log.error("scheduled maintenance sweep exceeded %ss — abandoning this tick, "
                      "the NEXT tick still fires on schedule", _SWEEP_TIMEOUT_S)
            from genios_engine.platform import ops_alert
            ops_alert.notify("scheduler_sweep_timeout", timeout_s=_SWEEP_TIMEOUT_S)
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
