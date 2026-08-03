"""Roll forward audit_log monthly partitions on Postgres.

Migration 0010 pre-creates 12 months ahead. Run this script monthly (cron) to
top up the lookahead — it creates partitions for any month within the next 12
that doesn't yet exist. Idempotent.

Usage:
    python -m scripts.audit_partitions [--months N] [--dry-run]

Cron (12:05 first of each month):
    5 0 1 * * cd /opt/genios && venv/bin/python -m scripts.audit_partitions
"""

from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import text

from core.foundations.db import get_engine
from core.foundations.telemetry import get_logger

log = get_logger(__name__)

DEFAULT_LOOKAHEAD_MONTHS = 12


def planned_partitions(start: datetime, n: int) -> list[tuple[str, str, str]]:
    """Return (partition_name, range_start, range_end) for next n months from `start`."""
    out: list[tuple[str, str, str]] = []
    year, month = start.year, start.month
    for _ in range(n):
        if month == 12:
            n_year, n_month = year + 1, 1
        else:
            n_year, n_month = year, month + 1
        rng_start = f"{year:04d}-{month:02d}-01"
        rng_end = f"{n_year:04d}-{n_month:02d}-01"
        name = f"audit_log_{year:04d}{month:02d}"
        out.append((name, rng_start, rng_end))
        year, month = n_year, n_month
    return out


def ensure_partitions(*, months: int = DEFAULT_LOOKAHEAD_MONTHS, dry_run: bool = False) -> int:
    """Create any missing partitions in [now, now+months). Returns # created.

    Skipped on non-Postgres dialects (SQLite tests, etc.).
    """
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        log.warning(
            "audit_partitions_skipped_non_postgres", dialect=engine.dialect.name
        )
        return 0

    plans = planned_partitions(datetime.utcnow(), months)
    created = 0
    with engine.begin() as conn:
        existing = {
            r[0]
            for r in conn.execute(
                text(
                    "SELECT inhrelid::regclass::text "
                    "FROM pg_inherits "
                    "WHERE inhparent = 'audit_log'::regclass"
                )
            ).fetchall()
        }
        for name, rng_start, rng_end in plans:
            if name in existing:
                continue
            sql = (
                f"CREATE TABLE {name} PARTITION OF audit_log "
                f"FOR VALUES FROM ('{rng_start}') TO ('{rng_end}')"
            )
            if dry_run:
                log.info("audit_partition_plan", name=name, sql=sql)
                continue
            conn.execute(text(sql))
            created += 1
            log.info("audit_partition_created", name=name, range_start=rng_start, range_end=rng_end)
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Roll forward audit_log partitions")
    parser.add_argument(
        "--months",
        type=int,
        default=DEFAULT_LOOKAHEAD_MONTHS,
        help="How many months ahead to maintain (default: 12)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print SQL without executing",
    )
    args = parser.parse_args()
    n = ensure_partitions(months=args.months, dry_run=args.dry_run)
    print(f"created {n} partition(s) (dry_run={args.dry_run})")


if __name__ == "__main__":
    main()
