"""The Reasoning Expertise of a file — the twelve situation-level units, run in shadow (STEP-13b).

`speedrun008/YC-II W27/` STEP-13b §8.4 item 1, tree `yc2_w27_s13b` M37.C2.L-logic.V1.U03. Claim 7
(§8.1, measured): the twenty-one reasoning units run only inside a compiled or legacy reasoning
run, never for a file — `reason/reasoners/__init__.py` names seventeen core units plus Temporal,
Relationship, SignalComposition and Planning, and nothing schedules any of them against a file
that has no admitted L2 situation. `units_for` is that missing path, for the twelve SITUATION-LEVEL
units only (Context, Timeline, Dependency, Constraint, Risk, Opportunity, Impact, Priority,
Confidence, Temporal, Relationship, SignalComposition — `06` D-s13b-3): each runs over the file
anchor's own `ContextSnapshot` (as `reason/runner._load_context` would build one), whether or not
the L2 publisher admitted a situation for this file at all. NO DECISION, NOTHING PERSISTED, NO
MODEL: a unit's own reading, named, with its evidence and why — never a candidate ranked, never a
play eliminated, never a row written. The nine units that judge COMPILED PLAYS (Tradeoff, Resource,
Scheduling, Cost, Policy, Alternative, Validation, Recommendation, Planning) have no plays here to
judge — a file is not a compiled situation — and are named once, not run (D-s13b-3): the expert
writes its own next move; these units' job is exactly that, for a play this file does not have.

A UNIT'S OWN ANATOMY, TRUSTED. Nine of the twelve (Context, Timeline, Dependency, Constraint, Risk,
Opportunity, Impact, Priority, Confidence) are `reason/unit.ReasoningUnit` subclasses: the same
fixed five-stage template (retrieve, validate, analyze, calculate, evaluate_meaning) every capability
in the compiled lane already runs them through, reviewed once for the whole roster rather than once
per caller. The other three (Temporal, Relationship, SignalComposition) are self-contained: they read
`request.context.facts` directly, with their own sensible field defaults, and never touch
`prior_results` at all — confirmed by reading each (`del prior_results` at the top of all three).

WHERE A UNIT'S WIRING COMES FROM. `reason/adapters/expertise._ROSTER` is the one place the compiled
lane already states, for twenty of the twenty-one non-legacy units, which fact paths fill which role
(`_bind_roles`) and which single field gates the unit through (`_declared_field`) — reused here
verbatim rather than re-derived, so a change to that wiring is one change, not two that can drift.
`core.signal_composition` is the one unit this roster does not carry at all (s13b-F19): it needs none
— it is self-contained and checks its own one field, `signals.open`.

GATING. A unit the roster marks `always` (its own account of why it is never starved: context,
dependency, constraint, risk, impact, priority, confidence) runs with no declared requirement — it
reads `request.context.facts` directly for whatever it needs, exactly as it does inside a real
compiled pass. The two that are NOT `always` — Timeline, Opportunity — declare `essential` roles: if
none of an essential role's candidate fields are present on this file, the unit is read as
INSUFFICIENT CONTEXT before it is even asked, naming the role; if every essential role binds, it runs
normally and the framework's own `MissingContextError` (should the bound field vanish between the
check and the read, which it cannot here, but the catch costs nothing) is read the same way.

LEVELS, NOT SCORES (the brief's own words). A unit's basis-point metrics are banded into
`contracts.expert_review.LEVELS` (`low · medium · high`, read, not edited — that file is STEP-16's) at
simple fixed thirds; this is this unit's own choice, not an existing vocabulary found anywhere else
for a reasoning unit's own numbers, and is written down as exactly that so a reviewer can override it.
A `[ru:<unit>]` line also carries the unit's reason codes and the evidence ids its findings cite
(`EngineLine.cites`) — never the raw basis points themselves, matching the brief.

A UNIT'S OWN FAULT NEVER CRASHES THE FILE'S READ. Every unit but `core.signal_composition` runs
inside a `try`; `MissingContextError` reads as insufficient context (named), any other exception
reads as failed (named by its type) — a reasoning unit's bug costs that one line, never the dossier.

Pure, deterministic, no model: a `ContextSnapshot` in, an `EngineRead` out.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal
from collections.abc import Mapping
from datetime import datetime

from genios_engine.contracts import engine_read as E
from genios_engine.contracts.expert_review import LEVELS
from genios_engine.contracts.reasoning import (CapabilityManifest, ContextSnapshot, Goal,
                                               PlayDefinition, ReasonerResult, ReasonerSpec,
                                               ReasoningRequest, ResultStatus)
from genios_engine.reason.adapters.expertise import _ROSTER, _bind_roles, _declared_field
from genios_engine.reason.protocols import MissingContextError
from genios_engine.reason.runner import _load_context
from genios_engine.reason.reasoners import (ConfidenceReasoner, ConstraintReasoner, ContextUnit,
                                            DependencyUnit, ImpactUnit, OpportunityUnit,
                                            PriorityReasoner, RelationshipReasoner, RiskReasoner,
                                            SignalCompositionReasoner, TemporalReasoner,
                                            TimelineUnit)

#: `06` D-s13b-3: the twelve situation-level units, in an order every declared dependency respects
#: (checked against `_ROSTER` below by `test_the_run_order_respects_every_dependency`).
RUN_ORDER: tuple[str, ...] = (
    "core.context", "core.temporal", "core.relationship", "core.timeline", "core.dependency",
    "core.constraint", "core.risk", "core.opportunity", "core.impact", "core.priority",
    "core.confidence", "core.signal_composition")

#: The nine units that judge COMPILED PLAYS — named once, never run for a file (D-s13b-3).
NOT_RUN: tuple[str, ...] = (
    "core.tradeoff", "core.resource", "core.scheduling", "core.cost", "core.policy",
    "core.alternative", "core.validation", "core.recommendation", "core.planning")

#: One instance per unit, built once — `reasoners/__init__.py`'s own pattern.
_UNITS: Mapping[str, object] = {
    "core.context": ContextUnit(), "core.temporal": TemporalReasoner(),
    "core.relationship": RelationshipReasoner(), "core.timeline": TimelineUnit(),
    "core.dependency": DependencyUnit(), "core.constraint": ConstraintReasoner(),
    "core.risk": RiskReasoner(), "core.opportunity": OpportunityUnit(),
    "core.impact": ImpactUnit(), "core.priority": PriorityReasoner(),
    "core.confidence": ConfidenceReasoner(), "core.signal_composition": SignalCompositionReasoner()}

#: `reason/adapters/expertise._ROSTER`'s own wiring, by id — no entry for `core.signal_composition`
#: (s13b-F19): that unit is self-contained and needs none.
_ROSTER_BY_ID: Mapping[str, object] = {unit.unit_id: unit for unit in _ROSTER}

_GOAL = Goal(goal_id="shadow.file_units",
            statement="Read the file's situation for the dossier, in shadow — no decision.")
#: A placeholder: this manifest has no real plays — a file is not a compiled situation — and
#: `CapabilityManifest` requires at least one. Read-only, one step, never shown to anybody.
_SHADOW_PLAY = PlayDefinition(play_id="shadow.read_only", version="1.0.0", label="Read only",
                              steps=("Read the file's own facts; decide nothing.",), read_only=True)

_VERSION = "1.0.0"
#: The roster's version for a file's fingerprint (STEP-13b M37.C5.L-logic.V4.U01): the units a file runs, those it does
#: not, and the units' own version — a unit added or retired is a different reader of the file.
UNITS_ROSTER_VERSION = "units-" + hashlib.sha256(
    "|".join([_VERSION, *RUN_ORDER, "/", *NOT_RUN]).encode("utf-8")).hexdigest()[:10]


def _manifest(context: ContextSnapshot) -> CapabilityManifest:
    """A capability manifest for no real capability — the shell every `ReasoningRequest` needs.

    Each unit's `required_fields` and `config` are resolved from `_ROSTER` against this file's own
    facts, standing in for the "available" fields a real authored capability would otherwise name
    (there is none; a file is not a compiled situation). `capability.required_fields` is every fact
    this file carries, so `core.context`'s completeness reading has a denominator — honestly a
    trivial one (this file against itself), which is this read's own limitation, not a hidden claim
    about what a professional would expect this file to hold.
    """
    facts = frozenset(context.facts)
    specs = []
    for unit_id in RUN_ORDER:
        roster = _ROSTER_BY_ID.get(unit_id)
        if roster is None:
            specs.append(ReasonerSpec(unit_id, _VERSION))
            continue
        config, bound, bound_lists = _bind_roles(roster, facts, facts)
        if unit_id == "core.priority":
            # `core.risk` publishes `risk_bp`, never `urgency_bp` — sourcing priority from it
            # would silently read the plugin's own neutral default every time (verified: it did).
            # `core.temporal` is the unit that actually measures decay into `urgency_bp`, and is
            # priority.py's own worked example of a declared source. Confidence is left
            # unconfigured: no unit in this roster publishes `confidence_bp` to bridge from, so
            # the bridge would never fire anyway — this is confidence computing its own blend,
            # which is the primary path the module docstring describes, not a fallback.
            config.setdefault("source_reasoner", "core.temporal")
        required = () if roster.always else _declared_field(roster, bound, bound_lists, facts)
        specs.append(ReasonerSpec(unit_id, _VERSION, dependencies=roster.dependencies,
                                  required_fields=required, config=config))
    return CapabilityManifest(
        capability_id="shadow.file_units", version=_VERSION, domain="shadow",
        root_entity_type=context.root_entity_type, goal=_GOAL, reasoners=tuple(specs),
        plays=(_SHADOW_PLAY,), required_fields=tuple(sorted(facts)), policies=("read_only",))


def _essential_gap(unit_id: str, facts: frozenset) -> tuple[str, ...]:
    """The essential roles (Timeline, Opportunity only) with no candidate present at all — read
    as insufficient context before the unit is even asked, rather than relying on the framework's
    `MissingContextError` to say the same thing one layer down."""
    roster = _ROSTER_BY_ID.get(unit_id)
    if roster is None or not roster.essential:
        return ()
    _config, bound, bound_lists = _bind_roles(roster, facts, facts)
    return tuple(key for key in roster.essential if key not in bound and key not in bound_lists)


def _level(value: int) -> str:
    if value < 3_334:
        return LEVELS[0]
    if value < 6_667:
        return LEVELS[1]
    return LEVELS[2]


def _levels(metrics: Mapping[str, int]) -> tuple[str, ...]:
    return tuple(f"{name[:-3]}: {_level(metrics[name])}" for name in sorted(metrics)
                if name.endswith("_bp"))


def _completed_words(result: ReasonerResult) -> str:
    parts = list(_levels(result.metrics))
    if result.matched is not None:
        parts.append(f"matched: {'yes' if result.matched else 'no'}")
    if result.reason_codes:
        parts.append("reasons: " + ", ".join(result.reason_codes))
    return "; ".join(parts) if parts else "completed, nothing to report"


def _line(unit_id: str, words: str, *, version: str = _VERSION,
          cites: tuple[str, ...] = ()) -> E.EngineLine:
    return E.EngineLine(ref=f"ru:{unit_id}", family=E.UNIT, words=words, source=unit_id,
                        source_version=version, reviewed=False, cites=cites)


def _result_line(unit_id: str, result: ReasonerResult) -> E.EngineLine:
    if result.status == ResultStatus.COMPLETED:
        words = _completed_words(result)
    elif result.status == ResultStatus.INSUFFICIENT_CONTEXT:
        words = "insufficient context" + (
            f" — missing {', '.join(result.missing_fields)}" if result.missing_fields else "")
    elif result.status == ResultStatus.SKIPPED:
        words = "skipped" + (f" — {', '.join(result.reason_codes)}" if result.reason_codes else "")
    else:
        words = "failed" + (f" — {', '.join(result.reason_codes)}" if result.reason_codes else "")
    return _line(unit_id, words, version=result.reasoner_version, cites=result.evidence_ids)


def _not_run_line() -> E.EngineLine:
    return _line("not_run", "not run — they judge compiled plays, and the expert writes its own "
                            "next move (06 D-s13b-3): " + ", ".join(NOT_RUN))


def units_for(context: ContextSnapshot) -> E.EngineRead:
    """The twelve situation-level units' reading of one file's anchor — see the module docstring.

    `context` is the file anchor's own `ContextSnapshot`, as `reason/runner._load_context` would
    build one for it — this function asks nothing more of its caller than that one frozen object.
    """
    manifest = _manifest(context)
    request = ReasoningRequest(org_id=context.org_id, capability=manifest, context=context,
                               evaluation_time=context.evaluation_time,
                               trigger_kind="shadow_file_units")
    facts = frozenset(context.facts)
    prior: dict[str, ReasonerResult] = {}
    lines: list[E.EngineLine] = []
    for unit_id in RUN_ORDER:
        gap = _essential_gap(unit_id, facts)
        if gap:
            lines.append(_line(unit_id, f"insufficient context — nothing present for {', '.join(gap)}"))
            continue
        unit = _UNITS[unit_id]
        try:
            result = unit.evaluate(request, prior)
        except MissingContextError as exc:
            lines.append(_line(unit_id, f"insufficient context — missing {', '.join(exc.fields)}"))
            continue
        except Exception as exc:  # noqa: BLE001 — a unit's own fault costs this line, not the file's
            lines.append(_line(unit_id, f"failed — {type(exc).__name__}"))
            continue
        prior[unit_id] = result
        lines.append(_result_line(unit_id, result))
    lines.append(_not_run_line())
    return E.EngineRead(lines=tuple(lines))


def _sanitized_facts(facts: Mapping[str, object]) -> dict[str, object]:
    """`NodeContext.facts`' own shape, with its one float replaced by the integer form every
    reader already prefers first. `_load_context` stamps `confidence` as a bare Python float
    (`graph_store`'s `graph_facts.confidence` column read straight through); `ContextSnapshot`
    forbids a float anywhere in its tree (`platform.canonical.canonicalize`'s semantic-artifact
    rule), and every reader of a fact record already checks `confidence_bp` BEFORE `confidence`
    (`reasoners/confidence.py:210-212`) — so converting loses nothing a unit would have read."""
    out: dict[str, object] = {}
    for field, record in facts.items():
        if not isinstance(record, Mapping) or "confidence" not in record:
            out[field] = _exact(record)
            continue
        value = record["confidence"]
        copy = dict(record)
        del copy["confidence"]
        if isinstance(value, float):
            copy["confidence_bp"] = max(0, min(10_000, round(value * 10_000)))
        elif value is not None:
            copy["confidence_bp"] = value
        out[field] = _exact(copy)
    return out


def _exact(value: object) -> object:
    """Every float in a fact's tree as the exact `Decimal` it prints as: `ContextSnapshot` refuses a float anywhere, and a
    fact's value (a money figure, a ratio) is one — the whole engine read of a file failed on it (golden F54)."""
    if isinstance(value, float):
        return Decimal(repr(value))
    if isinstance(value, Mapping):
        return {key: _exact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_exact(item) for item in value]
    return value


def units_for_node(store, org_id: str, node_id: str, node_type: str, *, evaluation_time: datetime,
                   graph_version: int = 0, selector_version: str = "shadow-v1") -> E.EngineRead:
    """`units_for`, built from the file's own graph node — `reason/runner._load_context`, the one
    read the module docstring names, with nothing else asked of the caller. `graph_version` and
    `selector_version` are this shadow read's own, never the compiled lane's (there is no compiled
    package behind this read to version) — named so a replay can tell a shadow snapshot from a real
    one at a glance rather than by the absence of a package id."""
    node = _load_context(store, org_id, node_id, node_type)
    context = ContextSnapshot(
        org_id=org_id, graph_version=graph_version, root_entity_id=node_id,
        root_entity_type=node_type, evaluation_time=evaluation_time,
        selector_version=selector_version, facts=_sanitized_facts(node.facts),
        neighbor_facts=_sanitized_facts(node.neighbor_facts),
        observations=tuple(node.obs), neighbor_observations=tuple(sorted(node.neighbor_obs)),
        edge_count=node.edge_count)
    return units_for(context)


__all__ = ["NOT_RUN", "RUN_ORDER", "UNITS_ROSTER_VERSION", "units_for", "units_for_node"]
