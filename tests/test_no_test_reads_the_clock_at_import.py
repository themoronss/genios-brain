"""STEP-17 · no test reads the wall clock when it is imported — it reads it when it runs.

    .venv/bin/python -m pytest -q tests/test_no_test_reads_the_clock_at_import.py

`yc2_w27_s17` M41.C1.L-integration.V1.U02 (S17-F6). ⛔ `03` F142: `tests/test_device_api.py` took
`NOW = datetime.now(...)` when the module was imported and paused a seat until `NOW + 1h`; the merge's
whole-suite run took 2 h 37 min of wall clock (the laptop slept), the pause was over by the time the
test ran, and the test failed for a reason that had nothing to do with the code. Measured on
2026-10-12: **22** test modules read the clock at import — among them
`tests/capture/test_unread_reread_pg.py`, three of F115's four "fail under load, pass alone" tests.
A slow runner, a sleeping laptop or a long database job moves the wall clock past every one of them.

The rule, read from the AST: nothing evaluated when a test module is imported — a module-level
statement, a class body, a decorator, a default argument — may call `datetime.now()`,
`datetime.utcnow()`, `datetime.today()`, `date.today()`, `time.time()`, `time.monotonic()` or
`time.perf_counter()`. A test reads the clock in the test (or in a fixture), or pins a fixed instant
where it hands the product `now` itself.

`M41.C1.L-integration.V1.U04` (S17X-F3): the guard saw only a read written at import itself. Two
modules hid theirs one call away — `tests/test_p10_nudges.py` built `POPUP = {… "due": _in_3h() …}`
and `tests/test_screen_followups.py` `ASK_V4` the same way, `_in_3h()` reading `datetime.now()` — and
the guard knew only the owners `datetime`, `date`, `time`, `dt` by name. Now it follows a call made
at import into the module's own function (or named lambda), and on from there; it resolves the
module's imports (`import time as t`, `from datetime import datetime as DT`); and it sees a bare
`time()`, `monotonic()` or `perf_counter()`.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

TESTS = Path(__file__).resolve().parent

#: The wall-clock reads, by their full name once the module's imports are resolved.
CLOCK_READS = frozenset({
    "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
    "datetime.date.today",
    "time.time", "time.time_ns", "time.monotonic", "time.monotonic_ns",
    "time.perf_counter", "time.perf_counter_ns"})
#: A bare call by one of these names that no import in the module binds (a star import, a name a
#: conftest hands over) is still the clock: `monotonic()`, `perf_counter()`, `time()`.
BARE_CLOCK_NAMES = frozenset({"time", "time_ns", "monotonic", "monotonic_ns", "perf_counter",
                              "perf_counter_ns"})
#: Owners nothing in the module imports: `datetime.now()`, `dt.now()`, `time.time()` read by name, as
#: the first guard did — so `self.now()` or `clock.time()` on a fake is not the wall clock.
CLOCK_CALLS = frozenset({"now", "utcnow", "today", "time", "monotonic", "perf_counter"})
CLOCK_OWNERS = frozenset({"datetime", "date", "time", "dt"})


def _imports(tree: ast.Module) -> dict[str, set[str]]:
    """{name an import binds: every full name it is bound to}, from every import in the module —
    a set, because a module may bind one name twice (`from datetime import datetime`, then
    `import datetime`) and the AST does not say which binding a line sees."""
    names: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                names.setdefault(alias.asname or root, set()).add(
                    alias.name if alias.asname else root)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            for alias in node.names:
                if alias.name != "*":
                    names.setdefault(alias.asname or alias.name, set()).add(
                        f"{node.module}.{alias.name}")
    return names


def _dotted(node: ast.expr, names: dict[str, set[str]]) -> tuple[set[str], bool] | None:
    """`(the full names it may stand for, whether an import binds its root)` for a Name or an
    Attribute chain."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    tail = list(reversed(parts))
    roots = names.get(node.id) or {node.id}
    return {".".join([root, *tail]) for root in roots}, node.id in names


def _is_clock_read(call: ast.Call, names: dict[str, set[str]]) -> bool:
    resolved = _dotted(call.func, names)
    if resolved is None:
        return False
    full, bound = resolved
    if full & CLOCK_READS:
        return True
    if bound:
        return False
    if isinstance(call.func, ast.Name):
        return call.func.id in BARE_CLOCK_NAMES
    if call.func.attr not in CLOCK_CALLS:
        return False
    owner = call.func.value
    while isinstance(owner, ast.Attribute):      # datetime.datetime.now
        if owner.attr in CLOCK_OWNERS:
            return True
        owner = owner.value
    return isinstance(owner, ast.Name) and owner.id in CLOCK_OWNERS


