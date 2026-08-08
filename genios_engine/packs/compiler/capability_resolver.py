"""Business Situation -> domain situations -> capability plan."""

from __future__ import annotations

from collections.abc import Mapping

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    SituationContextSlice,
)

from .authoring import ExpertBrainCatalog
from .context_adapter import ContextAdapter, PredicateState
from .errors import (
    AuthoringIntegrityError,
    NoExpertiseRoute,
    SituationContextIncomplete,
)
from .models import RoutePlan


def _load_set(manifest: dict) -> tuple[set[str], set[str]]:
    required: set[str] = set()
    optional: set[str] = set()
    for bucket in ("core", "scoped"):
        block = manifest.get(bucket) or {}
        required.update(block.get("required") or ())
        optional.update(block.get("optional") or ())
    optional -= required
    return required, optional


class CapabilityResolver:
    """Uses the generated reverse index, then narrows it with authored situation predicates."""

    def __init__(self, catalog: ExpertBrainCatalog, *, max_capabilities: int = 64,
                 max_objects: int = 128) -> None:
        self.catalog = catalog
        self.max_capabilities = max_capabilities
        self.max_objects = max_objects

    def resolve(self, situation: BusinessSituationObject,
                context: SituationContextSlice | None = None) -> RoutePlan:
        hints = set(situation.domain_hints)
        unknown_hints = hints - set(self.catalog.domains)
        if unknown_hints:
            raise NoExpertiseRoute(
                f"situation {situation.id!r} names unknown domains {sorted(unknown_hints)}")
        domain_ids = sorted(hints or self.catalog.domains.keys())
        adapter = ContextAdapter(situation, context)
        selected_domains: set[str] = set()
        situation_ids: set[str] = set()
        capability_ids: set[str] = set()
        required: set[str] = set()
        optional: set[str] = set()
        never: set[str] = set()
        unresolved: set[str] = set()
        skipped_capabilities: set[str] = set()
        saw_index_route = False

        for domain_id in domain_ids:
            domain = self.catalog.domain(domain_id)
            route = domain.routes.get(situation.type)
            if not isinstance(route, Mapping):
                continue
            saw_index_route = True
            selected_here: list[str] = []
            for situation_id in route.get("situations") or ():
                source = domain.situations.get(situation_id)
                if source is None:
                    raise AuthoringIntegrityError(
                        f"registry route references missing situation {situation_id!r}")
                matches = source.content.get("matches") or {}
                conditions = matches.get("when") or ()
                verdict = adapter.matches(conditions)
                if verdict.state is PredicateState.TRUE:
                    selected_here.append(situation_id)
                elif verdict.state is PredicateState.UNKNOWN:
                    unresolved.update(f"{situation_id}:{item}" for item in verdict.missing)

            if not selected_here:
                continue
            selected_domains.add(domain_id)
            situation_ids.update(selected_here)
            local_capabilities: set[str] = set()
            for situation_id in selected_here:
                authored = domain.situations[situation_id].content
                owner = (authored.get("identity") or {}).get("owner_capability")
                serving = ([owner] if owner else []) + list(authored.get("also_serves") or ())
                local_capabilities.update(value for value in serving if value)
                objects = authored.get("objects") or {}
                required.update(objects.get("load") or ())
                optional.update(objects.get("optional") or ())
                never.update(objects.get("never_load") or ())

            for capability_id in tuple(local_capabilities):
                capability = domain.capabilities.get(capability_id)
                if capability is None:
                    raise AuthoringIntegrityError(
                        f"routed capability {capability_id!r} is not authored")
                if (capability.content.get("identity") or {}).get("stub"):
                    local_capabilities.remove(capability_id)
                    skipped_capabilities.add(capability_id)
                    continue
                manifest = domain.object_manifests[capability_id].content
                manifest_required, manifest_optional = _load_set(dict(manifest))
                required.update(manifest_required)
                optional.update(manifest_optional)
                never.update(manifest.get("never_load") or ())

            capability_ids.update(local_capabilities)

            generated_caps = set(route.get("capabilities") or ())
            if not local_capabilities <= generated_caps:
                stale = sorted(local_capabilities - generated_caps)
                raise AuthoringIntegrityError(
                    f"generated registry is stale for {domain_id}:{situation.type}; "
                    f"missing capabilities {stale}")

        if not selected_domains:
            if unresolved:
                raise SituationContextIncomplete(
                    f"situation {situation.id!r} cannot resolve authored routes; missing "
                    f"{sorted(unresolved)}")
            if saw_index_route:
                raise NoExpertiseRoute(
                    f"situation {situation.id!r} matched the type index but no authored "
                    "situation predicate")
            scope = f" in domains {domain_ids}" if hints else ""
            raise NoExpertiseRoute(
                f"no expertise route for situation type {situation.type!r}{scope}")

        required -= never
        optional -= never | required
        if not required:
            raise AuthoringIntegrityError("an expertise route resolved no required objects")
        if not capability_ids:
            raise AuthoringIntegrityError(
                f"all routed capabilities are incomplete stubs: {sorted(skipped_capabilities)}")
        if len(capability_ids) > self.max_capabilities:
            raise AuthoringIntegrityError(
                f"route expands to {len(capability_ids)} capabilities; limit is "
                f"{self.max_capabilities}")
        if len(required | optional) > self.max_objects:
            raise AuthoringIntegrityError(
                f"route expands to {len(required | optional)} objects; limit is "
                f"{self.max_objects}")

        return RoutePlan(
            domain_ids=tuple(sorted(selected_domains)),
            situation_ids=tuple(sorted(situation_ids)),
            capability_ids=tuple(sorted(capability_ids)),
            required_object_ids=tuple(sorted(required)),
            optional_object_ids=tuple(sorted(optional)),
            never_object_ids=tuple(sorted(never)),
            unresolved_predicates=tuple(sorted(unresolved)),
            skipped_capability_ids=tuple(sorted(skipped_capabilities)),
        )


__all__ = ["CapabilityResolver"]
