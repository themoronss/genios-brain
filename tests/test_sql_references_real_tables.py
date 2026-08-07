"""The SQL ratchet — every table AND column this code names must exist in a migration.

THE GAP THIS CLOSES
The whole suite runs against in-memory repos, so no test has ever executed a line of the
SQL embedded in this package. SQL naming something no migration creates is green in CI and
raises `UndefinedTable`/`UndefinedColumn` the first time a real tenant drains. Layer 2's
own overview calls that the failure it is most exposed to: code that is *written, tested,
green — and does nothing.*

This reads `migrations/*.sql` as the schema (see `platform/schema.py`), extracts every SQL
string handed to `text()` in `genios_engine/`, and fails the build when the two disagree.
It is not a substitute for a database — it says nothing about types, constraints or
semantics — but it catches the class of error a DB-free suite otherwise cannot see at all.

WHAT CHANGED, AND WHY THE FILE KEPT ITS NAME
The original version checked table names only, with a regex over single string literals.
It could not see a query assembled with `+` (the authority CTE preludes), could not see an
f-string, and read only the first clause of a multi-clause `ALTER TABLE` — which is how
migration 0043's `expires_at` and `signal_state` looked like phantom columns. Column
checking is the part that matters most: a select against a missing column fails on the
first read, but a wrong *insert* column list drifts silently until a tenant writes.

READ THIS BEFORE ADDING AN IGNORE
A failure here is a real defect until proven otherwise. The escape hatches below are for
identifiers that are not tables (CTEs, subquery aliases, Postgres catalogs, set-returning
functions), never for "this table will exist later". A table that does not exist yet needs
a migration, not an entry in `_NOT_TABLES`.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from genios_engine.platform.schema import UNKNOWN_COLUMNS, parse_schema

_ROOT = Path(__file__).resolve().parents[1] / "genios_engine"

# What an f-string interpolation leaves behind, so a computed table name reads as a hole
# rather than as whatever word happened to follow it. See `_flatten`.
_HOLE = "__hole__"

# Words a table-position regex can capture that are SQL syntax, not relations.
#   of / skip / share — row-locking tails: `for update of k`, `for update skip locked`
_NOT_TABLES = frozenset({
    "set", "select", "values", "only", "lateral", "unnest", "generate_series",
    "dual", "from", "where", "table", "of", "skip", "share", _HOLE,
})

# `trim(both '"' from value::text)` puts a non-table in a from-position. Removing the
# trim-specific prefix before scanning is safer than teaching the table regex about it.
_TRIM_FROM = re.compile(r"\b(?:both|leading|trailing)\b[^)]*?\bfrom\b", re.I)

_SQL_VERB = re.compile(
    r"\b(select|insert\s+into|update|delete\s+from|with)\b", re.I)

_CTE = re.compile(r"(?:with|,)\s+([a-z_][a-z0-9_]*)\s+as\s*\(", re.I)
# A prelude constant opens with the CTE name itself; the caller supplies the `WITH`.
_CTE_HEAD = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s+as\s*\(", re.I)
_FROM = re.compile(r"\bfrom\s+([a-z_][a-z0-9_]*)\b", re.I)
_JOIN = re.compile(r"\bjoin\s+([a-z_][a-z0-9_]*)\b", re.I)
_INSERT = re.compile(r"\binsert\s+into\s+([a-z_][a-z0-9_]*)\b", re.I)
_UPDATE = re.compile(r"\bupdate\s+([a-z_][a-z0-9_]*)\b", re.I)
_DELETE = re.compile(r"\bdelete\s+from\s+([a-z_][a-z0-9_]*)\b", re.I)
_INSERT_COLS = re.compile(
    r"\binsert\s+into\s+([a-z_][a-z0-9_]*)\s*\(([^)]*)\)", re.I)
_CONFLICT_COLS = re.compile(r"\bon\s+conflict\s*\(([^)]*)\)", re.I)
_DOTTED = re.compile(r"\.\s*$")


def _flatten(node: ast.AST, consts: dict[str, str]) -> str:
    """The constant text of an expression built from literals, `+` and module constants.

    `text("select … " + SCORE_SQL + " from cards")` and `text(_REACHED)` both reach the
    checker whole. An interpolated fragment we cannot resolve contributes nothing rather
    than breaking the parse — a missed query is a gap, an exception is a broken build.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id, "")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten(node.left, consts) + " " + _flatten(node.right, consts)
    if isinstance(node, ast.JoinedStr):                      # f-string
        return " ".join(_flatten(v, consts) for v in node.values)
    if isinstance(node, ast.FormattedValue):
        return f" {_HOLE} "                                  # the hole, not its contents
    if isinstance(node, ast.Call):                           # SQL.format(...) / .join(...)
        if isinstance(node.func, ast.Attribute):
            return _flatten(node.func.value, consts)
        return ""
    return ""


