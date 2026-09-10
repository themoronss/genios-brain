"""Layer 4 · Part 3 — the Decision Maker.

The orchestrator schedules; the reasoning units analyse; **only this module decides**.  It is the
single point of synthesis in GeniOS: every unit before it emits a typed observation about the
world, and none of them may name a winner.  Keeping that boundary physical — a separate module
with one entry point — is what stops a unit from quietly becoming a second decision authority.

Its shape follows the frozen architecture:

    Evidence Aggregator   → every citation the units stood behind, deduplicated
    Confidence Calculator → one authoritative confidence for the whole decision
    Decision Synthesizer  → declared plays become scored candidates
    Decision Evaluator    → hard checks eliminate candidates *before* anything is ranked
    Decision Ranker       → a total order over the survivors
    Decision Object Builder → one immutable, hashable ReasoningDecision

Two rules hold everywhere below. All arithmetic is integer basis points (0..10,000) with
half-up division, because a float would make the decision hash machine-dependent and destroy
replay.  And every ordering is total — never "whatever order the database returned" — because a
tie broken by iteration order is a decision that cannot be reproduced.

No language model participates here.  Under the confidence floor this module widens uncertainty
and lets the executive layer ask a human; it never invents the missing fact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Any

from genios_engine.capture.validate.confidence import ConfidenceViolation
from genios_engine.contracts.reasoning import (
    CONFIDENCE_VECTOR_KEYS,
    COST_COMPONENTS,
    FORMULA_UTILITY_COMPONENT,
    RANKING_WEIGHTS_V2_SCALE,
    RANKING_WEIGHTS_V2_VERSION,
    UTILITY_COMPONENTS,
    CandidateAdjustment,
    CandidateCheck,
    CandidateDisposition,
    CheckOutcome,
    DecisionCandidate,
    DecisionOutcome,
    ReasonerResult,
    ReasoningDecision,
    ResultStatus,
)
from genios_engine.platform.canonical import semantic_hash

from .protocols import OrchestrationError
from .reasoners.common import clamp_bp, divide_half_up

DECISION_MAKER_VERSION = "1.0.0"

#: Reasoner that owns the final word on each shared metric.  Several units legitimately observe
#: confidence and urgency along the way — a legacy rule, a gate, a temporal decay — but exactly one
#: gets to publish the value the decision is built on.  Without a named authority the winner would
#: be "whichever emitter happened to run last", so adding a unit could silently move every score in
#: the system.  Capabilities may name their own authority through the metadata keys below.
CONFIDENCE_AUTHORITY = "core.confidence"
PRIORITY_AUTHORITY = "core.priority"
CONFIDENCE_AUTHORITY_KEY = "confidence_authority"
PRIORITY_AUTHORITY_KEY = "priority_authority"

#: Capability metadata naming the confidence below which a ranked winner stops being a
#: recommendation and becomes a question for a human.
#:
#: It used to default to 0, which meant the floor had never fired on any lane that did not
#: declare one — and the compiled lane declares none. A floor that defaults to 0 is not a floor
#: (Law 3): the system could BLOCK a candidate, which nobody sees, but it had no way to SAY it
#: did not know. The default is now the LANE's floor, never zero; see `resolve_confidence_floor`.
CONFIDENCE_FLOOR_KEY = "confidence_floor_bp"

#: Recorded in `ReasoningDecision.uncertainty` when the floor converts a decision into an ask.
BELOW_FLOOR_REASON = "below_confidence_floor"

#: What a below-floor DEFER names so that silence is ACTIONABLE rather than merely quiet: the
#: declared context fields that never arrived, the declared units that never ran, and — when
#: nothing at all is absent — the weakest of Rule 11's named inputs, which is the axis a human
#: would have to strengthen. Every one of these is an ABSENCE this run actually recorded. None of
#: them supplies the missing fact: invariant 8 says a below-floor DEFER never invents it, and a
#: reason code naming what is missing is the opposite of inventing it.
BELOW_FLOOR_MISSING_FIELD = "below_floor_missing_field"
BELOW_FLOOR_ABSENT_UNIT = "below_floor_absent_unit"
BELOW_FLOOR_WEAK_INPUT = "below_floor_weak_input"

#: How many named resolvers a single DEFER carries. `uncertainty` is rendered on the card a human
#: reads (`deliver/card_builder.py`), so an unbounded list of forty absent fields would bury the
#: two that matter. Sorted first, so which ones survive the cap is deterministic.
BELOW_FLOOR_RESOLVER_CAP = 8

#: Capability metadata naming the LANE a manifest was built for — the adapter that authored it.
#: Floors are declared per lane (doc 01 C6), and the lane has to be read from the manifest rather
#: than from the request, because `reason.store`'s replay verifier re-derives the decision from a
#: capability and a context alone. A floor that varied with execution mode would make replay
#: disagree with the run it replays.
LANE_KEY = "adapter"

#: A manifest that declares no adapter is not an exempt lane; it is an unnamed one.
UNDECLARED_LANE = "undeclared"

#: The seed floor. doc 01 C6 sets 4500 bp on the compiled lane, and every other lane inherits it
#: until it declares its own — "never zero by default" is the whole point, so an unknown lane
#: gets the floor rather than an exemption.
DEFAULT_CONFIDENCE_FLOOR_BP = 4_500

#: Per-lane floors, keyed by `metadata[LANE_KEY]`. A lane tunes its own bar here or, better, in
#: its own manifest; what it cannot do is opt out.
CONFIDENCE_FLOOR_BY_LANE: Mapping[str, int] = {
    "expertise_to_capability": DEFAULT_CONFIDENCE_FLOOR_BP,   # the compiled lane — doc 01 C6
    "legacy.rule.v1": DEFAULT_CONFIDENCE_FLOOR_BP,            # the pack's own gate.c_min wins
}

#: How a floor was arrived at, recorded on every resolution: the manifest declared it, the lane
#: supplied it, or the manifest declared ZERO and the lane overrode that. The third is a state
#: worth naming — a manifest whose author wrote 0 did not declare "no floor", because no such
#: lane exists; it declined to choose, and the record says so instead of silently permitting.
FLOOR_SOURCE_DECLARED = "declared"
FLOOR_SOURCE_LANE = "lane_default"
FLOOR_SOURCE_LANE_OVER_ZERO = "lane_default_over_declared_zero"

#: The single unstated independence pool. Everything that asserted no origin — and every citation
#: that does not resolve inside the frozen snapshot — shares it, and it can only LOWER a
#: confidence. Independence is asserted, never inferred: two refs that look independent because
#: they came from two rows are exactly the echo Rule 11 exists to stop. The literal matches what
#: `reason/adapters/legacy_context.py` writes when a fact carries no group.
UNATTRIBUTED_GROUP = "unattributed"

#: Reason codes on `ConfidenceComposition.receipts` — one per movement, so "why 6400?" is
#: answerable from the record rather than by re-running the DAG.
CONFIDENCE_BASE_REASON = "confidence_base"
CONFIDENCE_LOWERED_REASON = "confidence_lowered"
CONFIDENCE_RAISED_REASON = "confidence_raised"
CONFIDENCE_HELD_REASON = "confidence_held"
CONFIDENCE_CAPPED_REASON = "confidence_degraded_cap"

#: Capability metadata carrying Layer 3's typed consumers — `reason/adapters/expertise.py`'s weld
#: (doc 03). The Decision Maker reads three things out of it and computes nothing of its own: the
#: quoted citations, the per-rule verdicts it turns into `constraints_applied` once candidate ids
#: exist, and whether two authored rules that both fired contradict each other.
WELD_KEY = "weld"

#: Recorded in `uncertainty` when two rules that BOTH fired are declared in tension with each
#: other. Doc 03: *"both fire; the contradiction surfaces on the decision as a named conflict —
#: L4 abstains rather than picking silently"*. Abstention here is DEFER, which is the outcome this
#: kernel already uses for "the ranked field is real, nothing is selected, ask a human" — the same
#: shape the confidence floor produces, for the same reason.
RULE_CONFLICT_REASON = "corpus_rule_conflict"

# ═════════════════════════════════════════════════════════════════════════════════════════════
# E1 · THE RANKING MODEL — one version switch, read off the weights themselves
# ═════════════════════════════════════════════════════════════════════════════════════════════
#
# Everything this wave adds to the ranker is reached only when the capability declares G-06's SIX
# weights (`ranking_weights@2`). That is not caution for its own sake: `reason/store.py` verifies
# a persisted audit row by RE-RUNNING `build_candidates` against the stored manifest and the
# stored reasoner results, so a capability whose weights are the legacy five must reach exactly
# the utility it reached the day it was written or every historic row stops verifying. The weight
# SHAPE is therefore the model version, the manifest carries it, and the switch is a property of
# the thing being replayed rather than of the machine replaying it.
#
# `ranking_weight_scale` is not used to make this decision even though it would answer it, because
# it answers a DIFFERENT question (which divisor) and a reader should not have to know that the two
# happen to coincide today.

#: The component doc 04 gives the largest weight in the engine — and the one this module has never
#: read. Its presence in `ranking_weights` is what says "this capability is on the v2 model".
IMPORTANCE_COMPONENT = "importance"

#: Capability metadata carrying L2's composed importance for the situation this capability was
#: compiled for: `{importance_bp, source, fallback, version}`. Written by
#: `reason/adapters/expertise.py` at the same seam that already carries the weld, because the BSO
#: is in scope there and is not in scope here — the Decision Maker must reach the same number on a
#: replay that has nothing but the persisted manifest, and metadata is what replay restores.
SITUATION_IMPORTANCE_KEY = "situation_importance"

#: Recorded in `uncertainty` when importance is NOT available and the remaining weights are
#: redistributed. Doc 04 E1: *"Never substitute 5000. A neutral default is exactly the bug that
#: made every card score 50."* The detail after the colon names WHY it is absent — `not_supplied`
#: (no carrier reached the manifest) or Layer 2's own `importance_source` for a situation whose
#: score is the documented fallback rather than a measurement.
IMPORTANCE_ABSENT_REASON = "L2_IMPORTANCE_NOT_ACTIVE"

#: E1b · the override becomes a PRIOR. 70% formula, 30% the authored corpus priority, in integers.
#: Doc 04 states the arithmetic literally as `(formula*7 + override*3) // 10`, floor division and
#: not half-up, so the demotion can never round a candidate ABOVE what either input claimed.
OVERRIDE_FORMULA_WEIGHT = 7
OVERRIDE_PRIOR_WEIGHT = 3
OVERRIDE_WEIGHT_SCALE = 10

#: Where the demoted override is recorded beside the formula's own answer. `formula_utility` alone
#: makes the divergence computable (`utility - formula`); this makes it DECOMPOSABLE, which is what
#: doc 08's retirement review needs — "the formula and the corpus disagreed by 900bp" is a
#: different finding from "the corpus said 9600 and the formula said 4200".
PRIORITY_OVERRIDE_COMPONENT = "priority_override"

#: E4 · where the cost of doing nothing is actually computed, in preference order. `core.cost`
#: prices inaction directly; `core.alternative` republishes that price when a cost unit ran and
#: composes one from headroom, momentum and exposure when it did not. Reading the second only when
#: the first is silent is what stops one silence being counted as two independent estimates.
DO_NOTHING_COST_SOURCES: tuple[tuple[str, str], ...] = (
    ("core.cost", "do_nothing_cost_bp"),
    ("core.alternative", "do_nothing_baseline_bp"),
)

#: E4 · the horizon. `core.timeline`'s `deadline_hours` is SIGNED and measured against
#: `evaluation_time` by the unit that published it — positive is ahead, zero or negative is
#: overdue. The horizon is that offset re-applied to the same instant, so no clock is read here.
DO_NOTHING_HORIZON_SOURCE: tuple[str, str] = ("core.timeline", "deadline_hours")


def _authority(request: Any, key: str, default: str) -> str:
    value = request.capability.metadata.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise OrchestrationError(f"capability metadata {key} must name a reasoner")
    return value.strip()


@dataclass(frozen=True, slots=True)
class DecisionSynthesis:
    """The complete output of Part 3: the candidate field and the decision drawn from it."""

    candidates: tuple[DecisionCandidate, ...]
    decision: ReasoningDecision
    #: How the decision's confidence was composed — the base, every movement and its reason code,
    #: the independence groups counted. Defaulted so nothing that already builds a synthesis by
    #: position breaks, and carried so a caller can answer "why 6400?" without re-running the DAG:
    #: a lawful raise and an unlawful one are indistinguishable once only the integer survives.
    confidence: "ConfidenceComposition | None" = None


# ---------------------------------------------------------------------------------------------
# Evidence Aggregator
# ---------------------------------------------------------------------------------------------

def aggregate_evidence(results: Sequence[ReasonerResult]) -> tuple[str, ...]:
    """Union every evidence id the units cited, directly or through findings and adjustments.

    A candidate carries the whole evidential basis of the run rather than one unit's slice, so the
    explanation a human sees can never cite less than what actually moved the score.
    """
    return tuple(sorted(set(
        evidence_id
        for result in results
        for evidence_id in (
            result.evidence_ids
            + tuple(ev for finding in result.findings for ev in finding.evidence_ids)
            + tuple(ev for adjustment in result.adjustments for ev in adjustment.evidence_ids)
        )
    )))


# ---------------------------------------------------------------------------------------------
# Confidence Calculator — Rule 11 (E2 · DLG-05)
# ---------------------------------------------------------------------------------------------

def _metadata_bp(request: Any, key: str, default: int) -> int:
    value = request.capability.metadata.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000:
        raise OrchestrationError(f"capability metadata {key} must be integer basis points")
    return value


def _published_confidence(result: ReasonerResult) -> int:
    """One unit's stated confidence, validated. Integer basis points or a manifest fault."""
    raw = result.metrics["confidence_bp"]
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise OrchestrationError("confidence_bp must be an integer")
    return clamp_bp(raw)


