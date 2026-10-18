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

`M41.C1.L-integration.V1.U05` (S17X-F1, second crosscheck): a third shape, not a read at import at
all — a module borrows a HELPER from a sibling test module (`from tests.test_moments_pg import
_seed`), and that helper falls back to the sibling's own `NOW: datetime = None`, which only the
sibling's own `autouse` fixture ever sets. Run together, file order saves it (the sibling's tests
run first and leave a live-enough instant behind — `test_moments_pg.py` < `test_p10_nudges.py`); run
alone, `NOW` is still `None` and the helper raises. The fix is `_seed(ws, *, now=None)`, falling back
to `NOW` only when the caller passes none — so the guard now follows a cross-module import to a
sibling that defines a `None`-initialised `datetime` global set only by an autouse fixture, and
flags it unless either the caller also imports that fixture (pytest finds an autouse fixture through
any name in the module's namespace, imported or not — `client` already rides in this way) or every
call the caller makes passes the parameter that shadows the fallback.
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


# ── S17X-F1: a helper borrowed from a sibling that falls back to the sibling's own stale clock ──
def _now_globals(tree: ast.Module, names: dict[str, set[str]]) -> set[str]:
    """Module-level names declared `X: datetime = None` — a clock an autouse fixture, and nothing
    else, can ever set."""
    found = set()
    for node in tree.body:
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Constant) and node.value.value is None):
            resolved = _dotted(node.annotation, names)
            if resolved and "datetime.datetime" in resolved[0]:
                found.add(node.target.id)
    return found


def _is_autouse_fixture(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                and dec.func.attr == "fixture"
                and isinstance(dec.func.value, ast.Name) and dec.func.value.id == "pytest"):
            if any(kw.arg == "autouse" and isinstance(kw.value, ast.Constant) and kw.value.value
                   for kw in dec.keywords):
                return True
    return False


def _autouse_setters(tree: ast.Module, now_globals: set[str]) -> set[str]:
    """Fixture names that `global`-declare and assign one of `now_globals` — the only way one is
    ever set to a live instant."""
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_autouse_fixture(node):
            if any(isinstance(n, ast.Global) and set(n.names) & now_globals
                   for n in ast.walk(node)):
                found.add(node.name)
    return found


def _reads_global(func: ast.FunctionDef | ast.AsyncFunctionDef, now_globals: set[str]) -> bool:
    """Whether this function's body reads one of `now_globals` at all — the ROOT risk (S17X-F1's
    original shape: `_seed` read `NOW` straight, with no parameter and so no way to override it)."""
    return any(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in now_globals
               for n in ast.walk(func))


def _fallback_param(func: ast.FunctionDef | ast.AsyncFunctionDef, now_globals: set[str]) -> str | None:
    """The parameter this function falls back FROM, onto one of `now_globals` — the idiom
    `x = p if p is not None else NOW` — or None if the function has no such fallback."""
    for node in ast.walk(func):
        if (isinstance(node, ast.IfExp) and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name) and len(node.test.ops) == 1
                and isinstance(node.test.ops[0], ast.IsNot) and len(node.test.comparators) == 1
                and isinstance(node.test.comparators[0], ast.Constant)
                and node.test.comparators[0].value is None
                and isinstance(node.body, ast.Name) and node.body.id == node.test.left.id
                and isinstance(node.orelse, ast.Name) and node.orelse.id in now_globals):
            return node.test.left.id
    return None


def _module_for(dotted: str, root: Path, prefix: str) -> Path | None:
    if not dotted.startswith(prefix):
        return None
    candidate = root / (dotted.replace(".", "/") + ".py")
    return candidate if candidate.is_file() else None


def _calls_override(tree: ast.Module, local_name: str, param: str) -> bool:
    """Whether EVERY call to `local_name` in `tree` passes `param` as a keyword — the one way a
    caller can shadow the fallback this guard found. No call at all is not yet a risk."""
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == local_name]
    return not calls or all(any(kw.arg == param for kw in c.keywords) for c in calls)