def _sql_literals(path: Path) -> list[str]:
    """Every string this file hands to SQLAlchemy's `text()`.

    Scoping to `text()` rather than to every string constant is what keeps prose out. A
    docstring explaining that a value is "selected from the graph" is not a query, and an
    earlier version of this test reported eighty of them.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    assigns = [(target.id, node.value)
               for node in ast.walk(tree) if isinstance(node, ast.Assign)
               for target in node.targets if isinstance(target, ast.Name)]

    # Two passes, because a SQL constant is routinely built from earlier ones —
    # `AUDITED_CARD_JUDGMENTS_CTES = ("audited_cards as (" … + AUTHORITATIVE_SIGNAL_JOINS …)`.
    # One pass would resolve that name to the empty string and lose the CTEs it declares.
    consts: dict[str, str] = {
        name: value.value for name, value in assigns
        if isinstance(value, ast.Constant) and isinstance(value.value, str)}
    for name, value in assigns:
        if name not in consts:
            resolved = _flatten(value, consts)
            if resolved.strip():
                consts[name] = resolved

    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = (node.func.id if isinstance(node.func, ast.Name)
                else node.func.attr if isinstance(node.func, ast.Attribute) else "")
        if name != "text":
            continue
        sql = _flatten(node.args[0], consts)
        if _SQL_VERB.search(sql):
            out.append(sql)

    return out


def _declared_ctes(path: Path) -> set[str]:
    """CTE names declared anywhere in a file, including in constants it never executes.

    The shared preludes in `reason/authority.py` are imported and concatenated by
    `feedback/calibrate.py` and `reason/foresight.py`, so the module that *declares*
    `audited_cards` never runs a query at all. Harvesting is kept separate from checking
    on purpose: a prelude may contribute names, but only a string actually handed to
    `text()` is held to the schema. Feeding preludes into the checker instead made a
    docstring in `extract/prompt.py` report a table called 'the'.
    """
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.update(m.lower() for m in _CTE.findall(node.value))
            head = _CTE_HEAD.match(node.value)
            if head:
                names.add(head.group(1).lower())
    return names


def _referenced_tables(sql: str, ctes: frozenset[str]) -> set[str]:
    """Tables named in a from/join/insert/update/delete position.

    `ctes` is collected across the whole PACKAGE, not per string or per file. The
    authority prelude in `reason/authority.py` defines `audited_cards`,
    `audited_impressions` and `canonical_judgments`, and `feedback/calibrate.py` and
    `reason/foresight.py` each concatenate that prelude in front of their own query — so
    the name that defines a CTE and the name that uses it are in different modules.
    """
    sql = _TRIM_FROM.sub(" ", sql)          # drop the clause, not just its keyword
    local_ctes = {m.lower() for m in _CTE.findall(sql)}
    found: set[str] = set()
    for pattern in (_FROM, _JOIN, _INSERT, _UPDATE, _DELETE):
        for match in pattern.finditer(sql):
            name = match.group(1).lower()
            tail = sql[match.end():match.end() + 1]
            # `information_schema.columns` captures its qualifier; `jsonb_each(x)` is a
            # function. Neither is a table, and both are followed by their own punctuation.
            if tail in (".", "("):
                continue
            if name in _NOT_TABLES or name in ctes or name in local_ctes:
                continue
            if name.startswith("pg_"):
                continue
            found.add(name)
    return found


def _all_ctes() -> frozenset[str]:
    """Every CTE name declared anywhere in the package."""
    names: set[str] = set()
    for py in sorted(_ROOT.rglob("*.py")):
        names |= _declared_ctes(py)
    return frozenset(names)


def _split_cols(clause: str) -> list[str]:
    """Column names from an insert list or conflict target.

    `_HOLE` marks a run-time interpolation: a column list built by `", ".join(fields)`
    cannot be checked statically, and reporting it as a missing column called
    `__hole__` would be noise that trains people to ignore this test.
    """
    return [c.strip().strip('"').lower() for c in clause.split(",")
            if c.strip() and _HOLE not in c]


def _sql_sources() -> list[tuple[Path, str]]:
    return [(py, sql) for py in sorted(_ROOT.rglob("*.py"))
            for sql in _sql_literals(py)]


def _sql_by_file() -> dict[Path, list[str]]:
    out: dict[Path, list[str]] = {}
    for py, sql in _sql_sources():
        out.setdefault(py, []).append(sql)
    return out


def test_every_queried_table_exists_in_a_migration() -> None:
    schema = parse_schema()
    ctes = _all_ctes()
    violations: list[str] = []
    for py, sql in _sql_sources():
        for table in _referenced_tables(sql, ctes):
            if table not in schema:
                violations.append(f"{py.relative_to(_ROOT.parent)}: table '{table}'")
    assert not violations, (
        "SQL names tables no migration creates:\n  " + "\n  ".join(sorted(set(violations))))


def test_every_inserted_column_exists_in_a_migration() -> None:
    """`insert into t (a, b, c)` — the column list is unambiguous, so it is checkable.

    This is where the damage lands: a select against a missing column fails on the first
    read, but an insert list drifts silently until a tenant writes.
    """
    schema = parse_schema()
    violations: list[str] = []
    for py, sql in _sql_sources():
        for table, cols in _INSERT_COLS.findall(sql):
            known = schema.get(table.lower())
            if known is None or known is UNKNOWN_COLUMNS:
                continue                        # table existence is the other test's job
            for col in _split_cols(cols):
                if col and col not in known:
                    violations.append(
                        f"{py.relative_to(_ROOT.parent)}: {table}.{col}")
    assert not violations, (
        "insert names columns no migration creates:\n  "
        + "\n  ".join(sorted(set(violations))))


def test_every_on_conflict_target_exists_in_a_migration() -> None:
    """An `on conflict (…)` target must be a real column AND carry a unique index.

    Only the first half is checkable without a database, and it is the half that fails
    silently: a misspelled conflict target raises at write time, on the one path no test
    exercises.
    """
    schema = parse_schema()
    violations: list[str] = []
    for py, sql in _sql_sources():
        insert = _INSERT.search(sql)
        conflict = _CONFLICT_COLS.search(sql)
        if not (insert and conflict):
            continue
        known = schema.get(insert.group(1).lower())
        if known is None or known is UNKNOWN_COLUMNS:
            continue
        for col in _split_cols(conflict.group(1)):
            if col and col not in known:
                violations.append(
                    f"{py.relative_to(_ROOT.parent)}: {insert.group(1)}.{col}")
    assert not violations, (
        "on-conflict targets that are not columns:\n  "
        + "\n  ".join(sorted(set(violations))))


def test_the_layer2_tables_are_declared_and_used() -> None:
    """Layer 2 shipped five migrations that have never run against Postgres. This proves
    at least that the code and the schema agree on what exists — and, just as important,
    that nothing was created and then left unread.

    `context_situations` is the known exception and is asserted separately below, because
    "built and unadopted" is a documented state, not an accident.
    """
    schema = parse_schema()
    ctes = _all_ctes()
    read: set[str] = set()
    for _, sql in _sql_sources():
        read |= _referenced_tables(sql, ctes)
    for table in ("graph_aliases", "context_correlations", "context_correlation_members",
                  "context_situations", "graph_health", "context_node_lifecycle",
                  "merge_proposals", "merge_history", "context_attention"):
        assert table in schema, f"{table} has no migration"
        assert table in read, f"{table} is created but no SQL reads it"


def test_the_parser_actually_sees_the_layer_2_schema() -> None:
    """A guard on the guard: if the DDL style changes and the parser silently stops
    matching, every test above passes vacuously. This pins the shape it must keep
    recognising."""
    schema = parse_schema()
    for table in ("graph_nodes", "graph_facts", "graph_edges", "graph_observations",
                  "graph_aliases", "context_correlations", "context_situations",
                  "context_attention", "graph_health", "merge_proposals"):
        assert table in schema, f"parser lost sight of {table}"
    assert {"situation_id", "confidence_overall", "coverage", "missing"} <= \
        schema["context_situations"]
    assert {"node_id", "canonical_key", "identity_strength"} <= schema["graph_nodes"]


@pytest.mark.parametrize(
    "package,floor",
    [("capture", 20), ("context", 80), ("reason", 60), ("executive", 40),
     ("deliver", 60), ("feedback", 10), ("api", 150)])
def test_the_ratchet_reaches_every_package_that_talks_to_postgres(
        package: str, floor: int) -> None:
    """Coverage, not correctness — the check above is only worth its runtime if it can
    actually see the queries.

    A package that drops below its floor has usually moved its SQL somewhere the AST walk
    cannot follow: a query builder, an f-string assembled across functions, or a helper
    that takes the table name as an argument. The queries did not get safer; they got
    invisible, and the tests above would go quietly green on a shrinking sample.

    Floors are set well under today's counts, so ordinary refactoring does not trip them.
    """
    seen = sum(1 for py, _ in _sql_sources()
               if str(py.relative_to(_ROOT)).split("/")[0] == package)
    assert seen >= floor, (
        f"{package}: the ratchet sees only {seen} SQL strings (floor {floor}). "
        "If SQL moved behind a builder, teach `_flatten` to follow it.")
