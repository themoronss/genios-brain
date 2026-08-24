"""Stateless-worker invariant check (g-i-8).

Per MD: workers must be stateless. If a process holds mutable module-level
state between requests, horizontal scaling silently breaks (results depend on
which worker handled the request).

This module walks a target package and flags any top-level mutable container
(dict / list / set / bytearray) that isn't an explicit allow-listed config
constant. Returns a list of violations — empty list = invariant holds.

Designed to be called from a CI test, not at runtime. Cheap (AST walk only),
runs on every commit.
"""

from __future__ import annotations

import ast
import pkgutil
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

MUTABLE_CALL_NAMES = {"dict", "list", "set", "bytearray", "defaultdict", "Counter", "deque"}


# Constants that are *intended* to be module-level dicts/lists (config, lookup tables).
# Add a name here only when you're sure it's never mutated at runtime.
ALLOWED_NAMES: frozenset[str] = frozenset(
    {
        # config dicts (read-only)
        "CONFIDENCE_WEIGHTS",
        "CRON_INTERVAL_HOURS",
        "GOLDEN_THRESHOLD",
        "LLM_DAILY_BUDGET_USD",
        # registry singletons (private, gated mutation through registered API)
        "_FACTORIES",
        "_REGISTRY",
        "_BUCKETS",
        "_TOOLS",
        "MUTABLE_CALL_NAMES",
        "ALLOWED_NAMES",
    }
)


@dataclass(frozen=True)
class StatefulSymbol:
    """One offending module-level mutable assignment."""

    module: str
    name: str
    lineno: int
    kind: str  # "dict" | "list" | "set" | etc.


def scan_package(package_name: str) -> list[StatefulSymbol]:
    """Walk every .py under `package_name` and report module-level mutables."""
    spec = find_spec(package_name)
    if spec is None or spec.submodule_search_locations is None:
        raise ValueError(f"package not importable: {package_name}")

    violations: list[StatefulSymbol] = []
    for root in spec.submodule_search_locations:
        for finder, mod_name, ispkg in pkgutil.walk_packages(  # noqa: B007
            [root], prefix=f"{package_name}."
        ):
            if ispkg:
                continue
            file_path = _module_file(mod_name)
            if file_path is None:
                continue
            violations.extend(_scan_file(mod_name, file_path))
    return violations


def _module_file(mod_name: str) -> Path | None:
    spec = find_spec(mod_name)
    if spec is None or spec.origin is None or spec.origin == "built-in":
        return None
    p = Path(spec.origin)
    if p.suffix != ".py":
        return None
    return p


def _scan_file(mod_name: str, path: Path) -> list[StatefulSymbol]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    violations: list[StatefulSymbol] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                name = target.id
                if name in ALLOWED_NAMES:
                    continue
                kind = _classify_value(node.value)
                if kind is not None:
                    violations.append(
                        StatefulSymbol(
                            module=mod_name, name=name, lineno=node.lineno, kind=kind
                        )
                    )
        elif isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name) or node.value is None:
                continue
            name = node.target.id
            if name in ALLOWED_NAMES:
                continue
            kind = _classify_value(node.value)
            if kind is not None:
                violations.append(
                    StatefulSymbol(
                        module=mod_name, name=name, lineno=node.lineno, kind=kind
                    )
                )
    return violations


def _classify_value(value: ast.expr) -> str | None:
    """Return a label if `value` is a mutable literal/constructor call, else None."""
    if isinstance(value, ast.Dict):
        return "dict_literal"
    if isinstance(value, ast.List):
        return "list_literal"
    if isinstance(value, ast.Set):
        return "set_literal"
    if isinstance(value, ast.Call):
        func = value.func
        name = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name in MUTABLE_CALL_NAMES:
            return f"{name}_call"
    return None
