"""Law 5 — no domain vocabulary in a core reasoning unit — made executable.

Two different defects live here, and they are the same defect.

**Vocabulary.** `core.opportunity` decided for itself that `open`, `active`, `in_progress` and
`negotiation` are the words that mean a piece of work is still winnable, and that the fact holding
the state is called `deal.status`. That is one vertical's schema compiled into a unit every
vertical runs. The readings move to the L3 manifest; the unit keeps the shape.

**Ghost sources.** `core.tradeoff` defaulted its cost axis to `core.effort` — a unit that has
never existed. `_prior_bp` cannot tell an unregistered unit from one that did not run, so the axis
returned nothing, forever, and the unit reported `axis_count: 2` while declaring three axes. The
scan below is the general cure: every `core.*` identifier written anywhere in the unit sources has
to name a unit the registry actually holds.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import genios_engine.reason.reasoners as reasoners_package
from genios_engine.reason.reasoners import CORE_UNITS, SUPPLEMENTARY_UNITS

#: Resolved from the imported package rather than from the working directory: a source scan that
#: silently scanned nothing would pass every assertion in this file.
UNIT_SOURCE_DIR = pathlib.Path(reasoners_package.__file__).resolve().parent

#: The vocabulary Globe names when it describes this drift. Underscores are treated as separators
#: so `deal_momentum_risk` is a hit, while `ideal` and `dealt` are not — the point is to catch the
#: word wherever an identifier is built out of it, not to ban a substring.
DOMAIN_TOKENS = re.compile(r"(?<![A-Za-z])(deal|champion|pipeline|ticket)s?(?![A-Za-z])", re.I)

#: The units this wave purged. Zero domain tokens, with exactly one pinned exception.
PURGED = ("opportunity.py", "risk.py", "resource_unit.py")

#: The ONE domain token allowed to survive the purge, and why. `core.risk` is one of the six units
#: that has actually been running, so this exact string is already in audit rows and in the reasons
#: attached to shipped signals; renaming it would orphan them to purify a spelling. Pinned as a
#: whole line so it cannot be joined by a second exception without this list changing.
FROZEN_LINES = {
    "risk.py": ('RISK_REASON_CODE = "deal_momentum_risk"',),
}

#: Units NOT in this wave's scope, with the number of domain-token lines each carries today. The
#: numbers are a RATCHET: a later wave may drive one to zero, and nothing may raise one. It is
#: also the honest inventory — Law 5 is not satisfied across the roster yet, and a test that only
#: looked at the three units this wave touched would let the next author believe it was.
DOMAIN_DEBT = {
    "alternative_unit.py": 1, "context_unit.py": 2, "cost_unit.py": 1, "dependency_unit.py": 4,
    "impact_unit.py": 12, "policy_unit.py": 4, "priority.py": 2, "recommendation_unit.py": 1,
    "relationship.py": 5, "scheduling_unit.py": 3, "timeline_unit.py": 9, "validation_unit.py": 1,
}

REGISTERED_IDS = frozenset(unit().spec.reasoner_id
                           for unit in CORE_UNITS + SUPPLEMENTARY_UNITS)


def _sources() -> dict[str, str]:
    return {path.name: path.read_text()
            for path in sorted(UNIT_SOURCE_DIR.glob("*.py"))}


def _domain_lines(source: str, allowed: tuple[str, ...] = ()) -> list[str]:
    return [line.strip() for line in source.splitlines()
            if DOMAIN_TOKENS.search(line) and line.strip() not in allowed]


@pytest.mark.parametrize("filename", PURGED)
def test_a_purged_unit_carries_no_domain_vocabulary(filename):
    """The reading moved to the manifest. If a token comes back, the reading came back with it."""
    leaked = _domain_lines(_sources()[filename], FROZEN_LINES.get(filename, ()))

    assert not leaked, f"{filename} names a domain again:\n  " + "\n  ".join(leaked)


def test_the_frozen_exception_is_exactly_one_line_and_still_there():
    """An allowlist nobody checks becomes the place vocabulary hides. This one is pinned to its
    exact text, so widening it is an edit to this test and therefore a decision somebody made."""
    source = _sources()["risk.py"]

    assert 'RISK_REASON_CODE = "deal_momentum_risk"' in source
    assert sum(1 for line in source.splitlines() if DOMAIN_TOKENS.search(line)) == 1


@pytest.mark.parametrize("filename", sorted(DOMAIN_DEBT))
def test_the_unpurged_units_never_take_on_more_domain_vocabulary(filename):
    """A ratchet, not a pass. These counts may fall; a rise is new drift on a unit this wave
    deliberately left alone, and it must not arrive unremarked."""
    count = len(_domain_lines(_sources()[filename]))

    assert count <= DOMAIN_DEBT[filename], (
        f"{filename} gained domain vocabulary: {count} lines, ratchet is {DOMAIN_DEBT[filename]}")


def test_the_debt_inventory_names_every_unit_that_actually_carries_debt():
    """The inventory has to be the real one. A unit that quietly acquires domain vocabulary while
    absent from both lists would satisfy every other test in this file."""
    carrying = {name for name, source in _sources().items()
                if _domain_lines(source, FROZEN_LINES.get(name, ()))}

    assert carrying - set(DOMAIN_DEBT) - set(PURGED) == set()
    assert set(DOMAIN_DEBT) <= carrying, (
        f"debt recorded for units that no longer carry any: {set(DOMAIN_DEBT) - carrying}")


def test_every_unit_a_default_names_is_a_unit_that_exists():
    """The `core.effort` class of bug, closed by enumeration.

    Every `core.*` string constant in the unit sources is either the unit's own id or a default
    source it reads a prior metric from. Both have to resolve. A default that names nothing is
    indistinguishable at runtime from a dependency that did not run, which is why this one hid for
    the entire life of `core.tradeoff`.
    """
    unknown: dict[str, set[str]] = {}
    for name, source in _sources().items():
        named = {node.value for node in ast.walk(ast.parse(source))
                 if isinstance(node, ast.Constant) and isinstance(node.value, str)
                 and re.fullmatch(r"core\.[a-z_]+", node.value)}
        missing = named - REGISTERED_IDS
        if missing:
            unknown[name] = missing

    assert not unknown, f"unit sources name unregistered reasoners: {unknown}"


def test_the_scan_would_have_caught_the_ghost():
    """Proof the check above is load-bearing rather than vacuous: the exact string that shipped
    for the life of `core.tradeoff` is still not a unit, and the scan's own predicate says so."""
    assert "core.effort" not in REGISTERED_IDS
    assert re.fullmatch(r"core\.[a-z_]+", "core.effort")
