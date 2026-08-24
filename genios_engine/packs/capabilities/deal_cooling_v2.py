"""``sales.deal_cooling_full`` — the same expertise, reasoned through the full unit roster.

v1 of this capability names seven units: the four it needs plus the shared scoring trio. That was
correct when seven units existed. Now there are seventeen, and a capability that ignores twelve of
them is not conservative — it is blind in twelve specific ways. It cannot see that the buyer is
waiting on us (Opportunity), that acting today would pre-empt tomorrow's meeting (Scheduling), that
the owner has no capacity (Resource), that its own conclusion rests on uncited claims (Validation),
or that two of its readings contradict each other.

This manifest reuses v1's plays, policies, thresholds, and intelligence objects verbatim — the
domain expertise is unchanged and deliberately so — and rewires only *how it reasons* over them.
It is a separate capability rather than a bump of v1 because the two are meant to run side by side:
v1 is the shipped baseline, this is the candidate, and comparing their decisions on the same
situation is how you find out whether twelve more units actually made the reasoning better.

The DAG follows the four categories in order — understand, evaluate, optimise, support — because
that is a real data dependency, not a taxonomy. You cannot weigh a tradeoff before knowing the risk
and the opportunity, and you cannot validate a conclusion before one exists.
"""

from __future__ import annotations

from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    FailurePolicy,
    ReasonerSpec,
)

from .deal_cooling import (
    CAPABILITY_ID as V1_CAPABILITY_ID,
    PLAY_VERSION,
    REASONER_VERSION,
    _intelligence_objects,
    _plays,
    _reasoners,
    build_deal_cooling_manifest,
)

CAPABILITY_ID = "sales.deal_cooling_full"
CAPABILITY_VERSION = "2.0.0"

#: Units whose judgement is load-bearing: without them the run cannot honestly reach a decision.
#: Everything else is OPTIONAL, so a situation that cannot feed a unit degrades confidence rather
#: than blocking advice the buyer is actively waiting for.
_REQUIRED = {"core.temporal", "core.relationship", "core.risk", "core.constraint",
             "core.priority", "core.confidence", "core.planning", "core.validation"}


def _inherited() -> dict[str, ReasonerSpec]:
    """v1's units, with their authored config intact.

    Re-deriving the thresholds here would create two sources of truth for the same expertise; the
    next person to tune a cadence would fix one and not the other.
    """
    return {spec.reasoner_id: spec for spec in _reasoners()}


def _spec(reasoner_id: str, dependencies: tuple[str, ...] = (), *,
          required_fields: tuple[str, ...] = (), config: dict | None = None,
          latency_budget_ms: int = 60) -> ReasonerSpec:
    """A unit added by v2. Optional by default — see `_REQUIRED`."""
    return ReasonerSpec(
        reasoner_id=reasoner_id,
        version=REASONER_VERSION,
        dependencies=dependencies,
        required_fields=required_fields,
        latency_budget_ms=latency_budget_ms,
        failure_policy=(FailurePolicy.REQUIRED if reasoner_id in _REQUIRED
                        else FailurePolicy.OPTIONAL),
        config=config or {},
    )


