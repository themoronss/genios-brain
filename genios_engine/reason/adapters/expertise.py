"""Adapt a Layer 3 ExpertisePackage into a Layer 4 CapabilityManifest.

This is the L3->L4 weld. The DomainCompiler emits knowledge (authored capabilities + objects +
four-brain rules); Layer 4's orchestrator reasons only over a `CapabilityManifest` — a DAG of
reasoning units plus plays. The authored corpus deliberately carries NO reasoner DAG (a capability
declares outcomes/failure-modes/KPIs, an object declares inference patterns), so this adapter
supplies a conservative default DAG and derives the load-bearing `required_fields` from the objects'
executable inference patterns. Package knowledge is content-hashed into the manifest version so an
overlay change yields new immutable bytes (same discipline as `legacy_capability_manifest`).

Knowledge-in, DAG-supplied. It never decides — it only shapes what Layer 4 will reason over.

WAVE Y1 · THE WELD (doc 03). Until this version, this adapter consumed `organization_rules` and
nothing else. Every authored rule, heuristic, mental model and decision framework — 446 of the
corpus's 712 artifacts — was retrieved, content-hashed into the manifest version, and dropped, and
the only receipt any of them got was `no_steps_artifact_unsupported`, which described this
function rather than the system. Law 4: knowledge is not shipped until Layer 4 can consume it,
TYPED. So each class now has a reader, and this module is where the three of them meet:

    rules (CLG-06)          `rule_compiler` -> compiled constraints; a blocking rule that fires
                            eliminates the plays in its own capability through `core.constraint`'s
                            existing tenant block seam, and names itself on the decision.
    heuristics (CLG-08)     `citations` -> quoted claims on the decision, byte-identical.
    models + frameworks     `citations` -> framing blocks: input material for the renderer.
    playbooks (CLG-07)      plays, with a cap that RANKS instead of sorting by filename.

`metadata["weld"]` carries all of it plus the receipt, and `decision_maker` reads three fields out
of it — nothing here decides anything, which is Law 1.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any

from genios_engine.contracts.domain_expertise import (
    BusinessSituationObject,
    ExpertisePackage,
    SituationContextSlice,
    require_weld_receipt,
)
from genios_engine.platform.canonical import stable_id
from genios_engine.contracts.reasoning import (
    RANKING_WEIGHTS_V2,
    CapabilityManifest,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerSpec,
)
from genios_engine.packs.compiler.context_adapter import ContextAdapter
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason.decision_maker import SITUATION_IMPORTANCE_KEY
from genios_engine.reason.plan import CONTEXT_AWARE_SELECTION_KEY, LATENCY_CEILING_KEY

from .citations import UNDATED, bind_citations, descending_date
from .play_priors import (
    EFFORT_DELTA_KEY,
    IMPACT_DELTA_KEY,
    RISK_REDUCTION_KEY,
    SUCCESS_DELTA_KEY,
    derive_play_priors,
    play_deltas,
)
from .rule_compiler import artifact_class, compile_package_rules, play_id_for
from .situation_projection import SituationProjection

ADAPTER_ID = "expertise_to_capability"
# 2.0.0 — the typed consumers (doc 03, wave Y1). Every artifact class the corpus carries now has
# a reader at this seam, so a manifest built by 1.0.0 and one built by this version are different
# objects even from identical knowledge: the version says which is which.
ADAPTER_VERSION = "2.0.0"

#: The weld's own schema name, carried in `manifest.metadata["weld"]` so a downstream reader can
#: tell a manifest that carries compiled doctrine from one that predates the typed consumers.
WELD_SCHEMA = "weld.v1"
_REQUIRED = FailurePolicy.REQUIRED


def _executable_required_fields(package: ExpertisePackage) -> tuple[str, ...]:
    """The graph fact paths Layer 4 must pull, taken only from EXECUTABLE inference patterns.

    `needs_signal` / `requires_signals` patterns name inputs that do not exist yet, so their
    fields are skipped — pulling them would fail the native context selector for no benefit.
    """
    fields: set[str] = set()
    for obj in package.objects:
        definition = obj.get("definition") if isinstance(obj, Mapping) else None
        patterns = (definition or {}).get("inference_patterns") or {}
        if not isinstance(patterns, Mapping):
            continue
        for group in ("deterministic", "heuristic"):
            for pattern in patterns.get(group, []) or []:
                if not isinstance(pattern, Mapping) or pattern.get("status") != "executable":
                    continue
                for path in pattern.get("evidence_fields", []) or []:
                    fields.add(str(path))
                for cond in pattern.get("when", []) or []:
                    if isinstance(cond, Mapping) and cond.get("path"):
                        fields.add(str(cond["path"]))
    return tuple(sorted(fields))


def _universal_required_fields(package: ExpertisePackage) -> tuple[str, ...]:
    """Fields EVERY executable pattern needs — the ones without which nothing can run.

    The selector should pull the union of what any pattern might use; the sufficiency gate must
    ask for far less. Stamping the union onto `core.context` made a single value-dependent pattern
    veto the whole capability: `expertise.opportunity` requires `deal.value` because one pattern
    reads it, and almost no email states a deal size, so all 18 situations on the design partner's
    org returned INSUFFICIENT_CONTEXT while every other field they needed was present.

    That contradicted this DAG's own stated intent — "a thin situation degrades confidence instead
    of being blocked out of reasoning entirely". A pattern whose inputs are absent simply does not
    fire; the patterns that CAN fire still should.
    """
    per_pattern: list[set[str]] = []
    for obj in package.objects:
        definition = obj.get("definition") if isinstance(obj, Mapping) else None
        patterns = (definition or {}).get("inference_patterns") or {}
        if not isinstance(patterns, Mapping):
            continue
        for group in ("deterministic", "heuristic"):
            for pattern in patterns.get(group, []) or []:
                if not isinstance(pattern, Mapping) or pattern.get("status") != "executable":
                    continue
                fields = {str(f) for f in pattern.get("evidence_fields", []) or []}
                fields |= {str(c["path"]) for c in pattern.get("when", []) or []
                           if isinstance(c, Mapping) and c.get("path")}
                if fields:
                    per_pattern.append(fields)
    if not per_pattern:
        return ()
    return tuple(sorted(set.intersection(*per_pattern)))


def _default_dag(required_fields: tuple[str, ...],
                 authored_priority_bp: int | None = None,
                 blocked_play_ids: tuple[str, ...] = ()) -> tuple[ReasonerSpec, ...]:
    """A conservative, situation-agnostic reasoning DAG that always terminates in a decision.

    understand (context) -> evaluate (risk) -> the mandatory REQUIRED constraint -> rank/score
    (priority + confidence, both sourced from risk) -> plan. No situation-specific gating unit, so
    a thin situation degrades confidence instead of being blocked out of reasoning entirely.
    """
    context = ReasonerSpec(
        "core.context", "1.0.0",
        required_fields=required_fields,
        failure_policy=_REQUIRED,
    )
    risk = ReasonerSpec(
        "core.risk", "1.0.0",
        dependencies=("core.context",),
        failure_policy=_REQUIRED,
    )
    # THE ORGANISATION BRAIN'S ONE HARD LEVER. `core.constraint` already reads
    # `blocked_play_ids` off its own config and eliminates those plays with a
    # `tenant_policy_block` row that `reason/store.py` and `reason/authority.py` both re-prove —
    # a seam built for exactly this and never wired to the brain that should drive it. An
    # organisation rule now removes an option BEFORE ranking, which is the difference between a
    # policy and a preference.
    constraint_config: dict[str, object] = {}
    if blocked_play_ids:
        constraint_config["blocked_play_ids"] = list(blocked_play_ids)
    constraint = ReasonerSpec(
        "core.constraint", "1.0.0",
        dependencies=("core.context",),
        input_kind="candidate_plays",
        output_kind="candidate_checks",
        config=constraint_config,
        failure_policy=_REQUIRED,
    )
    # `core.risk` measures pressure; it does not RULE on priority, so the declared-override path
    # found nothing and every compiled candidate fell back to a neutral 5000 utility — which is
    # why every compiled card scored exactly 50. The situation author already ruled: the corpus
    # carries 30 distinct `priority_bp` values across 48 situations. Handing that ruling to the
    # unit as config is what turns it back into a ranking.
    priority_config: dict[str, object] = {"source_reasoner": "core.risk"}
    if authored_priority_bp is not None:
        priority_config["authored_priority_bp"] = int(authored_priority_bp)
    priority = ReasonerSpec(
        "core.priority", "1.0.0",
        dependencies=("core.risk", "core.constraint"),
        config=priority_config,
        failure_policy=_REQUIRED,
    )
    confidence = ReasonerSpec(
        "core.confidence", "1.0.0",
        dependencies=("core.risk",),
        config={"source_reasoner": "core.risk"},
        failure_policy=_REQUIRED,
    )
    planning = ReasonerSpec(
        "core.planning", "1.0.0",
        dependencies=("core.constraint", "core.priority", "core.confidence"),
        input_kind="ranked_candidates",
        output_kind="planning_checks",
        failure_policy=_REQUIRED,
    )
    return (context, risk, constraint, priority, confidence, planning)


# =================================================================================================
# WAVE Z1 · THE STAGED ROSTER (doc 01 C1, doc 02 U1/U2)
# =================================================================================================
#
# `_default_dag` above schedules six units: context, risk, constraint, priority, confidence,
# planning. Twenty-three unit ids are registered (`reasoners.default_registry`, counted rather
# than remembered), and the four categories of the frozen architecture reason about time,
# dependencies, policy, opportunity, impact, cost, resource, scheduling, tradeoffs, alternatives,
# validation and recommendation — none of which has ever run on this lane. Worse, the six that DO
# run, run half-blind: `core.risk`
# reads `drop_bp` from `core.temporal` and `coverage_bp` from `core.relationship`, and neither was
# scheduled, so two of its three plugins have been correctly silent since the day it shipped.
#
# THE MECHANISM IS NOT NEW. `reason/plan.py` has carried a deterministic, receipted Unit Selector
# since it was written and no manifest has ever switched it on. This roster declares the full
# family, marks everything that is not load-bearing OPTIONAL with the inputs it actually reads,
# and sets `context_aware_selection`. The selector then drops what this situation cannot feed and
# says so, per unit, by name — which is the only honest way to run a twenty-unit roster.
#
# WHAT DECIDES WHETHER A UNIT IS DECLARED AT ALL. Two different questions, and conflating them is
# how a roster becomes noise:
#
#   does this EXPERTISE read anything this unit can use?   -> the manifest declares it, or does
#                                                             not, and `metadata["roster"]` says
#                                                             which and why
#   does this SITUATION carry that input?                  -> the selector schedules it, or drops
#                                                             it with a `SkippedStep` receipt
#
# The first question is answered against the package's own executable inference patterns — the
# fact paths the corpus itself names — so nothing here invents a vocabulary. A unit whose roles
# bind nothing is left out with a receipt naming its candidates, rather than declared with fields
# no authored pattern ever asked for: those names would enter `core.context`'s completeness
# denominator (`context_unit.declared_fields` unions every reasoner's `required_fields`) and make
# every situation read as less complete than it is. Binding only to fields the expertise already
# selects means the denominator cannot move.
#
# WHY AT MOST ONE FIELD IS DECLARED PER UNIT. The orchestrator refuses a unit when ANY declared
# field is missing (`orchestrator.execute` -> `required_missing`), while the selector drops it only
# when EVERY declared field is missing. Declaring three fields therefore buys one extra drop case
# and three extra refusal cases. So a unit declares the single field it most needs — the one whose
# absence means it has nothing to read — and reads everything else through config, which it can do
# because `native._selected_fields` pulls the union of the capability's `selection_fields` into the
# snapshot whether a unit declared it or not.

#: Fact paths that answer "when did the other side last move?". Both spellings: Layer 2 writes
#: `thread.last_inbound` on people and threads, and the corpus's sales patterns name
#: `deal.last_inbound` on the deal. Preference order is L2's own spelling first.
_INBOUND_MOMENTS: tuple[str, ...] = ("thread.last_inbound", "deal.last_inbound")

#: "When did we last move?" — the mirror of the above.
_OUTBOUND_MOMENTS: tuple[str, ...] = ("thread.last_outbound", "deal.last_outbound")

#: Every dated event `core.timeline` can arrange into a shape.
_TIMELINE_MOMENTS: tuple[str, ...] = _INBOUND_MOMENTS + _OUTBOUND_MOMENTS + ("meeting.start_at",)

#: Dated obligations a situation can be materially late for — the input to U5's urgency ladder.
#: `commitment.due_at` is the one the corpus and Layer 2 both carry; `deal.close_date` is
#: `core.scheduling`'s own default and binds the day a connector writes it.
_DEADLINES: tuple[str, ...] = ("commitment.due_at", "deal.close_date")

#: Proportions `core.temporal` can read as engagement. `derived.sentiment` is deliberately absent:
#: it is signed, and a negative sentiment read through `ratio_bp` clamps to zero, which this unit
#: would publish as total engagement collapse. A wrong reading is worse than no reading.
_ENGAGEMENT_RATIOS: tuple[str, ...] = ("derived.engagement", "derived.momentum")

#: The state of the relationship itself, for `core.relationship`'s anchor. Only a genuine status
#: qualifies: the unit compares it to an expected value and reports `linked_open_deal` or not, so
#: binding it to `thread.ball_in_court` would put a false reading in the trace to keep a unit busy.
_RELATIONSHIP_STATUS: tuple[str, ...] = ("deal.status",)

#: What this work is worth, for `core.impact` and `core.policy`'s approval threshold.
_MONEY: tuple[str, ...] = ("deal.value",)

#: Who would carry the work out, for `core.dependency`, `core.opportunity` and `core.resource`.
_OWNER: tuple[str, ...] = ("deal.owner",)

#: Which values of a bound status fact mean the work is STILL LIVE. `core.opportunity` refuses a
#: status field with no vocabulary — correctly, because "is `negotiation` still open?" is domain
#: knowledge and a core unit that answered it would be shipping one vertical to every tenant. The
#: answer belongs to a manifest, so it is stated here, per fact, for the compiled lane; the same
#: vocabulary is authored by hand on the native sales capability
#: (`packs/capabilities/deal_cooling_v2`), which is the sibling declaration to compare against
#: when either moves. A candidate with no entry here is never bound to a status role: a guess
#: about what counts as live is exactly what the unit refused to make.
_ACTIVE_STATUSES: Mapping[str, tuple[str, ...]] = {
    "deal.status": ("open", "active", "in_progress", "negotiation"),
}

#: Approval gates. Restated rather than imported from `reasoners/dependency_unit.py`: a core unit's
#: defaults are that unit's business, and importing them would make this adapter fail to load the
#: day the roster renames a constant. `tests/reason/adapters/test_roster_v2.py` asserts the two
#: lists agree, so the copy cannot drift silently either.
_GATE_FIELDS: tuple[str, ...] = ("approval.status", "finance.approval_status",
                                 "legal.review_status", "procurement.status",
                                 "security.review_status")


@dataclass(frozen=True, slots=True)
class _RosterUnit:
    """One unit's place in the compiled roster: its edges, its budget, and what it reads.

    `roles` and `list_roles` map a unit's own config key to the fact paths that can fill it, in
    preference order. `gates_on` names the roles whose bound field is DECLARED (and therefore
    gates the unit through the selector); `essential` names the roles without which the unit is
    not declared at all. `always` is the opposite claim, and it has to be stated in words: a unit
    that can never be dropped for want of a fact must say why, or "it never drops" is
    indistinguishable from "nobody declared its inputs".
    """

    unit_id: str
    dependencies: tuple[str, ...] = ()
    required: bool = False
    latency_budget_ms: int = 25
    roles: tuple[tuple[str, tuple[str, ...]], ...] = ()
    list_roles: tuple[tuple[str, tuple[str, ...]], ...] = ()
    gates_on: tuple[str, ...] = ()
    essential: tuple[str, ...] = ()
    sources: tuple[tuple[str, str], ...] = ()
    config: Mapping[str, Any] = field(default_factory=dict)
    input_kind: str = "context_snapshot"
    output_kind: str = "finding"
    always: str | None = None


#: The roster, in the four categories of the frozen architecture. Dependencies are Globe's shape
#: where Globe states one (`tradeoff <- risk, opportunity, impact, cost`;
#: `validation <- risk, opportunity, impact, confidence`) and each unit's own declared sources
#: otherwise — an axis whose source is not a dependency is an axis that can never read, which is
#: precisely the defect `core.effort` was.
_ROSTER: tuple[_RosterUnit, ...] = (
    # --- Category 1 · Situation Understanding ----------------------------------------------------
    _RosterUnit("core.context", required=True, latency_budget_ms=40,
                always="the situation's own completeness is never absent"),
    _RosterUnit("core.temporal", ("core.context",), latency_budget_ms=20,
                roles=(("engagement_field", _ENGAGEMENT_RATIOS),
                       ("timestamp_field", _INBOUND_MOMENTS)),
                gates_on=("engagement_field",), essential=("engagement_field",)),
    _RosterUnit("core.relationship", ("core.context",), latency_budget_ms=20,
                roles=(("status_field", _RELATIONSHIP_STATUS),),
                gates_on=("status_field",), essential=("status_field",),
                config={"status_location": "root", "target_relationships": 3}),
    _RosterUnit("core.timeline", ("core.context", "core.temporal"), latency_budget_ms=30,
                list_roles=(("timeline_fields", _TIMELINE_MOMENTS),
                            ("deadline_fields", _DEADLINES)),
                gates_on=("timeline_fields", "deadline_fields"),
                essential=("timeline_fields", "deadline_fields")),
    _RosterUnit("core.dependency", ("core.context",), latency_budget_ms=30,
                roles=(("owner_field", _OWNER),),
                list_roles=(("gate_fields", _GATE_FIELDS),),
                always="an absent prerequisite is this unit's subject; absence cannot starve it"),
    # --- Category 2 · Business Evaluation --------------------------------------------------------
    _RosterUnit("core.constraint", ("core.context",), required=True, latency_budget_ms=40,
                input_kind="candidate_plays", output_kind="candidate_checks",
                always="elimination is required before anything may be ranked"),
    _RosterUnit("core.policy", ("core.context",), latency_budget_ms=30,
                roles=(("approval_value_field", _MONEY),
                       ("approval_status_field", ("deal.approval_status",)),
                       ("do_not_contact_field", ("contact.do_not_contact",)),
                       ("consent_status_field", ("contact.consent_status",))),
                gates_on=("approval_value_field", "approval_status_field",
                          "do_not_contact_field", "consent_status_field"),
                essential=("approval_value_field", "approval_status_field",
                           "do_not_contact_field", "consent_status_field")),
    _RosterUnit("core.risk", ("core.context", "core.temporal", "core.relationship"),
                required=True, latency_budget_ms=25,
                sources=(("temporal_reasoner", "core.temporal"),
                         ("relationship_reasoner", "core.relationship")),
                always="pressure is the reading the whole lane already depends on"),
    _RosterUnit("core.opportunity", ("core.context", "core.temporal"), latency_budget_ms=25,
                roles=(("inbound_field", _INBOUND_MOMENTS),
                       ("outbound_field", _OUTBOUND_MOMENTS),
                       ("status_field", _RELATIONSHIP_STATUS),
                       ("owner_field", _OWNER)),
                sources=(("momentum_source", "core.temporal"),),
                gates_on=("inbound_field", "status_field", "owner_field"),
                essential=("inbound_field", "outbound_field", "status_field", "owner_field")),
    _RosterUnit("core.impact", ("core.context", "core.relationship"), latency_budget_ms=25,
                roles=(("value_field", _MONEY),),
                sources=(("relationship_reasoner", "core.relationship"),),
                always="account weight is read from the relationship prior, not from a fact"),
    _RosterUnit("core.cost", ("core.context", "core.temporal", "core.opportunity"),
                latency_budget_ms=30,
                roles=(("delay_field", _INBOUND_MOMENTS),),
                always="the effort of the declared plays is readable with no fact at all"),
    _RosterUnit("core.resource", ("core.context",), latency_budget_ms=25,
                roles=(("deadline_field", _DEADLINES), ("owner_field", _OWNER)),
                gates_on=("deadline_field", "owner_field"),
                essential=("deadline_field", "owner_field")),
    _RosterUnit("core.scheduling", ("core.context",), latency_budget_ms=30,
                roles=(("next_interaction_field", ("meeting.start_at",
                                                   "calendar.next_meeting_at")),
                       ("deadline_field", _DEADLINES),
                       ("last_contact_field", _OUTBOUND_MOMENTS),
                       ("quiet_until_field", ("schedule.quiet_until",))),
                gates_on=("next_interaction_field", "deadline_field", "last_contact_field",
                          "quiet_until_field"),
                essential=("next_interaction_field", "deadline_field", "last_contact_field",
                           "quiet_until_field")),
    # --- Category 3 · Optimization ---------------------------------------------------------------
    _RosterUnit("core.tradeoff",
                ("core.risk", "core.opportunity", "core.impact", "core.cost", "core.confidence",
                 "core.temporal"),
                latency_budget_ms=25,
                sources=(("benefit_source", "core.impact"),
                         ("certainty_source", "core.confidence"),
                         ("cost_source", "core.cost"),
                         ("reward_source", "core.opportunity"),
                         ("risk_source", "core.risk"),
                         ("speed_source", "core.temporal")),
                always="a tension is read from priors; it has no fact of its own"),
    _RosterUnit("core.alternative",
                ("core.constraint", "core.cost", "core.opportunity", "core.temporal", "core.risk"),
                latency_budget_ms=25,
                sources=(("inaction_cost_source", "core.cost"),
                         ("headroom_source", "core.opportunity"),
                         ("momentum_source", "core.temporal"),
                         ("exposure_source", "core.risk")),
                always="the options are the capability's own declared plays"),
    _RosterUnit("core.priority",
                ("core.constraint", "core.risk", "core.temporal", "core.timeline"),
                required=True, latency_budget_ms=20,
                always="urgency is resolved for every decision, or nothing can be ranked"),
    _RosterUnit("core.confidence", ("core.context", "core.risk"), required=True,
                latency_budget_ms=25,
                always="a thin snapshot must answer with low confidence, never with silence"),
    # --- Category 4 · Decision Support -----------------------------------------------------------
    _RosterUnit("core.validation",
                ("core.risk", "core.opportunity", "core.impact", "core.confidence"),
                latency_budget_ms=30,
                always="a conclusion is checked against itself, with or without facts"),
    _RosterUnit("core.recommendation", ("core.validation", "core.dependency"),
                latency_budget_ms=30,
                sources=(("dependency_source", "core.dependency"),),
                always="play support is read from the capability's own plays"),
    _RosterUnit("core.planning", ("core.constraint", "core.priority", "core.confidence"),
                required=True, latency_budget_ms=20,
                input_kind="ranked_candidates", output_kind="planning_checks",
                always="whether an outcome is observable is a property of the plays"),
)

#: The whole sequential run's declared ceiling. Every unit above declares its own budget and the
#: planner refuses the manifest when they exceed this — the refusal that makes a twenty-unit
#: roster safe to switch on. Tune the BUDGETS if a roster outgrows it; never this number, and
#: never the refusal (doc 01 C2).
ROSTER_LATENCY_CEILING_MS = 1_500

#: The receipt's schema name, in `metadata["roster"]`.
ROSTER_SCHEMA = "roster.v2"


def _bind_role(candidates: tuple[str, ...], available: frozenset[str],
               present: frozenset[str]) -> str | None:
    """The one fact path that fills a role, or None when this expertise names none.

    Two filters, in this order. A candidate must be a field the EXPERTISE reads (`available`, the
    union of the package's executable inference patterns) — anything else would be a fact nobody
    authored and nobody selects. Among those, a field this SITUATION actually carries wins, so the
    field a unit is gated on is a field that is there. Preference order breaks the remaining tie,
    deterministically.
    """
    eligible = [name for name in candidates if name in available]
    for name in eligible:
        if name in present:
            return name
    return eligible[0] if eligible else None


def authored_role_paths(domain: str) -> dict[str, tuple[str, ...]]:
    """`{role key: fact paths}` a domain declares for itself, in its `domain.yaml`.

    THE CANDIDATE LISTS ABOVE ARE A SALES VOCABULARY. `_OWNER` is `("deal.owner",)`, `_DEADLINES`
    is `("commitment.due_at", "deal.close_date")`, `_RELATIONSHIP_STATUS` is `("deal.status",)`.
    A support desk's owner is `ticket.assignee` and its deadline is `sla.breach_at`; a clinic's
    are `episode.clinician` and `appointment.starts_at`. None of those appears in any tuple here,
    so `_bind_role` returns None, the unit's essential role is unbound, and the unit is DECLINED
    — with a receipt saying "no declared field in this expertise", which is true and reads as
    the corpus's fault rather than the vocabulary's.

        roles:
          owner:    [ticket.assignee]
          deadline: [sla.breach_at]

    AUTHORED PATHS GO FIRST, then the shipped ones. A domain that names its own owner means it;
    the sales spellings stay behind as the fallback so a corpus that declares only `deadline`
    keeps everything else working. `_bind_role`'s two filters are unchanged — a path must still
    be one the EXPERTISE reads, and a path this situation carries still wins — so an authored
    name that nothing writes binds nothing, exactly as an unwritten shipped name does.
    """
    from genios_engine.platform.corpus import authored_domains

    for domain_id, data in authored_domains():
        if domain_id != domain:
            continue
        block = (data.get("roles") or {}) if isinstance(data, dict) else {}
        out: dict[str, tuple[str, ...]] = {}
        for key, paths in block.items():
            names = tuple(str(p).strip() for p in (paths or []) if str(p).strip())
            if names:
                out[str(key).strip()] = names
        return out
    return {}


def _bind_roles(unit: _RosterUnit, available: frozenset[str], present: frozenset[str],
                authored: "Mapping[str, tuple[str, ...]] | None" = None
                ) -> tuple[dict[str, Any], dict[str, str], dict[str, list[str]]]:
    """Resolve every role this unit declares into config. Returns (config, bound, bound_lists)."""
    config: dict[str, Any] = dict(unit.config)
    bound: dict[str, str] = {}
    bound_lists: dict[str, list[str]] = {}
    extra = authored or {}
    for key, candidates in unit.roles:
        name = _bind_role((*extra.get(key, ()), *candidates), available, present)
        if name is None:
            continue
        if key == "status_field" and unit.unit_id == "core.opportunity":
            # A status field with no live vocabulary is a question this manifest asked and did not
            # answer, and `core.opportunity` raises rather than guess. So the two travel together
            # or neither is bound.
            live = _ACTIVE_STATUSES.get(name)
            if not live:
                continue
            config["active_statuses"] = list(live)
        config[key] = name
        bound[key] = name
    for key, candidates in unit.list_roles:
        names = [name for name in candidates if name in available]
        if names:
            config[key] = names
            bound_lists[key] = names
    return config, bound, bound_lists


def _declared_field(unit: _RosterUnit, bound: Mapping[str, str],
                    bound_lists: Mapping[str, list[str]],
                    present: frozenset[str]) -> tuple[str, ...]:
    """The single field this unit is gated on, or `()` when it is gated on nothing.

    One field, never several: the orchestrator refuses a unit when ANY declared field is missing,
    while the selector drops it only when EVERY declared field is missing, so a second declared
    field buys one extra drop case and one extra refusal. The gate is therefore the single field
    whose absence means the unit has nothing at all to read; everything else it reads travels as
    config, which the snapshot supplies anyway.

    A field this situation CARRIES wins over one it merely might: gating a scheduled unit on a
    field that is not there would drop a unit that had something to say.
    """
    gated = [name for key in unit.gates_on
             for name in ([bound[key]] if key in bound else bound_lists.get(key, []))]
    for name in gated:
        if name in present:
            return (name,)
    return (gated[0],) if gated else ()


#: WHICH UNIT READS WHICH DELTA MAP. The four maps are the ONLY path from a measured unit output to
#: the ranking formula, and every one of them was authored in exactly one hand-written native
#: capability and nowhere on the compiled lane — so `core.impact`, `core.risk`,
#: `core.recommendation` and `core.cost` ran on every compiled tenant, emitted, and moved no score
#: by design. A key spelled here that the unit does not read is a silent no-op, which is the
#: failure being removed, so the pairing is a constant and
#: `tests/reason/adapters/test_play_priors.py` asserts each unit's source actually reads its key.
#: `core.cost` IS ABSENT ON PURPOSE, and finding out why is the reason this table is explicit.
#: `packs/capabilities/deal_cooling_v2.py` authors `play_effort_bp` in `core.cost`'s config and
#: **no code reads that key** — `cost_unit` corrects effort by comparing the play's declared
#: `effort_bp` against `_step_effort`, and has never looked for an authored map. Copying that key
#: onto the compiled lane would have shipped 228 playbooks' worth of config that nothing consumes,
#: which is the exact silent no-op the other three entries exist to remove. The effort component
#: gets its variance from the PRIOR instead (`play_priors._effort`), and `cost_unit` now reads the
#: same actor-weighted basis so the two cannot disagree.
_DELTA_CONSUMERS: Mapping[str, str] = {
    "core.impact": IMPACT_DELTA_KEY,
    "core.risk": RISK_REDUCTION_KEY,
    "core.recommendation": SUCCESS_DELTA_KEY,
}


def _package_domain(package) -> str:
    """Which domain this package belongs to, off the capabilities — the same place
    `capability_resolver` reads it when it matches a `pack_id`."""
    try:
        for capability in (getattr(package, "capabilities", None) or ()):
            domain = str((capability or {}).get("domain") or "").strip()
            if domain:
                return domain
    except Exception:      # noqa: BLE001 — an enrichment, never a reason to lose the roster
        return ""
    return ""


def _authored_roster(domain: str) -> tuple[_RosterUnit, ...]:
    """`_ROSTER`, tuned by whatever this domain declared. The shipped roster when it declared
    nothing — which is every domain today.

    WHAT A DOMAIN MAY SAY, and the honest limit. A genuinely new reasoning UNIT is still Python:
    a unit is a computation over a typed snapshot, and no YAML can supply one. What a domain can
    now state without a deploy is which of the seventeen apply to it, how long each may take, and
    which of its roles are load-bearing:

        reasoning:
          - unit: core.opportunity
            enabled: false            # a clinic has no pipeline; declining it every time is noise
          - unit: core.dependency
            latency_budget_ms: 80     # this domain's chains are deep and worth the wait
            essential: [owner_field]  # without an owner this analysis says nothing here

    THREE THINGS IT MAY NOT DO, each for a failure it would cause:

      * DISABLE A REQUIRED UNIT. `core.context` and the validation gate are `required=True`
        because a plan that skips them is a plan that hides a missing prerequisite behind a
        confident answer — the exact defect the orchestrator's own failure table calls dangerous.
        `enabled: false` on one is ignored, loudly in the receipt rather than silently.
      * INVENT A UNIT. A `unit:` naming nothing in `_ROSTER` is skipped; there is no computation
        behind the name and scheduling it would be scheduling nothing.
      * SET A BUDGET OF ZERO OR LESS. That is not "fast", it is "never runs", and a domain that
        wanted a unit off has `enabled: false` to say so plainly.
    """
    if not domain:
        return _ROSTER
    from genios_engine.platform.corpus import authored_domains

    declared: dict[str, dict] = {}
    try:
        for domain_id, data in authored_domains():
            if domain_id != domain:
                continue
            for entry in ((data.get("reasoning") or []) if isinstance(data, dict) else []):
                unit_id = str((entry or {}).get("unit") or "").strip()
                if unit_id:
                    declared[unit_id] = dict(entry)
            break
    except Exception:      # noqa: BLE001 — an enrichment; the shipped roster still runs
        return _ROSTER
    if not declared:
        return _ROSTER

    from dataclasses import replace

    out: list[_RosterUnit] = []
    for unit in _ROSTER:
        entry = declared.get(unit.unit_id)
        if entry is None:
            out.append(unit)
            continue
        if entry.get("enabled") is False and not unit.required:
            continue
        changes: dict = {}
        budget = entry.get("latency_budget_ms")
        try:
            if budget is not None and int(budget) > 0:
                changes["latency_budget_ms"] = int(budget)
        except (TypeError, ValueError):
            pass
        essential = entry.get("essential")
        if isinstance(essential, list):
            # ONLY ROLES THIS UNIT ACTUALLY DECLARES. Naming a role it does not have would make
            # the unit permanently undeclinable-but-unbindable — essential against a key that
            # can never be bound is a unit that never runs and never says why.
            known = {key for key, _ in (unit.roles + unit.list_roles)}
            named = tuple(str(k).strip() for k in essential if str(k).strip() in known)
            if named:
                changes["essential"] = named
        out.append(replace(unit, **changes) if changes else unit)
    return tuple(out)


def _package_roles(package) -> dict[str, tuple[str, ...]]:
    """The authored role map for whatever domain this package belongs to, or `{}`.

    The domain comes off the capabilities, which is where `capability_resolver` already reads it
    when it matches a `pack_id` — one answer to "which domain is this", not a second.
    """
    try:
        for capability in (getattr(package, "capabilities", None) or ()):
            domain = str((capability or {}).get("domain") or "").strip()
            if domain:
                return authored_role_paths(domain)
    except Exception:      # noqa: BLE001 — an enrichment; the shipped tuples still bind
        return {}
    return {}


def _roster_specs(package: ExpertisePackage, *, gate_fields: tuple[str, ...],
                  available: frozenset[str], present: frozenset[str],
                  authored_priority_bp: int | None,
                  blocked_play_ids: tuple[str, ...],
                  play_definitions: Mapping[str, Mapping[str, Any]] | None = None,
                  projection: SituationProjection | None = None
                  ) -> tuple[tuple[ReasonerSpec, ...], dict[str, Any]]:
    """The staged roster for one package, plus the receipt for everything it declined.

    Declaration happens in two passes because an edge may only point at a unit that survived the
    first: a dependency on a unit this expertise cannot feed would fail `topological_order`, and a
    `*_source` naming one is refused by the registry check that exists to catch exactly that.

    WAVE Z5 · WHERE THE PROJECTION IS CONSUMED (DLG-06). Two units, two different consumptions,
    and neither of them invents a reading:

      `core.context` DECLARES every projected fact this situation carries. Its declared set is
      the completeness denominator (`context_unit.declared_fields`) and `FactCoveragePlugin`
      cites the evidence of every declared field it finds — so Layer 2's trend, cohort position,
      anomaly, confidence axes and typed absences are read, counted and CITED by a registered
      unit on the live compiled lane, which is doc 06's IN-1 acceptance row. The unknown-typed
      names are NOT declared: they reach the same denominator through the snapshot's
      `missing_fields`, where they count as known absences rather than dropping the unit.

      `core.dependency` STOPS declaring the UNKNOWABLE ones. `PrerequisiteAbsencePlugin` reports
      a declared fact that is not in the snapshot as a blocker the workflow can go and clear —
      "go find it". For a fact path Layer 2 has typed UNKNOWABLE there is nothing to go to: no
      connected source could have carried it, and reporting it as a chaseable prerequisite is the
      exact negative inference `context.quality.missing` exists to refuse. They are withheld and
      NAMED in the receipt, so the withholding is visible rather than a shorter list.
    """
    projected_declared = projection.declared_fields if projection is not None else ()
    unknowable = frozenset(projection.unknowable_paths) if projection is not None else frozenset()
    # Built ONCE for the roster rather than per unit: four units read four different keys off one
    # derivation, and deriving it four times would be four chances for them to disagree about the
    # same play.
    deltas = play_deltas(play_definitions or {})
    # READ ONCE for the whole roster: seventeen units asking the same corpus the same question
    # is seventeen file reads and seventeen chances to disagree about which domain they are in.
    authored_roles = _package_roles(package)
    roster = _authored_roster(_package_domain(package))
    declined: dict[str, dict[str, Any]] = {}
    kept: list[tuple[_RosterUnit, dict[str, Any], dict[str, str], dict[str, list[str]]]] = []
    for unit in roster:
        config, bound, bound_lists = _bind_roles(unit, available, present,
                                                 authored=authored_roles)
        if unit.essential and not (set(bound) | set(bound_lists)) & set(unit.essential):
            declined[unit.unit_id] = {
                "reason": "no_declared_field_in_this_expertise",
                "roles": sorted(unit.essential),
                "candidates": sorted({name for key, names in (unit.roles + unit.list_roles)
                                      if key in unit.essential for name in names}),
            }
            continue
        kept.append((unit, config, bound, bound_lists))

    declared_ids = {unit.unit_id for unit, _, _, _ in kept}
    specs: list[ReasonerSpec] = []
    receipt_units: dict[str, Any] = {}
    pruned: dict[str, list[str]] = {}
    for unit, config, bound, bound_lists in kept:
        for key, source in unit.sources:
            if source in declared_ids:
                config[key] = source
            else:
                pruned.setdefault(unit.unit_id, []).append(f"{key}={source}")
        dependencies = tuple(name for name in unit.dependencies if name in declared_ids)
        if unit.unit_id == "core.context":
            declared_fields = tuple(sorted(set(gate_fields) | set(projected_declared)))
        elif unit.unit_id == "core.dependency":
            # The prerequisites ARE the expertise's own executable fields: this unit's subject is
            # what the reasoning waits on, and Layer 3 is the only layer that knows what that is.
            # MINUS the paths Layer 2 typed UNKNOWABLE — see this function's docstring.
            config["prerequisite_fields"] = sorted(available - unknowable)
            declared_fields = ()
        else:
            declared_fields = _declared_field(unit, bound, bound_lists, present)
        if unit.unit_id == "core.constraint" and blocked_play_ids:
            config["blocked_play_ids"] = list(blocked_play_ids)
        # K1 · THE MEASURED HALF REACHES THE SCORE. Without this key the unit measures its
        # dimension, publishes the metric, iterates an empty authored map and emits no adjustment
        # at all — which is what `core.impact`, `core.risk`, `core.recommendation` and `core.cost`
        # have done on every compiled decision this engine has made. The ceiling per play comes
        # from the same authored evidence the priors read (`adapters/play_priors.play_deltas`), so
        # a play that declared a measurable outcome is tilted further by a measured stake than a
        # procedural checklist is.
        delta_key = _DELTA_CONSUMERS.get(unit.unit_id)
        if delta_key is not None and deltas.get(delta_key):
            config[delta_key] = dict(deltas[delta_key])
        if unit.unit_id == "core.priority" and authored_priority_bp is not None:
            # THE AUTHOR'S RULING, and no `source_reasoner`. A declared source disables
            # `MaximumUrgencyPlugin` outright, and the six-unit lane declared `core.risk` — a unit
            # that publishes no `urgency_bp` — so every compiled decision read the neutral 5,000
            # midpoint. With no source declared, priority resolves max-wins across every prior it
            # can see, which is what `core.timeline`'s urgency ladder (doc 02 U5) exists to feed.
            config["authored_priority_bp"] = int(authored_priority_bp)
        specs.append(ReasonerSpec(
            unit.unit_id, "1.0.0",
            dependencies=dependencies,
            required_fields=declared_fields,
            latency_budget_ms=unit.latency_budget_ms,
            failure_policy=(_REQUIRED if unit.required else FailurePolicy.OPTIONAL),
            input_kind=unit.input_kind,
            output_kind=unit.output_kind,
            config=config,
        ))
        receipt_units[unit.unit_id] = {
            "policy": "required" if unit.required else "optional",
            "declared_fields": list(declared_fields),
            "bound": dict(sorted(bound.items())),
            "bound_lists": {key: sorted(value) for key, value in sorted(bound_lists.items())},
            "dependencies": list(dependencies),
            "never_dropped": unit.always,
        }

    receipt = {
        "schema": ROSTER_SCHEMA,
        "declared": sorted(declared_ids),
        "declared_count": len(declared_ids),
        "required": sorted(unit.unit_id for unit, _, _, _ in kept if unit.required),
        "optional": sorted(unit.unit_id for unit, _, _, _ in kept if not unit.required),
        "gated_on_a_fact": sorted(unit_id for unit_id, row in receipt_units.items()
                                  if row["declared_fields"]),
        "declined": dict(sorted(declined.items())),
        "pruned_sources": {unit_id: sorted(values) for unit_id, values in sorted(pruned.items())},
        "units": dict(sorted(receipt_units.items())),
        "available_fields": sorted(available),
        "latency_ceiling_ms": ROSTER_LATENCY_CEILING_MS,
        "sequential_budget_ms": sum(spec.latency_budget_ms for spec in specs),
        # WAVE Z5. Present only when a projection reached this roster, so a manifest built
        # without one is byte-identical to what it was.
        **({"situation_projection": {
            "declared_on_core_context": list(projected_declared),
            "unknown_typed": list(projection.unknown_fields),
            # The withheld prerequisites, NAMED. A shorter `prerequisite_fields` with no record
            # of what left it is indistinguishable from an expertise that reads fewer facts.
            "prerequisites_withheld_unknowable": sorted(available & unknowable),
        }} if projection is not None else {}),
    }
    return tuple(specs), receipt


#: How many plays a manifest carries. A cap is legitimate (the Decision Maker ranks a small
#: candidate set, not a corpus); a SILENT cap is not — see `_plays`' receipt fields.
#: How many authored strategies may reach Layer 4 as candidates.
#:
#: Raised from 4. A play is a CANDIDATE, not a card — the Decision Maker picks one — so the cap
#: was never limiting output, it was limiting choice, and it did so by dropping whatever sorted
#: last alphabetically. `account_admin` routes thirteen capabilities and therefore thirteen
#: playbooks: nine authored strategies were cut by rule id, which is file-naming, not judgment.
#:
#: Still bounded, and deliberately. An unbounded list would let one wide route dominate the
#: reasoning budget, and `play_receipt` records anything still cut — a silent truncation is the
#: failure this number is meant to make visible, not the number itself.
MAX_PLAYS = 16


def _learned_play_efficacy(package: ExpertisePackage) -> dict[str, tuple[int, str]]:
    """This tenant's OWN measured success rate per play — {play_id: (success_bp, entry_id)}.

    THE CONVENTION IS L6's, NOT INVENTED HERE. `feedback/units.unit_recommendation_learning`
    already publishes into the ADAPTIVE brain, one entry per play, carrying
    ``{"play": <id>, "success_rate_bp": ..., "attention_per_outcome_bp": ..., "efficacy_bp": ...}``
    — real outcomes, labelled, over a minimum observation count the learning policy enforces. It
    has been writing that shape into `learned_brain_entries` and nothing has ever read it.

    `success_rate_bp` rather than `efficacy_bp` deliberately. Efficacy discounts success by the
    attention the play cost, which is a judgment about whether a play is WORTH it — and that
    judgment belongs to the ranking model, which already penalises `effort_bp` on its own terms.
    Feeding efficacy here would apply the attention penalty twice.
    """
    learned: dict[str, tuple[int, str]] = {}
    for entry in package.adaptive_preferences or ():
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        play_id = str(value.get("play") or "").strip()
        rate = value.get("success_rate_bp")
        if not play_id or isinstance(rate, bool) or not isinstance(rate, int):
            continue
        learned[play_id] = (max(0, min(10_000, rate)), str(entry.get("entry_id") or ""))
    return learned


def _blocked_play_ids(package: ExpertisePackage) -> tuple[str, ...]:
    """Plays this ORGANISATION has forbidden, for `core.constraint`'s tenant block list.

    The constraint unit already owns this seam and documents it as "a hard, id-level retirement
    that a tenant can apply without touching authored expertise" — it emits a `tenant_policy_block`
    ELIMINATE row, which `reason/store.py` and `reason/authority.py` both re-prove. So an
    organisation rule reaches the decision through a path that was BUILT for it and that two
    independent verifiers already understand; no new check row, no frozen-shape change, no replay
    break. It was simply never connected to the organisation brain.

    Only permission-axis entries may block. `packs/compiler/runtime_brains._PERMISSION_CATEGORIES`
    is the same list the compiler uses to decide which entries carry permission authority at all,
    read from there rather than restated, so the two cannot drift into disagreeing about what
    counts as a policy.
    """
    from genios_engine.packs.compiler.runtime_brains import _PERMISSION_CATEGORIES

    blocked: set[str] = set()
    for entry in package.organization_rules or ():
        if not isinstance(entry, Mapping):
            continue
        value = entry.get("value")
        if not isinstance(value, Mapping):
            continue
        category = str(value.get("category") or value.get("kind") or "").lower()
        if category not in _PERMISSION_CATEGORIES:
            continue
        named = value.get("blocked_play_ids") or value.get("blocks_plays")
        if isinstance(named, str):
            named = [named]
        for item in list(named or ()) + [value.get("blocks_play")]:
            if isinstance(item, str) and item.strip():
                blocked.add(item.strip())
    return tuple(sorted(blocked))


#: Which artifact classes are consumed by a reader OTHER than the play converter, and by which
#: one. This mapping is the whole of the J1 gate's "`no_steps_artifact_unsupported` receipts on
#: rules / heuristics / models / frameworks: 0" — those four now have consumers, so the receipt
#: that said nobody read them is replaced by a receipt naming who does.
_CONSUMED_ELSEWHERE: Mapping[str, str] = {
    "rule": "consumed_as_compiled_constraint",
    "heuristic": "consumed_as_citation",
    "mental_model": "consumed_as_framing_block",
    "decision_framework": "consumed_as_framing_block",
}

#: Sorts last in the recency term. THE citation binder's constant, imported rather than restated,
#: so "undated" cannot come to mean two different positions in two rankings.
_UNDATED = UNDATED


def _capability_recency(package: ExpertisePackage) -> dict[str, str]:
    """capability id -> the date its document was last stamped.

    Doc 03 asks the play cap to rank on "capability admission recency (re-stamped = maintained)".
    The `admission` block holds a content hash and NO timestamp — re-stamping proves the reviewer
    saw the current bytes, not when — so the date the corpus actually carries is
    `metadata.last_updated`, which `_tools/admit.py` and the author move together. Named here
    rather than quietly substituted: this is a proxy, and a reader deserves to know which.
    """
    out: dict[str, str] = {}
    for capability in package.capabilities or ():
        if not isinstance(capability, Mapping):
            continue
        definition = capability.get("definition")
        metadata = definition.get("metadata") if isinstance(definition, Mapping) else None
        last_updated = (metadata or {}).get("last_updated") if isinstance(metadata, Mapping) else None
        out[str(capability.get("id") or "")] = str(last_updated or _UNDATED)
    return out


def _authored_play_priority(definition: Mapping[str, Any]) -> int | None:
    """A playbook's own declared priority, in basis points, or None when it declares none.

    Nothing in the shipped corpus declares one. The term exists because doc 03 names it and
    because an author who wants to order two plays inside one capability has nowhere else to say
    so; the receipt reports how many plays used it, so "this rank term is currently constant" is a
    number rather than a thing to rediscover.
    """
    metadata = definition.get("metadata") if isinstance(definition, Mapping) else None
    raw = (metadata or {}).get("priority_bp") if isinstance(metadata, Mapping) else None
    if isinstance(raw, bool) or not isinstance(raw, int) or not 0 <= raw <= 10_000:
        return None
    return raw


def _plays(package: ExpertisePackage) -> tuple[tuple[PlayDefinition, ...], dict,
                                               dict[str, Mapping[str, Any]]]:
    """Playbook `expert_rules` (definitions carrying steps) become read-only review plays —
    plus a RECEIPT of everything this conversion refused or cut.

    The old shape was three silent judgments in a row: a rule without steps was `continue`d (no
    trace), the fifth play onward was `break`ed (no trace), and an empty result appended a
    hardcoded "review the situation" (indistinguishable from authored content). Consequence,
    `[MODELLED]` but structural: a 1,748-file corpus could compile successfully, hash into a new
    manifest version, and still emit one generic play — activation would LOOK successful while
    producing generic output, which is precisely the state L3's flip must be able to detect.

    CLG-07 · THE CAP IS LEGITIMATE; ALPHABETICAL SELECTION WAS NOT. Ordering was deterministic
    (rule id, not corpus iteration order) and that fixed the enumeration bug — but it left the
    SELECTION to file naming. On the design partner's `deal` route that is not academic: 21
    playbooks compile, sixteen survive, and the five cut are `need_analysis`, `pipeline_management`,
    `procurement`, `stakeholder_mapping` and `value_proposition` — four of which declare the very
    situation that fired — while five `icp_definition` plays survive because "i" sorts before "n".
    A cut decided by the first letter of a filename is not judgment.

    Plays are now ranked by what the author actually declared, in doc 03's order:

      1. SITUATION FIT   the play's `when_to_use.situations` names one of the situations that
                         matched. The strongest authored statement of relevance there is.
      2. ADMISSION RECENCY  the owning capability's `metadata.last_updated` — a re-stamped
                         capability is a maintained one. The `admission` block itself carries only
                         a content hash and no date, so this is the recency signal the corpus
                         actually holds, named here rather than implied.
      3. AUTHORED PRIORITY  `metadata.priority_bp` on the playbook, if declared. NOTHING in the
                         shipped corpus declares one today, so this term is currently constant and
                         the receipt says so with a count rather than leaving it to be discovered.
      4. RULE ID         the final tie-break, LAST — where a deterministic tie-break belongs, not
                         first, where it was the selector.

    Everything Layer 3 supplies is advisory knowledge, so every play is read_only and leaves any
    outreach to explicit human approval.
    """
    situations = frozenset(str(item) for item in
                           (package.metadata.get("matched_situation_ids") or ()))
    recency = _capability_recency(package)
    candidates: list[tuple[tuple, str, PlayDefinition]] = []
    skipped: dict[str, str] = {}
    seen: set[str] = set()
    fits = 0
    prioritised = 0
    efficacy = _learned_play_efficacy(package)
    # K1 · the derivation's own workings, kept per play so the receipt can carry the arithmetic and
    # `_roster_specs` can author the delta maps from the SAME declared evidence the priors read.
    # Keyed by play id rather than rule id because that is what every downstream consumer — the
    # config maps, the receipt, the candidate rows — addresses a play by.
    priors_by_play: dict[str, Any] = {}
    definitions_by_play: dict[str, Mapping[str, Any]] = {}
    for position, rule in enumerate(package.expert_rules):
        if not isinstance(rule, Mapping):
            skipped[f"unmapped_{position}"] = "not_a_mapping"
            continue
        rule_id = str(rule.get("id") or f"rule_{position}")
        definition = rule.get("definition") or {}
        klass = artifact_class(rule)
        if klass in _CONSUMED_ELSEWHERE:
            # THE RECEIPT THAT USED TO SAY `no_steps_artifact_unsupported` FOR ALL OF THESE. It
            # was accurate about this function and wrong about the system: a heuristic has no steps
            # because it is a claim, not a procedure, and it now travels as a citation. Naming the
            # consumer per class is what makes "5 of 5 artifact classes have a typed consumer"
            # readable from the receipt instead of assertable only in a review.
            skipped[rule_id] = _CONSUMED_ELSEWHERE[klass]
            continue
        raw_steps = definition.get("steps") if isinstance(definition, Mapping) else None
        if not raw_steps:
            # A PLAYBOOK with no steps is a real authoring defect (the schema requires them); an
            # artifact class this adapter has never heard of is the honest survivor of the old
            # receipt, and it stays, because the day a sixth class is authored this is the line
            # that says nobody consumes it.
            skipped[rule_id] = ("playbook_without_steps" if klass == "playbook"
                                else "no_steps_artifact_unsupported")
            continue
        steps = tuple(
            str(step.get("description") or step.get("name")) if isinstance(step, Mapping)
            else str(step)
            for step in raw_steps
        )
        steps = tuple(s for s in steps if s and s != "None")
        if not steps:
            skipped[rule_id] = "steps_empty_after_normalisation"
            continue
        # ONE spelling of a play id, shared with the rule compiler's scope map. Two copies of
        # this line would let a rule's blast radius and the manifest's play list disagree about
        # what the same playbook is called, which is an elimination pointing at nothing.
        play_id = play_id_for(rule_id)
        if play_id in seen:
            skipped[rule_id] = "duplicate_play_id"
            continue
        seen.add(play_id)
        # THE ORG'S OWN MEASURED SUCCESS RATE, where it has one. `success_probability_bp` is a
        # weighted term in `decision_maker._weighted_utility`, and every compiled play carried the
        # 5,000bp default — so the same expertise ranked its options identically for a tenant
        # where a play works and one where it does not. This is the whole of "it learns how we
        # operate", and it is not a new mechanism: the field already means exactly this, the
        # learning already measured it, and the two had simply never been joined.
        learned = efficacy.get(play_id)
        identity = definition.get("identity") if isinstance(definition, Mapping) else {}
        owner = str((identity or {}).get("owner_capability") or "")
        declared = frozenset(str(item) for item in
                             ((definition.get("when_to_use") or {}).get("situations") or ()))
        fit = bool(declared & situations)
        priority_bp = _authored_play_priority(definition)
        fits += int(fit)
        prioritised += int(priority_bp is not None)
        rank = (0 if fit else 1, descending_date(recency.get(owner, _UNDATED)),
                -(priority_bp or 0), play_id)
        # K1 · THE THREE COMPONENTS THIS LANE NEVER MEASURED. Until now `PlayDefinition` was
        # constructed without `impact_bp`, `effort_bp` or `risk_bp`, so every compiled play took
        # the dataclass defaults — 5,000 apiece — and 45% of the ranking formula's weight sat on
        # three numbers that were identical across every candidate on every situation. The priors
        # are read off what the AUTHOR declared (steps and their actors, failure modes, limits,
        # declared outcomes, status); `adapters/play_priors` carries the derivation and the
        # arithmetic receipt for each term.
        priors = derive_play_priors(definition, situation_fit=fit)
        priors_by_play[play_id] = priors
        definitions_by_play[play_id] = definition
        candidates.append((rank, play_id, PlayDefinition(
            play_id, "1.0.0", str(definition.get("name") or play_id)[:200],
            steps=steps,
            read_only=True,
            impact_bp=priors.impact_bp,
            effort_bp=priors.effort_bp,
            risk_bp=priors.risk_bp,
            # MEASURED BEATS AUTHORED, and only in that direction. The org's own outcomes win
            # wherever the learning has them; the authored prior replaces the flat 5,000 fallback
            # everywhere else, which is every play on a tenant that has not yet accumulated any —
            # i.e. every play on day one, which is exactly when ranking has to work.
            success_probability_bp=learned[0] if learned else priors.success_bp,
            tags=("human_approval", "playbook"),
            metadata={"source": "expert_playbook", "external_recipient_required": False,
                      # Provenance on the play itself, so an auditor reading a candidate can see
                      # WHICH learned entry moved it rather than inferring it from a score.
                      **({"learned_success_from": learned[1]} if learned else {}),
                      "success_source": "learned" if learned else "authored_prior",
                      # WHY THE EFFORT BASIS TRAVELS ON THE PLAY. `PlayDefinition.steps` is a
                      # tuple of STRINGS — the actor each step declares is gone by the time
                      # `core.cost` sees it, so `cost_unit._step_effort` prices every step at one
                      # flat human rate. That was harmless while `effort_bp` was a flat 5,000 and
                      # actively wrong the moment it stopped being: a nine-step AUTOMATED play
                      # would read as drifted and be "corrected" back up by 3,000bp, re-imposing
                      # the human assumption the prior exists to remove. The adapter knows the
                      # actor mix; the unit does not; so the adapter says so here and the unit
                      # reads it (`cost_unit._step_effort`) instead of guessing.
                      "effort_basis_bp": priors.effort_bp},
        )))

    candidates.sort(key=lambda item: item[0])
    plays = [play for _, _, play in candidates[:MAX_PLAYS]]
    truncated = [play_id for _, play_id, _ in candidates[MAX_PLAYS:]]
    for play_id in truncated:
        skipped[play_id] = f"over_play_cap_{MAX_PLAYS}"

    receipt = {
        "authored_rules": len(package.expert_rules),
        "plays_emitted": len(plays),
        # CLG-07's own numbers. "Ranked, not alphabetical" is only a claim if the ranking's inputs
        # are visible: how many plays declared the situation that fired, how many the corpus gave
        # an authored priority (zero today), and which plays the ranked cap actually cut.
        "plays_situation_fit": fits,
        "plays_with_authored_priority": prioritised,
        "plays_truncated": sorted(truncated),
        "selection": "situation_fit, capability recency, authored priority, then rule id",
        # Which plays this tenant's own outcomes re-scored, and which kept the 5,000bp default.
        # A number, not a boolean: "the adaptive brain influenced this decision" is only a real
        # claim if you can say how many of the options it touched.
        "plays_rescored_by_learning": sorted(
            play.play_id for play in plays if play.metadata.get("learned_success_from")),
        "skipped_rule_ids": dict(sorted(skipped.items())),
        "truncation_reason": (f"ranked cap at {MAX_PLAYS} plays: situation fit first, "
                              "rule id last" if truncated else None),
        "generic_fallback_used": not plays,
        # K1 · THE ARITHMETIC BEHIND THE THREE COMPONENTS THAT USED TO BE CONSTANT. Per surviving
        # play, every term that produced its impact, effort, risk and authored success, naming the
        # corpus field each was read from. This is what makes "the formula decides" checkable from
        # a stored manifest rather than by re-running the compiler: a reviewer asking why play A
        # outranked play B reads the two receipts side by side.
        "play_components": {
            play.play_id: {
                "impact_bp": play.impact_bp,
                "effort_bp": play.effort_bp,
                "risk_bp": play.risk_bp,
                "success_probability_bp": play.success_probability_bp,
                "success_source": play.metadata.get("success_source"),
                "derivation": dict(priors_by_play[play.play_id].receipt),
            }
            for play in plays if play.play_id in priors_by_play
        },
        # The spread, as one number per component, so "three of six ranking components do not move"
        # is answerable from the receipt instead of from a population sweep. A 1 here on a
        # multi-play capability is the defect returning.
        "component_distinct_values": {
            name: len({getattr(play, name) for play in plays})
            for name in ("impact_bp", "effort_bp", "risk_bp", "success_probability_bp")
        },
    }
    if not plays:
        plays.append(PlayDefinition(
            "review_situation", "1.0.0", "Review the compiled expertise",
            steps=(
                "Review the compiled expert, organization, behavior and adaptive knowledge.",
                "Choose the safest next step with the owner.",
                "Leave any outreach or system change for explicit human approval.",
            ),
            read_only=True,
            # `review` AND `non_prescriptive`: this play was written by the ADAPTER, not by any
            # expert, and a card built from it must never render as a confident instruction —
            # that would be the compiler failing while its output reads as advice.
            tags=("human_approval", "review", "non_prescriptive"),
            metadata={"source": "adapter_default", "external_recipient_required": False},
        ))
    # The SURVIVING plays' authored definitions, for the delta maps. Only the survivors: a ceiling
    # authored for a play the cap cut is config nothing can ever read, and every unit's config
    # reaches the manifest's content address, so carrying the cut ones would move a capability
    # version for plays that are not in it.
    surviving = {play.play_id: definitions_by_play[play.play_id]
                 for play in plays if play.play_id in definitions_by_play}
    return tuple(plays), receipt, surviving


@dataclass(frozen=True, slots=True)
class Weld:
    """Everything the typed consumers produced for one package — CLG-06, CLG-07 and CLG-08.

    One object rather than three return values because the three consumers are not independent:
    a rule's scope is resolved against the plays that survived the cap, a citation is refused when
    it contradicts a rule that fired, and the receipt has to add up across all of them. Assembling
    them in one place is what makes "every refusal named and counted" checkable in one read.
    """

    compiled_constraints: tuple[Mapping[str, Any], ...] = ()
    citations: tuple[Mapping[str, Any], ...] = ()
    framing_blocks: tuple[Mapping[str, Any], ...] = ()
    rule_verdicts: tuple[Mapping[str, Any], ...] = ()
    conflicts: tuple[Mapping[str, Any], ...] = ()
    abstain_on_conflict: bool = False
    blocked_play_ids: tuple[str, ...] = ()
    receipt: Mapping[str, Any] = field(default_factory=dict)
    bound: bool = False

    def as_metadata(self) -> dict[str, Any]:
        """The manifest-borne form. Plain lists and dicts, because this crosses `jsonb` on the way
        into `reasoning_capability_snapshots` and comes back through `capability_from_manifest`;
        `freeze` normalises list and tuple identically, so the round trip is hash-stable."""
        return {
            "schema": WELD_SCHEMA,
            "adapter_version": ADAPTER_VERSION,
            # False when no situation slice reached this adapter — every rule is then `unevaluable`
            # naming `situation_slice_not_supplied`, and this flag is what stops a reader taking
            # that for "no rule applied".
            "bound": self.bound,
            "compiled_constraints": [dict(item) for item in self.compiled_constraints],
            "citations": [dict(item) for item in self.citations],
            "framing_blocks": [dict(item) for item in self.framing_blocks],
            "rule_verdicts": [dict(item) for item in self.rule_verdicts],
            "conflicts": [dict(item) for item in self.conflicts],
            "abstain_on_conflict": self.abstain_on_conflict,
            "blocked_play_ids": list(self.blocked_play_ids),
            "weld_receipt": dict(self.receipt),
        }


def weld_package(package: ExpertisePackage, *, declared_play_ids: frozenset[str],
                 play_receipt: Mapping[str, Any],
                 adapter: ContextAdapter | None = None) -> Weld:
    """Run every typed consumer over one package and account for the result.

    ORDER IS LOAD-BEARING. Plays are already chosen when this runs, so a blocking rule can only
    eliminate a candidate that exists (`declared_play_ids`). Rules are compiled and bound before
    citations, so the binder knows which doctrine fired and can refuse a claim that denies it.
    The receipt is built last, from what the other two actually produced, and is validated by the
    contract's `require_weld_receipt` — all eight counters, zeros included, arithmetic checked.
    """
    rules = compile_package_rules(package, adapter, declared_play_ids=declared_play_ids)
    binding = bind_citations(package, rules.verdicts)

    refusals = dict(rules.refusals)
    for reason, count in binding.refusals.items():
        refusals[reason] = refusals.get(reason, 0) + count

    receipt = require_weld_receipt({
        "rules_compiled": len(rules.constraints),
        "rules_fired": len(rules.fired),
        "rules_unevaluable": len(rules.unevaluable),
        "rules_skipped": len(rules.skipped),
        "citations_attached": len(binding.citations),
        "citations_truncated": binding.citations_truncated,
        "plays_selected": int(play_receipt.get("plays_emitted") or 0),
        "plays_over_cap": len(play_receipt.get("plays_truncated") or ()),
        # Beyond the eight the contract fixes. Framing blocks are capped by this adapter rather
        # than by the contract, so their truncation is counted here or nowhere.
        "framing_blocks_attached": len(binding.framing_blocks),
        "framing_blocks_truncated": binding.framing_truncated,
        "rules_blocking_fired": sum(1 for verdict in rules.verdicts if verdict.blocks),
        "conflicts_named": len(binding.conflicts),
        "by_class": binding.by_class,
        "refusals": [{"reason": reason, "count": count}
                     for reason, count in sorted(refusals.items())],
        "skipped_rule_ids": dict(rules.skipped),
    }, "weld receipt")

    return Weld(
        compiled_constraints=rules.constraints,
        citations=binding.citations,
        framing_blocks=binding.framing_blocks,
        rule_verdicts=tuple(verdict.as_record() for verdict in rules.verdicts),
        conflicts=binding.conflicts,
        abstain_on_conflict=binding.abstain,
        blocked_play_ids=rules.blocked_play_ids,
        receipt=receipt,
        bound=adapter is not None,
    )


def _goal(package: ExpertisePackage, situation_type: str) -> Goal:
    """The FIRST capability's question is the statement; the rest become success criteria.

    Taking only the first and dropping the others silently meant a package compiled from three
    capabilities looked identical to one compiled from one — the other two questions vanished
    without a trace. They are secondary by position (the router ordered them), not disposable.
    """
    questions = []
    for capability in package.capabilities:
        definition = capability.get("definition") if isinstance(capability, Mapping) else None
        question = (definition or {}).get("question")
        if question:
            questions.append(str(question))
    statement = questions[0] if questions else (
        f"Resolve the {situation_type} situation using the compiled expertise.")
    return Goal(
        f"expertise.{situation_type}",
        statement,
        success_criteria=tuple(questions[1:4]),
        constraints=("Never send or mutate an external system autonomously.",),
    )


def _situation_importance(situation: BusinessSituationObject | None) -> dict[str, Any]:
    """WAVE Z3 · L2's composed importance, carried onto the manifest for the Decision Maker.

    This is the last hop of a three-layer supply chain that has never delivered. L1's ALG-17
    scores a signal, L2's BLG-18 composes those scores into a situation's `importance_bp`, and
    Layer 4 — the layer both were built for — has never opened the envelope: before this wave
    `importance_bp` appeared exactly once anywhere under `reason/`, in a SQL select.

    It is carried as METADATA and not as a context fact on purpose. `reason/store.py` proves a
    persisted audit row by re-running the ranker against the stored manifest, so the number the
    ranker read has to be inside the thing that was stored; the context snapshot is stored too but
    is built by field SELECTION off the graph, and a situation-level score is not a fact about the
    anchor node.

    `fallback` and `source` travel with the number because the number alone cannot be trusted.
    `context/situation_bso.importance_base` publishes the neutral 5,000 midpoint for a situation
    whose signals Layer 1 never scored, and a composed 5,000 and a defaulted 5,000 are the same
    integer — so the BSO declares which, and `decision_maker.situation_importance` reweighs rather
    than ranking a whole tenant on a constant.
    """
    if situation is None:
        return {}
    metadata = situation.metadata or {}
    return {SITUATION_IMPORTANCE_KEY: {
        "importance_bp": int(situation.importance_bp),
        "source": str(metadata.get("importance_source") or "unknown"),
        # Defaults to True — an unstated provenance is not a measurement.
        "fallback": bool(metadata.get("importance_fallback", True)),
        "version": (str(metadata["importance_version"])
                    if metadata.get("importance_version") else None),
    }}


def expertise_capability_manifest(
    package: ExpertisePackage, *, root_entity_type: str,
    live_delivery_enabled: bool = False,
    situation: BusinessSituationObject | None = None,
    context: SituationContextSlice | None = None,
    roster_v2: bool = False,
    ranking_v2: bool = False,
    projection: SituationProjection | None = None,
) -> CapabilityManifest:
    """One ExpertisePackage -> one CapabilityManifest driving Layer 4's reasoning.

    ``situation`` and ``context`` are what CLG-06 BINDS against, and they are parameters rather
    than something read off the package because the package does not carry them: an
    `ExpertisePackage` holds the knowledge that was selected, not the facts it was selected for.
    `ContextAdapter` is the compiler's own three-state evaluator and needs both — and it is the
    only thing that can tell an UNKNOWABLE absence from an unmet one, which is the difference
    between a blocking rule firing and a blocking rule abstaining. `domain_shadow` has both in
    scope at the call site.

    Omitting them is legal and honest, not silent: every rule is then `unevaluable` naming
    `situation_slice_not_supplied`, `metadata["weld"]["bound"]` is False, and nothing is
    eliminated. A caller that only wants the manifest's shape gets it without the weld claiming a
    binding it never performed.

    ``roster_v2`` is doc 02 U1's staged roster, gated per tenant on
    ``l4_activation(org, 'roster_v2')`` and therefore a PARAMETER rather than a flag read here:
    this function must reach the same manifest for the same package on every machine, and an
    adapter that read an activation table would make its own output depend on a database. False
    (the default, and every caller that has not been switched on) builds the six-unit DAG below,
    byte for byte, so an unactivated tenant's manifest — and its content-addressed version —
    cannot move. True declares the full family, binds each unit's inputs to the fact paths this
    expertise actually reads, and switches on the planner's Unit Selector so the units this
    SITUATION cannot feed are dropped with a receipt instead of running blind.

    ``ranking_v2`` is doc 04 E1's six-weight utility model, gated per tenant on
    ``l4_activation(org, 'ranking_v2')`` and a PARAMETER for exactly the reason ``roster_v2`` is.
    False builds the five-weight manifest byte for byte, so an unactivated tenant's capability
    version cannot move and the audit rows already written against it stay verifiable. True
    declares ``RANKING_WEIGHTS_V2`` — importance at 2,500 of 10,000, the largest weight in the
    engine — and carries L2's composed importance onto the manifest so the Decision Maker can read
    it; without the carrier the ranker reweighs the other five and records
    ``L2_IMPORTANCE_NOT_ACTIVE``, which is honest and is not the point of the wave.

    ``projection`` is doc 06 IN-1's BSO-to-snapshot projection (wave Z5), built once by the caller
    from the same ``situation`` and ``context`` this function binds against and handed to
    ``reason_native_capability`` as well. It is a PARAMETER rather than something derived here for
    one reason: the manifest DECLARES the projected fields and the snapshot SUPPLIES them, and two
    derivations of the same projection is exactly how a manifest ends up declaring a field its
    snapshot does not carry. One object, two consumers, no drift — and ``native_context_snapshot``
    refuses the mismatch rather than reasoning through it.

    A projection is only legal alongside ``roster_v2``. The six-unit DAG has no consumer for it,
    so declaring it there would change an unactivated tenant's snapshot — and therefore its
    decision hashes — for facts nothing reads. That is refused loudly instead of ignored quietly.

    ``live_delivery_enabled`` defaults to False — the measurement pass must stay advisory. It is
    True only on the cutover path, because the delivery authority predicate reads it directly
    (``rcap.manifest->'live_delivery_enabled' = 'true'``): a signal whose capability snapshot says
    False can never become a card, however complete the rest of its audit bundle is.
    """
    situation_type = str(package.metadata.get("situation_type") or "situation")
    plays, play_receipt, play_definitions = _plays(package)
    adapter = ContextAdapter(situation, context) if situation is not None else None
    weld = weld_package(package, declared_play_ids=frozenset(play.play_id for play in plays),
                        play_receipt=play_receipt, adapter=adapter)
    # TWO SOURCES, ONE BLOCK LIST. The organisation brain's permission entries and the corpus's
    # own blocking doctrine both reach `core.constraint` through the seam it already owns and that
    # `reason/store.py` and `reason/authority.py` already re-prove. Merged and sorted so the
    # config is a property of what was decided rather than of which source was read first.
    blocked_plays = tuple(sorted(set(_blocked_play_ids(package)) | set(weld.blocked_play_ids)))
    domain_ids = package.metadata.get("domain_ids") or ()
    domain = str(domain_ids[0]) if domain_ids else "general"
    required_fields = _executable_required_fields(package)
    # SELECT the union, GATE on the intersection — two different questions that shared one answer.
    # The manifest's own `required_fields` is BOTH: the orchestrator gates on it
    # (`initial_missing`) and native's selector seeds from it. It carries the gate set, and the
    # union reaches the selector through the reasoner specs and play preconditions, which
    # `_selected_fields` unions in anyway. So nothing stops being pulled; a capability simply
    # stops being vetoed by a field only one of its patterns reads.
    gate_fields = _universal_required_fields(package)

    # WHAT THIS SITUATION ACTUALLY CARRIES, for the roster's field binding. Root and neighbour
    # both, because `native.native_context_snapshot` resolves a root field from the 1-hop
    # neighbourhood when the anchor does not hold it — an aggregate anchor owns no facts of its
    # own, and gating a unit on a field the snapshot will happily borrow would drop it for a
    # reason the snapshot does not agree with.
    present: frozenset[str] = frozenset()
    if context is not None:
        present = frozenset(context.facts) | frozenset(context.neighbor_facts)
    if projection is not None and not roster_v2:
        raise ValueError(
            "a situation projection was supplied without roster_v2 — the six-unit DAG declares no "
            "projected fact, so the projection would enter the snapshot unread and move an "
            "unactivated tenant's decision hashes for nothing")
    if roster_v2:
        reasoners, roster_receipt = _roster_specs(
            package, gate_fields=gate_fields, available=frozenset(required_fields),
            present=present, authored_priority_bp=package.metadata.get("authored_priority_bp"),
            blocked_play_ids=blocked_plays, play_definitions=play_definitions,
            projection=projection)
    else:
        reasoners = _default_dag(gate_fields, package.metadata.get("authored_priority_bp"),
                                 blocked_play_ids=blocked_plays)
        roster_receipt = None

    knowledge_hash = semantic_hash({
        "capabilities": package.capabilities,
        "objects": package.objects,
        "expert_rules": package.expert_rules,
        "organization_rules": package.organization_rules,
        "behavior_patterns": package.behavior_patterns,
        "adaptive_preferences": package.adaptive_preferences,
        "brain_snapshot_id": package.brain_snapshot_id,
    })

    manifest = CapabilityManifest(
        capability_id=f"expertise.{situation_type}",
        # Provisional — replaced below once the manifest's own content can be hashed.
        version=f"exp.{knowledge_hash[:16]}",
        domain=domain,
        root_entity_type=str(root_entity_type or "entity"),
        goal=_goal(package, situation_type),
        reasoners=reasoners,
        plays=plays,
        required_fields=gate_fields,
        # The projected names ride in `selection_fields`, never in `required_fields`: the
        # orchestrator GATES the whole capability on `required_fields`, and a capability vetoed
        # because Layer 2 published no trend would be the projection making the engine quieter.
        # `native._projected_declarations` reads this set, so the snapshot/manifest mismatch guard
        # fires even for a package whose roster declared nothing.
        selection_fields=tuple(sorted(set(required_fields) | set(
            projection.declared_fields if projection is not None else ()))),
        # WAVE Z3. Conditional so the default construction is untouched: the five-weight default
        # lives on `CapabilityManifest` and passing it explicitly here would be a second copy of a
        # number that must not be able to disagree with itself.
        **({"ranking_weights": dict(RANKING_WEIGHTS_V2)} if ranking_v2 else {}),
        policies=("read_only", "human_approval_required", "evidence_required"),
        live_delivery_enabled=live_delivery_enabled,   # advisory by default; True only on cutover
        do_nothing_consequence=(
            f"The {situation_type} situation is left unaddressed while its evidence compounds."
        ),
        metadata={
            "adapter": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            # WAVE Z1. Present only when the roster is awake, so an unactivated tenant's manifest
            # bytes — and therefore its version — are exactly what they were. When it is present
            # it carries the Unit Selector's switch, the run's declared ceiling, and the receipt
            # naming every unit this expertise could not feed and why.
            **({CONTEXT_AWARE_SELECTION_KEY: True,
                LATENCY_CEILING_KEY: ROSTER_LATENCY_CEILING_MS,
                "roster": roster_receipt} if roster_receipt is not None else {}),
            # What the play conversion refused or cut — so "compiled fine, emitted one generic
            # play" is a readable state instead of a successful-looking silence.
            # WAVE Z3, and present only when the six-weight model is on — for the same reason
            # the roster receipt is: an unactivated tenant's manifest bytes, and therefore its
            # content-addressed version, must not move.
            **(_situation_importance(situation) if ranking_v2 else {}),
            "play_receipt": play_receipt,
            # THE WELD (doc 03). Compiled constraints, quoted citations, framing blocks, the
            # per-rule verdicts the Decision Maker turns into `constraints_applied` once candidate
            # ids exist, and the receipt that says what every artifact class contributed or why it
            # did not. This is the structure that makes Law 4 checkable: knowledge that is not
            # here was not consumed.
            "weld": weld.as_metadata(),
            "situation_type": situation_type,
            # The situation's own card copy. Delivery reads it off `rcap.manifest` — the same
            # audited snapshot the authority predicate already joins — so a card's wording is
            # pinned to the capability version that produced it and cannot drift underneath it.
            "render": package.metadata.get("render"),
            "render_situation_id": package.metadata.get("render_situation_id"),
            "expertise_id": package.id,
            "brain_snapshot_id": package.brain_snapshot_id,
            "object_coverage_bp": package.metadata.get("object_coverage_bp"),
            "knowledge_hash": knowledge_hash,
            "schema": "capability.v1",
            # The three learned brains, TYPED — not only folded into `knowledge_hash`.
            #
            # Organization, Behavior and Adaptive values entered the decision at exactly two
            # places, both identity-only: the manifest `version` string and this `knowledge_hash`.
            # A repo-wide grep for the three names under `reason/` found zero read sites. So a
            # tenant could approve an organization rule, watch the hash change, and nothing about
            # any decision would differ — governance and personalisation were provenance theatre.
            #
            # Carrying them as structure is what lets a reasoner CONSULT them. Counts travel
            # alongside so "did any brain actually influence this?" is answerable from the
            # manifest rather than by diffing hashes between runs.
            "brains": {
                "organization": list(package.organization_rules or ()),
                "behavior": list(package.behavior_patterns or ()),
                "adaptive": list(package.adaptive_preferences or ()),
            },
            "brain_influence": {
                "organization": len(package.organization_rules or ()),
                "behavior": len(package.behavior_patterns or ()),
                "adaptive": len(package.adaptive_preferences or ()),
                # True when every brain is empty: the manifest is authored expertise only, and a
                # personalisation claim about this decision would be false.
                "hash_only": not any((package.organization_rules,
                                      package.behavior_patterns,
                                      package.adaptive_preferences)),
                # WHAT THE BRAINS ACTUALLY DID, which is a different question from how many
                # entries came along. Carrying only the counts was how "the brains reached the
                # decision" stayed true-sounding and unfalsifiable for as long as it did: a
                # tenant could hold forty entries, every one of them about a play this capability
                # does not declare, and the count would say forty.
                "plays_blocked_by_organization": list(blocked_plays),
                "plays_rescored_by_adaptive": play_receipt["plays_rescored_by_learning"],
                # Behavior has no consumer yet and says so. The three brains are not equivalent —
                # organization states policy, adaptive measures outcomes, and behavior describes
                # how the org works — and the third has no seam in this DAG that would not be an
                # invented one. Named as absent rather than implied to be working.
                "behavior_consumed": False,
            },
        },
    )

    # Re-version on the MANIFEST's content, not only the knowledge's.
    #
    # `knowledge_hash` covers the compiled expertise, but the manifest built from it also varies
    # with the situation: goal, root entity type, the plays that survived conversion, the gate and
    # selection sets. Two situations therefore produced two different manifests under one version,
    # and the audit store's immutability guard correctly refused the second — "immutable capability
    # version mismatch". A version that does not move when the thing it names moves is not a
    # version. Two hashes, not one: knowledge first so the lineage stays legible at a glance,
    # manifest second so the identity is honest.
    content = stable_id("capmanifest", manifest.to_semantic_dict()).split("_", 1)[-1]
    return replace(manifest, version=f"exp.{knowledge_hash[:12]}.{content[:12]}")


__all__ = ["ADAPTER_ID", "ADAPTER_VERSION", "MAX_PLAYS", "ROSTER_LATENCY_CEILING_MS",
           "ROSTER_SCHEMA", "WELD_SCHEMA", "Weld",
           "expertise_capability_manifest", "weld_package"]
