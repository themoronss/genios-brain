from __future__ import annotations

import hashlib
import re
from pathlib import Path

from sqlalchemy import text

from genios_engine.platform.config import get_settings
from genios_engine.platform.db import get_engine

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"

# Applied-migrations ledger. Before this existed, every *.sql re-ran on every invocation,
# so correctness silently depended on every statement being idempotent forever — and one
# non-idempotent statement aborted every later statement in its file (one tx per file).
_LEDGER_DDL = """
create table if not exists schema_migrations (
    filename    text primary key,
    checksum    text not null,
    applied_at  timestamptz not null default current_timestamp
)
"""


def _checksum(sql_file: Path) -> str:
    return hashlib.sha256(sql_file.read_bytes()).hexdigest()


def apply_migrations(database_url: str | None = None,
                     migrations_dir: Path | None = None) -> list[str]:
    """Apply each migrations/*.sql exactly once, in filename order, recording it in
    schema_migrations. A previously applied file whose content has CHANGED fails loudly
    (edit-in-place is forbidden — ship a new numbered file instead). Run:
        .venv/bin/python -m genios_engine.platform.migrate
    """
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("Set GENIOS_DATABASE_URL (in .env) before applying migrations.")
    engine = get_engine(url)
    mdir = migrations_dir or _MIGRATIONS
    with engine.begin() as conn:
        conn.execute(text(_LEDGER_DDL))
        applied_rows = conn.execute(
            text("select filename, checksum from schema_migrations")).all()
    ledger = {r.filename: r.checksum for r in applied_rows}

    applied: list[str] = []
    for sql_file in sorted(mdir.glob("*.sql")):
        cs = _checksum(sql_file)
        if sql_file.name in ledger:
            if ledger[sql_file.name] != cs:
                raise RuntimeError(
                    f"{sql_file.name} was edited after being applied "
                    f"(checksum drift). Migrations are immutable — add a new file.")
            continue                                   # already applied → skip
        # strip `-- ...` line comments (which may contain ';') before splitting
        sql = re.sub(r"--[^\n]*", "", sql_file.read_text())
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        with engine.begin() as conn:                   # file + its ledger row: one tx
            for stmt in statements:
                conn.execute(text(stmt))
            conn.execute(text(
                "insert into schema_migrations (filename, checksum) values (:f, :c)"),
                {"f": sql_file.name, "c": cs})
        applied.append(sql_file.name)
    return applied


if __name__ == "__main__":
    print("Applied migrations:", apply_migrations())
