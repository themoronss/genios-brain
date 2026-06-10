"""Drop every v1 table and run v2 alembic upgrade head, in one step.

Safety:
- Prints v1 row counts BEFORE dropping (so operator sees what's lost)
- Requires explicit --confirm flag
- Refuses to run if GENIOS_ENV is 'production' AND --force-prod is not passed
- Wraps everything in a transaction-per-statement (DROP TABLE doesn't transact
  fully on Postgres, but the SQL file uses one BEGIN..COMMIT block)

Usage:
    venv/bin/python -m scripts.wipe_v1_and_migrate --confirm

To preview (no writes):
    venv/bin/python -m scripts.wipe_v1_and_migrate --dry-run
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from core.foundations.config import settings
from core.foundations.db import get_engine
from core.foundations.telemetry import get_logger

log = get_logger(__name__)

SQL_PATH = Path(__file__).parent / "drop_v1_tables.sql"
ALEMBIC_INI = Path(__file__).parent.parent / "migrations_v2" / "alembic.ini"


def _v1_table_names() -> list[str]:
    """Parse the DROP statements out of the SQL file to know which tables we care about."""
    sql = SQL_PATH.read_text()
    out: list[str] = []
    for line in sql.splitlines():
        line = line.strip()
        if line.startswith("DROP TABLE IF EXISTS "):
            name = line.removeprefix("DROP TABLE IF EXISTS ").split()[0].rstrip(";")
            if name != "alembic_version":
                out.append(name)
    return out


def _row_counts(table_names: list[str]) -> dict[str, int | str]:
    """Best-effort row count per table. Returns {name: count or error-msg}."""
    engine = get_engine()
    out: dict[str, int | str] = {}
    with engine.connect() as conn:
        for name in table_names:
            # Names come from the hard-coded SQL file; not user input. Identifiers
            # can't be parameterized in Postgres so inlining is necessary here.
            try:
                n = conn.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar_one()  # noqa: S608
                out[name] = int(n)
            except Exception as e:
                out[name] = f"<not present: {type(e).__name__}>"
    return out


def _execute_drop_sql(*, lock_timeout_ms: int = 5000, max_retries: int = 5) -> None:
    """Drop each table in its own short transaction so production writes can't
    deadlock the whole wipe. On deadlock/lock-timeout we re-queue the table and
    try again after a short backoff. Each table gets up to `max_retries`.
    """
    import time

    sql = SQL_PATH.read_text()
    stmts: list[str] = []
    for raw in sql.split(";"):
        s = raw.strip()
        if not s or s.startswith("--") or s in ("BEGIN", "COMMIT"):
            continue
        stmts.append(s)

    engine = get_engine()
    failed: list[tuple[str, str]] = []  # (statement, last error)

    for stmt in stmts:
        for attempt in range(1, max_retries + 1):
            try:
                with engine.begin() as conn:
                    # Per-tx lock timeout — DROP either grabs the lock fast or
                    # bails (no indefinite wait for the prod app's writes).
                    conn.execute(text(f"SET LOCAL lock_timeout = {lock_timeout_ms}"))
                    conn.execute(text(stmt))
                break
            except Exception as e:
                msg = str(e).lower()
                retryable = "deadlock" in msg or "lock timeout" in msg or "lock_timeout" in msg
                if attempt >= max_retries or not retryable:
                    failed.append((stmt, str(e).splitlines()[0]))
                    print(
                        f"  FAILED ({attempt}x): {stmt[:60]}…  -> {str(e).splitlines()[0]}",
                        file=sys.stderr,
                    )
                    break
                wait = 1.5 * attempt
                print(
                    f"  retry {attempt}/{max_retries} after {wait:.1f}s: {stmt[:60]}…",
                    file=sys.stderr,
                )
                time.sleep(wait)

    if failed:
        print(f"\n{len(failed)} drop statement(s) could not complete:", file=sys.stderr)
        for stmt, err in failed:
            print(f"  - {stmt}", file=sys.stderr)
            print(f"    reason: {err}", file=sys.stderr)
        raise SystemExit(
            "Some tables remain — pause the production app (Celery + FastAPI) "
            "and re-run, or DROP them by hand."
        )


def _run_alembic_upgrade() -> int:
    cmd = [
        sys.executable,
        "-m",
        "alembic",
        "-c",
        str(ALEMBIC_INI),
        "upgrade",
        "head",
    ]
    # cmd is fully hard-coded — no untrusted input.
    proc = subprocess.run(cmd, cwd=ALEMBIC_INI.parent.parent, check=False)  # noqa: S603
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe v1 + run v2 migrations")
    parser.add_argument("--confirm", action="store_true", help="Actually run the drop")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would happen; no writes",
    )
    parser.add_argument(
        "--force-prod",
        action="store_true",
        help="Allow running when GENIOS_ENV is production (refused by default)",
    )
    parser.add_argument(
        "--skip-alembic",
        action="store_true",
        help="Drop tables but don't run alembic upgrade afterwards",
    )
    args = parser.parse_args()

    env = settings.GENIOS_ENV.lower()
    if env == "production" and not args.force_prod:
        print(
            "REFUSED: GENIOS_ENV=production. Pass --force-prod if you really mean it.",
            file=sys.stderr,
        )
        return 2

    tables = _v1_table_names()
    print(f"v1 tables targeted for DROP: {len(tables)}")
    counts = _row_counts(tables)
    nonempty = {k: v for k, v in counts.items() if isinstance(v, int) and v > 0}
    if nonempty:
        print("\nNON-EMPTY tables (these rows will be lost):")
        for name, n in sorted(nonempty.items(), key=lambda kv: -kv[1]):  # type: ignore[arg-type]
            print(f"  {name:40s}  {n:>10d} rows")
    else:
        print("(all v1 tables are empty or missing — clean wipe)")

    if args.dry_run:
        print("\n--dry-run: no changes applied.")
        return 0

    if not args.confirm:
        print(
            "\nRefusing without --confirm. Re-run with --confirm to apply.",
            file=sys.stderr,
        )
        return 1

    print("\nDropping v1 tables...")
    _execute_drop_sql()
    print("v1 drop complete.")

    if args.skip_alembic:
        print("--skip-alembic: not running migrations.")
        return 0

    print("\nRunning alembic upgrade head...")
    rc = _run_alembic_upgrade()
    if rc != 0:
        print(f"alembic exited {rc}", file=sys.stderr)
        return rc
    print("v2 migrations applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
