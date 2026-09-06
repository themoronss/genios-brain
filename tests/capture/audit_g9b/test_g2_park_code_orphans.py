"""G2 DEFECT · park codes the gate emits that NO drain path claims.

`capture/parked/drain.py`'s own docstring states the rule and the consequence:

    EVERY ``DOC-*`` code `gate/rules.py::content_integrity_rule` can return must appear here or
    in `RE_ADJUDICABLE` … A code in neither set is worse than an unhandled one: `drain_parked`
    counts it into ``by_reason`` and then walks past it, `parked_aging` labels it ``"terminal"``
    — a claim nobody made …

The rule was enforced for ``DOC-*`` only, by a test
(`tests/capture/parked/test_park_code_coverage.py`) that drives `content_integrity_rule` with
every `DocumentStatus`. `content_integrity_rule` has a branch that no `DocumentStatus` reaches —
``MUT-01``, the versionless-mutable park — and `gate/gate.py` parks under two more codes of its
own, ``visibility_unknown`` (S0.6) and ``mapping_missing`` (S1.5). Only the last of those is
claimed.

So the enumeration here is driven from the PARK SITES, not from `content_integrity_rule`: every
`reason_code=` that accompanies a `"park"` anywhere in `capture/gate/`.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.gate import gate as GATE_MODULE
from genios_engine.capture.gate import rules as RULES_MODULE
from genios_engine.capture.parked.drain import (NEEDS_REFETCH, RE_ADJUDICABLE, STALE_AFTER,
                                                parked_aging)

NOW = datetime(2026, 3, 11, 10, 30, tzinfo=timezone.utc)


def park_codes_from_the_gate() -> frozenset[str]:
    """Every reason code the gate can PARK under, read out of the gate's own source.

    Two syntactic shapes carry a park in this package and both are matched:

    * ``trace.record(stage, "park", reason_code="X")`` / ``GateResult(action="park",
      reason_code="X")`` — a keyword `reason_code` in a call whose arguments also contain the
      literal ``"park"``;
    * ``return ("X", "park")`` — the `(code, action)` tuple `content_integrity_rule` returns.

    Source-driven rather than listed, for the reason the drain gives: a list is a second place
    to forget, and forgetting is the entire defect.
    """
    found: set[str] = set()
    for module in (GATE_MODULE, RULES_MODULE):
        tree = ast.parse(inspect.getsource(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                literals = {a.value for a in node.args
                            if isinstance(a, ast.Constant) and isinstance(a.value, str)}
                literals |= {k.value.value for k in node.keywords
                             if isinstance(k.value, ast.Constant)
                             and isinstance(k.value.value, str)}
                if "park" not in literals:
                    continue
                for kw in node.keywords:
                    if kw.arg == "reason_code" and isinstance(kw.value, ast.Constant):
                        found.add(str(kw.value.value))
            elif isinstance(node, ast.Tuple) and len(node.elts) == 2:
                code, action = node.elts
                if (isinstance(code, ast.Constant) and isinstance(code.value, str)
                        and isinstance(action, ast.Constant) and action.value == "park"):
                    found.add(code.value)
    return frozenset(found)


def test_the_enumeration_finds_the_park_sites_this_file_is_about():
    """Guard on the guard: if the AST walk found nothing, the orphan test below is vacuous."""
    codes = park_codes_from_the_gate()
    assert len(codes) >= 10, sorted(codes)
    for expected in ("MUT-01", "visibility_unknown", "mapping_missing", "DOC-05",
                     "llm_junk_unconfident", "low_relevance"):
        assert expected in codes, f"{expected} is a park site the enumeration missed: {sorted(codes)}"


def test_every_park_code_the_gate_emits_is_claimed_by_exactly_one_drain_path():
    """THE GATE CRITERION. A code in neither set sits at `status='pending'` forever while every
    surface that could show it reads clean."""
    codes = park_codes_from_the_gate()
    orphans = sorted(c for c in codes
                     if c not in NEEDS_REFETCH and c not in RE_ADJUDICABLE
                     and c not in _third_class())
    assert not orphans, (
        "park codes no drain path claims — drain_parked walks past them, parked_aging calls "
        f"them 'terminal', and no G2 count can see them: {orphans}")


def test_no_park_code_is_claimed_by_two_paths():
    classes = (NEEDS_REFETCH, RE_ADJUDICABLE, _third_class())
    for code in park_codes_from_the_gate():
        owners = [i for i, s in enumerate(classes) if code in s]
        assert len(owners) <= 1, f"{code} is claimed by drain classes {owners}"


def _third_class() -> frozenset[str]:
    """The class for parks that only a re-derivation or a later capture can settle.

    Read through `getattr` so this probe records the state it was WRITTEN against: before the fix
    the module did not exist and the set was empty, which is how the orphan list was produced.
    """
    try:
        from genios_engine.capture.parked import recapture
    except ImportError:                     # noqa: BLE001 — the pre-fix state, kept observable
        return frozenset()
    return getattr(recapture, "NEEDS_RECAPTURE", frozenset())


# -- the observable damage, on the real surfaces ----------------------------------------------

class _FakeRows:
    def __init__(self, rows) -> None:
        self._rows = rows

    def fetchall(self):
        return self._rows

    def all(self):
        return self._rows


class _Row:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class _FakeConn:
    def __init__(self, rows) -> None:
        self._rows = rows

    def execute(self, *_a, **_k):
        return _FakeRows(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _FakeEngine:
    def __init__(self, rows) -> None:
        self._rows = rows

    def connect(self):
        return _FakeConn(self._rows)

    def begin(self):
        return _FakeConn(self._rows)


@pytest.mark.parametrize("code", ["MUT-01", "visibility_unknown"])
def test_an_orphan_park_is_not_labelled_terminal_by_the_aging_surface(code):
    """`parked_aging`'s `class` column is what an operator alarms on. `terminal` means "stop
    looking" — and nobody ever decided that about these."""
    rows = [_Row(reason_code=code, status="pending", refetch_failure_kind=None, n=7,
                 oldest=NOW - STALE_AFTER - timedelta(days=1))]
    aging = parked_aging(_FakeEngine(rows), org_id="org_1", now=NOW)
    assert aging[0]["class"] != "terminal", (
        f"{code} is reported as 'terminal' — a claim nobody made, about 7 events that are "
        "still pending")