def _full_roster() -> tuple[ReasonerSpec, ...]:
    inherited = _inherited()

    # --- Category 1 · Situation Understanding -------------------------------------------------
    understanding = (
        _spec("core.context"),
        _spec("core.timeline", config={
            # A fortnight of silence on a deal that was in active dialogue is the point at which
            # the relationship, not just the thread, has gone quiet.
            "cadence_hours": 336,
        }),
        _spec("core.dependency"),
        inherited["core.temporal"],
        inherited["core.relationship"],
        inherited["core.constraint"],
    )

    # --- Category 2 · Business Evaluation ----------------------------------------------------
    evaluation = (
        inherited["core.risk"],
        _spec("core.opportunity", ("core.temporal",), config={
            # An unanswered buyer is the cheapest opportunity in the system: they already spent
            # the effort, and the whole cost of capture is one considered reply.
            "opportunity_threshold_bp": 2_500,
        }),
        _spec("core.impact", config={
            "play_impact_bp": {"restore_momentum": 400},
        }),
        inherited["core.priority"],
        inherited["core.confidence"],
    )

    # --- Category 3 · Optimization -----------------------------------------------------------
    optimization = (
        _spec("core.resource"),
        _spec("core.scheduling"),
        _spec("core.cost", config={
            # Multithreading costs more than a follow-up: it spends relationship capital that
            # cannot be spent twice, so the effort figure should say so.
            "play_effort_bp": {"multithread_account": 600},
        }),
        _spec("core.policy"),
        _spec("core.tradeoff",
              ("core.risk", "core.opportunity", "core.impact", "core.cost")),
    )

    # --- Category 4 · Decision Support --------------------------------------------------------
    support = (
        _spec("core.alternative", ("core.constraint", "core.cost")),
        _spec("core.validation",
              ("core.risk", "core.opportunity", "core.impact", "core.confidence"),
              config={
                  # A cooling deal is a low-stakes, reversible draft for a human to approve, so
                  # the bar to *consider* it is lower than for an irreversible move. It still
                  # cannot be built on a contradiction.
                  "safety_floor_bp": 3_000,
              }),
        _spec("core.recommendation", ("core.validation", "core.dependency")),
        inherited["core.planning"],
    )

    return understanding + evaluation + optimization + support


def build_deal_cooling_full_manifest() -> CapabilityManifest:
    """v1's expertise, reasoned through every unit of the roster."""
    baseline = build_deal_cooling_manifest()
    return CapabilityManifest(
        capability_id=CAPABILITY_ID,
        version=CAPABILITY_VERSION,
        domain=baseline.domain,
        root_entity_type=baseline.root_entity_type,
        goal=baseline.goal,
        reasoners=_full_roster(),
        plays=_plays(),
        required_fields=baseline.required_fields,
        intelligence_objects=tuple(
            # Intelligence objects are capability-scoped by contract, so they are re-homed rather
            # than shared; the expertise itself is byte-identical to v1's.
            type(item)(
                object_id=item.object_id,
                version=item.version,
                capability_id=CAPABILITY_ID,
                purpose=item.purpose,
                required_context=item.required_context,
                relationships=item.relationships,
                knowledge=item.knowledge,
                metadata=item.metadata,
            ) for item in _intelligence_objects()
        ),
        ranking_weights=baseline.ranking_weights,
        policies=baseline.policies,
        # LOCK 2 (deployment runbook, Part 5): kept shadow-locked. This is the flag the authority
        # predicate reads out of the frozen manifest bytes (`rcap.manifest->'live_delivery_enabled'`),
        # so flipping it to True changes the capability's content address — correct and intended,
        # because a capability that may reach a human is not the same capability as one that may not.
        # Activation (Step 5.2) sets this True only after Steps 1-4 produce shadow evidence.
        live_delivery_enabled=False,
        do_nothing_consequence=baseline.do_nothing_consequence,
        expiry_hours=baseline.expiry_hours,
        metadata={
            **dict(baseline.metadata),
            "activation": "live",
            "supersedes": V1_CAPABILITY_ID,
            "unit_roster": "full",
            # A cooling deal does not become newly cooling every day. Resting a subject for the
            # life of its own decision means the next thing a human hears about this deal is a
            # genuinely new reading, not the same one restated.
            "publication_cooldown_hours": 72,
            # Below this, a winner is a question for a human rather than a recommendation. The
            # floor is what turns Law 03 from a principle into behaviour.
            "confidence_floor_bp": 4_500,
            # Every declared unit costs its budget; refuse the manifest if the roster outgrows
            # what a sweep can afford, instead of discovering it as latency in production.
            "latency_ceiling_ms": 1_500,
        },
    )


DEAL_COOLING_FULL_V2 = build_deal_cooling_full_manifest()

__all__ = ["CAPABILITY_ID", "CAPABILITY_VERSION", "DEAL_COOLING_FULL_V2",
           "build_deal_cooling_full_manifest"]
