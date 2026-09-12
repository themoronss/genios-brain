"""Per-stage wall time for the ingest → graph → reasoning → cards chain.

Nothing on this path was timed, so "where does the hour go" had no answer but a guess. Each
`stage()` block writes ONE log line — `stage=<name> org=<id> ms=<n> [db=<n>] [k=v …]` — and hands
the caller a dict carrying the same numbers, so a script can collect them without parsing logs.

`db=` (statements sent) appears only once `count_statements(engine)` has been installed. The count
is process-wide, so it is exact when one chain runs alone (the measurement script) and approximate
under concurrent load; production only needs `ms`. Timing is logging only: a stage block never
changes, retries or swallows what it wraps.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Iterator

from genios_engine.platform.logging import get_logger

_log = get_logger("genios.stage")
_lock = threading.Lock()
_statements = 0
_counting = False


def count_statements(engine) -> None:
    """Count every statement `engine` sends (idempotent). Round-trips, not rows: over a WAN each
    one costs a full RTT, which is why a stage that is fast on a local copy can be slow on prod."""
    global _counting
    if getattr(engine, "_genios_stage_counter", False):
        return
    from sqlalchemy import event

    def _bump(*_a, **_k) -> None:
        global _statements
        with _lock:
            _statements += 1

    event.listen(engine, "before_cursor_execute", _bump)
    engine._genios_stage_counter = True
    _counting = True


@contextmanager
def stage(name: str, org_id: str, **fields) -> Iterator[dict]:
    rec: dict = {"stage": name, "org_id": org_id, **fields}
    start_db = _statements
    t0 = time.perf_counter()
    try:
        yield rec
    finally:
        rec["ms"] = round((time.perf_counter() - t0) * 1000)
        if _counting:
            rec["db"] = _statements - start_db
        extra = " ".join(f"{k}={v}" for k, v in rec.items()
                         if k not in ("stage", "org_id", "ms", "db"))
        _log.info("stage=%s org=%s ms=%s%s%s", name, org_id, rec["ms"],
                  f" db={rec['db']}" if "db" in rec else "", f" {extra}" if extra else "")
