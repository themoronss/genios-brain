"""Durable sync-job store — enqueue / atomic-claim / heartbeat / checkpoint / complete / fail.

The worker (platform/sync_worker.py) drives this; the Sync endpoints only enqueue. Claiming is
multi-instance safe (FOR UPDATE SKIP LOCKED), and a 'running' job whose heartbeat has gone stale is
treated as crashed and re-claimable — that is what makes a sync survive a deploy / OOM / worker
recycle and resume from its checkpoint.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.platform.ids import new_id

_STALE_SECONDS = 180          # a running job silent this long is presumed dead → reclaimable
_MAX_ATTEMPTS = 6             # give a genuinely-broken job a bounded number of resumes, then fail


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue(engine, org_id: str, sources: list[str]) -> bool:
    """Queue a sync job for the org. No-op (returns False) if one is already active — the durable
    overlap guard (unique partial index) means a duplicate Sync click can't spawn a second job."""
    try:
        with engine.begin() as c:
            row = c.execute(text(
                "insert into sync_jobs (id, org_id, sources, status, created_at, updated_at) "
                "values (:id,:o,cast(:s as jsonb),'queued',:ts,:ts) "
                "on conflict do nothing returning id"),
                {"id": new_id("job"), "o": org_id, "s": json.dumps(sources), "ts": _now()}).first()
        return row is not None
    except Exception:      # noqa: BLE001 — unique violation (active job exists) → treat as "already queued"
        return False


def claim_next(engine, worker_id: str) -> dict | None:
    """Atomically claim the oldest queued job, OR a running job whose heartbeat is stale (crashed).
    Returns the claimed job as a dict (with its checkpoint) or None if nothing to do."""
    now = _now()
    stale_before = now - timedelta(seconds=_STALE_SECONDS)
    with engine.begin() as c:
        r = c.execute(text(
            "update sync_jobs set status='running', claimed_by=:w, heartbeat_at=:ts, "
            "attempts=attempts+1, updated_at=:ts where id = ("
            "  select id from sync_jobs where status='queued' "
            "     or (status='running' and heartbeat_at < :stale) "
            "  order by created_at for update skip locked limit 1) "
            "returning id, org_id, sources, checkpoint, attempts"),
            {"w": worker_id, "ts": now, "stale": stale_before}).first()
    if r is None:
        return None
    return {"id": r.id, "org_id": r.org_id,
            "sources": r.sources if isinstance(r.sources, list) else json.loads(r.sources or "[]"),
            "checkpoint": r.checkpoint if isinstance(r.checkpoint, dict) else json.loads(r.checkpoint or "{}"),
            "attempts": int(r.attempts or 0)}


def heartbeat(engine, job_id: str, checkpoint: dict | None = None) -> None:
    """Prove liveness (and persist progress). Called frequently by the worker as it works, so a
    crash leaves a stale heartbeat that another worker can detect and resume from `checkpoint`."""
    if checkpoint is not None:
        with engine.begin() as c:
            c.execute(text("update sync_jobs set heartbeat_at=:ts, checkpoint=cast(:cp as jsonb), "
                           "updated_at=:ts where id=:id"),
                      {"ts": _now(), "cp": json.dumps(checkpoint), "id": job_id})
    else:
        with engine.begin() as c:
            c.execute(text("update sync_jobs set heartbeat_at=:ts, updated_at=:ts where id=:id"),
                      {"ts": _now(), "id": job_id})


def complete(engine, job_id: str) -> None:
    with engine.begin() as c:
        c.execute(text("update sync_jobs set status='done', updated_at=:ts where id=:id"),
                  {"ts": _now(), "id": job_id})


def fail(engine, job_id: str, error: str) -> None:
    """A crashed/errored run. Under the attempt cap → back to 'queued' so a worker RESUMES it (the
    work is idempotent). Over the cap → 'failed' (stop retrying a genuinely-broken job)."""
    with engine.begin() as c:
        c.execute(text(
            "update sync_jobs set status = case when attempts >= :cap then 'failed' else 'queued' end, "
            "error=:e, updated_at=:ts where id=:id"),
            {"cap": _MAX_ATTEMPTS, "e": (error or "")[:400], "ts": _now(), "id": job_id})
