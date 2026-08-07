"""Layer 5 · the store must only ever name columns that exist.

CI has no Postgres, so nothing else in the suite would notice a store that writes to a column a
migration never created. The failure would surface for the first time in production, at the
moment a commitment was being written, which is the worst possible place to discover a typo.

So the schema is parsed out of the migrations and the SQL is parsed out of the source, and the
two are compared. Same idea as ``tests/test_account_erasure.py`` — a static proof beats a
checklist — but done through the AST rather than with a regex over the whole file, because these
statements are assembled from string concatenation and shared SQL fragments, and a regex would
happily run one statement into the next.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from genios_engine.api import executive_routes
from genios_engine.contracts.execution import ExecutionState
from genios_engine.executive import execution_store, sweep

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
STORE = ROOT / "genios_engine" / "executive" / "execution_store.py"
ROUTES = ROOT / "genios_engine" / "api" / "executive_routes.py"
SWEEP = ROOT / "genios_engine" / "executive" / "sweep.py"

_CONSTRAINT_PREFIXES = ("primary", "unique", "foreign", "check", "constraint", "exclude")


# --- the schema, as the migrations actually define it ---------------------------------------

def _schema() -> dict[str, set[str]]:
    """Every table and its columns, across every migration.

    Reads all migrations rather than only 0041: ``org_seats`` is defined in 0008 and extended
    here, so a test that looked only at the new file would happily accept a store writing to a
    column that was never actually added.
    """
    tables: dict[str, set[str]] = {}
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = path.read_text()
        for table, body in re.findall(
                r"create\s+table\s+if\s+not\s+exists\s+(\w+)\s*\((.*?)\n\);",
                sql, flags=re.IGNORECASE | re.DOTALL):
            columns = tables.setdefault(table, set())
            for line in body.splitlines():
                stripped = line.strip().strip(",")
                if not stripped or stripped.startswith("--"):
                    continue
                head = stripped.split()[0].lower()
                if head.startswith(_CONSTRAINT_PREFIXES) or not re.fullmatch(r"\w+", head):
                    continue
                columns.add(head)
        for table, column in re.findall(
                r"alter\s+table\s+(\w+)\s+add\s+column\s+if\s+not\s+exists\s+(\w+)",
                sql, flags=re.IGNORECASE):
            tables.setdefault(table, set()).add(column.lower())
    return tables


# --- the SQL, as the source actually assembles it --------------------------------------------

def _resolve(module) -> dict[str, str]:
    return {name: value for name, value in vars(module).items() if isinstance(value, str)}


def _flatten(node: ast.AST, constants: dict[str, str]) -> str:
    """Reconstruct one SQL string from concatenation, f-strings and module constants.

    Unresolvable fragments become a space rather than being dropped, so two statement halves can
    never be silently welded into one that parses as something neither of them says.
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else " "
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flatten(node.left, constants) + _flatten(node.right, constants)
    if isinstance(node, ast.Name):
        return constants.get(node.id, " ")
    if isinstance(node, ast.JoinedStr):
        return "".join(_flatten(part, constants) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        return _flatten(node.value, constants)
    return " "


def _statements(path: Path, module) -> list[str]:
    """Every SQL string handed to SQLAlchemy's ``text()`` in this file."""
    constants = _resolve(module)
    tree = ast.parse(path.read_text())
    found: list[str] = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "text" and node.args):
            found.append(" ".join(_flatten(node.args[0], constants).split()))
    return found


SCHEMA = _schema()
SOURCES = [(STORE, execution_store), (ROUTES, executive_routes), (SWEEP, sweep)]
L5_TABLES = ("executions", "execution_actions", "execution_escalations", "execution_events",
             "execution_outcomes")


def test_the_migration_creates_every_table_layer_five_uses():
    assert set(L5_TABLES) <= set(SCHEMA)
    assert "manager_seat_id" in SCHEMA["org_seats"], (
        "escalation to a manager has nowhere to go without the reporting line column")


def test_the_sql_is_actually_parseable_so_this_ratchet_is_not_vacuous():
    """A guard against the guard: if the AST walk stopped finding statements, every assertion
    below would pass by examining nothing."""
    for path, module in SOURCES:
        statements = _statements(path, module)
        assert len(statements) >= 5, f"{path.name} yielded only {len(statements)} statements"
        assert any("insert into executions" in item for item in _statements(STORE,
                                                                           execution_store))


@pytest.mark.parametrize("path,module", SOURCES, ids=lambda item: getattr(item, "name", ""))
def test_every_inserted_column_exists(path: Path, module):
    """Catches the classic drift: a column added to an INSERT and forgotten in the migration."""
    for statement in _statements(path, module):
        for table, columns in re.findall(r"insert into (\w+) \(([^)]*)\)", statement,
                                         flags=re.IGNORECASE):
            if table not in SCHEMA:
                continue
            named = {item.strip().lower() for item in columns.split(",") if item.strip()}
            unknown = named - SCHEMA[table]
            assert not unknown, f"{path.name} inserts unknown columns into {table}: {unknown}"


