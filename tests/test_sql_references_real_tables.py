"""Every table the code queries must exist in a migration.

There is no database in this suite — 579 tests run in two seconds because nothing
connects. That is worth keeping, but it means a whole class of bug is invisible: SQL
naming a table that no migration creates passes every test and fails on the first real
request.

This closes the cheapest and most common part of that gap. It cannot check column names
or semantics without a real parser and a real database, and it does not pretend to. What
it does catch is the failure that actually happens: a typo, or code shipped ahead of the
migration that was supposed to create its table.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "genios_engine"
MIGRATIONS = ROOT / "migrations"

# Table names appear after these keywords. `into` also covers `insert into`.
#
# The negative lookahead rejects `trim(both '"' from value::text)` — SQL's `trim` uses
# `from` inside a function call, and a real table is never immediately cast.
_TABLE_REF = re.compile(
    r"\b(?:from|join|into|update)\s+([a-z_][a-z0-9_]{2,})\b(?!\s*::)", re.I)
_SQL_MARKERS = ("select ", "insert into ", "update ", "delete from ")

# Words that follow a table keyword without being a table. `set` comes from
# `on conflict do update set`; the rest are Postgres set-returning functions used in a
# FROM clause. Each is here because it appears in real SQL in this repo.
_NOT_TABLES = frozenset({
    # `on conflict do update set …` and `… for update skip locked` — both put a keyword
    # where a table name would otherwise sit.
    "set", "skip",
    "excluded", "lateral", "only", "select", "values",
    "unnest", "generate_series", "jsonb_array_elements", "jsonb_array_elements_text",
    "jsonb_each", "jsonb_to_recordset", "json_array_elements", "regexp_split_to_table",
})

# CTE names are declared inside the query itself, so they are resolved per-statement
# rather than allowlisted — an allowlist would go stale and start hiding real typos.
_CTE = re.compile(r"(?:\bwith\b|,)\s+([a-z_][a-z0-9_]*)\s+as\s*\(", re.I)


def _declared_tables() -> set[str]:
    """Tables any migration creates — plus the bootstrap ledger, which migrate.py has to
    create in Python before any migration can run."""
    created = {"schema_migrations"}
    for sql_file in MIGRATIONS.glob("*.sql"):
        sql = sql_file.read_text().lower()
        created |= set(re.findall(r"create table(?:\s+if not exists)?\s+([a-z_][a-z0-9_]*)", sql))
        created |= set(re.findall(r"create (?:or replace )?view\s+([a-z_][a-z0-9_]*)", sql))
        created |= set(re.findall(
            r"create materialized view(?:\s+if not exists)?\s+([a-z_][a-z0-9_]*)", sql))
    return created


def _sql_strings(path: Path) -> list[str]:
    """SQL passed to `text(...)`, and nothing else.

    Scanning every string literal drags in docstrings and comments that merely mention
    "select" or "from the", which produced enough false positives to make the check
    useless. Only a string handed to SQLAlchemy's `text()` is definitely SQL. Adjacent
    literals are already merged by the parser, so multi-line statements arrive whole.
    """
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:                                   # pragma: no cover
        return []
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "text" and node.args):
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            lowered = arg.value.lower()
            if any(marker in lowered for marker in _SQL_MARKERS):
                found.append(lowered)
    return found


def _referenced_tables() -> dict[str, set[str]]:
    """table name → the files that query it. CTE names defined in the same statement are
    resolved away, since they are real names that are simply not tables."""
    references: dict[str, set[str]] = {}
    for path in ENGINE.rglob("*.py"):
        for sql in _sql_strings(path):
            local = set(_CTE.findall(sql))
            for name in _TABLE_REF.findall(sql):
                if name in _NOT_TABLES or name in local:
                    continue
                references.setdefault(name, set()).add(str(path.relative_to(ROOT)))
    return references


def test_migrations_declare_some_tables() -> None:
    """Guard the guard: a broken parser here would silently pass everything below."""
    declared = _declared_tables()
    assert len(declared) > 20
    assert {"graph_nodes", "graph_facts", "source_events"} <= declared


def test_the_scanner_finds_sql_to_check() -> None:
    references = _referenced_tables()
    assert len(references) > 20
    assert "graph_facts" in references


def test_every_queried_table_exists_in_a_migration() -> None:
    """The bug this catches: code shipped ahead of the migration that creates its table.
    Green tests, then a 500 on the first real request."""
    declared = _declared_tables()
    missing = {name: sorted(files) for name, files in _referenced_tables().items()
               if name not in declared}
    assert missing == {}, (
        "SQL references tables no migration creates — add the migration, or fix the "
        f"name: {missing}")


def test_the_layer2_tables_are_declared_and_used() -> None:
    """Steps 1–3 shipped four migrations that have never been executed. This at least
    proves the code and the schema agree on what exists."""
    declared = _declared_tables()
    referenced = _referenced_tables()
    for table in ("graph_aliases", "context_correlations", "context_correlation_members",
                  "context_situations"):
        assert table in declared, f"{table} has no migration"
        assert table in referenced, f"{table} is created but nothing reads it"