def _cited_evidence_ids(result: ReasonerResult) -> tuple[str, ...]:
    """Everything this ONE unit stood behind — the result, its findings, its adjustments.

    The same union `aggregate_evidence` takes over the whole run, taken per unit instead: Rule 11
    asks whether *this* raise is backed by evidence *this* unit named, and a union over every unit
    would let a raise borrow a neighbour's citation.
    """
    return tuple(sorted(set(
        result.evidence_ids
        + tuple(item for finding in result.findings for item in finding.evidence_ids)
        + tuple(item for adjustment in result.adjustments for item in adjustment.evidence_ids))))


def _stated_groups(result: ReasonerResult, request: Any) -> Mapping[str, int]:
    """The STATED independence groups this unit cited, each with its weakest witness.

    Independence is asserted, never inferred — L1's `capture/validate/confidence.py` settled that
    and this is the same rule one layer up. An evidence ref that stated no group, and any id that
    does not resolve inside the frozen snapshot, lands in the single unstated pool
    (:data:`UNATTRIBUTED_GROUP`) which is deliberately absent from this mapping: unstated origins
    may lower a confidence and can never raise one. Two refs that look independent because they
    came from different rows are exactly the echo Rule 11 exists to stop.

    The weakest witness in a group is what the group is worth. Taking the strongest would let one
    strong ref carry a group full of weak ones, which is the same echo wearing a better name.
    """
    by_id = {item.evidence_id: item for item in request.context.evidence}
    groups: dict[str, int] = {}
    for evidence_id in _cited_evidence_ids(result):
        ref = by_id.get(evidence_id)
        if ref is None:
            continue                       # unresolvable: unstated pool, never a qualifying group
        group = str(ref.independence_group or "").strip()
        if not group or group == UNATTRIBUTED_GROUP:
            continue                       # asserted nothing: unstated pool
        witness = clamp_bp(int(ref.confidence_bp))
        groups[group] = min(groups[group], witness) if group in groups else witness
    return groups


