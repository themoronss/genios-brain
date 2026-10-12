r"""Every SQL statement the engine and its scripts hold, whole — and whether Postgres can plan it.

STEP-17 §3.2 (`yc2_w27_s17` M40.C1). ⛔ WHY THIS EXISTS. The weekly calibration raised
`UndefinedColumn card_level` on every run from 2026-09-10 (STEP-18 B1) while 14,624 tests passed:
no test ran that statement on Postgres, and nothing else ever asked Postgres whether the SQL the
engine holds is SQL. This module asks it, for every statement that can be read from the source.

⛔⛔ "EVERY STATEMENT `table_coverage` KNOWS" WAS NOT ENOUGH, MEASURED. `table_coverage._statements`
reads every string node that starts like SQL — right for its question (which tables does a module
name) and wrong for this one:

  * **pieces.** `"select … from " + T` is a BinOp whose left side is ALSO a string node, so one
    statement counts twice and the piece fails to plan on its own. 745 of its 3,064 at `c97155cd`;
  * **docstrings.** *"Select only the rule-relevant legacy context…"* starts like SQL. 21;
  * **⛔ B1 ITSELF.** The calibration statement is `"with " + AUDITED_CARD_JUDGMENTS_CTES + …` —
    three modules of fragments. Rendered as text it is a statement with holes, and a planner that
    skips a statement with holes would have skipped exactly the one that broke.

So the census takes the OUTERMOST string expression only, never a docstring or a single word, and
resolves each ``{NAME}`` through the module's own value: an engine module is IMPORTED and its
attribute read (the value Python actually computed, however it was built); a script is READ from its
AST and never imported — some scripts read production, and importing one runs its top level.

What still cannot be resolved stays a NAMED hole — ``{where}`` from a local, ``{?}`` from any other
expression, ``%`` for a ``%``-formatted statement, ``+=`` for one finished by ``sql += …`` — and is
assembled at run time: the database suite is its only check, and the planner's test holds their
number under a ceiling so it cannot grow in silence.
"""
from __future__ import annotations

import ast
import importlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from genios_engine.platform import table_coverage as _tc

#: A hole the census could not fill: ``{NAME}`` from a variable, ``{?}`` from any other expression.
#: ⛔ A name or ``?`` only — ``'{}'`` (an empty JSON or array literal) and ``x{64}`` (a regex count)
#: are SQL, not holes.
HOLE = re.compile(r"\{(\?|[A-Za-z_][A-Za-z_0-9]*)\}")

#: The two run-time assemblies that are not a ``{NAME}``.
PERCENT_FORMAT = "%"
AUGMENTED = "+="


@dataclass(frozen=True)
class Statement:
    """One whole SQL expression: where it lives, its text with constants resolved, its holes."""

    path: str
    line: int
    sql: str
    holes: tuple[str, ...]


# ── rendering ─────────────────────────────────────────────────────────────────────────────────

def _is_stringy(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) \
        or isinstance(node, ast.JoinedStr) \
        or (isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod))
            and (_is_stringy(node.left) or _is_stringy(node.right)))


def _render(node: ast.AST) -> str:
    """The expression as text, ``{NAME}`` for a variable and ``{?}`` for anything else.

    ⛔ NEVER NONE. `table_coverage._template` answers None for `"select " + ", ".join(cols)`, which
    is right for attribution and would make the whole statement invisible here. A part that is not
    a string is a hole, and the statement is still counted."""
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else "{?}"
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
                parts.append("{" + value.value.id + "}")
            else:
                parts.append("{?}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _render(node.left) + _render(node.right)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        return _render(node.left)
    if isinstance(node, ast.Name):
        return "{" + node.id + "}"
    return "{?}"


def _is_piece(node: ast.AST, parent: ast.AST | None) -> bool:
    """A string inside a larger string expression — counted with its whole, never alone."""
    return isinstance(parent, (ast.JoinedStr, ast.FormattedValue)) or (
        isinstance(parent, ast.BinOp) and isinstance(parent.op, (ast.Add, ast.Mod))
        and _is_stringy(parent))


def _resolve(text: str, resolve: Callable[[str], str | None]) -> str:
    def sub(match: re.Match) -> str:
        if match.group(1) == "?":
            return match.group(0)
        value = resolve(match.group(1))
        return value if isinstance(value, str) else match.group(0)
    return HOLE.sub(sub, text)


def _augmented_names(tree: ast.Module) -> set[str]:
    return {node.target.id for node in ast.walk(tree)
            if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add)
            and isinstance(node.target, ast.Name)}


def census_of(path: str, source: str, *, resolve: Callable[[str], str | None]) -> list[Statement]:
    """The whole SQL expressions of one module, with ``resolve(name)`` filling each ``{name}``.

    Also returns nothing for — and `census()` counts — the pieces, the docstrings and the single
    words it leaves out."""
    return _census(path, source, resolve, counts=None)


