"""Versioned reasoner registry and deterministic DAG planning.

**A DECLARED SOURCE MUST BE A REAL UNIT.** Beyond holding implementations, this module answers one
question the kernel had no answer to: when a unit reads another unit's published metric, does the
unit it names exist? `core.tradeoff` compared three axes and reported two for the whole life of the
roster, because its cost axis read `effort_bp` from `core.effort` — a unit that has never been
written, never registered, and never published anything. Nothing failed. A source that is not
registered is indistinguishable, at read time, from a source that ran and had nothing to say, and
the second is a legitimate silence this engine deliberately protects. So the fault could only ever
be caught where the two are still distinguishable: before the run, against the registry.

Two checks, deliberately separate, because they fail for different reasons and at different times:

    `validate_sources()`            every source a REGISTERED UNIT declares in `source_units` is
                                    itself registered. Runs when a registry is built, so an
                                    implementation that points at a ghost cannot be deployed.
    `validate_capability(...)`      every unit a MANIFEST declares is registered, and every source
                                    a manifest NAMES (`*_source` / `*_reasoner` config) is
                                    registered, declared by that same manifest, and a declared
                                    dependency of the unit that reads it. Runs at plan resolution,
                                    before any unit observes the situation.

The dependency half of that last rule is not pedantry: the orchestrator hands a unit only the
results of the dependencies it declared, so a manifest naming a source it never made visible has
configured a read that cannot happen. That is the same ghost wearing a manifest.
"""

from __future__ import annotations

import heapq
import re
from collections.abc import Iterable, Mapping

from genios_engine.contracts.reasoning import CapabilityManifest, ReasonerSpec

from .protocols import Reasoner

#: Config keys ending in one of these name ANOTHER UNIT whose published metric this unit reads.
#: A suffix rule rather than a list of the fourteen keys in the roster today, because the failure
#: this guards against arrives with the fifteenth: a new axis, a new key, and no reason for anyone
#: to remember to register it here.
SOURCE_KEY_SUFFIXES: tuple[str, ...] = ("_source", "_reasoner")

#: What a unit id looks like — `core.risk`, `legacy.score_gate`. A `*_source` key whose value is
#: not shaped like a unit id (`"crm"`, `"manual"`) is a plain configuration value and is left
#: alone; the check must not seize a key because of its name when its content says otherwise.
_UNIT_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")

#: Optional class attribute a unit may declare: the units it reads metrics from when the manifest
#: names none. `AXIS_SOURCES`-style defaults are a hard dependency on the roster even though no
#: capability ever spells them, and this is where a unit states them so they can be checked.
SOURCE_UNITS_ATTR = "source_units"


class ReasonerRegistryError(ValueError):
    pass


class UnknownReasoner(ReasonerRegistryError):
    pass


class ReasonerDependencyError(ReasonerRegistryError):
    pass


class UnregisteredSourceUnit(ReasonerRegistryError):
    """A unit — or a manifest — reads a metric from a unit that does not exist."""


def named_source_units(spec: ReasonerSpec) -> tuple[tuple[str, str], ...]:
    """The `(config key, unit id)` pairs one spec names as sources, sorted by key."""
    named: list[tuple[str, str]] = []
    for key, value in spec.config.items():
        name = str(key)
        if not name.endswith(SOURCE_KEY_SUFFIXES):
            continue
        if isinstance(value, str) and _UNIT_ID.match(value.strip()):
            named.append((name, value.strip()))
    return tuple(sorted(named))


def declared_source_units(reasoner: Reasoner) -> tuple[str, ...]:
    """The units an IMPLEMENTATION says it reads by default, or `()` when it declares none.

    Read through `getattr` rather than the protocol so a unit written before this attribute
    existed is not a deployment failure — it is simply a unit whose defaults are unchecked, which
    is where every unit was.
    """
    declared = getattr(reasoner, SOURCE_UNITS_ATTR, ()) or ()
    if isinstance(declared, str) or not isinstance(declared, (tuple, list, frozenset, set)):
        raise ReasonerRegistryError(
            f"{reasoner.spec.reasoner_id} declares a non-iterable {SOURCE_UNITS_ATTR}")
    return tuple(sorted({str(item).strip() for item in declared if str(item).strip()}))


def validate_capability_sources(capability: CapabilityManifest) -> None:
    """Refuse a manifest that names a source it does not schedule or does not make visible.

    Pure: no registry, no clock, no IO — so the structural half of the ghost check runs at plan
    time, on the manifest alone, wherever a plan is built.
    """
    declared: Mapping[str, ReasonerSpec] = {
        spec.reasoner_id: spec for spec in capability.reasoners}
    for spec in capability.reasoners:
        for key, source in named_source_units(spec):
            if source == spec.reasoner_id:
                raise UnregisteredSourceUnit(
                    f"capability {capability.capability_id}@{capability.version} names "
                    f"{spec.reasoner_id}.{key}={source}, which is the unit itself")
            if source not in declared:
                raise UnregisteredSourceUnit(
                    f"capability {capability.capability_id}@{capability.version} names "
                    f"{spec.reasoner_id}.{key}={source}, a unit it never declares")
            if source not in spec.dependencies:
                raise UnregisteredSourceUnit(
                    f"capability {capability.capability_id}@{capability.version} names "
                    f"{spec.reasoner_id}.{key}={source} without declaring it a dependency, so "
                    f"{spec.reasoner_id} can never see it")