def _local_callables(tree: ast.Module) -> dict[str, ast.AST]:
    """The module's own functions and named lambdas, by name: what an import-time call can run."""
    found: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found[node.name] = node
        elif (isinstance(node, ast.Assign) and isinstance(node.value, ast.Lambda)
              and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            found[node.targets[0].id] = node.value
    return found


def _evaluated_at_import(tree: ast.Module):
    """Every node Python evaluates while importing the module: its top-level statements and class
    bodies, and a function's decorators and default arguments — never a function's own body."""
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(node.decorator_list)
            stack.extend(node.args.defaults)
            stack.extend(d for d in node.args.kw_defaults if d is not None)
            continue
        if isinstance(node, ast.ClassDef):
            stack.extend(node.decorator_list)
            stack.extend(node.bases)
            stack.extend(node.body)
            continue
        if isinstance(node, ast.Lambda):
            continue
        yield node
        stack.extend(ast.iter_child_nodes(node))


def _reads_the_clock(call: ast.Call, names: dict[str, set[str]], local: dict[str, ast.AST],
                     seen: set[str]) -> bool:
    """Whether this call reads the clock — itself, or inside the module's own function it calls,
    followed as far as the module's own functions go."""
    if _is_clock_read(call, names):
        return True
    if not (isinstance(call.func, ast.Name) and call.func.id in local) or call.func.id in seen:
        return False
    seen.add(call.func.id)
    body = local[call.func.id]
    return any(isinstance(node, ast.Call) and _reads_the_clock(node, names, local, seen)
               for node in ast.walk(body.body if isinstance(body, ast.Lambda) else
                                    ast.Module(body=body.body, type_ignores=[])))


def _clock_reads_at_import(source: str) -> list[int]:
    tree = ast.parse(source)
    names, local = _imports(tree), _local_callables(tree)
    return sorted(node.lineno for node in _evaluated_at_import(tree)
                  if isinstance(node, ast.Call) and _reads_the_clock(node, names, local, set()))


def test_the_reader_sees_every_shape_a_test_has_used():
    """The guard's own test: each shape found on 2026-10-12, and the reads that are fine."""
    sample = (
        "import time\nfrom datetime import date, datetime, timedelta, timezone\n"
        "NOW = datetime.now(timezone.utc)\n"                                   # 3
        "LATER = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=1)\n"  # 4
        "TODAY = date.today()\n"                                              # 5
        "class K:\n    AT = time.time()\n"                                    # 7
        "@pytest.mark.parametrize('x', [datetime.utcnow()])\n"                # 8
        "def test_a(x, at=time.monotonic()):\n"                               # 9
        "    fine = datetime.now(timezone.utc)\n"
        "FIXED = datetime(2026, 10, 1, tzinfo=timezone.utc)\n"
        "def helper(clock):\n    return clock.now()\n"
        "fn = lambda: datetime.now(timezone.utc)\n"
        "import datetime as datetime\n"                                     # 15
        "QUALIFIED = datetime.datetime.now()\n"                              # 16
        "STAMP = fake_clock.now()\n")                                        # 17: a fake's, not the wall's
    assert _clock_reads_at_import(sample) == [3, 4, 5, 7, 8, 9, 16]


def test_the_reader_follows_a_call_into_the_modules_own_functions():
    """S17X-F3's shape — `POPUP = {… "due": _in_3h() …}` — and the ways around the names."""
    sample = (
        "import time as t\n"
        "from time import time as stamp, monotonic, perf_counter\n"
        "from datetime import datetime as DT, timedelta\n"
        "import datetime as D\n"
        "A = t.time()\n"                                                      # 5  an aliased module
        "B = stamp()\n"                                                       # 6  an aliased function
        "C = monotonic()\n"                                                   # 7  bare
        "E = perf_counter()\n"                                                # 8  bare
        "F = DT.now()\n"                                                      # 9  an aliased class
        "G = D.date.today()\n"                                                # 10
        "def _in_3h():\n    return (DT.now() + timedelta(hours=3)).isoformat()\n"
        "POPUP = {'items': [{'due': _in_3h()}]}\n"                           # 13 one call away
        "def _indirect():\n    return [_in_3h()]\n"
        "TWO = _indirect()\n"                                                # 16 two calls away
        "def _pure():\n    return timedelta(hours=3)\n"
        "FINE = _pure()\n"                                                   # 19 a helper that reads no clock
        "late = lambda: DT.now()\n"
        "LAMBDA = late()\n"                                                  # 21 a named lambda, called
        "def _loop(n):\n    return _loop(n - 1) if n else 0\n"
        "LOOP = _loop(3)\n"                                                  # 24 recursion ends
        "def test_x():\n    assert _in_3h()\n"                               # called in a test: fine
        "clock = FakeClock()\nSTILL = clock.time()\n"                         # 28 a fake's
        "def _f(at=_in_3h()):\n    pass\n")                                  # 29 a default, one away
    assert _clock_reads_at_import(sample) == [5, 6, 7, 8, 9, 10, 13, 16, 21, 29]


def test_a_bare_name_an_import_binds_elsewhere_is_not_the_clock():
    """`from freezegun import freeze_time as time` — bound, and not to the time module."""
    sample = ("from mylib import time, monotonic\n"
              "A = time()\n"
              "B = monotonic()\n"
              "from time import *\n"
              "C = perf_counter()\n")                                        # 5: unbound, bare
    assert _clock_reads_at_import(sample) == [5]


def test_no_test_module_reads_the_clock_at_import():
    offenders = []
    for path in sorted(TESTS.rglob("*.py")):
        lines = _clock_reads_at_import(path.read_text(encoding="utf-8"))
        offenders += [f"{path.relative_to(TESTS.parent)}:{n}" for n in lines]
    assert not offenders, (
        f"{len(offenders)} clock read(s) at import — a long run moves the wall clock past them "
        "(03 F142). Read the clock in the test or a fixture, or pin a fixed instant:\n  "
        + "\n  ".join(offenders))