@pytest.mark.parametrize("path,module", SOURCES, ids=lambda item: getattr(item, "name", ""))
def test_every_updated_column_exists(path: Path, module):
    for statement in _statements(path, module):
        match = re.search(r"update (\w+) set (.*?) where ", statement, flags=re.IGNORECASE)
        if not match or match.group(1) not in SCHEMA:
            continue
        table, assignments = match.groups()
        named = {item.group(1).lower()
                 for item in re.finditer(r"(?:^|,)\s*(\w+)\s*=", assignments)}
        unknown = named - SCHEMA[table]
        assert not unknown, f"{path.name} updates unknown columns on {table}: {unknown}"


#: ``from`` is not always a FROM clause. ``is not distinct from x.y`` is a comparison operator,
#: and the authority predicate uses it heavily; matching it as a table would make this ratchet
#: fail on correct Layer 4 SQL that Layer 5 merely embeds.
_FROM_CLAUSE = re.compile(r"(?<!distinct )\bfrom (\w+)\b", re.IGNORECASE)


@pytest.mark.parametrize("path,module", SOURCES, ids=lambda item: getattr(item, "name", ""))
def test_every_selected_table_exists(path: Path, module):
    known = set(SCHEMA) | {"orgs"}
    for statement in _statements(path, module):
        for table in _FROM_CLAUSE.findall(statement):
            assert table in known or table.startswith(("jsonb", "lateral")), (
                f"{path.name} reads unknown table {table}")


def test_the_execution_insert_binds_one_value_per_column():
    """A column list and a values list that drift apart shift every field by one — and every
    field after the shift is silently the wrong data, not an error."""
    columns = [item.strip() for item in execution_store._EXECUTION_COLUMNS.split(",")]
    assert set(columns) <= SCHEMA["executions"]
    assert len(columns) == len(set(columns)), "duplicate column in the executions insert"

    statement = next(item for item in _statements(STORE, execution_store)
                     if item.lower().startswith("insert into executions"))
    values = re.search(r"values \((.*?)\) on conflict", statement, flags=re.IGNORECASE)
    assert values, "the executions insert no longer has a recognisable values clause"
    bound = [item.strip() for item in values.group(1).split(",")]
    assert len(bound) == len(columns), (
        f"{len(columns)} columns but {len(bound)} values in the executions insert")


def _execute_calls(path: Path, module) -> list[tuple[str, set[str], int]]:
    """Every ``conn.execute(text(sql), {params})`` pair: the SQL, its bound names, its line."""
    constants = _resolve(module)
    tree = ast.parse(path.read_text())
    calls: list[tuple[str, set[str], int]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute" and node.args):
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Call) and isinstance(first.func, ast.Name)
                and first.func.id == "text"):
            continue
        sql = " ".join(_flatten(first.args[0], constants).split())
        supplied: set[str] = set()
        if len(node.args) > 1 and isinstance(node.args[1], ast.Dict):
            supplied = {key.value for key in node.args[1].keys
                        if isinstance(key, ast.Constant) and isinstance(key.value, str)}
        elif len(node.args) > 1:
            supplied = {"*"}          # built elsewhere; nothing static to check
        calls.append((sql, supplied, node.lineno))
    return calls


@pytest.mark.parametrize("path,module", SOURCES, ids=lambda item: getattr(item, "name", ""))
def test_every_bind_parameter_is_supplied(path: Path, module):
    """Embedded SQL fragments carry their own binds, and forgetting one is invisible until the
    statement runs.

    ``reason/authority.py``'s predicate requires ``:authority_time``; a caller that pastes it in
    and does not bind it raises only when a real signal is being re-validated — which is to say,
    at the exact moment a live commitment is deciding whether it may still escalate.
    """
    for sql, supplied, line in _execute_calls(path, module):
        if "*" in supplied:
            continue
        required = set(re.findall(r"(?<![:\w]):([a-z_]\w*)", sql))
        missing = required - supplied
        assert not missing, f"{path.name}:{line} does not bind {sorted(missing)}"


def test_the_api_only_selects_columns_that_exist():
    fields = {item.strip().lower()
              for item in executive_routes._COMMITMENT_FIELDS.split(",")}
    assert fields <= SCHEMA["executions"]


def test_every_state_the_machine_can_reach_is_documented_in_the_migration():
    """The state column is free text in Postgres, so the migration's comment is the only place a
    reader learns the vocabulary. It has to stay complete or it becomes actively misleading."""
    sql = (MIGRATIONS / "0041_l5_execution.sql").read_text()
    documented = sql.split("state               text not null default 'created',", 1)[1][:400]
    for state in ExecutionState:
        assert state.value in documented, f"{state.value} is not documented in the migration"
