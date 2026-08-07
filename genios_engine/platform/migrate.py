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


def _split_sql(script: str) -> list[str]:
    """Split PostgreSQL migration text without cutting quoted/commented semicolons.

    SQLAlchemy's ``text`` executes one statement at a time for our drivers, but ``str.split``
    cannot distinguish a statement terminator from punctuation in COMMENT text or a function
    body. This small lexer handles PostgreSQL single/double quotes, line/block comments and
    dollar-quoted bodies while deliberately leaving SQL interpretation to PostgreSQL.
    """
    statements: list[str] = []
    buf: list[str] = []
    state = "normal"
    dollar_tag = ""
    i = 0
    while i < len(script):
        pair = script[i:i + 2]
        char = script[i]
        if state == "line_comment":
            if char == "\n":
                buf.append(char)
                state = "normal"
            i += 1
            continue
        if state == "block_comment":
            if pair == "*/":
                state = "normal"
                i += 2
            else:
                i += 1
            continue
        if state == "single":
            buf.append(char)
            if char == "'":
                if i + 1 < len(script) and script[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                state = "normal"
            i += 1
            continue
        if state == "double":
            buf.append(char)
            if char == '"':
                if i + 1 < len(script) and script[i + 1] == '"':
                    buf.append('"')
                    i += 2
                    continue
                state = "normal"
            i += 1
            continue
        if state == "dollar":
            if script.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                state = "normal"
            else:
                buf.append(char)
                i += 1
            continue

        if pair == "--":
            state = "line_comment"
            i += 2
        elif pair == "/*":
            state = "block_comment"
            i += 2
        elif char == "'":
            buf.append(char)
            state = "single"
            i += 1
        elif char == '"':
            buf.append(char)
            state = "double"
            i += 1
        elif char == "$":
            match = re.match(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$", script[i:])
            if match:
                dollar_tag = match.group(0)
                buf.append(dollar_tag)
                i += len(dollar_tag)
                state = "dollar"
            else:
                buf.append(char)
                i += 1
        elif char == ";":
            statement = "".join(buf).strip()
            if statement:
                statements.append(statement)
            buf.clear()
            i += 1
        else:
            buf.append(char)
            i += 1
    if state in {"single", "double", "block_comment", "dollar"}:
        raise ValueError(f"unterminated SQL {state.replace('_', ' ')}")
    statement = "".join(buf).strip()
    if statement:
        statements.append(statement)
    return statements


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
    applied: list[str] = []
    with engine.connect() as conn:
        postgres = conn.dialect.name == "postgresql"
        if postgres:
            # Session-scoped because every file keeps its own transaction. This serializes the
            # ledger read and all subsequent DDL across replicas; transaction-scoped locking
            # would be released before the first file and recreate the startup race.
            conn.execute(text(
                "select pg_advisory_lock(hashtextextended('genios-schema-migrations',0))"))
            conn.commit()
        try:
            with conn.begin():
                conn.execute(text(_LEDGER_DDL))
                applied_rows = conn.execute(
                    text("select filename, checksum from schema_migrations")).all()
            ledger = {r.filename: r.checksum for r in applied_rows}

            for sql_file in sorted(mdir.glob("*.sql")):
                cs = _checksum(sql_file)
                if sql_file.name in ledger:
                    if ledger[sql_file.name] != cs:
                        raise RuntimeError(
                            f"{sql_file.name} was edited after being applied "
                            f"(checksum drift). Migrations are immutable — add a new file.")
                    continue                           # already applied → skip
                statements = _split_sql(sql_file.read_text())
                with conn.begin():                    # file + its ledger row: one tx
                    for stmt in statements:
                        conn.execute(text(stmt))
                    conn.execute(text(
                        "insert into schema_migrations (filename, checksum) values (:f, :c)"),
                        {"f": sql_file.name, "c": cs})
                ledger[sql_file.name] = cs
                applied.append(sql_file.name)
        finally:
            if postgres:
                if conn.in_transaction():
                    conn.rollback()
                conn.execute(text(
                    "select pg_advisory_unlock(hashtextextended('genios-schema-migrations',0))"))
                conn.commit()
    return applied


if __name__ == "__main__":
    print("Applied migrations:", apply_migrations())