@dataclass(frozen=True, slots=True)
class RaiseClaim:
    """The only thing that may lift a confidence: named evidence from an uncounted origin.

    Built from what the unit already published — no unit has to learn a new emission shape for
    Rule 11 to bind it, which is the point. A raise with no claim is not a lower-quality raise; it
    is a :class:`ConfidenceViolation`.
    """

    unit_id: str
    claimed_bp: int
    groups: tuple[str, ...]
    witness_bp: int
    evidence_ids: tuple[str, ...]


def raise_claim(result: ReasonerResult, request: Any,
                counted_groups: frozenset[str]) -> RaiseClaim | None:
    """The claim behind a raise, or None when there is nothing that could license one.

    A group that has already been counted for this decision cannot be counted again — a forwarded
    copy of an email is not a second witness, and that is what re-counting an origin looks like
    from the inside.
    """
    groups = {name: witness for name, witness in _stated_groups(result, request).items()
              if name not in counted_groups}
    if not groups:
        return None
    return RaiseClaim(
        unit_id=result.reasoner_id,
        claimed_bp=_published_confidence(result),
        groups=tuple(sorted(groups)),
        witness_bp=min(groups.values()),
        evidence_ids=_cited_evidence_ids(result))


def bounded_raise(running_bp: int, claim: RaiseClaim) -> int:
    """What naming buys: a bounded raise, never an exemption.

    ``running + (headroom * earned) // 10000 // 2``, capped at what the unit itself claimed.
    Three properties, each load-bearing, and the first two are L1's `corroborate` verbatim:

    * **bounded** — at most half the remaining headroom, so no chain of agreeing units reaches
      certainty;
    * **proportional to the witness** — ``earned`` is the weaker of what the unit claims and what
      its weakest new origin is worth, because agreeing weakly is not the same as agreeing;
    * **never past the claim** — the publisher stated a value for this metric, not merely a
      corroborating observation, so the composition may approach that value and never overshoot
      it.

    L1 shipped the alternative first — a named source RETURNED THE RAW VALUE — and one 100 bp
    Slack aside lifted a ceiling of 100 to 9003. An exemption with a name attached is a rule with
    an off switch, and it looks exactly like rigour in the audit record.
    """
    headroom = 10_000 - running_bp
    earned = min(claim.claimed_bp, claim.witness_bp)
    return min(claim.claimed_bp, running_bp + headroom * earned // 10_000 // 2)


@dataclass(frozen=True, slots=True)
class ConfidenceComposition:
    """One confidence, and the receipt for how it got there.

    Returned rather than merely computed because Rule 11's whole value is that every movement is
    answerable: which unit moved the number, in which direction, on whose evidence. A composition
    that only handed back an integer would make a lawful raise and an unlawful one look identical
    once the function returned.
    """

    confidence_bp: int
    base_bp: int
    settled_by: str
    vector: Mapping[str, int] = field(default_factory=dict)
    counted_groups: tuple[str, ...] = ()
    receipts: tuple[str, ...] = ()
    degraded_cap_bp: int | None = None


def _rule_11_inputs(result: ReasonerResult) -> Mapping[str, int]:
    """The named inputs `core.confidence` already publishes — E2's raw material, kept.

    A SUBSET of `CONFIDENCE_VECTOR_KEYS`: an input the unit could not compute is absent, never
    zero. Substituting a number for an input that does not exist is the bug that made every card
    score 50, and E1 forbids reintroducing it under a new name.
    """
    return {key: clamp_bp(int(result.metrics[key])) if key.endswith("_bp")
            else max(0, int(result.metrics[key]))
            for key in CONFIDENCE_VECTOR_KEYS
            if key in result.metrics and not isinstance(result.metrics[key], bool)
            and isinstance(result.metrics[key], int)}


def compose_confidence(results: Sequence[ReasonerResult], request: Any,
                       degraded: bool) -> ConfidenceComposition:
    """Resolve the one confidence that describes this decision, under Rule 11.

    **Rule 11, the standing law: confidence falls freely; it rises only with named independent
    evidence.** What this function replaced was a last-writer scan — every unit that published
    `confidence_bp` overwrote the previous one, so a unit late in the DAG could raise the number
    with nothing named at all, and the decision's confidence was whatever the last unit to speak
    happened to say. That is the precise failure Rule 11 exists to forbid, and it matters beyond
    correctness: confidence gates SILENCE (the floor below), so a fabricated raise does not merely
    mis-score a card, it pushes a card past the floor that should have suppressed it.

    The composition, in the order it runs:

    1. **The named authority owns the starting point.** Exactly one unit publishes this metric —
       `CONFIDENCE_AUTHORITY`, or whichever unit the capability appoints — and `core.confidence`
       computes its number FROM Rule 11's own inputs (independent evidence groups, coverage,
       corroboration, source quality). Its publication is therefore the composed belief, not a
       transition applied to somebody else's; when it speaks, the composition is settled and no
       later unit may move it. That boundary is not new and is not negotiable: it is what stops
       adding a unit from silently re-scoring every decision in the system.
    2. **When no authority speaks, the observers are composed — under Rule 11.** A failed,
       unscheduled or silent authority used to hand the decision to the last observer in the list.
       Now the capability's declared default is the base and each observer is a TRANSITION:
       lowering is free and receipted; raising requires a :class:`RaiseClaim` naming evidence from
       an independence group not yet counted, and is then BOUNDED (`bounded_raise`); a raise with
       no qualifying claim is a :class:`ConfidenceViolation` and fails closed.
    3. **A degraded run keeps its ceiling.** Unchanged: a decision reached with a blind spot must
       never present itself as well-evidenced as one reached with every input intact.

    Why the exception is an exception and not a receipt: the acceptance row is "an uncited
    confidence raise throws", because a warn ships. L1 draws the same line in the same place — its
    `corroborate` RAISES at the seam where an unnamed raise is a programming error, and only
    CLAMPS at the outer batch boundary where dying mid-ingest would be the worse failure. There is
    no batch here: one decision, one run, and a decision built on a confidence nobody can point at
    is exactly the output this layer exists to prevent.

    Pure: no clock, no I/O, no model. `request` is read for the capability's declared defaults and
    for the frozen evidence the claims resolve against, which is why `reason.store`'s replay path
    (which hands this a capability and a context and nothing else) recomposes byte-identically.
    """
    authority = _authority(request, CONFIDENCE_AUTHORITY_KEY, CONFIDENCE_AUTHORITY)
    base = _metadata_bp(request, "default_confidence_bp", 5_000)
    receipts: list[str] = []

    # THE PREFIX. A completed authority ends the scan exactly as it always has — everything after
    # it is an observation about a number that already has an owner.
    prefix: list[ReasonerResult] = []
    for result in results:
        prefix.append(result)
        if result.reasoner_id == authority and result.status == ResultStatus.COMPLETED:
            break

    settled = next((item for item in prefix
                    if item.reasoner_id == authority
                    and item.status == ResultStatus.COMPLETED
                    and "confidence_bp" in item.metrics), None)
    if settled is not None:
        value = _published_confidence(settled)
        vector = _rule_11_inputs(settled)
        counted = tuple(sorted(_stated_groups(settled, request)))
        receipts.append(f"{CONFIDENCE_BASE_REASON}:{authority}:{value}")
        settled_by = "confidence_authority"
    else:
        # No owner spoke. Compose the observers, under Rule 11.
        #
        # THE FIRST PUBLICATION IS THE BELIEF, not a raise against the manifest's default. The
        # default is a placeholder for "nobody said anything" — L1 draws the same line, taking the
        # incumbent belief as the base only when a previous layer actually held one and otherwise
        # starting from the strongest source rather than from a neutral number. Treating the first
        # measurement as a raise against 5000 would refuse every capability whose appointed
        # authority is not scheduled, which is a manifest shape, not a Rule 11 violation.
        value = base
        vector = {}
        counted_set: set[str] = set()
        stated = False
        for result in prefix:
            if result.status != ResultStatus.COMPLETED or "confidence_bp" not in result.metrics:
                continue
            published = _published_confidence(result)
            if not stated:
                stated = True
                value = published
                counted_set.update(_stated_groups(result, request))
                receipts.append(f"{CONFIDENCE_BASE_REASON}:{result.reasoner_id}:{published}")
                continue
            if published == value:
                receipts.append(f"{CONFIDENCE_HELD_REASON}:{result.reasoner_id}:{published}")
                continue
            if published < value:
                receipts.append(
                    f"{CONFIDENCE_LOWERED_REASON}:{result.reasoner_id}:{value}->{published}")
                value = published
                continue
            claim = raise_claim(result, request, frozenset(counted_set))
            if claim is None:
                raise ConfidenceViolation(
                    f"Rule 11: {result.reasoner_id} raised confidence {value}->{published} with "
                    "no independent evidence named — a layer may only raise a confidence by "
                    "adding independent evidence from an origin not already counted, and it must "
                    "name that evidence")
            lifted = bounded_raise(value, claim)
            receipts.append(
                f"{CONFIDENCE_RAISED_REASON}:{result.reasoner_id}:{value}->{lifted}"
                f":{'+'.join(claim.groups)}")
            counted_set.update(claim.groups)
            value = lifted
        counted = tuple(sorted(counted_set))
        if not stated:
            receipts.append(f"{CONFIDENCE_BASE_REASON}:capability_default:{base}")
        settled_by = "rule_11_composition"

    cap: int | None = None
    if degraded:
        cap = _metadata_bp(request, "optional_failure_confidence_cap_bp", 5_000)
        if cap < value:
            receipts.append(f"{CONFIDENCE_CAPPED_REASON}:{value}->{cap}")
            value = cap
    return ConfidenceComposition(
        confidence_bp=value, base_bp=base, settled_by=settled_by, vector=vector,
        counted_groups=counted, receipts=tuple(receipts), degraded_cap_bp=cap)


def calculate_confidence(results: Sequence[ReasonerResult], request: Any, degraded: bool) -> int:
    """The one confidence this decision carries — :func:`compose_confidence` without its receipt.

    Kept as the narrow integer seam because `reason.store` re-runs the whole candidate pipeline to
    verify a persisted audit row, and a verifier that had to reconstruct a receipt in order to
    check a number would be checking its own reconstruction.
    """
    return compose_confidence(results, request, degraded).confidence_bp


def priority_metrics(results: Sequence[ReasonerResult],
                     request: Any) -> tuple[int, int | None]:
    """Resolve shared urgency and any explicit priority override.

    An override is read only from the priority authority — a unit cannot seize ranking control by
    emitting the metric opportunistically. On `ranking_weights@1` it still REPLACES the weighted
    utility; on `ranking_weights@2` `score_candidate` demotes it to a 70/30 prior. What it means is
    the scorer's business; what it is allowed to come FROM is this function's, and that has not
    changed.

    `request` is required rather than optional: an authority resolved from a default instead of
    from the capability would quietly answer a different question than the caller asked.
    """
    authority = _authority(request, PRIORITY_AUTHORITY_KEY, PRIORITY_AUTHORITY)
    urgency = 5_000
    override = None
    for result in results:
        if result.status != ResultStatus.COMPLETED:
            continue
        if "urgency_bp" in result.metrics:
            urgency = clamp_bp(int(result.metrics["urgency_bp"]))
        if result.reasoner_id == authority:
            if "priority_override_bp" in result.metrics:
                override = clamp_bp(int(result.metrics["priority_override_bp"]))
            break
    return urgency, override


# ---------------------------------------------------------------------------------------------
# Decision Evaluator
# ---------------------------------------------------------------------------------------------

def ordered_checks(checks: Sequence[CandidateCheck]) -> tuple[CandidateCheck, ...]:
    """Impose a total order on checks so an audit row is byte-stable across runs."""
    return tuple(sorted(checks, key=lambda item: (
        item.stage,
        item.evaluator_id,
        item.evaluator_version,
        item.reason_code,
        semantic_hash(item.detail),
    )))


# ---------------------------------------------------------------------------------------------
# Decision Synthesizer
# ---------------------------------------------------------------------------------------------

def ranking_model_is_v2(request: Any) -> bool:
    """Is this capability on G-06's six-weight model?

    Read off the weight KEY SET, exactly as `contracts.reasoning.require_ranking_weights` tells the
    two shapes apart, and never off an activation table: this module is re-run by `reason/store.py`
    against a persisted manifest to prove an audit row, and a decision that depended on what a
    database said today could not be verified against what it said the day it was made.
    """
    return IMPORTANCE_COMPONENT in request.capability.ranking_weights


def situation_importance(request: Any) -> tuple[int | None, str | None]:
    """L2's composed importance for this situation, or `None` and the reason it is not available.

    THE HONESTY GUARD, and it is the whole of E1a's difficulty. Layer 2 always publishes an
    `importance_bp`: when Layer 1 scored the situation's signals it is a measurement, and when it
    did not, `context/situation_bso.importance_base` publishes `DEFAULT_IMPORTANCE_BP` — the
    neutral 5,000 midpoint — and declares that it did through `importance_fallback`. Reading the
    integer alone would therefore hand the ranker a constant for every unscored tenant while the
    weight table says importance is 25% of the answer, which is the "every card scores 50" defect
    rebuilt out of new parts. So the carrier is trusted only when Layer 2 says the number was
    MEASURED, and absence is returned as absence with a reason code.

    A carrier that is present but malformed raises rather than degrading: a manifest that declares
    an importance it cannot state in basis points is a deployment fault, and silently reweighing
    around it would hide the fault behind a correct-looking decision.
    """
    carrier = request.capability.metadata.get(SITUATION_IMPORTANCE_KEY)
    if not isinstance(carrier, Mapping):
        return None, f"{IMPORTANCE_ABSENT_REASON}:not_supplied"
    raw = carrier.get("importance_bp")
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 10_000:
        raise OrchestrationError(
            f"capability metadata {SITUATION_IMPORTANCE_KEY}.importance_bp "
            "must be integer basis points")
    if carrier.get("fallback") is not False:
        # `fallback` is checked for the literal False rather than for falsiness: a carrier that
        # omitted the key, or carried None, is one whose provenance nobody stated, and an
        # unstated provenance must read as "not measured" and not as "measured".
        return None, f"{IMPORTANCE_ABSENT_REASON}:{carrier.get('source') or 'unknown'}"
    return raw, None


def _component_order(name: str) -> int:
    """The fixed position a component holds in doc 04's table; unknown names sort last, by name."""
    return (UTILITY_COMPONENTS.index(name) if name in UTILITY_COMPONENTS
            else len(UTILITY_COMPONENTS))


def effective_weights(weights: Mapping[str, int],
                      components: Mapping[str, int]) -> Mapping[str, int]:
    """The declared weights with every ABSENT component's share redistributed over the rest.

    Doc 04 E1: *"if importance_bp is None: reweigh the remaining five to 10000"*, and the same
    mechanism for any component whose source unit was skipped. Redistribution rather than
    substitution is the point — a missing input must not be able to move a candidate up or down,
    and both a zero and a neutral 5,000 do exactly that.

    Integer basis points end to end, with a largest-remainder pass so the weights sum to the scale
    EXACTLY. Floor division alone loses up to one basis point per component, and a weight vector
    that sums to 9,998 quietly scales every candidate down by two parts in ten thousand — small
    enough never to be noticed and large enough to reorder a tie. The remainder is handed out in a
    total order (largest remainder, then doc 04's table position, then name) so the result cannot
    depend on mapping iteration order on any machine.
    """
    absent = [name for name in weights if name not in components]
    if not absent:
        return weights
    kept = {name: weights[name] for name in weights if name in components}
    total = sum(kept.values())
    if total <= 0:
        raise OrchestrationError(
            "every weighted ranking component is absent; nothing can be ranked")
    scale = RANKING_WEIGHTS_V2_SCALE
    scaled = {name: value * scale // total for name, value in kept.items()}
    shortfall = scale - sum(scaled.values())
    order = sorted(kept, key=lambda name: (-((kept[name] * scale) % total),
                                           _component_order(name), name))
    for name in order[:shortfall]:
        scaled[name] += 1
    return scaled


@dataclass(frozen=True, slots=True)
class ProposedCandidate:
    """A candidate mid-synthesis, before it has been judged, ranked, or made immutable."""

    play: Any
    components: Mapping[str, int]
    utility_bp: int
    checks: tuple[CandidateCheck, ...] = ()
    disposition: CandidateDisposition = CandidateDisposition.ELIGIBLE
    rank_position: int | None = None


def synthesize_candidates(request: Any, adjustments: Sequence[CandidateAdjustment],
                          urgency_bp: int, priority_override: int | None,
                          importance_bp: int | None = None
                          ) -> tuple[ProposedCandidate, ...]:
    """Turn each operation the domain exposed into a scored candidate.

    The action space is authored, not invented here, and that is deliberate: Law 02 says domain
    expertise never decides, it only exposes operations.  So Layer 3 declares *what could be done*
    and this function decides *how good each option looks given this situation* — which is the
    synthesis the architecture actually asks for.  Inventing an action no expert authored would be
    the Decision Maker quietly becoming a domain author.

    Units move a candidate by publishing typed adjustments against a named component; they cannot
    write a score directly, which is what keeps analysis and synthesis separable.
    """
    proposals: list[ProposedCandidate] = []
    for play in sorted(request.capability.plays, key=lambda item: item.play_id):
        components = {
            "impact": play.impact_bp,
            "success": play.success_probability_bp,
            "urgency": urgency_bp,
            "effort": play.effort_bp,
            "risk": play.risk_bp,
        }
        if importance_bp is not None:
            # E1a. SITUATION-LEVEL, not play-level, and therefore identical across the candidates
            # of one run: it is a statement about how much this situation matters, not about how
            # good a move is. It cannot reorder a field, and it is not supposed to — what it
            # orders is one situation against another, which is the ordering a daily brief is and
            # the ordering three layers have been computing an input for. It is deliberately NOT
            # in `guards.CANDIDATE_COMPONENTS`: no reasoning unit may move it, because Layer 2
            # owns it and a unit that could raise it could raise its own card.
            components[IMPORTANCE_COMPONENT] = importance_bp
        for adjustment in adjustments:
            if adjustment.play_id == play.play_id:
                components[adjustment.component] = clamp_bp(
                    components[adjustment.component] + adjustment.delta_bp)
        proposals.append(ProposedCandidate(
            play=play,
            components=components,
            utility_bp=score_candidate(request, components, priority_override),
        ))
    return tuple(proposals)


def score_candidate(request: Any, components: Mapping[str, int],
                    priority_override: int | None) -> int:
    """Weighted utility in integer basis points, and E1b's demotion of the override.

    Effort and risk are costs, so the candidate is rewarded for their *absence* — a cheap, safe
    play with modest impact can rightly beat an expensive, dangerous one with high impact.

    **The override is no longer a verdict on the v2 model.** `reason/adapters/expertise.py` hands
    the authored corpus priority to `core.priority` as config for EVERY compiled candidate, so a
    `priority_override_bp` was present on every compiled decision this engine has ever made and
    the weighted formula has never once decided anything. Doc 04 demotes it to a 70/30 prior: the
    formula leads, the human ranking of the corpus's situations is real signal and is kept, and
    the DIVERGENCE between the two is recorded on every candidate so the weight is revisited at
    retirement against evidence rather than taste.

    `ranking_weights@1` keeps the old behaviour exactly. `reason/store.py` re-runs this function to
    verify persisted audit rows, and a capability that was ranked under the five-weight model must
    still reach the utility it reached then or every historic row stops verifying.
    """
    formula = _weighted_utility(request, components)
    # Recorded on EVERY branch and every shape, which is what makes K1's "divergence recorded on
    # 100% of decisions" a property of the code rather than of a reporting job:
    # `DecisionCandidate.formula_utility_bp` reads this key and `utility_divergence_bp` is the
    # difference. The two being equal is itself the finding — it says the override changed nothing.
    components[FORMULA_UTILITY_COMPONENT] = formula
    if priority_override is None:
        return formula
    if not ranking_model_is_v2(request):
        return priority_override
    # DECOMPOSABLE, not merely computable: the divergence alone cannot say whether the corpus
    # ranked high and the formula low or the reverse, and doc 08's retirement review asks exactly
    # that question of the recorded data.
    components[PRIORITY_OVERRIDE_COMPONENT] = priority_override
    formula_w, prior_w = _override_blend(request)
    return clamp_bp((formula * formula_w + priority_override * prior_w)
                    // (formula_w + prior_w))


def _override_blend(request) -> tuple[int, int]:
    """How much of the author's own ranking survives the formula, as `(formula, prior)`.

    70/30 was a module constant, and it is a JUDGMENT about how far to trust a human's ordering
    against a computed one. That judgment is exactly what differs between a domain whose corpus
    was written by the person who does the work and one whose corpus is a first draft — and the
    number was the same for both.

    READ FROM THE CAPABILITY MANIFEST, which is the seam that makes it safe. The manifest is
    inside the persisted capability snapshot `reason/store.py` replays, so a historic audit row
    still verifies against the blend that produced it. A tenant setting stored anywhere else
    would silently rewrite the past every time somebody changed it — the same argument that
    made `ranking_weights` manifest data rather than config.

    REFUSES A DEGENERATE PAIR rather than defaulting past it. `[0, 0]` would divide by zero and
    a negative weight would invert the blend; both are typos, and a typo must not quietly become
    a ranking policy.
    """
    default = (OVERRIDE_FORMULA_WEIGHT, OVERRIDE_PRIOR_WEIGHT)
    try:
        declared = (getattr(request, "capability_metadata", None)
                    or {}).get("priority_override_blend")
        if not declared:
            return default
        formula_w, prior_w = (int(declared[0]), int(declared[1]))
        if formula_w < 0 or prior_w < 0 or (formula_w + prior_w) <= 0:
            return default
        return formula_w, prior_w
    except Exception:      # noqa: BLE001 — a malformed blend is not a reason to lose the rank
        return default


def _weighted_utility(request, components: Mapping[str, int]) -> int:
    """The ranking model: reward importance, impact, success and urgency; penalise effort and risk.

    Two shapes, told apart by the weights themselves, and the legacy branch is written out in full
    rather than folded into the general one on purpose. The five-weight lane accepts weights that
    are not integers (one manifest in the tree declares percentages as floats), and float addition
    is not associative — a general loop that summed the same five terms in a different order could
    return a different last bit and break the replay of a stored row for no reason a reader would
    ever find.
    """
    weights = request.capability.ranking_weights
    if IMPORTANCE_COMPONENT not in weights:
        weighted = (
            components["impact"] * weights["impact"]
            + components["success"] * weights["success"]
            + components["urgency"] * weights["urgency"]
            + (10_000 - components["effort"]) * weights["effort"]
            + (10_000 - components["risk"]) * weights["risk"]
        )
        return clamp_bp(divide_half_up(weighted, 100))
    effective = effective_weights(weights, components)
    # Iterated in doc 04's declared order rather than over the mapping, so the sum is byte-stable
    # whatever order the weights were authored in.
    weighted = 0
    for name in UTILITY_COMPONENTS:
        weight = effective.get(name)
        if weight is None:
            continue
        value = components[name]
        weighted += (10_000 - value if name in COST_COMPONENTS else value) * weight
    return clamp_bp(divide_half_up(weighted, RANKING_WEIGHTS_V2_SCALE))


# ---------------------------------------------------------------------------------------------
# Decision Evaluator
# ---------------------------------------------------------------------------------------------

def evaluate_candidates(proposals: Sequence[ProposedCandidate],
                        checks: Sequence[CandidateCheck]) -> tuple[ProposedCandidate, ...]:
    """Apply hard checks and remove anything a unit ruled out.

    This runs *before* ranking, and that order is the whole safety property: a play eliminated by
    policy never competes on score, so it can never win and then be quietly demoted.  The check
    that removed it travels with the candidate, so the record shows what was rejected and by which
    rule — a rejection without its reason is indistinguishable from an oversight.
    """
    judged: list[ProposedCandidate] = []
    for proposal in proposals:
        play_checks = ordered_checks([item for item in checks
                                      if item.play_id == proposal.play.play_id])
        eliminated = any(item.outcome == CheckOutcome.ELIMINATE for item in play_checks)
        judged.append(replace(
            proposal,
            checks=play_checks,
            disposition=(CandidateDisposition.ELIMINATED if eliminated
                         else CandidateDisposition.ELIGIBLE),
        ))
    return tuple(judged)


# ---------------------------------------------------------------------------------------------
# Decision Ranker
# ---------------------------------------------------------------------------------------------

def rank_candidates(proposals: Sequence[ProposedCandidate]) -> tuple[ProposedCandidate, ...]:
    """Impose a total order: survivors by utility, ties broken by play id, eliminated last.

    The tie-break is not cosmetic.  Two equally-scored plays must resolve the same way on every
    machine and every replay, so the order can never come from whatever sequence the plays happened
    to arrive in.
    """
    eligible = sorted((item for item in proposals
                       if item.disposition == CandidateDisposition.ELIGIBLE),
                      key=lambda item: (-item.utility_bp, item.play.play_id))
    eliminated = sorted((item for item in proposals
                         if item.disposition == CandidateDisposition.ELIMINATED),
                        key=lambda item: item.play.play_id)
    ranked = tuple(replace(item, rank_position=rank)
                   for rank, item in enumerate(eligible, start=1))
    return ranked + tuple(eliminated)


# ---------------------------------------------------------------------------------------------
# Decision Object Builder
# ---------------------------------------------------------------------------------------------

def build_candidate_objects(proposals: Sequence[ProposedCandidate], confidence_bp: int,
                            evidence: tuple[str, ...]) -> tuple[DecisionCandidate, ...]:
    """Freeze the ranked field into immutable, content-addressed candidates."""
    return tuple(DecisionCandidate(
        play_id=item.play.play_id,
        play_version=item.play.version,
        disposition=item.disposition,
        utility_bp=item.utility_bp,
        confidence_bp=confidence_bp,
        score_components=item.components,
        rank_position=item.rank_position,
        checks=item.checks,
        evidence_ids=evidence,
        parameters={
            "label": item.play.label,
            "steps": item.play.steps,
            # `read_only` is the delivery authority bit: adapters refuse anything else.
            "read_only": item.play.read_only,
            "tags": item.play.tags,
            "metadata": item.play.metadata,
            "success_events": item.play.success_events,
            "window_days": item.play.window_days,
        },
    ) for item in proposals)


def build_candidates(request: Any, results: Sequence[ReasonerResult],
                     degraded: bool) -> tuple[tuple[DecisionCandidate, ...], int]:
    """Synthesize → evaluate → rank → build, in that fixed order.

    Kept as one entry point because `reason.store` re-runs exactly this pipeline to verify a
    persisted audit row; two callers proving the same law is what makes a forged row detectable.
    """
    confidence_bp = calculate_confidence(results, request, degraded)
    urgency_bp, priority_override = priority_metrics(results, request)
    adjustments = [item for result in results for item in result.adjustments]
    checks = [item for result in results for item in result.checks]
    # E1a. Read only on the v2 model: adding a sixth entry to `score_components` on a v1
    # capability would move every candidate id, and candidate ids are what `reason/store.py`
    # compares a persisted row against. The reason code the absent branch produces is recorded on
    # the decision by `decide()`, which re-reads this same pure function — `build_candidates` has
    # a two-value return that `store.py` calls, and widening it to carry a reason code would make
    # the verifier and the engine disagree about the shape of the thing being verified.
    importance_bp = (situation_importance(request)[0]
                     if ranking_model_is_v2(request) else None)

    proposals = synthesize_candidates(request, adjustments, urgency_bp, priority_override,
                                      importance_bp)
    proposals = evaluate_candidates(proposals, checks)
    proposals = rank_candidates(proposals)
    return build_candidate_objects(
        proposals, confidence_bp, aggregate_evidence(results)), confidence_bp


def _completed_metric(results: Sequence[ReasonerResult], reasoner_id: str,
                     metric: str) -> int | None:
    """One integer metric off one COMPLETED unit, or None.

    Status is checked rather than assumed: a unit that failed or ran out of context publishes no
    metrics, and the difference between "it measured nothing" and "it did not run" is the whole
    content of E4's `source` field.
    """
    for result in results:
        if result.reasoner_id != reasoner_id or result.status != ResultStatus.COMPLETED:
            continue
        value = result.metrics.get(metric)
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        return value
    return None


def _do_nothing_statement(request: Any, cost_bp: int, hours: int | None) -> str:
    """The sentence, TEMPLATED from the two computed numbers — never written by a model.

    Doc 04 E4: *"the LLM may FRAME it (R-4), never compute it"*. What leaves this function is the
    computation stated plainly; a narrator downstream may re-say it, and if it re-says it with a
    different number the bundle's own number check catches that rather than this one.
    """
    subject = str(request.capability.metadata.get("situation_type") or "situation").replace(
        "_", " ")
    lead = (f"Leaving this {subject} unaddressed carries a measured inaction cost of "
            f"{cost_bp} basis points")
    if hours is None:
        return lead + "; no material date was measured."
    if hours > 0:
        return lead + f"; the nearest material date is {hours} hours away."
    return lead + f"; the nearest material date passed {-hours} hours ago."


def do_nothing_record(request: Any, results: Sequence[ReasonerResult]) -> dict[str, Any]:
    """E4 · what standing still actually costs — `{cost_bp, horizon, statement, source}`.

    **The defect this replaces.** `do_nothing_consequence` is copied verbatim off the manifest, so
    every card in the system says the same sentence about a different situation, while `core.cost`
    computes a real `do_nothing_cost_bp` and `core.alternative` a real `do_nothing_baseline_bp` and
    neither number reaches anything. The sentence was not wrong; it was unfalsifiable, and a
    consequence nobody can check is not a consequence a human can weigh.

    **`source` is the honesty of the other three.** When neither unit ran, the manifest string is
    used and LABELLED `manifest_fallback`, so a card can never imply a computation that did not
    happen. That is why the key is mandatory in `contracts.require_do_nothing` rather than
    defaulted: a mapping that could omit it would let a fallback render as a measurement.
    """
    cost_bp: int | None = None
    for reasoner_id, metric in DO_NOTHING_COST_SOURCES:
        value = _completed_metric(results, reasoner_id, metric)
        if value is not None:
            cost_bp = clamp_bp(value)
            break
    hours = _completed_metric(results, *DO_NOTHING_HORIZON_SOURCE)
    # No clock. `deadline_hours` is an offset the timeline unit measured against this run's own
    # `evaluation_time`, and re-applying it to the same instant is the only way to name the date
    # without reading one.
    horizon = (request.evaluation_time + timedelta(hours=hours)) if hours is not None else None
    if cost_bp is None:
        return {"cost_bp": 0, "horizon": horizon,
                "statement": request.capability.do_nothing_consequence,
                "source": "manifest_fallback"}
    return {"cost_bp": cost_bp, "horizon": horizon,
            "statement": _do_nothing_statement(request, cost_bp, hours),
            "source": "computed"}


# ---------------------------------------------------------------------------------------------
# Confidence Policy — the floor, per lane (E3 · doc 01 C6)
# ---------------------------------------------------------------------------------------------

def resolve_confidence_floor(request: Any) -> tuple[int, str]:
    """The confidence below which this lane stops recommending, and where that number came from.

    **A floor that defaults to 0 is not a floor.** The mechanism below it has always been correct
    and honest — below the floor the ranked field is kept, nothing is selected, and the missing
    input is named rather than invented — and it had never fired on the compiled lane, because
    that lane declares no floor and the default was zero. So the system could BLOCK a candidate,
    which nobody sees, and it had no way to SAY it did not know, which is a different and more
    honest output. Silence is the product promise; a silence that is structurally unreachable is
    not a conservative default, it is a missing feature.

    Resolution, in order:

    1. the manifest's own `confidence_floor_bp`, when it declares a positive one;
    2. otherwise the LANE's floor (`CONFIDENCE_FLOOR_BY_LANE`, seeded at
       :data:`DEFAULT_CONFIDENCE_FLOOR_BP`), including when the manifest declared **zero** — zero
       is not a declaration of "no floor", because no live lane has one; it is a manifest that
       declined to choose, and the returned source says exactly that.

    Read from the CAPABILITY and nothing else. Not from `request.mode`: `reason.store`'s replay
    verifier re-derives a decision from a stored capability and context with no mode at all, so a
    floor that varied by execution mode would make a replay disagree with the run it replays —
    and replay is what the whole audit story rests on.

    A malformed floor is still a manifest fault (`_metadata_bp` refuses anything that is not
    integer basis points), because an unreadable declaration must never quietly become a default.
    """
    metadata = request.capability.metadata
    lane = str(metadata.get(LANE_KEY) or UNDECLARED_LANE).strip() or UNDECLARED_LANE
    lane_floor = CONFIDENCE_FLOOR_BY_LANE.get(lane, DEFAULT_CONFIDENCE_FLOOR_BP)
    if CONFIDENCE_FLOOR_KEY not in metadata:
        return lane_floor, f"{FLOOR_SOURCE_LANE}:{lane}"
    declared = _metadata_bp(request, CONFIDENCE_FLOOR_KEY, lane_floor)
    if declared > 0:
        return declared, f"{FLOOR_SOURCE_DECLARED}:{lane}"
    return lane_floor, f"{FLOOR_SOURCE_LANE_OVER_ZERO}:{lane}"


def below_floor_resolvers(request: Any, results: Sequence[ReasonerResult],
                          composition: ConfidenceComposition) -> tuple[str, ...]:
    """What would resolve this DEFER — named ABSENCES, and never the missing fact itself.

    Invariant 8 (doc 08) says a below-floor DEFER never invents the fact it lacks, and naming what
    is absent is the opposite of inventing it: a card that says *"nobody ran core.risk and
    deal.owner never arrived"* asks an answerable question, where *"confidence too low"* asks a
    human to go and re-derive the run.

    Three kinds, in the order a human can act on them:

    * **units that did not run** — declared by the capability, absent from the results, or present
      and not COMPLETED. The status travels with the id, because "skipped by the selector" and
      "failed" are fixed by different people;
    * **fields that did not arrive** — from the frozen snapshot's own `missing_fields` and from
      every unit that reported one;
    * **the weakest Rule 11 input**, when nothing at all is absent. Then the evidence is present
      and thin rather than missing, and the axis that is thinnest — zero independent evidence
      groups, or the lowest of the published basis-point inputs — is the thing to strengthen.

    Capped at :data:`BELOW_FLOOR_RESOLVER_CAP`; the list is sorted first, so which resolvers
    survive the cap is deterministic rather than a property of dict order.
    """
    declared_units = {spec.reasoner_id for spec in request.capability.reasoners}
    status_by_unit = {item.reasoner_id: item.status.value for item in results}
    completed = {item.reasoner_id for item in results
                 if item.status == ResultStatus.COMPLETED}
    named = [f"{BELOW_FLOOR_ABSENT_UNIT}:{unit}:{status_by_unit.get(unit, 'not_run')}"
             for unit in sorted(declared_units - completed)]
    named += [f"{BELOW_FLOOR_MISSING_FIELD}:{item}" for item in sorted(
        set(request.context.missing_fields)
        | {field for result in results for field in result.missing_fields})]
    if not named:
        vector = composition.vector
        if vector.get("independent_evidence_groups") == 0:
            # The snapshot has no independent origins at all, so nothing in it can ever lawfully
            # raise a confidence. That is the one fact worth printing.
            named.append(f"{BELOW_FLOOR_WEAK_INPUT}:independent_evidence_groups:0")
        else:
            measured = {key: value for key, value in vector.items() if key.endswith("_bp")}
            if measured:
                weakest = min(measured, key=lambda key: (measured[key], key))
                named.append(f"{BELOW_FLOOR_WEAK_INPUT}:{weakest}:{measured[weakest]}")
    return tuple(named[:BELOW_FLOOR_RESOLVER_CAP])


class DecisionMaker:
    """The sole synthesis authority of Layer 4."""

    def __init__(self, *, version: str = DECISION_MAKER_VERSION) -> None:
        self.version = str(version).strip()
        if not self.version:
            raise ValueError("decision maker version is required")

    def decide(self, request: Any, results: Sequence[ReasonerResult], *,
               terminal: DecisionOutcome | None, uncertainty: Sequence[str],
               degraded: bool) -> DecisionSynthesis:
        """Produce the decision for one execution.

        `terminal` is the orchestrator's report that execution itself ended the run — a required
        unit failed, context was insufficient, or a gate said this situation does not apply. Those
        are facts about execution, not judgements, which is why Part 1 determines them and Part 3
        merely records them.  A terminal run yields no candidates at all: publishing a ranked field
        no unit ever validated would be the exact fabrication this architecture exists to prevent.

        A run that *did* reach a winner still has one more gate: the confidence floor.  Silence and
        a question are both valid outputs of this system, and shipping a weakly-evidenced
        recommendation as though it were a strong one is how an intelligence layer loses the trust
        it cannot re-earn.
        """
        uncertainty = list(uncertainty)
        weld = request.capability.metadata.get(WELD_KEY) or {}
        ranking_v2 = ranking_model_is_v2(request)
        if ranking_v2:
            # E1a's honesty guard, ON THE RECORD. The reweigh already happened inside the scorer;
            # what a reader needs from the decision is that it happened and why, because a
            # five-component ranking and a six-component one are different models and a card that
            # did not know which it came from could not be compared with one that did.
            _importance_bp, importance_absent = situation_importance(request)
            if importance_absent is not None:
                uncertainty.append(importance_absent)
        composition = compose_confidence(request=request, results=results, degraded=degraded)
        if terminal is None:
            candidates, confidence_bp = build_candidates(request, results, degraded)
            outcome = (DecisionOutcome.DECISION if any(
                item.disposition == CandidateDisposition.ELIGIBLE for item in candidates)
                       else DecisionOutcome.BLOCKED)
            floor_bp, _floor_source = resolve_confidence_floor(request)
            if outcome == DecisionOutcome.DECISION and confidence_bp < floor_bp:
                # Below the floor GeniOS stops recommending and starts asking.  The ranked field
                # is kept — the human deserves to see what was considered — but nothing is
                # selected, so no downstream adapter can read this as an instruction.  This is
                # Law 03 in code: when the system is not confident, it widens uncertainty and
                # requests input rather than inventing the missing fact.
                #
                # And it now names what WOULD resolve it, so the silence is actionable rather
                # than merely quiet — every entry an absence this run recorded, never a
                # substitute for the fact that is missing.
                outcome = DecisionOutcome.DEFER
                uncertainty.append(f"{BELOW_FLOOR_REASON}:{confidence_bp}<{floor_bp}")
                uncertainty.extend(below_floor_resolvers(request, results, composition))
            if outcome == DecisionOutcome.DECISION and weld.get("abstain_on_conflict"):
                # Two pieces of authored doctrine both applied and the corpus itself says they
                # disagree. Selecting one of them would be this kernel arbitrating an expert
                # dispute it has no basis to settle, silently. The field stays visible and
                # nothing is selected.
                outcome = DecisionOutcome.DEFER
                uncertainty.extend(
                    f"{RULE_CONFLICT_REASON}:{conflict['left']}|{conflict['right']}"
                    for conflict in weld.get("conflicts") or ()
                    if conflict.get("left_role") == "fired_rule"
                    and conflict.get("right_role") == "fired_rule")
        else:
            candidates = ()
            confidence_bp = composition.confidence_bp
            outcome = terminal

        selected = next((item for item in candidates
                         if item.disposition == CandidateDisposition.ELIGIBLE), None)
        play_by_id = {play.play_id: play for play in request.capability.plays}
        # LAYER 3's CONTRIBUTION, ATTACHED WHERE IT BECOMES ANSWERABLE. The citations were chosen
        # and quoted at the weld; the constraint APPLICATIONS could not be, because a rule can
        # only name the candidate it eliminated once the candidate exists, and candidate ids are
        # minted from candidate content a few lines above. Imported inside the function because
        # `reason.adapters` imports the orchestrator, which imports this module.
        from genios_engine.reason.adapters.rule_compiler import constraint_applications
        decision = ReasoningDecision(
            outcome=outcome,
            capability_id=request.capability.capability_id,
            capability_version=request.capability.version,
            context_snapshot_id=request.context.context_snapshot_id,
            candidates=candidates,
            selected_candidate_id=(selected.candidate_id if outcome == DecisionOutcome.DECISION
                                   and selected is not None else None),
            confidence_bp=confidence_bp,
            uncertainty=tuple(uncertainty),
            do_nothing_consequence=request.capability.do_nothing_consequence,
            expires_at=request.evaluation_time + timedelta(
                hours=request.capability.expiry_hours),
            outcome_window_days=(play_by_id[selected.play_id].window_days
                                 if outcome == DecisionOutcome.DECISION
                                 and selected is not None else None),
            citations=tuple(weld.get("citations") or ()),
            constraints_applied=constraint_applications(
                weld.get("rule_verdicts") or (), candidates),
            # G-02's two conditional fields, carried ONLY on the v2 model. Both are excluded from
            # `to_semantic_dict` when empty, so a v1 decision hashes to exactly the bytes it
            # hashed to before this wave — which is the condition under which the audit rows the
            # replay verifier reads are still the rows it can verify.
            ranking_weights_version=(RANKING_WEIGHTS_V2_VERSION if ranking_v2 else None),
            do_nothing=(do_nothing_record(request, results) if ranking_v2 else {}),
        )
        return DecisionSynthesis(candidates=candidates, decision=decision,
                                 confidence=composition)


__all__ = ["BELOW_FLOOR_ABSENT_UNIT", "BELOW_FLOOR_MISSING_FIELD",
           "BELOW_FLOOR_RESOLVER_CAP", "BELOW_FLOOR_WEAK_INPUT",
           "CONFIDENCE_BASE_REASON", "CONFIDENCE_CAPPED_REASON", "CONFIDENCE_FLOOR_BY_LANE",
           "CONFIDENCE_HELD_REASON", "CONFIDENCE_LOWERED_REASON", "CONFIDENCE_RAISED_REASON",
           "DEFAULT_CONFIDENCE_FLOOR_BP", "FLOOR_SOURCE_DECLARED", "FLOOR_SOURCE_LANE",
           "FLOOR_SOURCE_LANE_OVER_ZERO", "LANE_KEY", "UNATTRIBUTED_GROUP", "UNDECLARED_LANE",
           "ConfidenceComposition", "ConfidenceViolation", "RaiseClaim",
           "below_floor_resolvers", "bounded_raise", "compose_confidence", "raise_claim",
           "resolve_confidence_floor",
           "BELOW_FLOOR_REASON", "RULE_CONFLICT_REASON", "WELD_KEY",
           "CONFIDENCE_AUTHORITY", "CONFIDENCE_AUTHORITY_KEY",
           "CONFIDENCE_FLOOR_KEY", "DECISION_MAKER_VERSION",
           "DO_NOTHING_COST_SOURCES", "DO_NOTHING_HORIZON_SOURCE",
           "IMPORTANCE_ABSENT_REASON", "IMPORTANCE_COMPONENT",
           "OVERRIDE_FORMULA_WEIGHT", "OVERRIDE_PRIOR_WEIGHT", "OVERRIDE_WEIGHT_SCALE",
           "PRIORITY_OVERRIDE_COMPONENT", "SITUATION_IMPORTANCE_KEY",
           "PRIORITY_AUTHORITY", "PRIORITY_AUTHORITY_KEY", "DecisionMaker", "DecisionSynthesis",
           "ProposedCandidate", "aggregate_evidence", "build_candidate_objects",
           "build_candidates", "calculate_confidence", "do_nothing_record",
           "effective_weights", "evaluate_candidates", "ordered_checks",
           "priority_metrics", "rank_candidates", "ranking_model_is_v2", "score_candidate",
           "situation_importance", "synthesize_candidates"]
