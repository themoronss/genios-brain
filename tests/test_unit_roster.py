"""Executable contract for the Layer 4 unit roster as a whole.

Individual unit tests prove each unit works. These prove the *roster* holds together — the
properties that only break when units are built independently and then meet for the first time.
"""

from __future__ import annotations

import pytest

from genios_engine.reason.decision_maker import CONFIDENCE_AUTHORITY, PRIORITY_AUTHORITY
from genios_engine.reason.protocols import Reasoner
from genios_engine.reason.reasoners import (
    BUSINESS_EVALUATION,
    CORE_UNITS,
    DECISION_SUPPORT,
    OPTIMIZATION,
    SITUATION_UNDERSTANDING,
    SUPPLEMENTARY_UNITS,
    default_registry,
)
from genios_engine.reason.unit import ReasoningUnit, UnitCategory

ALL_UNITS = CORE_UNITS + SUPPLEMENTARY_UNITS

#: Metrics the Decision Maker resolves through a named authority. Exactly one unit may publish
#: each, or the winner becomes "whichever ran last".
RESERVED = ("confidence_bp", "urgency_bp", "priority_override_bp")


def _instances():
    return [unit() for unit in ALL_UNITS]


def test_the_roster_covers_all_four_categories():
    assert len(SITUATION_UNDERSTANDING) == 4
    assert len(BUSINESS_EVALUATION) == 5
    assert len(OPTIMIZATION) == 5
    assert len(DECISION_SUPPORT) == 3
    assert len(CORE_UNITS) == 17


@pytest.mark.parametrize("unit", ALL_UNITS, ids=lambda u: u.__name__)
def test_every_unit_satisfies_the_reasoner_protocol(unit):
    """The orchestrator resolves implementations up front; a unit that cannot be called is a
    failed deployment, so this is checked for the whole roster rather than per unit."""
    assert isinstance(unit(), Reasoner)


@pytest.mark.parametrize("unit", ALL_UNITS, ids=lambda u: u.__name__)
def test_every_unit_declares_an_identity(unit):
    instance = unit()
    assert instance.spec.reasoner_id
    assert instance.spec.version
    assert instance.spec.reasoner_id.startswith(("core.", "legacy."))


def test_every_unit_id_is_unique():
    ids = [unit().spec.reasoner_id for unit in ALL_UNITS]

    assert len(ids) == len(set(ids))


def test_the_registry_accepts_the_whole_roster():
    """Registration is where duplicate ids and protocol violations surface together."""
    registry = default_registry()

    for unit in ALL_UNITS:
        assert registry.get(unit().spec) is not None


@pytest.mark.parametrize("unit", [u for u in ALL_UNITS if issubclass(u, ReasoningUnit)],
                         ids=lambda u: u.__name__)
def test_framework_units_declare_a_category_and_plugins(unit):
    instance = unit()

    assert isinstance(instance.category, UnitCategory)
    assert instance.plugins, "a unit with no plugins is a monolith wearing the framework"
    assert instance.publishes, "a unit must declare what it publishes"


def test_no_unit_publishes_a_metric_another_unit_owns():
    """Two publishers of one metric name is the ambiguity the authority rule exists to remove —
    and the Validation unit would report the overlap as a contradiction in the reasoning."""
    published: dict[str, list[str]] = {}
    for instance in _instances():
        for name in getattr(instance, "publishes", ()):
            published.setdefault(name, []).append(instance.spec.reasoner_id)

    collisions = {name: owners for name, owners in published.items() if len(owners) > 1}

    assert not collisions, f"metric published by more than one unit: {collisions}"


@pytest.mark.parametrize("metric", RESERVED)
def test_only_the_named_authority_publishes_a_shared_decision_metric(metric):
    """A unit that published confidence_bp or urgency_bp would silently re-score every decision
    in the system the day it was added to a capability."""
    authorities = {"confidence_bp": CONFIDENCE_AUTHORITY,
                   "urgency_bp": PRIORITY_AUTHORITY,
                   "priority_override_bp": PRIORITY_AUTHORITY}
    offenders = [instance.spec.reasoner_id for instance in _instances()
                 if metric in getattr(instance, "publishes", ())
                 and instance.spec.reasoner_id != authorities[metric]]

    assert not offenders, f"{metric} may only be published by {authorities[metric]}: {offenders}"


@pytest.mark.parametrize("unit", [u for u in ALL_UNITS if issubclass(u, ReasoningUnit)],
                         ids=lambda u: u.__name__)
def test_plugin_ids_are_unique_within_a_unit(unit):
    ids = [plugin.plugin_id for plugin in unit().plugins]

    assert len(ids) == len(set(ids))


def test_no_unit_reaches_for_a_clock_or_a_database():
    """Determinism is only as strong as the least pure unit in the plan, so this is asserted
    across the roster rather than trusted per author."""
    import inspect

    banned = ("datetime.now", "time.time", "time.monotonic", "random.", "os.environ",
              "requests.", "sqlalchemy", "openai", "anthropic")
    offenders = []
    for unit in ALL_UNITS:
        source = inspect.getsource(inspect.getmodule(unit))
        for token in banned:
            if token in source:
                offenders.append(f"{unit.__name__}: {token}")

    assert not offenders, "\n".join(offenders)
