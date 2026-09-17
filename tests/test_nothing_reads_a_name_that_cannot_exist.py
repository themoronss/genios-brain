"""A name no scope can bind is a crash that only fires on the branch nobody tested.

    pytest tests/test_nothing_reads_a_name_that_cannot_exist.py -q

TWO OF THESE SHIPPED IN ONE WEEK, and both were invisible for the same reason.

`reason/domain_shadow` called `l1_refusal(c, ...)` where the connection in scope is `conn`. The
branch runs only when a situation has NO Layer 1 signal, and every test in the suite supplies one,
so the line was never executed by a test and crashed on 47 of the pilot's 103 situations the first
time it met real data. It did not fail the sweep: the pass wraps each situation in
`except Exception: counts["error"] += 1`, which is correct — one bad situation must not abort the
other hundred — and which therefore converts a NameError into a tally that reads like a skip.

`context/correlation_membership` carried a copy of its own writer that still called the private
names it had been extracted away from (`_finding_events`, `_Finding`). Nothing called the copy, so
nothing failed, and it would have raised the moment anyone did.

WHY A TEST AND NOT A LINTER. This is `pyflakes` F821, and pyflakes is not a dependency here. The
check below is `symtable` — the interpreter's own scope resolution, the same one that decides at
runtime whether a name can be found — so it agrees with Python by construction rather than by
reimplementing its rules.

WHAT IT CANNOT SEE, stated so nobody reads more into a green run: a name that EXISTS but is bound
to the wrong object, an attribute that is missing, and anything reached dynamically through
`globals()` or `getattr`. It answers exactly one question — could this name ever resolve — and the
answer for every function in the engine must be yes.
"""
from __future__ import annotations

import builtins
import pathlib
import symtable

import pytest

pytestmark = pytest.mark.unit

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "genios_engine"

#: Names the interpreter supplies to a scope without any binding appearing in the source.
#: `__class__` is created by any method that mentions it (zero-argument `super()` uses it);
#: `__file__` and friends are module attributes the loader sets.
IMPLICIT = frozenset({
    "__class__", "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__path__", "__builtins__", "__debug__", "__module__",
    "__qualname__", "__dict__",
})

BUILTINS = frozenset(dir(builtins))


def _bound_here(table: symtable.SymbolTable) -> set[str]:
    """Every name this scope binds — assignment, import, parameter, def/class."""
    return {sym.get_name() for sym in table.get_symbols()
            if sym.is_assigned() or sym.is_imported() or sym.is_parameter()
            or sym.is_namespace()}


def unresolvable(source: str, path: str) -> list[tuple[str, str, int]]:
    """`(scope, name, line)` for every name read that no enclosing scope could bind."""
    found: list[tuple[str, str, int]] = []

    def walk(table: symtable.SymbolTable, enclosing: frozenset[str]) -> None:
        visible = enclosing | _bound_here(table)
        for sym in table.get_symbols():
            name = sym.get_name()
            if (sym.is_referenced()
                    and not sym.is_assigned() and not sym.is_parameter()
                    and not sym.is_imported() and not sym.is_namespace()
                    and name not in visible
                    and name not in BUILTINS
                    and name not in IMPLICIT):
                found.append((table.get_name(), name, table.get_lineno()))
        for child in table.get_children():
            walk(child, frozenset(visible))

    walk(symtable.symtable(source, path, "exec"), frozenset())
    return found


def test_the_engine_reads_no_name_that_cannot_resolve() -> None:
    """Every module under `genios_engine`, every scope inside it."""
    problems: list[str] = []
    for module in sorted(ENGINE.rglob("*.py")):
        for scope, name, line in unresolvable(module.read_text(), str(module)):
            rel = module.relative_to(ENGINE.parent)
            problems.append(f"{rel}:{line} — {scope}() reads {name!r}, which nothing binds")
    assert not problems, "\n".join(["names that can only raise NameError:", *problems])


def test_the_check_catches_the_shape_that_shipped() -> None:
    """The `domain_shadow` defect, reduced: the connection is `conn`, the call says `c`."""
    source = (
        "from situation_bso import l1_refusal\n"
        "def compile(conn, org_id):\n"
        "    for row in conn:\n"
        "        refusal = l1_refusal(c, org_id, row)\n"
        "    return refusal\n"
    )
    assert [(s, n) for s, n, _ in unresolvable(source, "<t>")] == [("compile", "c")]


def test_a_module_level_helper_is_visible_to_a_function_below_it() -> None:
    """The obvious false positive, ruled out: forward references to module globals resolve."""
    source = ("def later(conn):\n"
              "    return helper(conn)\n"
              "def helper(conn):\n"
              "    return conn\n")
    assert unresolvable(source, "<t>") == []


def test_a_closure_over_an_enclosing_local_is_not_reported() -> None:
    """The second obvious false positive: a nested scope reading the name above it."""
    source = ("def outer(rows):\n"
              "    total = 0\n"
              "    def inner():\n"
              "        return total\n"
              "    return inner()\n")
    assert unresolvable(source, "<t>") == []


def test_a_renamed_private_helper_is_reported() -> None:
    """The `correlation_membership` defect: a copy kept calling the private name it left behind."""
    source = ("def declare(conn):\n"
              "    return _finding_events(conn)\n"
              "def finding_events(conn):\n"
              "    return ()\n")
    assert [(s, n) for s, n, _ in unresolvable(source, "<t>")] == [("declare", "_finding_events")]
