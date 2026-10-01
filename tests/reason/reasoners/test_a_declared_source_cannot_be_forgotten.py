r"""Plane R `S5.U07` · every default source a unit names in a constant is DECLARED.

⛔ WHAT WAS WRONG, AND IT IS NOT WHAT THE PLAN SAID. `ReasonerRegistry.validate_sources()` runs in the
constructor, on **every registration, in every process** — and validated **zero** sources, because all
23 units returned `()` through `declared_source_units`. So this was never "a guard waiting to be
built". It was a guard running continuously with nothing to check.

⛔ AND THE BUG IT PREVENTS HAD ALREADY SHIPPED. `tradeoff_unit.AXIS_SOURCES` carries the receipt:

    "CostVersusBenefitPlugin returned no observation, and this unit has been comparing two axes while
     declaring three since the day it shipped. Nothing failed, because a missing source is
     indistinguishable from a source that did not run, which is exactly the silence a tradeoff is
     supposed to keep."

⛔ WHY THIS TEST IS SOURCE-DERIVED. A test asserting `RiskUnit.source_units == ("core.relationship",
"core.temporal")` passes forever and proves nothing: add `DEFAULT_OWNER_SOURCE`, forget to declare it,
and the test stays green — which is the shape of every guard this programme has had to rewrite. So it
reads each module's own constants out of the AST and demands each one appear in the declaration.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from genios_engine.reason.reasoners import (CORE_UNITS, SUPPLEMENTARY_UNITS, default_registry)
from genios_engine.reason.registry import (SOURCE_UNITS_ATTR, declared_source_units)

REASONERS = pathlib.Path(
    __import__("genios_engine.reason.reasoners", fromlist=["x"]).__file__).parent

ALL_UNITS = CORE_UNITS + SUPPLEMENTARY_UNITS
_UNIT_ID_SHAPE = ("core.", "legacy.")


def _id_of(unit_cls) -> str:
    """The unit's id, from wherever it keeps it.

    ⛔ THE SIX SUPPLEMENTARY UNITS HAVE NO `unit_id` CLASS ATTRIBUTE. They *"predate the framework"*
    — the roster module says so — and identify themselves through `spec.reasoner_id` on an instance.
    A test that reached for `cls.unit_id` failed at collection on exactly that, which is a fact about
    this roster worth having in one helper rather than discovered per assertion.
    """
    declared = getattr(unit_cls, "unit_id", None)
    if declared:
        return str(declared)
    return str(unit_cls().spec.reasoner_id)


def _module_of(unit_cls) -> pathlib.Path:
    return pathlib.Path(__import__(unit_cls.__module__, fromlist=["x"]).__file__)


def _constant_sources(path: pathlib.Path) -> dict[str, str]:
    """Module-level `*_SOURCE` constants whose value looks like a unit id, from the AST.

    ⛔ AST, NOT A GREP, AND THE REASON IS IN THESE FILES. Every one of these constants sits under a
    paragraph of prose that NAMES it and names the unit it points at — `risk.py`'s comment mentions
    `core.temporal` three times before the assignment. A regex over the text matches the explanation.
    Four tests written earlier in this programme failed on exactly that and were rewritten as walks.
    """
    out: dict[str, str] = {}
    for node in ast.parse(path.read_text()).body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        value = getattr(node, "value", None)
        for target in targets:
            if not isinstance(target, ast.Name) or not target.id.endswith("_SOURCE"):
                continue
            if isinstance(value, ast.Constant) and isinstance(value.value, str) \
                    and value.value.startswith(_UNIT_ID_SHAPE):
                out[target.id] = value.value
    return out


def _axis_sources(path: pathlib.Path) -> dict[str, str]:
    """`AXIS_SOURCES` entries, as `{key: unit_id}`, from the AST."""
    out: dict[str, str] = {}
    for node in ast.parse(path.read_text()).body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        if not any(isinstance(t, ast.Name) and t.id == "AXIS_SOURCES" for t in targets):
            continue
        value = getattr(node, "value", None)
        if not isinstance(value, (ast.Tuple, ast.List)):
            continue
        for item in value.elts:
            if isinstance(item, (ast.Tuple, ast.List)) and len(item.elts) >= 2:
                key, unit = item.elts[0], item.elts[1]
                if isinstance(key, ast.Constant) and isinstance(unit, ast.Constant):
                    out[str(key.value)] = str(unit.value)
    return out


# ── the derivation itself ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("unit_cls", ALL_UNITS, ids=_id_of)
def test_every_constant_named_source_is_declared(unit_cls):
    """⛔ THE WHOLE UNIT. A constant naming a unit id is a hard dependency on the roster; if it is not
    in `source_units`, `validate_sources` cannot see it and a rename is silent."""
    path = _module_of(unit_cls)
    named = {**_constant_sources(path), **_axis_sources(path)}
    declared = set(declared_source_units(unit_cls()))
    missing = {name: unit for name, unit in named.items() if unit not in declared}
    assert not missing, (
        f"{_id_of(unit_cls)} names {missing} in a module constant and does not declare it in "
        f"{SOURCE_UNITS_ATTR}. A source the registry cannot see is a source a rename silences — see "
        f"tradeoff_unit.AXIS_SOURCES for the time that already happened.")


def test_the_derivation_finds_something_so_the_check_is_not_vacuous():
    """⛔ A parametrised test over an empty set of constants passes for every unit. This proves the
    AST walk actually resolves values — the trap `situation_admission_reason`'s own tests name."""
    found = {}
    for unit_cls in ALL_UNITS:
        path = _module_of(unit_cls)
        named = {**_constant_sources(path), **_axis_sources(path)}
        if named:
            found[_id_of(unit_cls)] = named
    assert len(found) >= 4, found
    assert "core.tradeoff" in found and len(found["core.tradeoff"]) == 6
    assert "core.risk" in found and len(found["core.risk"]) == 2


