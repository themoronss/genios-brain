"""The eight Atlas compiler components composed into one deterministic Layer 3 service."""

from __future__ import annotations

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    ExpertisePackage,
    SituationContextSlice,
)

from .authoring import ExpertBrainCatalog
from .brain_resolver import BrainResolver
from .capability_resolver import CapabilityResolver
from .evidence_aggregator import EvidenceAggregator
from .expertise_builder import ExpertiseBuilder
from .expertise_publisher import ExpertisePublisher
from .knowledge_retriever import KnowledgeRetriever
from .object_resolver import ObjectResolver
from .runtime_brains import RuntimeBrains


class DomainCompiler:
    """Resolve, retrieve, bind, evidence, build, and optionally publish. Never decide."""

    def __init__(self, *, catalog: ExpertBrainCatalog, runtime_brains: RuntimeBrains,
                 publisher: ExpertisePublisher | None = None,
                 capability_resolver: CapabilityResolver | None = None,
                 require_admission: bool = True,
                 activated_domains: frozenset[str] | None = None) -> None:
        self.catalog = catalog
        self.capability_resolver = capability_resolver or CapabilityResolver(
            catalog, require_admission=require_admission,
            activated_domains=activated_domains)
        self.object_resolver = ObjectResolver(catalog)
        self.knowledge_retriever = KnowledgeRetriever(catalog)
        self.brain_resolver = BrainResolver(catalog, runtime_brains)
        self.evidence_aggregator = EvidenceAggregator()
        self.builder = ExpertiseBuilder()
        self.publisher = publisher

    def compile(self, situation: BusinessSituationObject,
                context: SituationContextSlice | None = None) -> ExpertisePackage:
        plan = self.capability_resolver.resolve(situation, context)
        objects = self.object_resolver.resolve(plan)
        knowledge = self.knowledge_retriever.retrieve(plan, situation)
        # THE COMPILER'S CLOCK IS THE SLICE'S, OR THERE ISN'T ONE. `SituationContextSlice`
        # already carries the sweep's `evaluation_time` and deliberately keeps it out of its own
        # semantic hash, so reading it here costs the package's content address nothing while
        # giving the Adaptive lease reader the frozen time its TTL has to be judged against.
        # `None` (a caller compiling with no context at all) means no lease is applied — see
        # `PostgresRuntimeBrains.snapshot`; the compiler never reaches for a wall clock.
        eval_time = getattr(context, "evaluation_time", None) if context is not None else None
        expert, runtime, brain_snapshot_id = self.brain_resolver.resolve(
            situation=situation, plan=plan, objects=objects, knowledge=knowledge,
            eval_time=eval_time)
        evidence = self.evidence_aggregator.aggregate(
            situation=situation, expert=expert, runtime=runtime)
        package = self.builder.build(
            situation=situation,
            plan=plan,
            expert=expert,
            runtime=runtime,
            brain_snapshot_id=brain_snapshot_id,
            evidence=evidence,
            context=context,
        )
        return self.publisher.publish(package) if self.publisher is not None else package


__all__ = ["DomainCompiler"]
