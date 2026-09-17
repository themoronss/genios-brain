"""`meeting_follow_through` produced zero cards on every tenant, and nothing failed.

    pytest tests/context/test_a_gather_that_raised_on_every_sweep.py -q

`outreach_situations` gathered its meetings with `text(_MEETINGS)` — a bare name no import in that
module ever bound. Every sweep the lambda raised `NameError`, `_optional` caught it, logged
"gather meetings unavailable; the reading it feeds is skipped", and returned `[]`.
`read_meetings_for_dispatch` then had nothing to read, so the reading registered for
`ANCHOR_MEETING` produced nothing — on this tenant and on every tenant, from the day the line was
written. Found in a live sweep log, not by a test.

THE SAVEPOINT GUARD DID ITS JOB AND THAT IS THE PROBLEM. `_optional` exists because a failed
gather must not take the other fourteen down with it — the transaction-abort defect it was written
for killed eleven readings at once. It converts a crash into a gap, which is right. It also
converts a permanently broken lane into a quiet one, and the only thing standing between those two
readings of the same log line is somebody looking. The same shape as
`correlation_dependency.event_parties` calling an un-imported `text`.

WHY A NAME-ONLY CHECK IS NOT ENOUGH, and why this file executes things. Every earlier version of
this defect passed source inspection: the name is spelled correctly, the call looks ordinary, and
only binding it at runtime shows there is nothing behind it.
"""
from __future__ import annotations

import ast
import inspect

import pytest

pytestmark = pytest.mark.unit


def test_the_meetings_query_is_actually_bound() -> None:
    """THE DEFECT ITSELF, checked by resolving the thing rather than by reading its name."""
    from genios_engine.context.meeting_touch import _MEETINGS

    assert isinstance(_MEETINGS, str) and _MEETINGS.strip(), "the meetings query is empty"
    assert "attended" in _MEETINGS, "this is not the query that finds meetings"


def test_every_global_the_module_reads_is_bound() -> None:
    """THE GENERAL FORM. A gather is a lambda inside a `try`, so an unbound name in one is invisible
    until a sweep runs it — and then it is a log line, not a failure.

    SCANNED OVER THE WHOLE MODULE, not one function. The first cut of this test inspected
    `refresh_state_situations` and the gather block lives in `_gather`, so it walked the wrong
    tree and passed against the very defect it was written for. Checking every module-level
    function means moving the code cannot silently move it out of scope again.
    """
    import builtins

    from genios_engine.context import outreach_situations

    tree = ast.parse(inspect.getsource(outreach_situations))
    module_names = set(vars(outreach_situations)) | set(dir(builtins))

    def _locally_bound(fn) -> set[str]:
        """Everything this function binds for itself: parameters, assignments, imports,
        comprehension targets, except-handlers, and any nested def or lambda's parameters."""
        names: set[str] = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                names.add(node.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    names.add(alias.asname or alias.name.split(".")[0])
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # ClassDef included: `support_situations._internal_emails` defines a `_Shim` class
                # inside itself, and omitting it reported that as an unbound global.
                names.add(node.name)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                args = node.args
                names.update(a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs))
                if args.vararg:
                    names.add(args.vararg.arg)
                if args.kwarg:
                    names.add(args.kwarg.arg)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                names.add(node.name)
            elif isinstance(node, ast.Global):
                names.update(node.names)
        return names

    offenders: dict[str, list[str]] = {}
    for fn in [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        bound = module_names | _locally_bound(fn)
        used = {n.id for n in ast.walk(fn)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        missing = sorted(n for n in used - bound if not n.startswith("__"))
        if missing:
            offenders[fn.name] = missing

    assert offenders == {}, (
        f"these names are read and bound nowhere: {offenders}. Each raises NameError the moment "
        f"the line runs; inside a gather that is swallowed by `_optional` and silently empties "
        f"the reading it feeds")


def test_the_meeting_reading_is_still_registered() -> None:
    """A lane that cannot fire and a lane nobody dispatches look identical from the card side."""
    from genios_engine.context.outreach_situations import ANCHOR_MEETING, READINGS

    assert ANCHOR_MEETING in {anchor for anchor, _ in READINGS}
