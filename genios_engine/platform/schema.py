"""The schema, as data — parsed from `migrations/*.sql` without a database.

WHY THIS EXISTS
Every table this codebase queries was verified to exist. **Column names were not.** The
whole test suite runs against in-memory repos, so a query naming a column that no
migration ever created is green in CI and raises `UndefinedColumn` the first time a real
tenant drains. Layer 2's own overview names that failure shape as the one it is most
exposed to: *"code that is written, tested, green — and does nothing."*

A database would catch it. There isn't one in CI, and waiting for one meant the gap stayed
open indefinitely. So this reads the migrations as the source of truth and answers two
questions with no connection at all:

    tables()             what tables will exist after every migration has run
    columns(table)       what columns that table will have

`tests/test_schema_conformance.py` uses it to check every SQL string in the package
against it, which turns "the SQL is probably right" into a build failure when it is not.

WHAT IT DELIBERATELY DOES NOT DO
No types, no constraints, no defaults. A column's *existence* is what a query can get
wrong silently; its type surfaces immediately and loudly. Parsing types would mean
implementing a fraction of a Postgres grammar and being subtly wrong about the rest.
`verify_live_schema` closes the remaining distance for anyone who does have a database.
"""
from __future__ import annotations

import re
from pathlib import Path

_MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"

# Words that open a table-level constraint rather than a column definition.
_CONSTRAINT_STARTERS = frozenset({
    "primary", "foreign", "unique", "check", "constraint", "exclude", "like",
})


def _strip_comments(sql: str) -> str:
    """Drop `-- …` line comments. They routinely contain commas, parens and the word
    'table', so every regex below would misfire without this."""
    return re.sub(r"--[^\n]*", "", sql)


def _split_top_level(body: str) -> list[str]:
    """Split a create-table body on commas that are not inside parentheses.

    `numeric(10, 2)` and `primary key (org_id, node_id)` both contain commas that do not
    separate definitions, so a plain `body.split(',')` mangles the column after each one.
    """
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _balanced_body(sql: str, open_paren: int) -> str:
    """The text between `sql[open_paren]` and its matching close paren."""
    depth = 0
    for i in range(open_paren, len(sql)):
        if sql[i] == "(":
            depth += 1
        elif sql[i] == ")":
            depth -= 1
            if depth == 0:
                return sql[open_paren + 1:i]
    return sql[open_paren + 1:]


_CREATE_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?([a-z_][a-z0-9_]*)\s*\(", re.I)
# One ALTER may carry many clauses:
#     alter table source_events
#       add column if not exists visibility   jsonb,
#       add column if not exists expires_at   timestamptz,
#       add column if not exists signal_state text not null default 'new';
# Matching `alter table X add column Y` only ever sees the FIRST clause, so migration
# 0043's `expires_at` and `signal_state` read as phantom columns. The statement is
# located first, then every add/drop inside it — which is how Postgres reads it too.
_ALTER_RE = re.compile(r"alter\s+table\s+(?:only\s+)?([a-z_][a-z0-9_]*)\b", re.I)
_ADD_COL_RE = re.compile(
    r"add\s+column\s+(?:if\s+not\s+exists\s+)?([a-z_][a-z0-9_]*)", re.I)
_DROP_COL_RE = re.compile(
    r"drop\s+column\s+(?:if\s+exists\s+)?([a-z_][a-z0-9_]*)", re.I)
_RENAME_COL_RE = re.compile(
    r"alter\s+table\s+(?:only\s+)?([a-z_][a-z0-9_]*)\s+rename\s+column\s+"
    r"([a-z_][a-z0-9_]*)\s+to\s+([a-z_][a-z0-9_]*)", re.I)
_DROP_TABLE_RE = re.compile(
    r"drop\s+table\s+(?:if\s+exists\s+)?([a-z_][a-z0-9_]*)", re.I)
_VIEW_RE = re.compile(
    r"create\s+(?:or\s+replace\s+)?view\s+([a-z_][a-z0-9_]*)", re.I)


def parse_schema(migrations_dir: Path | None = None) -> dict[str, set[str]]:
    """Replay every migration in filename order and return `{table: {columns}}`.

    Filename order is the order `platform.migrate.apply_migrations` uses, so a column
    added in 0028 and dropped in 0033 correctly ends up absent.
    """
    from genios_engine.platform.migrate import _LEDGER_DDL

    mdir = migrations_dir or _MIGRATIONS
    schema: dict[str, set[str]] = {}
    # The ledger is real schema that no migration creates — `apply_migrations` issues it
    # before it can consult itself. Leaving it out makes `schema_migrations` look like a
    # phantom table to every caller.
    for sql in [_strip_comments(_LEDGER_DDL)] + [
            _strip_comments(f.read_text()) for f in sorted(mdir.glob("*.sql"))]:

        for match in _CREATE_RE.finditer(sql):
            table = match.group(1).lower()
            body = _balanced_body(sql, match.end() - 1)
            cols = schema.setdefault(table, set())
            for part in _split_top_level(body):
                tokens = part.strip().split()
                if not tokens or tokens[0].lower() in _CONSTRAINT_STARTERS:
                    continue
                cols.add(tokens[0].strip('"').lower())

        for match in _ALTER_RE.finditer(sql):
            table = match.group(1).lower()
            end = sql.find(";", match.end())
            statement = sql[match.end():end if end != -1 else len(sql)]
            for col in _ADD_COL_RE.findall(statement):
                schema.setdefault(table, set()).add(col.lower())
            for col in _DROP_COL_RE.findall(statement):
                schema.get(table, set()).discard(col.lower())

        for table, old, new in _RENAME_COL_RE.findall(sql):
            cols = schema.get(table.lower(), set())
            cols.discard(old.lower())
            cols.add(new.lower())
        for table in _DROP_TABLE_RE.findall(sql):
            schema.pop(table.lower(), None)
        # A view is queryable like a table; its columns come from a select we do not
        # parse, so it is registered as "exists, columns unknown" (see UNKNOWN_COLUMNS).
        for view in _VIEW_RE.findall(sql):
            schema.setdefault(view.lower(), UNKNOWN_COLUMNS)
    return schema


# Sentinel for a relation whose columns cannot be derived from DDL (views). Membership
# tests against it always succeed, so a view never produces a false column failure.
class _AnyColumns(frozenset):
    def __contains__(self, item) -> bool:  # noqa: D105
        return True


UNKNOWN_COLUMNS = _AnyColumns()


def verify_live_schema(database_url: str | None = None) -> dict[str, list[str]]:
    """Compare a real database against the parsed migrations. Requires a connection.

    Returns `{"missing_tables": [...], "missing_columns": ["table.column", ...]}` — empty
    lists mean the live schema is at least as complete as the migrations describe. Extra
    tables and columns in the database are not reported: a hand-added index column is not
    a defect, and a migration that has not run yet is.
    """
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    expected = parse_schema()
    engine = get_engine(database_url) if database_url else get_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "select table_name, column_name from information_schema.columns "
            "where table_schema = 'public'")).all()
    live: dict[str, set[str]] = {}
    for table, column in rows:
        live.setdefault(table.lower(), set()).add(column.lower())

    missing_tables = sorted(t for t in expected if t not in live)
    missing_columns = sorted(
        f"{t}.{c}"
        for t, cols in expected.items()
        if t in live and cols is not UNKNOWN_COLUMNS
        for c in cols if c not in live[t])
    return {"missing_tables": missing_tables, "missing_columns": missing_columns}
