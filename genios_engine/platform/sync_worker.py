"""In-process durable sync-job worker. A single daemon thread claims queued (or crashed/stale)
sync jobs from sync_jobs and runs them to completion — heart-beating + checkpointing — so a sync
survives the process being restarted and the user closing their tab. No Celery/Upstash: a plain
thread + the DB (the durable queue). Started from main.py's lifespan; stopped on shutdown.

The poll is a SERVER-side claim loop (one cheap indexed query every few seconds) — NOT the client
waiting. LISTEN/NOTIFY was avoided because the Supabase transaction pooler doesn't support it.
"""

from __future__ import annotations

import os
import socket
import threading

from genios_engine.platform.config import get_settings
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.sync_worker")
_thread: threading.Thread | None = None
_stop = threading.Event()
_POLL_SECONDS = float(os.environ.get("GENIOS_SYNC_WORKER_POLL", "5"))
_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def _loop(initial_delay: float) -> None:
    # lazy import — routes.py wires the stores at import time; import here avoids a cycle
    from genios_engine.api.routes import run_one_sync_job

    if _stop.wait(initial_delay):
        return
    while not _stop.is_set():
        ran = False
        try:
            ran = run_one_sync_job(_WORKER_ID)     # claim + run one job (or no-op if queue empty)
        except Exception:                          # noqa: BLE001 — a crash must never kill the loop
            _log.exception("sync worker tick crashed")
        # If we just ran a job, loop again immediately (drain the queue); else sleep before polling.
        if not ran and _stop.wait(_POLL_SECONDS):
            return


def start_sync_worker() -> bool:
    """Start the daemon worker. Idempotent. Deliberately NOT gated by scheduler_enabled: user Sync
    jobs MUST run even when the periodic auto-sweep is disabled (e.g. multi-instance). The atomic
    claim (FOR UPDATE SKIP LOCKED) makes running a worker on every instance safe. Opt out only via
    GENIOS_SYNC_WORKER_ENABLED=false. main.py already gates the call on use_real_db."""
    global _thread
    if os.environ.get("GENIOS_SYNC_WORKER_ENABLED", "true").lower() == "false":
        _log.info("sync worker disabled (GENIOS_SYNC_WORKER_ENABLED=false)")
        return False
    if _thread is not None and _thread.is_alive():
        return True
    _stop.clear()
    initial_delay = float(get_settings().sync_initial_delay_seconds)   # let startup settle first
    _thread = threading.Thread(target=_loop, args=(initial_delay,),
                               daemon=True, name="genios-sync-worker")
    _thread.start()
    _log.info("durable sync worker started (id=%s, poll=%ss)", _WORKER_ID, _POLL_SECONDS)
    return True


def stop_sync_worker() -> None:
    _stop.set()
    global _thread
    _thread = None
