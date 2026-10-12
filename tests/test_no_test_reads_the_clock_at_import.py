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
`datetime.utcnow()`, `date.today()`, `time.time()` or `time.monotonic()`. A test reads the clock in
the test (or in a fixture), or pins a fixed instant where it hands the product `now` itself.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

TESTS = Path(__file__).resolve().parent

#: The wall-clock reads, by the attribute or name called.
CLOCK_CALLS = frozenset({"now", "utcnow", "today", "time", "monotonic"})
#: …on one of these — so `self.now()` or `clock.time()` on a fake is not the wall clock.
CLOCK_OWNERS = frozenset({"datetime", "date", "time", "dt"})


def _is_clock_read(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in CLOCK_CALLS:
        owner = func.value
        while isinstance(owner, ast.Attribute):      # datetime.datetime.now
            if owner.attr in CLOCK_OWNERS:
                return True
            owner = owner.value
        return isinstance(owner, ast.Name) and owner.id in CLOCK_OWNERS
    return False


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


def _clock_reads_at_import(source: str) -> list[int]:
    return sorted(node.lineno for node in _evaluated_at_import(ast.parse(source))
                  if isinstance(node, ast.Call) and _is_clock_read(node))


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


def test_no_test_module_reads_the_clock_at_import():
    offenders = []
    for path in sorted(TESTS.rglob("*.py")):
        lines = _clock_reads_at_import(path.read_text(encoding="utf-8"))
        offenders += [f"{path.relative_to(TESTS.parent)}:{n}" for n in lines]
    assert not offenders, (
        f"{len(offenders)} clock read(s) at import — a long run moves the wall clock past them "
        "(03 F142). Read the clock in the test or a fixture, or pin a fixed instant:\n  "
        + "\n  ".join(offenders))
