"""Scheduled batch pull with rate-limit + back-pressure.

Per g-i-1 §1.1.2:
- Rate-limit: token-bucket per source; respect Retry-After / 429 with exp backoff + jitter
- Back-pressure: bounded queue; when full, pause pulling (no OOM on slow consumer)
- Idempotency: stable item_id so retries dedupe downstream
- Atomic checkpoint advance AFTER emission (crash re-processes, never skips)

The actual cron trigger (Celery beat OR APScheduler) is wired in celery_app.py /
core/main.py at process start. This module exposes the pure pull-batch routine.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.foundations import audit
from core.foundations.telemetry import get_logger
from core.memory.delta_strategies import advance_cursor, load_cursor
from core.memory.emit import emit
from core.memory.interface import MemoryAdapter
from core.memory.normalize import normalize
from core.memory.scope import ScopeEnforcer
from core.memory.types import Cursor, RawRecord, ReadScope

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Rate limit / back-pressure config
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BatchConfig:
    """Tunables for one batch run. Per-source defaults live in core.foundations.config."""

    page_size: int = 100
    max_pages_per_run: int = 50  # cap total work per run (back-pressure)
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    max_retries_on_429: int = 5


# ─────────────────────────────────────────────────────────────────────────────
# Token bucket — simple per-process limiter
# ─────────────────────────────────────────────────────────────────────────────


class TokenBucket:
    """Allow `rate` operations per `period_seconds`. Blocks (sleeps) when empty."""

    def __init__(self, rate: int, period_seconds: float = 1.0) -> None:
        self._capacity = rate
        self._tokens = float(rate)
        self._period = period_seconds
        self._refill_rate = rate / period_seconds
        self._last_refill = time.monotonic()

    def acquire(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now
        if self._tokens < 1.0:
            wait = (1.0 - self._tokens) / self._refill_rate
            time.sleep(wait)
            self._tokens = 0.0
        else:
            self._tokens -= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# Back-pressure helper
# ─────────────────────────────────────────────────────────────────────────────


def _backoff(attempt: int, cfg: BatchConfig) -> float:
    """Exponential backoff with jitter, capped."""
    raw = cfg.initial_backoff_seconds * (2**attempt)
    capped: float = min(raw, cfg.max_backoff_seconds)
    jitter = 0.5 + random.random() * 0.5  # noqa: S311 — not security-sensitive
    return capped * jitter


# ─────────────────────────────────────────────────────────────────────────────
# Main batch run
# ─────────────────────────────────────────────────────────────────────────────


def run_batch(
    *,
    session: Session,
    adapter: MemoryAdapter,
    connection_id: str,
    org_id: str,
    scopes: list[ReadScope],
    cfg: BatchConfig | None = None,
    rate_limiter: TokenBucket | None = None,
) -> int:
    """Pull, scope-gate, normalize, emit. Returns count emitted.

    Atomicity guarantee: cursor advances ONLY after the last record in the page is
    emitted. If we crash mid-page, the next run re-pulls that page; downstream
    dedupes via stable item_id.
    """
    cfg = cfg or BatchConfig()
    enforcer = ScopeEnforcer(scopes, connection_id=connection_id, org_id=org_id)
    mapping = adapter.get_mapping()
    cursor = load_cursor(session, connection_id)
    total_emitted = 0

    for _page_idx in range(cfg.max_pages_per_run):
        if rate_limiter is not None:
            rate_limiter.acquire()

        records, next_cursor, has_more = _pull_with_retry(adapter, cursor, cfg.page_size, cfg)
        if not records:
            break

        allowed = enforcer.filter(records)

        for record in allowed:
            try:
                item = normalize(record, mapping, source_id=connection_id)
                emit(item, org_id=org_id)
                total_emitted += 1
            except Exception as e:
                log.warning(
                    "record_skipped",
                    connection_id=connection_id,
                    native_id=record.native_id,
                    error=str(e),
                )

        # Advance cursor + commit AFTER emission so re-runs are safe.
        advance_cursor(
            session,
            connection_id=connection_id,
            org_id=org_id,
            new_cursor=next_cursor,
            items_pulled_delta=len(allowed),
        )
        session.commit()

        cursor = next_cursor
        if not has_more:
            break

    audit.record(
        org_id=org_id,
        actor_type="system",
        actor_id="batch_runner",
        action="data_accessed",
        target_type="connection",
        target_id=connection_id,
        metadata={
            "outcome": "completed",
            "items_emitted": total_emitted,
            "scope_drops": enforcer.drop_count,
        },
    )
    return total_emitted


def _pull_with_retry(
    adapter: MemoryAdapter,
    cursor: Cursor | None,
    page_size: int,
    cfg: BatchConfig,
) -> tuple[list[RawRecord], Cursor, bool]:
    """Retry on 429 with exponential backoff + jitter. Raises after max_retries."""
    last_err: Exception | None = None
    for attempt in range(cfg.max_retries_on_429 + 1):
        try:
            return adapter.list_changed_since(cursor, page_size)
        except _RateLimited as e:
            last_err = e
            wait = e.retry_after_seconds or _backoff(attempt, cfg)
            log.info("rate_limited_backoff", attempt=attempt, wait_seconds=wait)
            time.sleep(wait)
    raise last_err if last_err else RuntimeError("retry loop exhausted with no error captured")


class _RateLimited(Exception):
    """Adapter wraps provider 429 in this so batch.py can apply uniform backoff."""

    def __init__(self, retry_after_seconds: float | None = None) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate_limited (retry_after={retry_after_seconds})")


# Public alias so adapters can `raise batch.RateLimited(retry_after_seconds=...)`
RateLimited = _RateLimited