class ReasonerRegistry:
    def __init__(self, reasoners: Iterable[Reasoner] = ()) -> None:
        self._reasoners: dict[tuple[str, str], Reasoner] = {}
        self._sources: dict[tuple[str, str], tuple[str, ...]] = {}
        for reasoner in reasoners:
            self.register(reasoner)
        # A registry is sealed the moment it is built: every default source its units name must
        # resolve inside it. Late `register()` calls re-run the same check, so the guarantee does
        # not depend on which constructor a caller used.
        self.validate_sources()

    def register(self, reasoner: Reasoner) -> None:
        if not isinstance(reasoner, Reasoner):
            raise TypeError("reasoner does not satisfy the Reasoner protocol")
        key = (reasoner.spec.reasoner_id, reasoner.spec.version)
        held = self._reasoners.get(key)
        if held is not None and held is not reasoner:
            raise ReasonerRegistryError(f"reasoner already registered: {key[0]}@{key[1]}")
        self._reasoners[key] = reasoner
        self._sources[key] = declared_source_units(reasoner)

    @property
    def unit_ids(self) -> frozenset[str]:
        """Every unit id this registry can schedule, version-independent."""
        return frozenset(reasoner_id for reasoner_id, _ in self._reasoners)

    def validate_sources(self) -> None:
        """Every source a registered unit declares by default must itself be registered."""
        known = self.unit_ids
        for (reasoner_id, version), sources in sorted(self._sources.items()):
            for source in sources:
                if source not in known:
                    raise UnregisteredSourceUnit(
                        f"{reasoner_id}@{version} reads {source}, which is not a registered "
                        f"reasoner")

    def validate_capability(self, capability: CapabilityManifest) -> None:
        """Refuse a manifest whose roster or whose named sources this registry cannot supply.

        Every DECLARED unit is checked, not only the ones a selection kept: an unregistered unit
        that this situation happened to drop would otherwise be found by whichever tenant first
        supplied the fact that scheduled it.
        """
        validate_capability_sources(capability)
        known = self.unit_ids
        for spec in capability.reasoners:
            if spec.reasoner_id not in known:
                raise UnknownReasoner(
                    f"capability {capability.capability_id}@{capability.version} declares "
                    f"{spec.reasoner_id}, which is not a registered reasoner")
            for key, source in named_source_units(spec):
                if source not in known:
                    raise UnregisteredSourceUnit(
                        f"capability {capability.capability_id}@{capability.version} names "
                        f"{spec.reasoner_id}.{key}={source}, which is not a registered reasoner")

    def get(self, spec: ReasonerSpec) -> Reasoner:
        key = (spec.reasoner_id, spec.version)
        reasoner = self._reasoners.get(key)
        if reasoner is None:
            raise UnknownReasoner(f"unknown reasoner: {key[0]}@{key[1]}")
        return reasoner

    def ordered(self, specs: Iterable[ReasonerSpec]) -> tuple[Reasoner, ...]:
        plan = self.topological_order(specs)
        return tuple(self.get(spec) for spec in plan)

    @staticmethod
    def topological_order(specs: Iterable[ReasonerSpec]) -> tuple[ReasonerSpec, ...]:
        by_id: dict[str, ReasonerSpec] = {}
        for spec in specs:
            if spec.reasoner_id in by_id:
                raise ReasonerDependencyError(f"duplicate reasoner id: {spec.reasoner_id}")
            by_id[spec.reasoner_id] = spec
        indegree = {reasoner_id: 0 for reasoner_id in by_id}
        children: dict[str, set[str]] = {reasoner_id: set() for reasoner_id in by_id}
        for spec in by_id.values():
            for dependency in spec.dependencies:
                if dependency not in by_id:
                    raise ReasonerDependencyError(
                        f"{spec.reasoner_id} depends on missing reasoner {dependency}")
                if spec.reasoner_id == dependency:
                    raise ReasonerDependencyError(f"self dependency: {spec.reasoner_id}")
                if spec.reasoner_id not in children[dependency]:
                    children[dependency].add(spec.reasoner_id)
                    indegree[spec.reasoner_id] += 1
        ready = [reasoner_id for reasoner_id, degree in indegree.items() if degree == 0]
        heapq.heapify(ready)
        ordered: list[ReasonerSpec] = []
        while ready:
            reasoner_id = heapq.heappop(ready)
            ordered.append(by_id[reasoner_id])
            for child in sorted(children[reasoner_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    heapq.heappush(ready, child)
        if len(ordered) != len(by_id):
            cyclic = sorted(reasoner_id for reasoner_id, degree in indegree.items() if degree > 0)
            raise ReasonerDependencyError("reasoner dependency cycle: " + ", ".join(cyclic))
        return tuple(ordered)


__all__ = ["SOURCE_KEY_SUFFIXES", "SOURCE_UNITS_ATTR", "ReasonerDependencyError",
           "ReasonerRegistry", "ReasonerRegistryError", "UnknownReasoner",
           "UnregisteredSourceUnit", "declared_source_units", "named_source_units",
           "validate_capability_sources"]