def _stale_clock_imports(path: Path, root: Path, prefix: str = "tests.") -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = _imports(tree)
    offenders = []
    for node in ast.walk(tree):   # an ImportFrom guarded by `if URL:` is not in tree.body itself
        if not (isinstance(node, ast.ImportFrom) and node.module and not node.level):
            continue
        target = _module_for(node.module, root, prefix)
        if target is None or target.resolve() == path.resolve():
            continue
        t_tree = ast.parse(target.read_text(encoding="utf-8"))
        now_globals = _now_globals(t_tree, _imports(t_tree))
        if not now_globals:
            continue
        imported = {(a.asname or a.name): a.name for a in node.names}
        if _autouse_setters(t_tree, now_globals) & set(imported):
            continue   # the sibling's own fixture rides along — pytest will pick it up
        funcs = {n.name: n for n in t_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        for local_name, orig_name in imported.items():
            func = funcs.get(orig_name)
            if func is None or not _reads_global(func, now_globals):
                continue
            param = _fallback_param(func, now_globals)
            if param and _calls_override(tree, local_name, param):
                continue   # every call supplies its own instant — the fallback is never taken
            offenders.append(
                f"{path}:{node.lineno} imports `{local_name}` from {node.module}, which reads its "
                f"stale `{'/'.join(sorted(now_globals))}`" +
                (f" unless `{param}=` is passed at every call" if param else
                 " and has no parameter to override it with"))
    return offenders


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


def test_the_guard_catches_a_helper_borrowed_without_its_fixture(tmp_path):
    """S17X-F1's own shape, built fresh so the rule is proven apart from the real tree: a sibling
    with a `NOW` only its own autouse fixture sets, a helper with no way to override it at all (the
    original `_seed`, always caught when borrowed bare) and one with a fallback parameter (caught
    only when a call forgets it) — against three borrowers: never overrides, brings the fixture
    along, overrides at every call."""
    pkg = tmp_path / "faketests"
    pkg.mkdir()
    (pkg / "owner.py").write_text(
        "from __future__ import annotations\n"
        "from datetime import datetime, timezone\n"
        "import pytest\n"
        "NOW: datetime = None\n"
        "@pytest.fixture(autouse=True)\n"
        "def _clock():\n"
        "    global NOW\n"
        "    NOW = datetime.now(timezone.utc)\n"
        "def _seed_bare(ws):\n"            # the original shape: no parameter at all
        "    return NOW\n"
        "def _seed(ws, *, now: datetime | None = None):\n"
        "    now = now if now is not None else NOW\n"
        "    return now\n")
    (pkg / "user_bad_bare.py").write_text(
        "from faketests.owner import _seed_bare\ndef test_x():\n    _seed_bare({})\n")
    (pkg / "user_bad.py").write_text("from faketests.owner import _seed\ndef test_x():\n    _seed({})\n")
    (pkg / "user_with_fixture.py").write_text(
        "from faketests.owner import _clock, _seed  # noqa: F401\ndef test_x():\n    _seed({})\n")
    (pkg / "user_overrides.py").write_text(
        "from faketests.owner import _seed\nimport datetime as dt\n"
        "def test_x():\n    _seed({}, now=dt.datetime.now(dt.timezone.utc))\n")

    def _scan(name):
        return _stale_clock_imports(pkg / name, root=tmp_path, prefix="faketests.")

    bare = _scan("user_bad_bare.py")
    assert len(bare) == 1 and "`_seed_bare`" in bare[0] and "no parameter" in bare[0]
    bad = _scan("user_bad.py")
    assert len(bad) == 1 and "`_seed`" in bad[0] and "`now=`" in bad[0]
    assert _scan("user_with_fixture.py") == []
    assert _scan("user_overrides.py") == []


def test_no_test_module_borrows_a_helper_without_its_clock():
    offenders = []
    for path in sorted(TESTS.rglob("*.py")):
        offenders += _stale_clock_imports(path, root=TESTS.parent)
    assert not offenders, (
        f"{len(offenders)} cross-module import(s) fall back to a sibling's stale clock (S17X-F1) — "
        "bring the sibling's own autouse fixture along, or pass the parameter that shadows it at "
        "every call:\n  " + "\n  ".join(offenders))