def _census(path: str, source: str, resolve: Callable[[str], str | None],
            counts: dict[str, int] | None) -> list[Statement]:
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    printed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
            printed.update(id(n) for n in ast.walk(node))
    augmented = _augmented_names(tree)

    def count(key: str) -> None:
        if counts is not None:
            counts[key] = counts.get(key, 0) + 1

    out: list[Statement] = []
    for node in ast.walk(tree):
        if id(node) in printed or not _is_stringy(node):
            continue
        parent = parents.get(node)
        raw = _render(node)
        # The shape is judged after the leading name is resolved: `CTES + "select …"` starts with
        # its constant, and judged as text it would not look like SQL at all.
        text = raw if _tc._SQL_SHAPE.match(raw) else _resolve(raw, resolve)
        if not _tc._SQL_SHAPE.match(text):
            continue
        if _is_piece(node, parent):
            count("pieces")
            continue
        if isinstance(parent, ast.Expr):
            count("docstrings")
            continue
        sql = _resolve(text, resolve)
        if len(sql.split()) < 2:
            count("words")
            continue
        holes = [h for h in HOLE.findall(sql)]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            holes.append(PERCENT_FORMAT)
        if isinstance(parent, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in augmented for t in parent.targets):
            holes.append(AUGMENTED)
        out.append(Statement(path=path, line=node.lineno, sql=sql, holes=tuple(holes)))
    return out


# ── resolution ────────────────────────────────────────────────────────────────────────────────


def _module_strings(tree: ast.Module, imported: Callable[[str], str | None]) -> dict[str, str]:
    """A script's module-level string constants, read from its AST — never by running it.

    Bounded: a constant renders from literals, from other constants of the module (three passes)
    and from names it imports from an engine module."""
    raw: dict[str, ast.AST] = {}
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        value = getattr(node, "value", None)
        if value is None or not _is_stringy(value):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                raw[target.id] = value
    known: dict[str, str] = {}
    for _ in range(3):
        for name, value in raw.items():
            rendered = _resolve(_render(value), lambda n: known.get(n) or imported(n))
            if "{?}" not in rendered:
                known[name] = rendered
    return known


def _engine_imports(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """``{local name: (engine module, attribute)}`` for ``from genios_engine.X import NAME``."""
    out: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level and node.module \
                and node.module.startswith("genios_engine"):
            for alias in node.names:
                out[alias.asname or alias.name] = (node.module, alias.name)
    return out


def _resolver(path: str, source: str, importer: Callable[[str], object],
              known_tables: frozenset[str],
              failures: dict[str, str] | None = None) -> Callable[[str], str | None]:
    tree = ast.parse(source)
    table_constants = {**_tc._imported_table_constants(tree),
                       **_tc._module_table_constants(tree, known_tables)}
    aliases = _tc._local_table_aliases(tree, table_constants)

    def from_engine(module: str, attribute: str) -> str | None:
        try:
            value = getattr(importer(module), attribute, None)
        except Exception as exc:                 # noqa: BLE001 — named, never swallowed
            if failures is not None:
                failures[module] = f"{type(exc).__name__}: {exc}"[:300]
            return None
        return value if isinstance(value, str) else None

    if path.startswith("genios_engine/"):
        module = path[:-3].replace("/", ".")

        def own(name: str) -> str | None:
            return from_engine(module, name)
    else:
        imports = _engine_imports(tree)

        def imported(name: str) -> str | None:
            return from_engine(*imports[name]) if name in imports else None

        constants = _module_strings(tree, imported)

        def own(name: str) -> str | None:
            return constants.get(name) or imported(name)

    def resolve(name: str) -> str | None:
        value = own(name)
        if value is not None:
            return value
        # ⛔ table_coverage's third hop: `table = L3_ACTIVATION_TABLE` inside a function, then
        # `f"insert into {table} …"`. Ambiguous aliases are already refused there.
        tables = aliases.get(name)
        return tables[0] if tables else None

    return resolve


def build_statements(*, importer: Callable[[str], object] = importlib.import_module,
                     counts: dict[str, int] | None = None,
                     failures: dict[str, str] | None = None) -> tuple[Statement, ...]:
    """The census over `genios_engine/` and `scripts/` — `table_coverage`'s own sources.

    ``counts`` receives what was left out, by kind; ``failures`` each engine module that could
    not be imported, with why — a module nobody can import keeps every hole it has."""
    out: list[Statement] = []
    known_tables = _tc._known_tables()
    for path, source in _tc._sources():
        try:
            resolve = _resolver(path, source, importer, known_tables, failures)
            out.extend(_census(path, source, resolve, counts))
        except SyntaxError:                        # pragma: no cover - the tree parses
            continue
    return tuple(out)


@lru_cache(maxsize=1)
def _cached() -> tuple[tuple[Statement, ...], tuple[tuple[str, int], ...],
                       tuple[tuple[str, str], ...]]:
    counts: dict[str, int] = {}
    failures: dict[str, str] = {}
    stmts = build_statements(counts=counts, failures=failures)
    return stmts, tuple(sorted(counts.items())), tuple(sorted(failures.items()))


def statements() -> tuple[Statement, ...]:
    """Every whole SQL expression of the engine and its scripts, constants resolved."""
    return _cached()[0]


def census() -> dict[str, int]:
    """What the census read and what it left out, by kind — reported beside every verdict."""
    stmts, left_out, _failures = _cached()
    counts = dict(left_out)
    counts.setdefault("pieces", 0)
    counts.setdefault("docstrings", 0)
    counts.setdefault("words", 0)
    counts["statements"] = len(stmts)
    counts["resolved_whole"] = sum(1 for s in stmts if not s.holes)
    counts["assembled_at_run_time"] = sum(1 for s in stmts if s.holes)
    return counts


def import_failures() -> tuple[tuple[str, str], ...]:
    """Engine modules the census could not import — every hole in them stays a hole."""
    return _cached()[2]


__all__ = ["AUGMENTED", "HOLE", "PERCENT_FORMAT", "Statement", "build_statements", "census",
           "census_of", "import_failures", "statements"]