def test_the_tradeoff_declaration_is_derived_and_not_retyped():
    """⛔ Six strings typed by hand would leave a seventh axis behind, reproducing the exact defect
    this section exists to end — inside the guard built to prevent it."""
    import inspect

    from genios_engine.reason.reasoners.tradeoff_unit import AXIS_SOURCES, TradeoffUnit

    src = inspect.getsource(TradeoffUnit)
    line = [ln for ln in src.splitlines() if SOURCE_UNITS_ATTR in ln and "=" in ln]
    assert line, "no source_units assignment found"
    assert "AXIS_SOURCES" in line[0], f"retyped rather than derived: {line[0].strip()}"
    assert set(TradeoffUnit.source_units) == {u for _, u, _ in AXIS_SOURCES}


# ── the guard's own invariants ─────────────────────────────────────────────────────────────────

def test_every_declared_source_is_a_registered_unit():
    """`validate_sources` proves this at import; asserting it here makes the failure readable."""
    registry = default_registry()
    known = registry.unit_ids
    for unit_cls in ALL_UNITS:
        for source in declared_source_units(unit_cls()):
            assert source in known, f"{_id_of(unit_cls)} reads unregistered {source}"


def test_no_unit_declares_itself_as_a_source():
    """⛔ `validate_capability_sources` forbids it for a MANIFEST; the class attribute has no such
    check, and a unit reading its own prior metric is a cycle the orchestrator cannot schedule."""
    for unit_cls in ALL_UNITS:
        assert _id_of(unit_cls) not in declared_source_units(unit_cls()), _id_of(unit_cls)


def test_the_supplementary_units_declare_nothing_deliberately():
    """⛔ Zero plugins between the six of them, and no metric reads. Declaring sources they do not
    have would be the opposite of this section — a dependency asserted to satisfy a checklist."""
    for unit_cls in SUPPLEMENTARY_UNITS:
        assert declared_source_units(unit_cls()) == (), _id_of(unit_cls)


def test_the_registry_now_has_something_to_validate():
    """⛔ THE MEASUREMENT THIS SECTION IS FOR. Before it: 23 units, 0 declaring, 0 sources checked on
    every registration. If this count returns to zero, the declarations were deleted and
    `validate_sources` is back to validating nothing while still running."""
    registry = default_registry()
    total = sum(len(v) for v in registry._sources.values())
    assert total >= 10, f"only {total} sources declared across {len(registry._sources)} units"


def test_the_two_manifest_only_units_declare_an_explicit_empty():
    """⛔ `()` and ABSENT are the same value through `getattr` and opposite facts. These two have
    genuinely no default; the declaration is what distinguishes them from the units that simply never
    said."""
    import inspect

    from genios_engine.reason.reasoners.confidence import ConfidenceReasoner
    from genios_engine.reason.reasoners.priority import PriorityReasoner

    for cls in (ConfidenceReasoner, PriorityReasoner):
        assert declared_source_units(cls()) == ()
        assert SOURCE_UNITS_ATTR in inspect.getsource(cls), (
            f"{cls.unit_id} has no default AND does not say so — indistinguishable from a unit that "
            f"was never updated")
