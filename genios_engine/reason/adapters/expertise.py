"""Adapt a Layer 3 ExpertisePackage into a Layer 4 CapabilityManifest.

This is the L3->L4 weld. The DomainCompiler emits knowledge (authored capabilities + objects +
four-brain rules); Layer 4's orchestrator reasons only over a `CapabilityManifest` — a DAG of
reasoning units plus plays. The authored corpus deliberately carries NO reasoner DAG (a capability
declares outcomes/failure-modes/KPIs, an object declares inference patterns), so this adapter
supplies a conservative default DAG and derives the load-bearing `required_fields` from the objects'
executable inference patterns. Package knowledge is content-hashed into the manifest version so an
overlay change yields new immutable bytes (same discipline as `legacy_capability_manifest`).

Knowledge-in, DAG-supplied. It never decides — it only shapes what Layer 4 will reason over.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genios_engine.contracts.domain_expertise import ExpertisePackage
from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    FailurePolicy,
    Goal,
    PlayDefinition,
    ReasonerSpec,
)
from genios_engine.platform.canonical import semantic_hash

ADAPTER_ID = "expertise_to_capability"
ADAPTER_VERSION = "1.0.0"
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
                for field in pattern.get("evidence_fields", []) or []:
                    fields.add(str(field))
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
                 *, select_fields: tuple[str, ...] = ()) -> tuple[ReasonerSpec, ...]:
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
        # Carries the SELECTION set: `_selected_fields` unions every reasoner's fields, so the
        # union still gets pulled into the snapshot even though only the intersection gates. Risk
        # is where they belong — it is the unit that reads them — and its own gate stays the
        # intersection because a missing optional field should cost a pattern, not the decision.
        required_fields=tuple(sorted(set(select_fields) & set(required_fields))) or required_fields,
        failure_policy=_REQUIRED,
    )
    constraint = ReasonerSpec(
        "core.constraint", "1.0.0",
        dependencies=("core.context",),
        input_kind="candidate_plays",
        output_kind="candidate_checks",
        failure_policy=_REQUIRED,
    )
    priority = ReasonerSpec(
        "core.priority", "1.0.0",
        dependencies=("core.risk", "core.constraint"),
        config={"source_reasoner": "core.risk"},
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


#: How many plays a manifest carries. A cap is legitimate (the Decision Maker ranks a small
#: candidate set, not a corpus); a SILENT cap is not — see `_plays`' receipt fields.
MAX_PLAYS = 4


def _plays(package: ExpertisePackage) -> tuple[tuple[PlayDefinition, ...], dict]:
    """Playbook `expert_rules` (definitions carrying steps) become read-only review plays —
    plus a RECEIPT of everything this conversion refused or cut.

    The old shape was three silent judgments in a row: a rule without steps was `continue`d (no
    trace), the fifth play onward was `break`ed (no trace), and an empty result appended a
    hardcoded "review the situation" (indistinguishable from authored content). Consequence,
    `[MODELLED]` but structural: a 1,748-file corpus could compile successfully, hash into a new
    manifest version, and still emit one generic play — activation would LOOK successful while
    producing generic output, which is precisely the state L3's flip must be able to detect.

    Ordering is deterministic before the cap is applied (rule id, not corpus iteration order),
    so which plays survive the cut cannot depend on file-system enumeration.

    Everything Layer 3 supplies is advisory knowledge, so every play is read_only and leaves any
    outreach to explicit human approval.
    """
    candidates: list[tuple[str, PlayDefinition]] = []
    skipped: dict[str, str] = {}
    seen: set[str] = set()
    for position, rule in enumerate(package.expert_rules):
        if not isinstance(rule, Mapping):
            skipped[f"unmapped_{position}"] = "not_a_mapping"
            continue
        rule_id = str(rule.get("id") or f"rule_{position}")
        definition = rule.get("definition") or {}
        raw_steps = definition.get("steps") if isinstance(definition, Mapping) else None
        if not raw_steps:
            # A rule with no steps is a NON-STEPS artifact class (a heuristic, a threshold, a
            # question), not a defect — but this adapter only knows how to consume steps, and
            # saying so per class is what makes "add a typed consumer" a visible piece of work
            # instead of a quiet loss.
            skipped[rule_id] = "no_steps_artifact_unsupported"
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
        play_id = rule_id.replace(" ", "_")[:120]
        if play_id in seen:
            skipped[rule_id] = "duplicate_play_id"
            continue
        seen.add(play_id)
        candidates.append((play_id, PlayDefinition(
            play_id, "1.0.0", str(definition.get("name") or play_id)[:200],
            steps=steps,
            read_only=True,
            tags=("human_approval", "playbook"),
            metadata={"source": "expert_playbook", "external_recipient_required": False},
        )))

    candidates.sort(key=lambda pair: pair[0])
    plays = [play for _, play in candidates[:MAX_PLAYS]]
    truncated = [play_id for play_id, _ in candidates[MAX_PLAYS:]]
    for play_id in truncated:
        skipped[play_id] = f"over_play_cap_{MAX_PLAYS}"

    receipt = {
        "authored_rules": len(package.expert_rules),
        "plays_emitted": len(plays),
        "skipped_rule_ids": dict(sorted(skipped.items())),
        "truncation_reason": (f"deterministic cap at {MAX_PLAYS} plays, ordered by rule id"
                              if truncated else None),
        "generic_fallback_used": not plays,
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
    return tuple(plays), receipt


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


def expertise_capability_manifest(
    package: ExpertisePackage, *, root_entity_type: str,
) -> CapabilityManifest:
    """One ExpertisePackage -> one CapabilityManifest driving Layer 4's reasoning."""
    situation_type = str(package.metadata.get("situation_type") or "situation")
    plays, play_receipt = _plays(package)
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

    knowledge_hash = semantic_hash({
        "capabilities": package.capabilities,
        "objects": package.objects,
        "expert_rules": package.expert_rules,
        "organization_rules": package.organization_rules,
        "behavior_patterns": package.behavior_patterns,
        "adaptive_preferences": package.adaptive_preferences,
        "brain_snapshot_id": package.brain_snapshot_id,
    })

    return CapabilityManifest(
        capability_id=f"expertise.{situation_type}",
        version=f"exp.{knowledge_hash[:16]}",
        domain=domain,
        root_entity_type=str(root_entity_type or "entity"),
        goal=_goal(package, situation_type),
        reasoners=_default_dag(gate_fields, select_fields=required_fields),
        plays=plays,
        required_fields=gate_fields,
        policies=("read_only", "human_approval_required", "evidence_required"),
        live_delivery_enabled=False,          # typed L3->L4 path stays advisory until cutover
        do_nothing_consequence=(
            f"The {situation_type} situation is left unaddressed while its evidence compounds."
        ),
        metadata={
            "adapter": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            # What the play conversion refused or cut — so "compiled fine, emitted one generic
            # play" is a readable state instead of a successful-looking silence.
            "play_receipt": play_receipt,
            "situation_type": situation_type,
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
            },
        },
    )


__all__ = ["expertise_capability_manifest", "ADAPTER_ID", "ADAPTER_VERSION"]
