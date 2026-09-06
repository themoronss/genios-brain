"""L1.1-U1 · the RATCHET — which capture doors exist, and which of them declare coverage.

The gate criterion is *every swept event carries a non-null `coverage_ready`*. Wiring the known
doors satisfies it today; nothing about wiring them stops a sixth door from being added tomorrow
without the injection, which is exactly how the first five got there. A guard that cannot observe
a door is not a guard, so this module observes them — by reading the source tree, not by trusting
a hand-maintained list of names.

**Why a source scan and not a required parameter.** Making `coverage_fn` a parameter with no
default on `capture_event` is the obvious answer and it is not sufficient, because the hole that
was actually found is one level up. `capture/intake.py` DOES pass `coverage_fn=` — it passes its
own parameter, which defaults to `None`, and both of its HTTP callers passed nothing. A required
parameter on `capture_event` would have been satisfied, in full, by the code that produced the
nulls. Forwarding is what defeats it: every door in this system is a forwarder, so the property
that has to hold is transitive, and only something that follows the forwarding can check it.

**How a door is found.** Start from `capture_event` and close over forwarding:

    a function is a DOOR when it calls a door and hands it coverage from its OWN signature —
    either `coverage_fn=coverage_fn` (its own parameter) or `**kw` (its own kwargs).

That definition is what makes the ratchet immune to naming: a seventh door called
`ingest_whatever` is discovered because of what it does, never because someone remembered to add
its name here. `ingest_human_event` and `ingest_agent_event` are the proof — they were doors from
the day they were written, the hand-listed scan did not name them, and both of their callers
emitted `coverage_ready=None` for the whole time the metric read clean.

**How a call site is judged.** A site DECLARES coverage when it passes `coverage_fn=<something
that is not the literal None>`, or `**kw` where `kw` is the enclosing function's own kwargs — and
that second case is not a loophole, because passing your kwargs through is precisely what makes
the enclosing function a door whose own call sites this module then judges by the same rule.
"""

from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass
from typing import Iterable, Sequence

#: The root of the forwarding closure. Every capture entry in the system reaches `source_events`
#: through it, so a door that does not (transitively) call it is not a capture door at all.
SEED = "capture_event"

#: The injected parameter, by name. One spelling, used by the pipeline, the doors and this scan.
COVERAGE_PARAM = "coverage_fn"


@dataclass(frozen=True)
class CaptureSite:
    """One call to a capture door, and whether it declares coverage."""

    path: str
    line: int
    callee: str
    declared: bool
    reason: str

    def __str__(self) -> str:            # what a failing gate prints
        return f"{self.path}:{self.line} {self.callee}() — {self.reason}"


@dataclass(frozen=True)
class CaptureDoorAudit:
    """Every capture door in the scanned tree, every call to one, and the undeclared subset."""

    doors: tuple[str, ...]
    sites: tuple[CaptureSite, ...]

    @property
    def undeclared(self) -> tuple[CaptureSite, ...]:
        return tuple(s for s in self.sites if not s.declared)


@dataclass(frozen=True)
class _Func:
    """A function definition, reduced to the two things that let it forward coverage."""

    path: str
    name: str
    line: int
    has_coverage_param: bool
    kwargs_name: str | None


@dataclass(frozen=True)
class _Call:
    """A call, with the chain of functions it is written inside (innermost last)."""

    path: str
    line: int
    callee: str | None
    node: ast.Call
    enclosing: tuple[_Func, ...]


class _Collector(ast.NodeVisitor):
    """Walks one module, recording function definitions and calls with their enclosing chain."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.funcs: list[_Func] = []
        self.calls: list[_Call] = []
        self._stack: list[_Func] = []

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        args = node.args
        named = {a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)}
        func = _Func(path=self.path, name=node.name, line=node.lineno,
                     has_coverage_param=COVERAGE_PARAM in named,
                     kwargs_name=args.kwarg.arg if args.kwarg else None)
        self.funcs.append(func)
        self._stack.append(func)
        self.generic_visit(node)
        self._stack.pop()

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def visit_Call(self, node: ast.Call) -> None:
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
        self.calls.append(_Call(path=self.path, line=node.lineno, callee=name, node=node,
                                enclosing=tuple(self._stack)))
        self.generic_visit(node)


def _python_files(roots: Iterable[pathlib.Path]) -> list[pathlib.Path]:
    out: list[pathlib.Path] = []
    for root in roots:
        root = pathlib.Path(root)
        if root.is_file():
            out.append(root)
            continue
        out.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(set(out))


def _forwards_own_coverage(call: _Call, func: _Func) -> bool:
    """Does this call hand `func`'s OWN coverage down — by parameter or by kwargs splat?"""
    for kw in call.node.keywords:
        if kw.arg is None:                                   # **something
            if func.kwargs_name is not None and _splat_name(kw.value) == func.kwargs_name:
                return True
        elif kw.arg == COVERAGE_PARAM and func.has_coverage_param:
            if isinstance(kw.value, ast.Name) and kw.value.id == COVERAGE_PARAM:
                return True
    return False


def _splat_name(node: ast.expr) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _declaration_reason(call: _Call) -> tuple[bool, str]:
    """Judge ONE call site. Returns (declares coverage, why) — the 'why' is the gate's message."""
    for kw in call.node.keywords:
        if kw.arg == COVERAGE_PARAM:
            if isinstance(kw.value, ast.Constant) and kw.value.value is None:
                # `coverage_fn=None` is spelled-out omission, and it is what the intake doors
                # defaulted to. Reading it as a declaration is how the metric stayed clean.
                return False, "passes coverage_fn=None, which is an omission with a keyword on it"
            return True, "declares coverage_fn"
        if kw.arg is None:
            splat = _splat_name(kw.value)
            if splat is not None and any(f.kwargs_name == splat for f in call.enclosing):
                return True, f"forwards its own **{splat}"
    return False, "passes no coverage_fn — every event it emits carries coverage_ready=None"


def audit_capture_doors(roots: Sequence[pathlib.Path | str], *,
                        seed: str = SEED) -> CaptureDoorAudit:
    """Every capture door reachable from `seed` in these trees, and every call to one.

    Pure: it reads source text and returns a value. No import of the code under audit, so a
    module with a heavy import side effect (the API package builds stores at import time) is
    scanned without being executed.
    """
    funcs: list[_Func] = []
    calls: list[_Call] = []
    for path in _python_files(pathlib.Path(r) for r in roots):
        text = path.read_text(encoding="utf-8")
        collector = _Collector(str(path))
        collector.visit(ast.parse(text, filename=str(path)))
        funcs.extend(collector.funcs)
        calls.extend(collector.calls)

    doors = {seed}
    changed = True
    while changed:                     # transitive closure over forwarding; terminates on a
        changed = False                # finite set of function names
        for call in calls:
            if call.callee not in doors:
                continue
            for func in call.enclosing:
                if func.name in doors:
                    continue
                if _forwards_own_coverage(call, func):
                    doors.add(func.name)
                    changed = True

    sites: list[CaptureSite] = []
    for call in calls:
        if call.callee not in doors:
            continue
        declared, reason = _declaration_reason(call)
        sites.append(CaptureSite(path=call.path, line=call.line, callee=call.callee,
                                 declared=declared, reason=reason))
    sites.sort(key=lambda s: (s.path, s.line))
    return CaptureDoorAudit(doors=tuple(sorted(doors)), sites=tuple(sites))


__all__ = ["COVERAGE_PARAM", "SEED", "CaptureDoorAudit", "CaptureSite", "audit_capture_doors"]
