"""The act pump — approved delegations reach the client's agent in SECONDS, not on the 6-hourly
distribution sweep (SCREEN_INTEL_P6_BUILD §3.1).

`outbox.drain()` runs only inside `run_distribution`, on the sync sweep. That cadence is right for
cards and wrong for an action a person just approved. So the approve route calls `kick(engine)`
after its transaction commits, and ONE daemon thread per process drains `agent_action` rows only
(`outbox.drain_actions`), then sleeps exactly until the next queued action row is due (the short
retry ladder: 10 s, 30 s, 2 min, 10 min), capped at IDLE_CAP_S. With nothing queued it waits on
its event and issues ZERO queries — no Celery task, no periodic job (the broker is quota-limited
Upstash; plan rule). Multiple processes are safe: the claim is FOR UPDATE SKIP LOCKED with a lease.

A row queued before a restart is picked up by the next `kick` (every approval and every
`GET /v1/delegations` kicks) or, at the latest, by the sweep's generic drain.
"""
from __future__ import annotations

import threading

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.deliver.act_pump")

IDLE_CAP_S = 60.0
MIN_WAIT_S = 0.5

_lock = threading.Lock()
_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None
_engine = None


def _loop() -> None:
    from genios_engine.deliver import outbox
    while not _stop.is_set():
        _wake.clear()
        try:
            outbox.drain_actions(_engine)
            wait = outbox.next_action_due_seconds(_engine)
        except Exception:      # noqa: BLE001 — a failed pass is retried on the cap, never fatal
            _log.exception("act pump pass failed")
            wait = IDLE_CAP_S
        timeout = None if wait is None else max(MIN_WAIT_S, min(float(wait), IDLE_CAP_S))
        _wake.wait(timeout)


def kick(engine) -> None:
    """Start the pump if needed and make it drain now. Call AFTER the approving commit."""
    global _thread, _engine
    with _lock:
        if _thread is None or not _thread.is_alive():
            _engine = engine
            _stop.clear()
            _thread = threading.Thread(target=_loop, name="genios-act-pump", daemon=True)
            _thread.start()
    _wake.set()


def running() -> bool:
    return _thread is not None and _thread.is_alive()


def stop(timeout: float = 5.0) -> None:
    """Stop the pump (tests, shutdown)."""
    global _thread
    _stop.set()
    _wake.set()
    t = _thread
    if t is not None:
        t.join(timeout)
    _thread = None


__all__ = ["IDLE_CAP_S", "kick", "running", "stop"]
