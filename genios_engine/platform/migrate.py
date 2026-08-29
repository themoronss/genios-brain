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


class ReadOnlyDatabaseError(RuntimeError):
    """Migrations are pending and the server will not accept writes.

    Raised INSTEAD of the driver's `ReadOnlySqlTransaction`, because the two need opposite
    handling at boot and the driver error cannot be told apart from a genuine migration failure
    without inspecting its message. See `apply_migrations` for why this one is survivable.
    """


def _pending(mdir: Path, ledger: dict[str, str]) -> list[Path]:
    """Migration files not yet in the ledger, in filename order. Checksum drift still raises."""
    out: list[Path] = []
    for sql_file in sorted(mdir.glob("*.sql")):
        cs = _checksum(sql_file)
        if sql_file.name in ledger:
            if ledger[sql_file.name] != cs:
                raise RuntimeError(
                    f"{sql_file.name} was edited after being applied "
                    f"(checksum drift). Migrations are immutable — add a new file.")
            continue
        out.append(sql_file)
    return out


def _read_ledger(engine) -> dict[str, str] | None:
    """The ledger as {filename: checksum}, or None if the table does not exist yet.

    A SELECT, deliberately — it is the one way to learn whether there is anything to do that
    works on a read-only server. The CREATE TABLE is deferred to the point where we already know
    a migration has to be written.
    """
    from sqlalchemy.exc import SQLAlchemyError
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("select filename, checksum from schema_migrations")).all()
        return {r.filename: r.checksum for r in rows}
    except SQLAlchemyError:
        return None


def _is_read_only(engine) -> bool:
    """Whether the server will refuse writes. False for anything that cannot answer the question.

    Asked of the SERVER (`show default_transaction_read_only`) rather than inferred from a failed
    write, so the answer is available before anything has been attempted. A hot standby reports
    the same way via `pg_is_in_recovery`, and both mean the same thing to a migration.
    """
    from sqlalchemy.exc import SQLAlchemyError
    try:
        with engine.connect() as conn:
            if str(conn.execute(text("show default_transaction_read_only")).scalar()).lower() == "on":
                return True
            return bool(conn.execute(text("select pg_is_in_recovery()")).scalar())
    except SQLAlchemyError:
        return False        # sqlite and friends: no such setting, and no read-only mode to hit


def _checksum(sql_file: Path) -> str:
    return hashlib.sha256(sql_file.read_bytes()).hexdigest()


def _split_statements(sql: str) -> list[str]:
    """Split a migration into statements on TOP-LEVEL ';' only — never a ';' inside a single-quoted
    string ('' escapes), a dollar-quoted body ($$...$$ / $tag$...$tag$ used by functions / DO blocks),
    or a '--' line comment. A naive sql.split(';') broke on the ';' inside a `COMMENT ON ... IS '...'`
    string — exactly the class of bug that only surfaces on a real Postgres run."""
    statements: list[str] = []
    buf: list[str] = []
    i, n = 0, len(sql)
    in_squote = False
    dollar_tag: str | None = None
    while i < n:
        ch = sql[i]
        if dollar_tag is not None:                       # inside a $tag$ ... $tag$ body
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag); i += len(dollar_tag); dollar_tag = None
            else:
                buf.append(ch); i += 1
            continue
        if in_squote:                                    # inside a '...' string literal
            buf.append(ch)
            if ch == "'":
                if i + 1 < n and sql[i + 1] == "'":      # '' → an escaped quote; stay inside
                    buf.append("'"); i += 2; continue
                in_squote = False
            i += 1
            continue
        if ch == "'":
            in_squote = True; buf.append(ch); i += 1; continue
        if ch == "-" and sql.startswith("--", i):        # line comment → skip to end of line
            j = sql.find("\n", i)
            i = n if j == -1 else j
            continue
        if ch == "$":                                    # possible $tag$ opener
            m = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
            if m:
                dollar_tag = m.group(0); buf.append(dollar_tag); i += len(dollar_tag); continue
        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []; i += 1; continue
        buf.append(ch); i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
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

    # READ before WRITE. This used to open with the ledger's CREATE TABLE IF NOT EXISTS, which
    # Postgres rejects on a read-only server EVEN WHEN THE TABLE ALREADY EXISTS — the read-only
    # check runs before the IF NOT EXISTS check. Since `apply_migrations` is the first thing
    # `main.lifespan` does, a read-only database (Supabase enforces one on disk quota) turned
    # every boot into a crash, every deploy into a crash-loop, and took the API's still-working
    # READS down with it. Asking the ledger a question first makes the fully-migrated case — the
    # normal one — issue no DDL at all, so it boots fine whatever the server's write state.
    ledger = _read_ledger(engine)
    pending = _pending(mdir, ledger or {})
    if ledger is not None and not pending:
        return []

    if _is_read_only(engine):
        raise ReadOnlyDatabaseError(
            f"{len(pending)} migration(s) pending and the database is in read-only mode: "
            f"{', '.join(p.name for p in pending[:5])}"
            f"{'...' if len(pending) > 5 else ''}. "
            "Lift read-only on the database before deploying code that needs these.")

    applied: list[str] = []
    with engine.begin() as conn:
        conn.execute(text(_LEDGER_DDL))
    for sql_file in pending:
        # split on top-level ';' only — respects '...' strings, $$ bodies and -- line comments
        statements = _split_statements(sql_file.read_text())
        with engine.begin() as conn:                   # file + its ledger row: one tx
            for stmt in statements:
                conn.execute(text(stmt))
            conn.execute(text(
                "insert into schema_migrations (filename, checksum) values (:f, :c)"),
                {"f": sql_file.name, "c": _checksum(sql_file)})
        applied.append(sql_file.name)
    return applied


if __name__ == "__main__":
    print("Applied migrations:", apply_migrations())
